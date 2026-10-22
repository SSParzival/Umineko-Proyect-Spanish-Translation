"""Unit and integration tests for `tools.esfile build` and round-trip persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_codec_and_extract import build_synthetic_script
from tools.esfile.builder import build_esfile
from tools.esfile.cli import main as cli_main
from tools.esfile.codec import (
    EsFileError,
    EsFileValidationError,
    decode_ons2,
    encode_ons2,
    sha256_hex,
)
from tools.esfile.extractor import extract_esfile


class TestBuildAndModificationPersistence(unittest.TestCase):
    """Tests for ONS2 compilation, effective modification, and validation guards."""

    def test_unmodified_roundtrip_is_binary_identical(self) -> None:
        script_text = build_synthetic_script()
        original_bytes = encode_ons2(script_text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_file = tmp_path / "src.file"
            src_file.write_bytes(original_bytes)

            extracted_dir = tmp_path / "translation"
            extract_esfile(src_file, extracted_dir)

            rebuilt_file = tmp_path / "rebuilt.file"
            report = build_esfile(extracted_dir, rebuilt_file)

            self.assertTrue(report["binary_identical_to_original"])
            self.assertTrue(report["plaintext_identical_to_original"])
            self.assertEqual(rebuilt_file.read_bytes(), original_bytes)
            self.assertEqual(sha256_hex(rebuilt_file.read_bytes()), sha256_hex(original_bytes))

            # Refuses to overwrite existing file without force=True
            with self.assertRaises(EsFileError):
                build_esfile(extracted_dir, rebuilt_file, force=False)

    def test_effective_modification_persists_across_rebuild_and_reextract(self) -> None:
        """Requirement 46: Extract -> Modify entry -> Build -> Verify changed -> Re-extract -> Verify persists."""
        script_text = build_synthetic_script()
        original_bytes = encode_ons2(script_text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_file = tmp_path / "src.file"
            src_file.write_bytes(original_bytes)

            # 1. Extract
            extracted_dir = tmp_path / "translation_a"
            extract_esfile(src_file, extracted_dir)

            # 2. Modify one dialogue entry and one stralias entry
            umi1_op_path = extracted_dir / "story" / "ep1" / "umi1_op.json"
            cat_data = json.loads(umi1_op_path.read_text(encoding="utf-8"))
            new_dialogue_text = "El huracán rugía con fuerza sobre la mansión de Rokkenjima."
            cat_data["entries"][0]["segments"][0]["text"] = new_dialogue_text
            cat_data["entries"][0]["text"] = new_dialogue_text
            umi1_op_path.write_text(
                json.dumps(cat_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            bgm_path = extracted_dir / "strings" / "bgm_titles.json"
            bgm_data = json.loads(bgm_path.read_text(encoding="utf-8"))
            bgm_data["entries"][0]["text"] = "Rosa Dorada Sintética"
            bgm_path.write_text(
                json.dumps(bgm_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            # 3. Rebuild via CLI
            rebuilt_file = tmp_path / "modified.file"
            rc = cli_main(["build", str(extracted_dir), str(rebuilt_file), "--verbose"])
            self.assertEqual(rc, 0)

            # 4. Verify that the generated binary file changed and has valid ONS2 header & sizes
            rebuilt_bytes = rebuilt_file.read_bytes()
            self.assertNotEqual(sha256_hex(rebuilt_bytes), sha256_hex(original_bytes))
            decoded_mod = decode_ons2(rebuilt_bytes)
            self.assertIn(new_dialogue_text.encode("utf-8"), decoded_mod.plaintext_bytes)
            self.assertIn("Rosa Dorada Sintética".encode("utf-8"), decoded_mod.plaintext_bytes)

            # 5. Extract again from modified.file
            reextracted_dir = tmp_path / "translation_b"
            extract_esfile(rebuilt_file, reextracted_dir)

            # 6. Verify that only those 2 entries changed and the modifications persist
            re_umi1_data = json.loads(
                (reextracted_dir / "story" / "ep1" / "umi1_op.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                re_umi1_data["entries"][0]["segments"][0]["text"],
                new_dialogue_text,
            )
            # Second entry in umi1_op.json must remain untouched
            self.assertEqual(
                re_umi1_data["entries"][1]["segments"],
                cat_data["entries"][1]["segments"],
            )

            re_bgm_data = json.loads(
                (reextracted_dir / "strings" / "bgm_titles.json").read_text(encoding="utf-8")
            )
            self.assertEqual(re_bgm_data["entries"][0]["text"], "Rosa Dorada Sintética")

    def test_build_rejects_invalid_edits(self) -> None:
        script_text = build_synthetic_script()
        original_bytes = encode_ons2(script_text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_file = tmp_path / "src.file"
            src_file.write_bytes(original_bytes)

            extracted_dir = tmp_path / "translation"
            extract_esfile(src_file, extracted_dir)
            umi1_op_path = extracted_dir / "story" / "ep1" / "umi1_op.json"
            original_cat_bytes = umi1_op_path.read_bytes()

            # Case 1: Unbalanced inline tag brace `{c:FF0000:verdad`
            bad_cat = json.loads(original_cat_bytes.decode("utf-8"))
            bad_cat["entries"][0]["segments"][0]["text"] = "Texto con llave sin cerrar {c:FF0000:rojo"
            umi1_op_path.write_text(json.dumps(bad_cat), encoding="utf-8")
            with self.assertRaises(EsFileValidationError):
                build_esfile(extracted_dir, tmp_path / "out1.file")

            # Case 2: Forbidden bracket `[` inside segment text
            bad_cat = json.loads(original_cat_bytes.decode("utf-8"))
            bad_cat["entries"][0]["segments"][0]["text"] = "Texto con marcador [lv 0] infiltrado"
            umi1_op_path.write_text(json.dumps(bad_cat), encoding="utf-8")
            with self.assertRaises(EsFileValidationError):
                build_esfile(extracted_dir, tmp_path / "out2.file")

            # Case 3: Duplicate entry ID
            bad_cat = json.loads(original_cat_bytes.decode("utf-8"))
            bad_cat["entries"][1]["id"] = bad_cat["entries"][0]["id"]
            umi1_op_path.write_text(json.dumps(bad_cat), encoding="utf-8")
            with self.assertRaises(EsFileValidationError):
                build_esfile(extracted_dir, tmp_path / "out3.file")

            # Restore valid catalog, then delete a catalog file to trigger missing file error
            umi1_op_path.write_bytes(original_cat_bytes)
            umi1_op_path.unlink()
            with self.assertRaises(EsFileValidationError):
                build_esfile(extracted_dir, tmp_path / "out4.file")


if __name__ == "__main__":
    unittest.main()
