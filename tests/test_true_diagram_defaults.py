from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

import scripts.build_packages as builder


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LINTER = _load_module(
    "vibe_diagram_true_diagram_linter",
    SKILL_ROOT / "scripts" / "vibe_diagram_lint.py",
)
SCAFFOLD = _load_module(
    "vibe_diagram_true_diagram_scaffold",
    SKILL_ROOT / "scripts" / "vibe_diagram_scaffold.py",
)


class TrueDiagramDefaultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.routing = LINTER.load_template_routing()
        cls.linter_policy = LINTER.load_family_policies()
        cls.builder_policy = builder.load_family_policies(
            SKILL_ROOT / "contracts" / "family-policies.json"
        )
        cls.builder_routing = builder.load_template_routing(
            SKILL_ROOT / "contracts" / "template-routing.json"
        )

    def test_every_family_has_one_ready_default(self) -> None:
        catalog = LINTER.load_template_layouts()
        self.assertEqual(set(catalog), set(self.routing["families"]))
        for family, definition in self.routing["families"].items():
            with self.subTest(family=family):
                ready = set(definition["ready_templates"])
                blocked = set(definition["blocked_templates"])
                self.assertIn(definition["default_template"], ready)
                self.assertFalse(ready & blocked)
                self.assertEqual(set(catalog[family]), ready | blocked)

    def test_blocked_template_cannot_be_scaffolded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "blocked.html"
            with contextlib.redirect_stdout(io.StringIO()):
                result = SCAFFOLD.main(
                    [
                        "--type",
                        "business-flow",
                        "--template",
                        "bpmn-light-flow",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(1, result)
            self.assertFalse(output.exists())

    def test_named_external_standard_cannot_silently_use_native_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "strict-standard.html"
            with contextlib.redirect_stdout(io.StringIO()):
                result = SCAFFOLD.main(
                    [
                        "--type",
                        "business-flow",
                        "--template",
                        "logic-flowchart",
                        "--standard",
                        "BPMN",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(1, result)
            self.assertFalse(output.exists())

    def test_ready_generic_templates_use_geometric_relation_carriers(self) -> None:
        for family, routing in self.routing["families"].items():
            if family == "code-sequence":
                continue
            for template_id in routing["ready_templates"]:
                html = (TEMPLATE_ROOT / family / f"{template_id}.html").read_text(
                    encoding="utf-8"
                )
                with self.subTest(family=family, template=template_id):
                    self.assertEqual(
                        [],
                        LINTER.true_diagram_errors(
                            html,
                            family,
                            routing=self.routing,
                            policy=self.linter_policy,
                        ),
                    )
                    self.assertEqual(
                        [],
                        builder.true_diagram_errors(
                            html,
                            family,
                            template_id,
                            self.builder_routing,
                            self.builder_policy,
                        ),
                    )

    def test_html_relation_ledger_cannot_replace_a_ready_svg_route(self) -> None:
        family = "business-flow"
        template_id = "logic-flowchart"
        html = (TEMPLATE_ROOT / family / f"{template_id}.html").read_text(
            encoding="utf-8"
        )
        mutated = html.replace(
            'data-diagram-visible-relation-id="layout-relation-001"',
            'data-retired-visible-relation-id="layout-relation-001"',
            1,
        )
        results = (
            LINTER.true_diagram_errors(
                mutated,
                family,
                routing=self.routing,
                policy=self.linter_policy,
            ),
            builder.true_diagram_errors(
                mutated,
                family,
                template_id,
                self.builder_routing,
                self.builder_policy,
            ),
        )
        for errors in results:
            self.assertTrue(
                any("primary SVG path" in error for error in errors),
                errors,
            )

    def test_authored_semantic_attributes_are_structure_mutable(self) -> None:
        for attribute in (
            "data-reading-guide",
            "data-semantic-role",
            "data-relation-kind",
            "data-visible-relation-kind",
            "data-branch-outcome",
            "data-node-primary-label",
            "data-sequence-message-id",
            "data-sequence-detail",
            "data-sequence-detail-trigger",
            "data-sequence-lifeline-for",
        ):
            self.assertIn(attribute, LINTER.MUTABLE_STRUCTURE_ATTRIBUTES)

    def test_ready_sequence_has_one_arrow_lifeline_and_detail_per_object(self) -> None:
        html = (
            TEMPLATE_ROOT / "code-sequence" / "async-callback-sequence.html"
        ).read_text(encoding="utf-8")
        self.assertEqual([], LINTER.lint_sequence_visual_contract(html))
        self.assertEqual([], builder._sequence_visual_errors(html))

    def test_ready_sequence_visual_carriers_fail_closed(self) -> None:
        html = (
            TEMPLATE_ROOT / "code-sequence" / "async-callback-sequence.html"
        ).read_text(encoding="utf-8")
        mutations = (
            html.replace('<span class="seq-arrow"', '<span class="seq-arrow-removed"', 1),
            html.replace(
                "</style>",
                "[data-sequence-message]::before{content:'→'}</style>",
                1,
            ),
            html.replace(
                '<i data-sequence-lifeline-for="layout-participant-001"',
                '<i data-retired-lifeline-for="layout-participant-001"',
                1,
            ),
            html.replace(
                '<a class="sequence-object-trigger" data-sequence-detail-trigger',
                '<a class="sequence-object-trigger" data-retired-detail-trigger',
                1,
            ),
            html.replace(
                "[data-sequence-canvas] [data-participant-id] {",
                "[data-sequence-canvas] [data-retired-participant-id] {",
                1,
            ),
            html.replace(
                "background: var(--caption-fill);",
                "background: #fff;",
                1,
            ),
        )
        for index, mutated in enumerate(mutations, start=1):
            with self.subTest(mutation=index):
                self.assertTrue(LINTER.lint_sequence_visual_contract(mutated))
                self.assertTrue(builder._sequence_visual_errors(mutated))


if __name__ == "__main__":
    unittest.main()
