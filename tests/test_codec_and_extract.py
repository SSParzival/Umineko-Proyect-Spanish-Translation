"""Unit and integration tests for ONS2 binary codec, parser, path security, and extraction."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.esfile.cli import main as cli_main
from tools.esfile.codec import (
    DEOBFUSCATE_INNER_LUT,
    DEOBFUSCATE_OUTER_LUT,
    INV_SUBSTITUTION_TABLE_T,
    OBFUSCATE_INNER_LUT,
    OBFUSCATE_OUTER_LUT,
    ONS2_HEADER_STRUCT,
    ONS2_KEY_FLAG,
    ONS2_MAGIC,
    SUBSTITUTION_TABLE_T,
    EsFileError,
    EsFileFormatError,
    EsFileSecurityError,
    check_case_collisions,
    decode_ons2,
    encode_ons2,
    resolve_safe_output_path,
    validate_safe_relative_path,
)
from tools.esfile.extractor import extract_esfile
from tools.esfile.inspector import inspect_esfile
from tools.esfile.parser import parse_script


def build_synthetic_script() -> str:
    """Create a synthetic ONScripter-RU script exercising all grammar constructs and mixed EOLs."""
    crlf_lines = [
        ";mode1920@2172,1222,value2500\r\n",
        ";gameid UminekoPS3ficationEs\r\n",
        "\r\n",
        "*define\r\n",
        'stralias localisation,"es"\r\n',
        "numalias releasedate,1759200733\r\n",
        'mov $CHIRU_MODE,"8.2b"\r\n',
        'if %CHIRU_MODE == 0 caption "Umineko ~Prueba Sintética~ (" + $CHIRU_MODE + ")"\r\n',
        'stralias bg_one,":c;backgrounds\\one.png"\r\n',
        'stralias verify_backgrounds,"Asegúrate de desempaquetar la carpeta backgrounds."\r\n',
        "game\r\n",
        "*start\r\n",
        "goto *boot\r\n",
    ]
    lf_story_lines = [
        "*umi1_op\n",
        "msgwnd_non\n",
        "*d1\n",
        "d `El viento soplaba sobre la isla de Rokkenjima.`[\\]\n",
        "msgwnd_bea\n",
        "*d2\n",
        'd [lv 0*"27"*"10700001"]`"¡Bienvenidos, {f:5:Beatrice} os saluda con {c:FF0000:verdad roja}!"`[@][lv 0*"27"*"10700002"]` ¿Acaso dudáis de la magia?`[\\]\n',
        "*d3\n",
        'd2 [lv 0*"19"*"11900001"]`"Imposible`error tipográfico` de creer."`[#][*][\\]\n',
        "*teatime_1\n",
        "*d4\n",
        "d `Fiesta de té del episodio 1.`[\\]\n",
        "*o1_0\n",
        "*o1_1\n",
        "\td [ak]`Omake con tabulación inicial.`[\\]\n",
        "definereset\n",
    ]
    crlf_post_lines = [
        "*ep1_end\r\n",
        "return\r\n",
        "*credits_base\r\n",
        'add $Free1,"{p:21:{a:c:Traducción Sintética}{n}}"\r\n',
        "*credits_end\r\n",
        "return\r\n",
        "*bt_def\r\n",
        'stralias r_tips_1_1,":s;#C7C7C7#FFFFFF`{p:13:Título de pista 1}"\r\n',
        'stralias tips_1_1,"Texto descriptivo de la pista 1."\r\n',
        'stralias r_grim1_1,":s;#C7C7C7#FFFFFF`Grimorio entrada 1"\r\n',
        'stralias chars_1_kin_1,":s;#FFFFFF`{p:3:Ushiromiya Kinzo}"\r\n',
        'stralias chars_3_hid_2,":s;#FFFFFF`Línea uno con salto literal\n',
        'y continuación en la segunda línea."\r\n',
        'stralias clock_scenario_6_10"12:15"\r\n',
        'stralias ep8_9_1,"Acertijo del episodio 8"\r\n',
        'stralias trophy_text_00,"{p:18:Trofeo de prueba}"\r\n',
        'stralias save_1_op,"Prólogo"\r\n',
        "*load_font_preference\r\n",
        "*goa_1e\r\n",
        "d `Vista previa de fuente gótica.`[\\]\r\n",
        "*bgm_locale_title\r\n",
        'if %BGM_Id == 1\tmov $BGM_Title,"Lirio Sintético" : return\r\n',
    ]
    return "".join(crlf_lines + lf_story_lines + crlf_post_lines)


class TestOns2Codec(unittest.TestCase):
    """Tests for the ONS2 binary codec and substitution tables."""

    def test_substitution_table_is_bijective(self) -> None:
        self.assertEqual(len(SUBSTITUTION_TABLE_T), 256)
        self.assertEqual(set(SUBSTITUTION_TABLE_T), set(range(256)))
        for x in range(256):
            self.assertEqual(INV_SUBSTITUTION_TABLE_T[SUBSTITUTION_TABLE_T[x]], x)
            self.assertEqual(DEOBFUSCATE_OUTER_LUT[OBFUSCATE_OUTER_LUT[x]], x)
            self.assertEqual(DEOBFUSCATE_INNER_LUT[OBFUSCATE_INNER_LUT[x]], x)

    def test_encode_decode_roundtrip(self) -> None:
        script_text = build_synthetic_script()
        raw_bytes = script_text.encode("utf-8")
        encoded = encode_ons2(raw_bytes)

        self.assertEqual(encoded[:4], ONS2_MAGIC)
        magic, comp_size, uncomp_size, key_flag = ONS2_HEADER_STRUCT.unpack_from(encoded, 0)
        self.assertEqual(magic, b"ONS2")
        self.assertEqual(key_flag, ONS2_KEY_FLAG)
        self.assertEqual(uncomp_size, len(raw_bytes))
        self.assertEqual(16 + comp_size, len(encoded))

        decoded = decode_ons2(encoded)
        self.assertEqual(decoded.plaintext_bytes, raw_bytes)
        self.assertEqual(decoded.header.comp_size, comp_size)
        self.assertEqual(decoded.header.uncomp_size, uncomp_size)

    def test_reject_corrupted_headers_and_payloads(self) -> None:
        # Too short
        with self.assertRaises(EsFileFormatError):
            decode_ons2(b"ONS2short")

        # Wrong magic
        bad_magic = ONS2_HEADER_STRUCT.pack(b"ONS1", 32, 32, ONS2_KEY_FLAG) + b"\x00" * 32
        with self.assertRaises(EsFileFormatError):
            decode_ons2(bad_magic)

        # Wrong key_flag
        bad_flag = ONS2_HEADER_STRUCT.pack(b"ONS2", 32, 32, 0x99) + b"\x00" * 32
        with self.assertRaises(EsFileFormatError):
            decode_ons2(bad_flag)

        # Out-of-bounds sizes
        bad_size = ONS2_HEADER_STRUCT.pack(b"ONS2", 8, 32, ONS2_KEY_FLAG) + b"\x00" * 8
        with self.assertRaises(EsFileFormatError):
            decode_ons2(bad_size)

        # Truncated payload
        valid_encoded = encode_ons2(build_synthetic_script().encode("utf-8"))
        with self.assertRaises(EsFileFormatError):
            decode_ons2(valid_encoded[:-5])

        # Trailing garbage in strict mode
        with self.assertRaises(EsFileFormatError):
            decode_ons2(valid_encoded + b"EXTRA", strict=True)

        # Missing gameid signature
        no_gameid = ";mode1920\n*define\ngame\n*start\n".encode("utf-8")
        with self.assertRaises(EsFileFormatError):
            encode_ons2(no_gameid, verify_gameid=True)


class TestPathSecurity(unittest.TestCase):
    """Tests for path traversal, reserved names, invalid chars, and collision checks."""

    def test_reject_unsafe_paths(self) -> None:
        unsafe = [
            "",
            "../secret.json",
            "story/../../etc/passwd",
            "/abs/path.json",
            "\\windows\\path.json",
            "C:/windows/system32.json",
            "story/ep1/bad:name.json",
            "story/ep1/CON.json",
            "story/ep1/nul.txt",
            "story/ep1/com1.json",
            "story/ep1/trailing_dot./file.json",
            "story/ep1/ leading_space.json",
        ]
        for path in unsafe:
            with self.subTest(path=path):
                with self.assertRaises(EsFileSecurityError):
                    validate_safe_relative_path(path)

    def test_case_collision_detection(self) -> None:
        with self.assertRaises(EsFileSecurityError):
            check_case_collisions(["story/ep1/umi1_1.json", "story/ep1/UMI1_1.json"])

    def test_symlink_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            outside = base / "outside"
            outside.mkdir()
            sub_dir = base / "out"
            sub_dir.mkdir()
            link = sub_dir / "story"
            link.symlink_to(outside)
            with self.assertRaises(EsFileSecurityError):
                resolve_safe_output_path(sub_dir, "story/ep1/umi1_op.json")


class TestParserAndExtractor(unittest.TestCase):
    """Tests for script parsing, catalog classification, and CLI extraction."""

    def test_parse_and_reconstruct_synthetic_script(self) -> None:
        script_text = build_synthetic_script()
        res = parse_script(script_text)

        self.assertEqual(res.metadata.localisation, "es")
        self.assertEqual(res.metadata.releasedate, 1759200733)
        self.assertEqual(res.metadata.chiru_mode_version, "8.2b")

        # Verify warnings captured for stray backtick, multiline stralias, and missing comma
        warn_codes = {w.code for w in res.warnings}
        self.assertIn("STRAY_BACKTICK_IN_DIALOGUE", warn_codes)
        self.assertIn("MULTILINE_STRALIAS", warn_codes)
        self.assertIn("MISSING_COMMA_IN_STRALIAS", warn_codes)

        # Verify exact script reconstruction from blocks + catalogs
        entry_map = {e.id: e for cat in res.catalogs.values() for e in cat.entries}
        rebuilt = "".join(
            rec["text"]
            if rec["kind"] == "raw"
            else entry_map[rec["id"]].reconstruct_script_line()
            for blk in res.blocks
            for rec in blk.records
        )
        self.assertEqual(rebuilt, script_text)

    def test_extract_and_inspect_workflow(self) -> None:
        script_text = build_synthetic_script()
        ons2_bytes = encode_ons2(script_text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_file = tmp_path / "synthetic.file"
            src_file.write_bytes(ons2_bytes)

            info = inspect_esfile(src_file)
            self.assertEqual(info["format"]["container_type"], "ONS2")
            self.assertGreater(info["counts"]["total_entries"], 10)

            out_dir = tmp_path / "extracted"
            report = extract_esfile(src_file, out_dir, keep_raw=True)
            self.assertEqual(report["status"], "ok")
            self.assertTrue((out_dir / "manifest.json").is_file())
            self.assertTrue((out_dir / "report.json").is_file())
            self.assertTrue((out_dir / "raw" / "decoded_script.txt").is_file())
            self.assertTrue((out_dir / "story" / "ep1" / "umi1_op.json").is_file())

            # Refuses to overwrite non-empty directory without force=True
            with self.assertRaises(EsFileError):
                extract_esfile(src_file, out_dir, force=False)

            # Deterministic output across second extraction
            out_dir2 = tmp_path / "extracted2"
            extract_esfile(src_file, out_dir2, keep_raw=True)
            self.assertEqual(
                (out_dir / "manifest.json").read_bytes(),
                (out_dir2 / "manifest.json").read_bytes(),
            )

            # CLI smoke test for inspect and extract
            rc_inspect = cli_main(["inspect", str(src_file)])
            self.assertEqual(rc_inspect, 0)
            out_dir3 = tmp_path / "extracted3"
            rc_extract = cli_main(["extract", str(src_file), "--output", str(out_dir3)])
            self.assertEqual(rc_extract, 0)
            self.assertEqual(
                (out_dir / "manifest.json").read_bytes(),
                (out_dir3 / "manifest.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
