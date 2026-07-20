from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts import build_packages
from tests.test_cross_template_contracts import _load_linter


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
INTERACTION_PATH = ROOT / "contracts" / "interaction_contract_baseline.json"
MIGRATION_PATH = ROOT / "contracts" / "template_migration_baseline.json"
POLICY_PATH = SKILL_ROOT / "contracts" / "family-policies.json"
B01_TEMPLATES = (
    "business-flow/swimlane-flow.html",
    "decision-communication/option-matrix-path.html",
)


def _block(html: str, tag: str) -> str:
    matches = re.findall(
        rf'<{tag} data-adaptive-viewport-kernel="1">\n?(.*?)</{tag}>',
        html,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        raise AssertionError(f"expected one {tag} adaptive kernel, found {len(matches)}")
    return matches[0].rstrip("\n")


class GenericTemplateTests(unittest.TestCase):
    def test_b01_is_the_exact_first_generic_migration_batch(self) -> None:
        interaction = json.loads(INTERACTION_PATH.read_text(encoding="utf-8"))
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(["B00", "B01"], interaction["scope"]["completed_batches"])
        self.assertEqual(list(B01_TEMPLATES), interaction["scope"]["completed_templates"])
        self.assertEqual(list(B01_TEMPLATES), policy["migration_batches"]["B01"])
        self.assertEqual(policy["migration_batches"], migration["interaction_migration_batches"])

    def test_b01_templates_pass_independent_generic_contract_parsers(self) -> None:
        linter = _load_linter()
        policy = build_packages.load_family_policies(POLICY_PATH)
        for relative in B01_TEMPLATES:
            family, name = relative.split("/", 1)
            template_id = Path(name).stem
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertEqual([], linter.lint_generic_contract(html, family, template_id))
                self.assertEqual(
                    [],
                    build_packages.generic_contract_errors(
                        html, family, template_id, policy
                    ),
                )

    def test_b01_templates_embed_the_exact_adaptive_kernel(self) -> None:
        css = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.css"
        ).read_text(encoding="utf-8").rstrip("\n")
        script = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js"
        ).read_text(encoding="utf-8").rstrip("\n")
        for relative in B01_TEMPLATES:
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertEqual(css, _block(html, "style"))
                self.assertEqual(script, _block(html, "script"))

    def test_b01_migration_preserves_the_source_slot_macro_contract(self) -> None:
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        for relative in B01_TEMPLATES:
            entry = migration["templates"][relative]
            with self.subTest(relative=relative):
                self.assertNotEqual(entry["source"], entry["canonical"])
                for key in ("data_slots", "macros", "slot_macro_pairs"):
                    self.assertEqual(entry["source"][key], entry["canonical"][key])
                self.assertEqual(
                    "approved adaptive viewport and semantic relation migration",
                    entry["change_reason"],
                )

    def test_swimlane_poc_declares_sticky_lanes_relations_zoom_and_stack_fallback(self) -> None:
        html = (TEMPLATE_ROOT / B01_TEMPLATES[0]).read_text(encoding="utf-8")
        self.assertIn('data-diagram-mobile="stack"', html)
        self.assertEqual(3, html.count('data-semantic-role="lane"'))
        self.assertEqual(9, html.count('data-semantic-role="activity"'))
        self.assertEqual(8, html.count("data-diagram-relation-id="))
        self.assertRegex(html, r"position:\s*sticky")
        for value in ("fit", "0.75", "0.9", "1"):
            self.assertIn(f'data-diagram-zoom-control="{value}"', html)

    def test_matrix_poc_declares_axes_cells_relations_and_summary_fallback(self) -> None:
        html = (TEMPLATE_ROOT / B01_TEMPLATES[1]).read_text(encoding="utf-8")
        self.assertIn('data-diagram-profile="matrix"', html)
        self.assertIn('data-diagram-mobile="summary"', html)
        self.assertEqual(3, html.count("data-matrix-row-id="))
        self.assertEqual(3, html.count("data-matrix-col-id="))
        self.assertEqual(3, html.count("data-matrix-row="))
        self.assertIn('<table', html)
        self.assertIn('data-fallback-for="option-matrix"', html)

    def test_cli_fails_closed_for_a_migrated_generic_contract(self) -> None:
        linter = _load_linter()
        html = (TEMPLATE_ROOT / B01_TEMPLATES[0]).read_text(encoding="utf-8")
        html = html.replace(
            'data-diagram-canvas data-diagram-contract="1"',
            'data-diagram-canvas data-diagram-contract="2"',
            1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "swimlane-flow.html"
            path.write_text(html, encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = linter.main([str(path), "--type", "business-flow"])
        self.assertEqual(1, result, output.getvalue())
        self.assertIn("contract", output.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
