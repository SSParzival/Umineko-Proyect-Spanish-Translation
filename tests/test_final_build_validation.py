"""Integration tests validating the final Spanish translation build and round-trip fidelity."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.esfile.builder import build_esfile
from tools.esfile.codec import decode_ons2
from tools.esfile.differ import diff_targets
from tools.esfile.extractor import extract_esfile
from tools.esfile.validator import validate_workspace
from tools.translation_lint.double_space_normalizer import apply_double_space_normalization

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSLATION_DIR = REPO_ROOT / "translation"
ORIGINAL_ES_FILE = REPO_ROOT / "es.file"
REVIEWED_ES_FILE = REPO_ROOT / "es.reviewed.file"

EXPECTED_ORIGINAL_SHA256 = (
    "0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1"
)


class TestFinalBuildValidation(unittest.TestCase):
    """End-to-end verification of final translation workspace, compilation, and preservation."""

    @unittest.skipUnless(ORIGINAL_ES_FILE.is_file(), "Requires the original es.file in the repository root")
    def test_original_esfile_unmodified(self) -> None:
        """Requirement: original es.file must never be modified or overwritten."""
        actual_sha = hashlib.sha256(ORIGINAL_ES_FILE.read_bytes()).hexdigest()
        self.assertEqual(
            actual_sha,
            EXPECTED_ORIGINAL_SHA256,
            "Original es.file SHA-256 hash must remain exactly unchanged.",
        )

    def test_translation_workspace_valid(self) -> None:
        """Translation directory must pass full validation with 0 errors."""
        report = validate_workspace(TRANSLATION_DIR, strict=True)
        self.assertTrue(report.valid, f"Workspace validation failed: {report.errors}")
        self.assertEqual(len(report.errors), 0)
        self.assertEqual(report.entries_checked, 68651)

    def test_double_spaces_normalized_and_puzzle_preserved(self) -> None:
        """Verify 0 unnecessary double spaces remain and puzzle lines are preserved."""
        # 1. Normalizer should find 0 pending changes
        changes = apply_double_space_normalization(TRANSLATION_DIR, dry_run=True)
        self.assertEqual(len(changes), 0, "No pending unnecessary double spaces should remain.")

        # 2. Intentional puzzle lines in Ep7 Ch2 must have their wide spaces intact
        p7 = json.loads((TRANSLATION_DIR / "story" / "ep7" / "umi7_2.json").read_text(encoding="utf-8"))
        e1 = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_2.d51163")
        e2 = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_2.d51165")
        e3 = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_2.d51167")

        self.assertIn("p u e d o", e1["segments"][0]["text"])
        self.assertIn("ll amar", e2["segments"][0]["text"])
        self.assertEqual(e3["segments"][0]["text"], '"' + " " * 60 + '."')

    def test_build_determinism_and_lossless_roundtrip(self) -> None:
        """Build twice to verify bit-level determinism, then re-extract to verify 100% round-trip fidelity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            out_file1 = tmp_path / "es.build1.file"
            out_file2 = tmp_path / "es.build2.file"
            reextract_dir = tmp_path / "reextracted"

            # 1. First build
            rep1 = build_esfile(TRANSLATION_DIR, out_file1, force=True, strict=True)
            self.assertTrue(out_file1.exists())

            # 2. Second build
            rep2 = build_esfile(TRANSLATION_DIR, out_file2, force=True, strict=True)
            self.assertTrue(out_file2.exists())

            # 3. Bit-level determinism
            sha1 = hashlib.sha256(out_file1.read_bytes()).hexdigest()
            sha2 = hashlib.sha256(out_file2.read_bytes()).hexdigest()
            self.assertEqual(sha1, sha2, "Two successive builds must produce identical SHA-256 hashes.")
            self.assertEqual(rep1["file_sha256"], rep2["file_sha256"])

            # 4. Re-extract
            extract_esfile(out_file1, reextract_dir)

            # 5. Semantic and plaintext diff against translation workspace
            diff = diff_targets(TRANSLATION_DIR, reextract_dir)
            summary = diff["summary"]
            self.assertTrue(summary["plaintext_identical"], "Re-extracted plaintext must match workspace exactly.")
            self.assertTrue(summary["semantically_identical"], "Re-extracted semantics must match workspace exactly.")
            self.assertEqual(summary["added_count"], 0)
            self.assertEqual(summary["removed_count"], 0)
            self.assertEqual(summary["modified_count"], 0)
            self.assertEqual(summary["altered_markers_count"], 0)
            self.assertFalse(summary["altered_order"])
            self.assertEqual(summary["altered_structural_blocks_count"], 0)

    def test_built_file_is_recognized_as_spanish_script(self) -> None:
        """The released es.file must keep the header and directives the game uses to list it as Spanish."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "es.file"
            build_esfile(TRANSLATION_DIR, out_file, force=True, strict=True)
            raw = out_file.read_bytes()

        self.assertEqual(raw[:4], b"ONS2")
        self.assertEqual(int.from_bytes(raw[4:8], "little"), len(raw) - 16)
        self.assertEqual(int.from_bytes(raw[12:16], "little"), 0x6E)

        container = decode_ons2(raw, strict=True, verify_gameid=True)
        lines = container.plaintext_bytes.decode("utf-8").splitlines()
        self.assertEqual(lines[0], ";mode1920@2172,1222,value2500")
        self.assertEqual(lines[1], ";gameid UminekoPS3ficationEs")
        self.assertIn('stralias localisation,"es"', lines[:40])


if __name__ == "__main__":
    unittest.main()
