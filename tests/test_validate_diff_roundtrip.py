"""Tests for `validate`, `diff`, fuzzing/robustness, and real `es.file` lossless round-trip."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from tests.test_codec_and_extract import build_synthetic_script
from tools.esfile.builder import build_esfile
from tools.esfile.cli import main as cli_main
from tools.esfile.codec import (
    OBFUSCATE_INNER_LUT,
    OBFUSCATE_OUTER_LUT,
    ONS2_HEADER_STRUCT,
    ONS2_KEY_FLAG,
    ONS2_MAGIC,
    EsFileError,
    EsFileFormatError,
    decode_ons2,
    encode_ons2,
    sha256_hex,
)
from tools.esfile.differ import diff_targets
from tools.esfile.extractor import extract_esfile
from tools.esfile.validator import validate_workspace


class TestValidator(unittest.TestCase):
    """Comprehensive tests for `tools.esfile validate` error and warning detection."""

    def setUp(self) -> None:
        self.script_text = build_synthetic_script()
        self.ons2_bytes = encode_ons2(self.script_text.encode("utf-8"))

    def test_valid_workspace_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src.file"
            src.write_bytes(self.ons2_bytes)
            out_dir = tmp_path / "translation"
            extract_esfile(src, out_dir)

            report = validate_workspace(out_dir, strict=True)
            self.assertTrue(report.valid)
            self.assertEqual(len(report.errors), 0)
            self.assertEqual(len(report.warnings), 1)  # 1 pre-existing stray backtick warning

            rc = cli_main(["validate", str(out_dir), "--strict", "--verbose"])
            self.assertEqual(rc, 0)

    def test_detects_all_validation_error_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src.file"
            src.write_bytes(self.ons2_bytes)
            out_dir = tmp_path / "translation"
            extract_esfile(src, out_dir)

            umi_path = out_dir / "story" / "ep1" / "umi1_op.json"
            orig_umi_bytes = umi_path.read_bytes()

            # 1. Missing inline tag in strict mode (`{f:5:Beatrice}` and `{c:FF0000:verdad roja}` removed)
            data = json.loads(orig_umi_bytes.decode("utf-8"))
            data["entries"][1]["segments"][0]["text"] = '"¡Bienvenidos sin etiquetas!"'
            umi_path.write_text(json.dumps(data), encoding="utf-8")
            rep_warn = validate_workspace(out_dir, strict=False)
            self.assertTrue(rep_warn.valid)
            self.assertIn("MISSING_INLINE_TAG", {w.code for w in rep_warn.warnings})
            rep_strict = validate_workspace(out_dir, strict=True)
            self.assertFalse(rep_strict.valid)
            self.assertIn("MISSING_INLINE_TAG", {e.code for e in rep_strict.errors})

            # 2. Empty segment, literal newline, unescaped backtick, and altered markers
            data = json.loads(orig_umi_bytes.decode("utf-8"))
            data["entries"][0]["segments"][0]["text"] = ""
            data["entries"][1]["segments"][0]["text"] = "Salto\nliteral y `acento grave` y [corchete]"
            data["entries"][1]["markers"][0] = "corrupted_marker_without_brackets"
            umi_path.write_text(json.dumps(data), encoding="utf-8")
            rep = validate_workspace(out_dir)
            self.assertFalse(rep.valid)
            codes = {e.code for e in rep.errors}
            self.assertIn("EMPTY_ENTRY", codes)
            self.assertIn("INVALID_NEWLINE", codes)
            self.assertIn("INVALID_SEQUENCE", codes)
            self.assertIn("ALTERED_MARKERS", codes)

            # 3. Duplicate ID, out-of-order line_number, and lone UTF-16 surrogate
            data = json.loads(orig_umi_bytes.decode("utf-8"))
            data["entries"][1]["id"] = data["entries"][0]["id"]
            data["entries"][1]["line_number"] = 1
            data["entries"][0]["segments"][0]["text"] = "Surrogate \ud800 inválido"
            umi_path.write_bytes(json.dumps(data, ensure_ascii=True).encode("utf-8"))
            rep = validate_workspace(out_dir)
            codes = {e.code for e in rep.errors}
            self.assertIn("DUPLICATE_ENTRY_ID", codes)
            self.assertIn("INVALID_ENTRY_ORDER", codes)
            self.assertIn("ENCODING_ERROR", codes)

            # Restore umi1_op.json, test unexpected extra file and corrupted block checksum
            umi_path.write_bytes(orig_umi_bytes)
            extra_file = out_dir / "story" / "ep1" / "unexpected.json"
            extra_file.write_text("{}", encoding="utf-8")
            blk_path = out_dir / "blocks" / "01_story_ep1.json"
            orig_blk_bytes = blk_path.read_bytes()
            blk_path.write_bytes(orig_blk_bytes + b"\n")

            rep = validate_workspace(out_dir)
            codes = {e.code for e in rep.errors}
            self.assertIn("UNEXPECTED_EXTRA_FILE", codes)
            self.assertIn("CHECKSUM_MISMATCH", codes)
            self.assertEqual(cli_main(["validate", str(out_dir)]), 1)


class TestSemanticAndBinaryDiffer(unittest.TestCase):
    """Tests for `tools.esfile diff` across .file archives and translation directories."""

    def test_diff_between_files_and_directories(self) -> None:
        script_text = build_synthetic_script()
        orig_bytes = encode_ons2(script_text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            file_a = tmp_path / "a.file"
            file_a.write_bytes(orig_bytes)

            dir_a = tmp_path / "dir_a"
            dir_b = tmp_path / "dir_b"
            extract_esfile(file_a, dir_a)
            extract_esfile(file_a, dir_b)

            # Identical diff
            d_same = diff_targets(file_a, file_a)
            self.assertTrue(d_same["summary"]["binary_identical"])
            self.assertTrue(d_same["summary"]["semantically_identical"])

            # Modify one entry in dir_b and build file_b
            umi_b = dir_b / "story" / "ep1" / "umi1_op.json"
            cat_b = json.loads(umi_b.read_text(encoding="utf-8"))
            cat_b["entries"][0]["segments"][0]["text"] = "Texto modificado para prueba de diff."
            umi_b.write_text(json.dumps(cat_b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            file_b = tmp_path / "b.file"
            build_esfile(dir_b, file_b)

            # Diff file_a vs file_b
            d_files = diff_targets(file_a, file_b)
            self.assertFalse(d_files["summary"]["binary_identical"])
            self.assertFalse(d_files["summary"]["plaintext_identical"])
            self.assertFalse(d_files["summary"]["semantically_identical"])
            self.assertEqual(d_files["summary"]["modified_count"], 1)
            self.assertEqual(d_files["modified_entries"][0]["id"], "ep1.umi1_op.d1")
            self.assertTrue(d_files["expected_binary_differences"])

            # Diff dir_a vs dir_b via CLI
            report_file = tmp_path / "diff_report.json"
            rc = cli_main(["diff", str(dir_a), str(dir_b), "--report", str(report_file), "--verbose"])
            self.assertEqual(rc, 0)
            rep_loaded = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertEqual(rep_loaded["summary"]["modified_count"], 1)


class TestFuzzingAndRobustness(unittest.TestCase):
    """Fuzzing and malformed input tests (Requirement 27)."""

    def test_malformed_and_fuzzed_containers(self) -> None:
        valid_script = build_synthetic_script().encode("utf-8")
        valid_file = encode_ons2(valid_script)

        # 1. Truncated at various byte offsets
        for cut in (0, 1, 4, 8, 15, 16, 20, len(valid_file) - 1):
            with self.subTest(truncation=cut):
                with self.assertRaises(EsFileFormatError):
                    decode_ons2(valid_file[:cut])

        # 2. Out-of-bounds header sizes
        for bad_comp, bad_uncomp in (
            (0, 100),
            (15, 100),
            (0x10000001, 100),
            (0xFFFFFFFF, 100),
            (100, 0),
            (100, 15),
            (100, 0x10000001),
        ):
            hdr = ONS2_HEADER_STRUCT.pack(ONS2_MAGIC, bad_comp, bad_uncomp, ONS2_KEY_FLAG)
            with self.subTest(comp=bad_comp, uncomp=bad_uncomp):
                with self.assertRaises(EsFileFormatError):
                    decode_ons2(hdr + b"\x00" * 100)

        # 3. Corrupted ZLIB stream inside valid ONS2 envelope
        corrupt_zlib = bytearray(valid_file)
        corrupt_zlib[20] ^= 0xFF
        corrupt_zlib[21] ^= 0xFF
        with self.assertRaises(EsFileFormatError):
            decode_ons2(bytes(corrupt_zlib))

        # 4. Valid ZLIB stream but wrong uncomp_size in header
        magic, comp_sz, uncomp_sz, flag = ONS2_HEADER_STRUCT.unpack_from(valid_file, 0)
        wrong_uncomp = ONS2_HEADER_STRUCT.pack(magic, comp_sz, uncomp_sz + 5, flag) + valid_file[16:]
        with self.assertRaises(EsFileFormatError):
            decode_ons2(wrong_uncomp)

        # 5. Embedded NUL byte in plaintext
        nul_plain = valid_script + b"\x00"
        z_nul = zlib.compress(nul_plain.translate(OBFUSCATE_INNER_LUT))
        f_nul = ONS2_HEADER_STRUCT.pack(
            ONS2_MAGIC, len(z_nul), len(nul_plain), ONS2_KEY_FLAG
        ) + z_nul.translate(OBFUSCATE_OUTER_LUT)
        with self.assertRaises(EsFileFormatError):
            decode_ons2(f_nul)

        # 6. Invalid UTF-8 byte sequence in plaintext
        bad_utf8_plain = valid_script + b"\xff\xfe\xfd"
        z_bad = zlib.compress(bad_utf8_plain.translate(OBFUSCATE_INNER_LUT))
        f_bad = ONS2_HEADER_STRUCT.pack(
            ONS2_MAGIC, len(z_bad), len(bad_utf8_plain), ONS2_KEY_FLAG
        ) + z_bad.translate(OBFUSCATE_OUTER_LUT)
        with self.assertRaises(EsFileFormatError):
            decode_ons2(f_bad)

    def test_large_entry_and_special_unicode(self) -> None:
        huge_segment = "«¡¿ÁÉÍÓÚÜÑáéíóúüñ—…♪?!» " * 2000  # ~96 KB single segment
        base = build_synthetic_script()
        large_script = base + f"*umi1_1\n*d999\nd `{huge_segment}`[\\]\n"
        encoded = encode_ons2(large_script.encode("utf-8"))
        decoded = decode_ons2(encoded)
        self.assertEqual(decoded.plaintext_bytes.decode("utf-8"), large_script)


@unittest.skipUnless(Path("es.file").is_file(), "Requires real es.file in workspace root")
class TestRealEsFileRoundTrip(unittest.TestCase):
    """End-to-end verification on the real Umineko Project `es.file` (Requirements 22 & 24)."""

    EXPECTED_ES_SHA256 = "0c00c9cf156b6429e01e6f1d26a6ae655329ef8301b6719a1742834b524300e1"

    def test_real_esfile_lossless_roundtrip_and_minimal_edit(self) -> None:
        es_path = Path("es.file")
        orig_sha = sha256_hex(es_path.read_bytes())
        self.assertEqual(orig_sha, self.EXPECTED_ES_SHA256)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trans_dir = tmp_path / "translation"

            # 1. Extract real es.file
            ext_report = extract_esfile(es_path, trans_dir)
            self.assertEqual(ext_report["counts"]["catalog_files"], 182)
            self.assertEqual(ext_report["counts"]["block_files"], 11)
            self.assertEqual(ext_report["counts"]["total_entries"], 68651)

            # 2. Validate extracted translation workspace
            val_report = validate_workspace(trans_dir, strict=True)
            self.assertTrue(val_report.valid)
            self.assertEqual(len(val_report.errors), 0)

            # 3. Rebuild without modifications and verify SHA-256 binary identity
            rebuilt_path = tmp_path / "es.rebuilt.file"
            build_report = build_esfile(trans_dir, rebuilt_path)
            self.assertTrue(build_report["binary_identical_to_original"])
            self.assertTrue(build_report["plaintext_identical_to_original"])
            self.assertEqual(build_report["file_sha256"], self.EXPECTED_ES_SHA256)
            self.assertEqual(sha256_hex(rebuilt_path.read_bytes()), self.EXPECTED_ES_SHA256)

            # 4. Verify semantic & binary diff reports 0 differences
            diff_same = diff_targets(es_path, rebuilt_path)
            self.assertTrue(diff_same["summary"]["binary_identical"])
            self.assertTrue(diff_same["summary"]["semantically_identical"])

            # 5. Requirement 24: Minimal controlled modification on a single entry
            sys_cat_path = trans_dir / "strings" / "define_system.json"
            sys_cat = json.loads(sys_cat_path.read_text(encoding="utf-8"))
            orig_caption = sys_cat["entries"][0]["text"]
            sys_cat["entries"][0]["text"] = orig_caption + " [Test]"
            sys_cat_path.write_text(
                json.dumps(sys_cat, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            mod_file = tmp_path / "es.modified.file"
            mod_build = build_esfile(trans_dir, mod_file)
            self.assertFalse(mod_build["binary_identical_to_original"])
            self.assertEqual(mod_build["modified_catalogs"], ["strings/define_system.json"])

            diff_mod = diff_targets(es_path, mod_file)
            self.assertFalse(diff_mod["summary"]["binary_identical"])
            self.assertEqual(diff_mod["summary"]["modified_count"], 1)
            self.assertEqual(diff_mod["summary"]["added_count"], 0)
            self.assertEqual(diff_mod["summary"]["removed_count"], 0)
            self.assertEqual(diff_mod["summary"]["altered_structural_blocks_count"], 0)
            self.assertEqual(diff_mod["modified_entries"][0]["id"], "define.caption.1")

        # Confirm original es.file in workspace was never modified
        self.assertEqual(sha256_hex(es_path.read_bytes()), self.EXPECTED_ES_SHA256)


if __name__ == "__main__":
    unittest.main()
