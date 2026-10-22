"""Unit tests for the `tools.translation_lint` toolkit."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.translation_lint.applicator import apply_corrections_workspace
from tools.translation_lint.models import Finding, LintReport
from tools.translation_lint.rules import (
    COMPILED_WORD_RULES,
    TARGETED_BY_ENTRY_ID,
    apply_outside_tags,
    load_accepted_words,
)
from tools.translation_lint.scanner import scan_entry_text, scan_workspace
from tools.translation_lint.validator import validate_workspace_lint


class TestTranslationLint(unittest.TestCase):
    """Test suite for linguistic rules, tag preservation, scanning, applying, and validating."""

    def test_apply_outside_tags_preserves_formatting(self) -> None:
        text = "Hola {c:FF0000:mundo} cruel, {f:5:Battler} dijo tambien {n}y salio."
        result = apply_outside_tags(text, lambda s: s.replace("tambien", "también"))
        self.assertIn("también", result)
        self.assertIn("{c:FF0000:mundo}", result)
        self.assertIn("{f:5:Battler}", result)
        self.assertIn("{n}", result)

    def test_load_accepted_words(self) -> None:
        words = load_accepted_words()
        self.assertIn("Ushiromiya", words)
        self.assertIn("Kinzo", words)
        self.assertIn("Battler", words)
        self.assertIn("to's", words)
        self.assertIn("pensa'o", words)

    def test_word_rules_correct_typos_and_tildes(self) -> None:
        cases = [
            ("Elegigo por el destino", "Elegido por el destino"),
            ("la caveza del monstruo", "la cabeza del monstruo"),
            ("Batlter se sorprendió", "Battler se sorprendió"),
            ("Ushromiya es la familia", "Ushiromiya es la familia"),
            ("construído en piedra", "construido en piedra"),
            ("casí todo terminó", "casi todo terminó"),
            ("no tengo fé en ello", "no tengo fe en ello"),
            ("dejame en paz", "déjame en paz"),
            ("tambien vendrá", "también vendrá"),
            ("un crímen atroz", "un crimen atroz"),
            ("órdenes estrictas", "órdenes estrictas"),
        ]
        for src, expected in cases:
            res = src
            for rx, _w_from, w_to, _cat, _reason in COMPILED_WORD_RULES:
                res = rx.sub(w_to, res)
            self.assertEqual(res, expected, f"Failed for input: {src}")

    def test_targeted_rules_and_spacing(self) -> None:
        self.assertIn("ep7.umi7_11.d53813", TARGETED_BY_ENTRY_ID)
        entry_rules = TARGETED_BY_ENTRY_ID["ep7.umi7_11.d53813"]
        s_from, s_to, cat, _reason = entry_rules[0]
        self.assertEqual(s_from, "¡Hurra , ya")
        self.assertEqual(s_to, "¡Hurra, ya")
        self.assertEqual(cat, "ESPACIADO")

    def test_medium_priority_resolutions_on_disk(self) -> None:
        workspace = Path(__file__).resolve().parent.parent / "translation"

        # 1. ep8.teatime_8.d67746
        p8 = json.loads((workspace / "story" / "ep8" / "teatime_8.json").read_text(encoding="utf-8"))
        e8 = next(e for e in p8["entries"] if e["id"] == "ep8.teatime_8.d67746")
        self.assertIn("alguien lo está entrenando infernalmente", e8["segments"][0]["text"])

        # 2. ep7.umi7_4.d51677
        p7 = json.loads((workspace / "story" / "ep7" / "umi7_4.json").read_text(encoding="utf-8"))
        e7 = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_4.d51677")
        self.assertIn("{ruby:an unusable scrap heap now.:un montón de chatarra inservible.}", e7["segments"][1]["text"])

        # 3. ep6.umi6_18.d50079
        p6 = json.loads((workspace / "story" / "ep6" / "umi6_18.json").read_text(encoding="utf-8"))
        e6_desafio = next(e for e in p6["entries"] if e["id"] == "ep6.umi6_18.d50079")
        self.assertIn("{f:5:desafío}", e6_desafio["segments"][1]["text"])

    def test_low_priority_stutters_preserved(self) -> None:
        workspace = Path(__file__).resolve().parent.parent / "translation"

        p6 = json.loads((workspace / "story" / "ep6" / "umi6_16.json").read_text(encoding="utf-8"))
        e6_1 = next(e for e in p6["entries"] if e["id"] == "ep6.umi6_16.d49232")
        self.assertIn("Deten...", e6_1["segments"][2]["text"])
        self.assertIn(" te", e6_1["segments"][3]["text"])
        self.assertIn("Deten...  te", e6_1["text"])

        e6_2 = next(e for e in p6["entries"] if e["id"] == "ep6.umi6_16.d49256")
        self.assertIn("deten... te...", e6_2["segments"][2]["text"])

        p8 = json.loads((workspace / "story" / "ep8" / "umi8_16.json").read_text(encoding="utf-8"))
        e8 = next(e for e in p8["entries"] if e["id"] == "ep8.umi8_16.d65167")
        self.assertIn("¡¡D-Deten—!!", e8["segments"][0]["text"])

    def test_review_decisions_registry(self) -> None:
        decisions_path = Path(__file__).resolve().parent.parent / "translation" / "config" / "review-decisions.jsonl"
        self.assertTrue(decisions_path.exists())
        lines = decisions_path.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 10)
        for line in lines:
            if not line.strip():
                continue
            item = json.loads(line)
            self.assertIn("id", item)
            self.assertIn("file", item)
            self.assertIn("entry_id", item)
            self.assertIn("decision", item)
            self.assertIn("status", item)

    def test_round_trip_application_on_fixture(self) -> None:
        fixture_catalog = {
            "schema_version": "1.0.0",
            "catalog_id": "story.ep1.test",
            "category": "story",
            "rel_path": "story/ep1/test.json",
            "episode": "ep1",
            "section": "test",
            "chapter": "test",
            "description": "Test chapter.",
            "entry_count": 2,
            "entries": [
                {
                    "id": "ep1.test.d001",
                    "kind": "dialogue",
                    "line_number": 10,
                    "line_span": 1,
                    "line_ending": "CRLF",
                    "chapter": "test",
                    "label": "*test_label",
                    "speaker": "battler",
                    "voice_files": ["b1/001"],
                    "command_prefix": "d ",
                    "command_suffix": "",
                    "sprite_prefix": "",
                    "markers": ["[lv 1*\"b1\"*\"001\"]", ""],
                    "segments": [
                        {
                            "index": 0,
                            "text": "Elegigo Batlter dijo {c:FF0000:tambien}.",
                            "inline_tags": ["{c:FF0000:"],
                        }
                    ],
                    "text": "Elegigo Batlter dijo {c:FF0000:tambien}.",
                    "inline_tags": ["{c:FF0000:"],
                },
                {
                    "id": "stralias.test_alias",
                    "kind": "stralias",
                    "line_number": 20,
                    "line_span": 1,
                    "line_ending": "LF",
                    "chapter": "define",
                    "label": "*define",
                    "speaker": "",
                    "voice_files": [],
                    "command_prefix": "stralias test_alias,\"",
                    "command_suffix": "\"",
                    "sprite_prefix": "",
                    "markers": [],
                    "segments": [],
                    "text": "Una caveza de oro",
                    "inline_tags": [],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cat_dir = tmppath / "story" / "ep1"
            cat_dir.mkdir(parents=True, exist_ok=True)
            cat_file = cat_dir / "test.json"
            cat_file.write_text(json.dumps(fixture_catalog, indent=2), encoding="utf-8")

            # 1. Scan before
            rep_before = scan_workspace(tmppath)
            self.assertGreaterEqual(rep_before.total_findings, 3)

            # 2. Apply corrections
            applied, modified = apply_corrections_workspace(tmppath, update_manifest=False)
            self.assertIn("story/ep1/test.json", modified)
            self.assertGreaterEqual(len(applied), 3)

            # 3. Read back and verify corrected content
            updated_data = json.loads(cat_file.read_text(encoding="utf-8"))
            e0 = updated_data["entries"][0]
            self.assertEqual(e0["id"], "ep1.test.d001")
            self.assertEqual(e0["voice_files"], ["b1/001"])
            self.assertEqual(e0["segments"][0]["text"], "Elegido Battler dijo {c:FF0000:tambien}.")
            self.assertEqual(e0["text"], "Elegido Battler dijo {c:FF0000:tambien}.")

            e1 = updated_data["entries"][1]
            self.assertEqual(e1["text"], "Una cabeza de oro")

            # 4. Validate
            val = validate_workspace_lint(tmppath)
            self.assertTrue(val.valid)
            self.assertEqual(len(val.errors), 0)

    def test_double_space_normalizer_rules(self) -> None:
        from tools.translation_lint.double_space_normalizer import normalize_spacing

        # Internal double space
        self.assertEqual(
            normalize_spacing("Siendo incapaz de resistir...  no podía"),
            "Siendo incapaz de resistir... no podía",
        )
        # Leading double space
        self.assertEqual(
            normalize_spacing("  pero después"),
            " pero después",
        )
        # Trailing double space
        self.assertEqual(
            normalize_spacing("Era una mujer.  "),
            "Era una mujer.",
        )
        # Spacing around tags
        self.assertEqual(
            normalize_spacing("{f:5:Bernkastel}  me miró"),
            "{f:5:Bernkastel} me miró",
        )
        # Tags with internal colon or params preserved
        self.assertEqual(
            normalize_spacing("Lucifer  ({p:4:ルシファー})"),
            "Lucifer ({p:4:ルシファー})",
        )

    def test_intentional_spacing_preserved(self) -> None:
        workspace = Path(__file__).resolve().parent.parent / "translation"
        p7 = json.loads((workspace / "story" / "ep7" / "umi7_2.json").read_text(encoding="utf-8"))
        e_call1 = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_2.d51163")
        e_call2 = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_2.d51165")
        e_pause = next(e for e in p7["entries"] if e["id"] == "ep7.umi7_2.d51167")

        self.assertIn("p u e d o", e_call1["segments"][0]["text"])
        self.assertIn("ll amar", e_call2["segments"][0]["text"])
        self.assertEqual(e_pause["segments"][0]["text"], '"' + " " * 60 + '."')


if __name__ == "__main__":
    unittest.main()
