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
B02_TEMPLATES = (
    "business-flow/bpmn-light-flow.html",
    "business-flow/exception-branch-flow.html",
    "business-flow/stage-track.html",
)
B03_TEMPLATES = (
    "state-data-model/data-flow-model.html",
    "state-data-model/er-lite.html",
    "state-data-model/lifecycle-track.html",
    "state-data-model/state-event-matrix.html",
    "state-data-model/state-machine.html",
)
B04_TEMPLATES = (
    "business-architecture/capability-domain-map.html",
    "business-architecture/participant-boundary.html",
    "business-architecture/rule-constraint-heatmap.html",
    "business-architecture/value-chain-map.html",
)
B05_TEMPLATES = (
    "technical-design/api-contract-swimlane.html",
    "technical-design/data-consistency-boundary.html",
    "technical-design/module-contract-data-topology.html",
    "technical-design/release-switch-track.html",
)
B06_TEMPLATES = (
    "fault-debugging/before-after-flow.html",
    "fault-debugging/bpmn-debug-flow.html",
    "fault-debugging/causal-chain.html",
    "fault-debugging/state-data-breakpoint.html",
)
B07_TEMPLATES = (
    "feature-iteration/current-target-flow.html",
    "feature-iteration/diff-heatmap.html",
    "feature-iteration/release-rollback-track.html",
)
B08_TEMPLATES = (
    "decision-communication/decision-tree.html",
    "decision-communication/recommended-path.html",
    "decision-communication/tradeoff-quadrant.html",
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
        self.assertEqual(
            ["B00", "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08"],
            interaction["scope"]["completed_batches"],
        )
        self.assertEqual(
            sorted(
                (
                    *B01_TEMPLATES,
                    *B02_TEMPLATES,
                    *B03_TEMPLATES,
                    *B04_TEMPLATES,
                    *B05_TEMPLATES,
                    *B06_TEMPLATES,
                    *B07_TEMPLATES,
                    *B08_TEMPLATES,
                )
            ),
            interaction["scope"]["completed_templates"],
        )
        self.assertEqual(list(B01_TEMPLATES), policy["migration_batches"]["B01"])
        self.assertEqual(policy["migration_batches"], migration["interaction_migration_batches"])

    def test_b02_is_the_exact_business_flow_family_closure(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(B02_TEMPLATES), policy["migration_batches"]["B02"])
        completed = {
            relative
            for batch in policy["migration_batches"].values()
            for relative in batch
            if relative.startswith("business-flow/")
        }
        expected = {
            path.relative_to(TEMPLATE_ROOT).as_posix()
            for path in (TEMPLATE_ROOT / "business-flow").glob("*.html")
        }
        self.assertEqual(expected, completed)

    def test_b02_templates_pass_parsers_and_embed_the_exact_kernel(self) -> None:
        linter = _load_linter()
        policy = build_packages.load_family_policies(POLICY_PATH)
        css = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.css"
        ).read_text(encoding="utf-8").rstrip("\n")
        script = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js"
        ).read_text(encoding="utf-8").rstrip("\n")
        for relative in B02_TEMPLATES:
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
                self.assertEqual(css, _block(html, "style"))
                self.assertEqual(script, _block(html, "script"))

    def test_b02_preserves_slots_and_declares_meaningful_flow_semantics(self) -> None:
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        minimums = {
            B02_TEMPLATES[0]: (5, 4, "graph"),
            B02_TEMPLATES[1]: (8, 7, "graph"),
            B02_TEMPLATES[2]: (9, 8, "timeline"),
        }
        for relative, (nodes, relations, profile) in minimums.items():
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            entry = migration["templates"][relative]
            with self.subTest(relative=relative):
                self.assertIn(f'data-diagram-profile="{profile}"', html)
                self.assertEqual(nodes, html.count("data-diagram-node-id="))
                self.assertGreaterEqual(html.count("data-diagram-relation-id="), relations)
                self.assertIn("data-reading-guide", html)
                self.assertIn("data-fallback-for=", html)
                for key in ("data_slots", "macros", "slot_macro_pairs"):
                    self.assertEqual(entry["source"][key], entry["canonical"][key])

    def test_b03_closes_state_data_model_with_profile_specific_semantics(self) -> None:
        policy_data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(B03_TEMPLATES), policy_data["migration_batches"]["B03"])
        expected = {
            path.relative_to(TEMPLATE_ROOT).as_posix()
            for path in (TEMPLATE_ROOT / "state-data-model").glob("*.html")
        }
        self.assertEqual(expected, set(B03_TEMPLATES))
        minimums = {
            B03_TEMPLATES[0]: (8, 7, "graph"),
            B03_TEMPLATES[1]: (12, 9, "graph"),
            B03_TEMPLATES[2]: (10, 9, "timeline"),
            B03_TEMPLATES[3]: (15, 9, "matrix"),
            B03_TEMPLATES[4]: (5, 4, "graph"),
        }
        for relative, (nodes, relations, profile) in minimums.items():
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            entry = migration["templates"][relative]
            with self.subTest(relative=relative):
                self.assertIn(f'data-diagram-profile="{profile}"', html)
                self.assertEqual(nodes, html.count("data-diagram-node-id="))
                self.assertGreaterEqual(html.count("data-diagram-relation-id="), relations)
                self.assertIn("data-reading-guide", html)
                self.assertIn("data-fallback-for=", html)
                for key in ("data_slots", "macros", "slot_macro_pairs"):
                    self.assertEqual(entry["source"][key], entry["canonical"][key])
        matrix = (TEMPLATE_ROOT / B03_TEMPLATES[3]).read_text(encoding="utf-8")
        self.assertEqual(3, matrix.count("data-matrix-row-id="))
        self.assertEqual(3, matrix.count("data-matrix-col-id="))
        self.assertEqual(9, matrix.count("data-matrix-row="))

    def test_b03_templates_pass_both_parsers_and_embed_shared_kernel(self) -> None:
        linter = _load_linter()
        policy = build_packages.load_family_policies(POLICY_PATH)
        css = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.css"
        ).read_text(encoding="utf-8").rstrip("\n")
        script = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js"
        ).read_text(encoding="utf-8").rstrip("\n")
        for relative in B03_TEMPLATES:
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
                self.assertEqual(css, _block(html, "style"))
                self.assertEqual(script, _block(html, "script"))

    def test_b04_closes_business_architecture_without_flattening_its_grammars(self) -> None:
        policy_data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(B04_TEMPLATES), policy_data["migration_batches"]["B04"])
        expected = {
            path.relative_to(TEMPLATE_ROOT).as_posix()
            for path in (TEMPLATE_ROOT / "business-architecture").glob("*.html")
        }
        self.assertEqual(expected, set(B04_TEMPLATES))
        minimums = {
            B04_TEMPLATES[0]: (11, 10, "graph"),
            B04_TEMPLATES[1]: (7, 6, "graph"),
            B04_TEMPLATES[2]: (12, 9, "matrix"),
            B04_TEMPLATES[3]: (8, 8, "graph"),
        }
        for relative, (nodes, relations, profile) in minimums.items():
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            entry = migration["templates"][relative]
            with self.subTest(relative=relative):
                self.assertIn(f'data-diagram-profile="{profile}"', html)
                self.assertEqual(nodes, html.count("data-diagram-node-id="))
                self.assertGreaterEqual(html.count("data-diagram-relation-id="), relations)
                self.assertIn("data-reading-guide", html)
                self.assertIn("data-fallback-for=", html)
                for key in ("data_slots", "macros", "slot_macro_pairs"):
                    self.assertEqual(entry["source"][key], entry["canonical"][key])
        heatmap = (TEMPLATE_ROOT / B04_TEMPLATES[2]).read_text(encoding="utf-8")
        self.assertEqual(3, heatmap.count("data-matrix-row-id="))
        self.assertEqual(3, heatmap.count("data-matrix-col-id="))
        self.assertEqual(9, heatmap.count("data-matrix-row="))

    def test_b04_templates_pass_both_parsers_and_embed_shared_kernel(self) -> None:
        linter = _load_linter()
        policy = build_packages.load_family_policies(POLICY_PATH)
        css = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.css"
        ).read_text(encoding="utf-8").rstrip("\n")
        script = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js"
        ).read_text(encoding="utf-8").rstrip("\n")
        for relative in B04_TEMPLATES:
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
                self.assertEqual(css, _block(html, "style"))
                self.assertEqual(script, _block(html, "script"))

    def test_b05_closes_technical_design_with_endpoints_and_exact_kernel(self) -> None:
        policy_data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(B05_TEMPLATES), policy_data["migration_batches"]["B05"])
        expected = {
            path.relative_to(TEMPLATE_ROOT).as_posix()
            for path in (TEMPLATE_ROOT / "technical-design").glob("*.html")
        }
        self.assertEqual(expected, set(B05_TEMPLATES))
        minimums = {
            B05_TEMPLATES[0]: (16, 15, "graph"),
            B05_TEMPLATES[1]: (8, 8, "graph"),
            B05_TEMPLATES[2]: (7, 7, "graph"),
            B05_TEMPLATES[3]: (7, 7, "timeline"),
        }
        linter = _load_linter()
        policy = build_packages.load_family_policies(POLICY_PATH)
        css = (SKILL_ROOT / "assets/contracts/adaptive-viewport/v1.css").read_text(encoding="utf-8").rstrip("\n")
        script = (SKILL_ROOT / "assets/contracts/adaptive-viewport/v1.js").read_text(encoding="utf-8").rstrip("\n")
        for relative, (nodes, relations, profile) in minimums.items():
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            entry = migration["templates"][relative]
            family, name = relative.split("/", 1)
            with self.subTest(relative=relative):
                self.assertEqual([], linter.lint_generic_contract(html, family, Path(name).stem))
                self.assertEqual([], build_packages.generic_contract_errors(html, family, Path(name).stem, policy))
                self.assertEqual(nodes, html.count("data-diagram-node-id="))
                self.assertGreaterEqual(html.count("data-diagram-relation-id="), relations)
                self.assertIn(f'data-diagram-profile="{profile}"', html)
                self.assertIn("data-reading-guide", html)
                self.assertIn("data-fallback-for=", html)
                self.assertEqual(css, _block(html, "style"))
                self.assertEqual(script, _block(html, "script"))
                for key in ("data_slots", "macros", "slot_macro_pairs"):
                    self.assertEqual(entry["source"][key], entry["canonical"][key])

    def test_b06_closes_only_non_sequence_fault_debugging_templates(self) -> None:
        policy_data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(B06_TEMPLATES), policy_data["migration_batches"]["B06"])
        self.assertNotIn("fault-debugging/debugging-sequence.html", B06_TEMPLATES)
        minimums = {B06_TEMPLATES[0]:(8,7,"graph"),B06_TEMPLATES[1]:(5,4,"graph"),B06_TEMPLATES[2]:(5,4,"graph"),B06_TEMPLATES[3]:(7,6,"matrix")}
        self._assert_completed_generic_batch(B06_TEMPLATES, minimums)

    def test_b07_closes_only_non_sequence_feature_iteration_templates(self) -> None:
        policy_data=json.loads(POLICY_PATH.read_text(encoding="utf-8")); self.assertEqual(list(B07_TEMPLATES),policy_data["migration_batches"]["B07"]); self.assertNotIn("feature-iteration/current-target-sequence.html",B07_TEMPLATES)
        self._assert_completed_generic_batch(B07_TEMPLATES,{B07_TEMPLATES[0]:(8,7,"graph"),B07_TEMPLATES[1]:(9,8,"matrix"),B07_TEMPLATES[2]:(8,7,"timeline")})

    def test_b08_closes_remaining_decision_communication_templates(self) -> None:
        policy_data=json.loads(POLICY_PATH.read_text(encoding="utf-8"));self.assertEqual(list(B08_TEMPLATES),policy_data["migration_batches"]["B08"])
        self._assert_completed_generic_batch(B08_TEMPLATES,{B08_TEMPLATES[0]:(8,7,"graph"),B08_TEMPLATES[1]:(7,6,"graph"),B08_TEMPLATES[2]:(4,3,"matrix")})

    def _assert_completed_generic_batch(self, templates, minimums) -> None:
        migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))
        linter = _load_linter(); policy = build_packages.load_family_policies(POLICY_PATH)
        css = (SKILL_ROOT / "assets/contracts/adaptive-viewport/v1.css").read_text(encoding="utf-8").rstrip("\n")
        script = (SKILL_ROOT / "assets/contracts/adaptive-viewport/v1.js").read_text(encoding="utf-8").rstrip("\n")
        for relative in templates:
            nodes, relations, profile = minimums[relative]; html=(TEMPLATE_ROOT/relative).read_text(encoding="utf-8"); family,name=relative.split("/",1); entry=migration["templates"][relative]
            with self.subTest(relative=relative):
                self.assertEqual([],linter.lint_generic_contract(html,family,Path(name).stem)); self.assertEqual([],build_packages.generic_contract_errors(html,family,Path(name).stem,policy))
                self.assertEqual(nodes,html.count("data-diagram-node-id=")); self.assertGreaterEqual(html.count("data-diagram-relation-id="),relations); self.assertIn(f'data-diagram-profile="{profile}"',html)
                self.assertIn("data-reading-guide",html); self.assertIn("data-fallback-for=",html); self.assertEqual(css,_block(html,"style")); self.assertEqual(script,_block(html,"script"))
                for key in ("data_slots","macros","slot_macro_pairs"): self.assertEqual(entry["source"][key],entry["canonical"][key])

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
