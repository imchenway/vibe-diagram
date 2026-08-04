from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"


def _load_linter():
    path = SKILL_ROOT / "scripts" / "vibe_diagram_lint.py"
    spec = importlib.util.spec_from_file_location("vibe_diagram_lint_v0110_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LINTER = _load_linter()


class V0110DrawingContractTest(unittest.TestCase):
    def test_markup_integrity_rejects_numeric_attributes_and_orphan_suffixes(self) -> None:
        errors = LINTER.lint_markup_integrity(
            '<main><div class="{{canvas-attribute-001}}" 17></div>'
            "<span>{{canvas-text-001}}42</span></main>"
        )
        self.assertTrue(any("Malformed numeric attribute" in error for error in errors))
        self.assertTrue(any("orphan numeric suffix" in error for error in errors))

    def test_markup_integrity_keeps_semantic_relation_carriers_outside_svg(self) -> None:
        invalid = (
            '<main><svg><path d="M0 0H10"></path>'
            '<span class="semantic-relation">关系</span>'
            '<path d="M10 0H20"></path></svg></main>'
        )
        errors = LINTER.lint_markup_integrity(invalid)
        self.assertTrue(
            any("must remain outside SVG" in error for error in errors)
        )
        self.assertEqual(
            [],
            LINTER.lint_markup_integrity(
                '<main><svg><path d="M0 0H10"></path></svg>'
                '<span class="semantic-relation">关系</span></main>'
            ),
        )

    def test_route_contract_enforces_bend_budgets_and_feedback_reason(self) -> None:
        valid = (
            '<svg><path d="M0 0H100" data-route-intent="direct" '
            'data-diagram-visible-relation-id="layout-relation-001"></path>'
            '<path d="M0 0H50V100" data-route-intent="branch" '
            'data-diagram-visible-relation-id="layout-relation-002"></path>'
            '<path d="M100 100V0" data-route-intent="feedback" '
            'data-route-reason="retry" '
            'data-diagram-visible-relation-id="layout-relation-003"></path></svg>'
        )
        self.assertEqual([], LINTER.lint_route_contract(valid))

        invalid = (
            '<svg><path d="M0 0H50V100" data-route-intent="direct" '
            'data-diagram-visible-relation-id="layout-relation-001"></path>'
            '<path d="M0 0H40V50H100" data-route-intent="merge" '
            'data-diagram-visible-relation-id="layout-relation-002"></path>'
            '<path d="M100 100V0" data-route-intent="feedback" '
            'data-diagram-visible-relation-id="layout-relation-003"></path></svg>'
        )
        errors = LINTER.lint_route_contract(invalid)
        self.assertTrue(any("zero bends" in error for error in errors))
        self.assertTrue(any("at most one bend" in error for error in errors))
        self.assertTrue(any("data-route-reason" in error for error in errors))

    def test_every_template_uses_the_global_zoom_order_and_short_guide(self) -> None:
        expected = ["0.75", "0.9", "1", "fit"]
        for path in sorted(TEMPLATE_ROOT.glob("*/*.html")):
            html = path.read_text(encoding="utf-8")
            modes = re.findall(r'data-diagram-zoom-control="([^"]+)"', html)
            if not modes:
                modes = re.findall(r'data-sequence-scale="([^"]+)"', html)
            with self.subTest(path=path.relative_to(TEMPLATE_ROOT)):
                self.assertGreaterEqual(len(modes), 4)
                self.assertEqual(0, len(modes) % 4)
                for index in range(0, len(modes), 4):
                    self.assertEqual(expected, modes[index : index + 4])
                self.assertNotIn("How to read this artifact", html)
                self.assertNotIn("如何阅读本图", html)

    def test_every_template_stacks_evidence_below_relations_with_strong_titles(
        self,
    ) -> None:
        for path in sorted(TEMPLATE_ROOT.glob("*/*.html")):
            html = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(TEMPLATE_ROOT)):
                self.assertIn(
                    'grid-template-areas:\n    "relations"\n    "evidence";',
                    html,
                )
                self.assertIn(
                    '[data-reading-guide-group="relations"] {\n'
                    "  grid-area: relations;\n"
                    "}",
                    html,
                )
                self.assertIn(
                    '[data-reading-guide-group="evidence"] {\n'
                    "  grid-area: evidence;\n"
                    "}",
                    html,
                )
                self.assertIn(
                    "[data-reading-guide-groups] [data-reading-guide-group-title]",
                    html,
                )

    def test_progressive_disclosure_supports_positioning_and_keyboard_close(self) -> None:
        runtime = (
            SKILL_ROOT / "assets" / "contracts" / "progressive-disclosure" / "v1.js"
        ).read_text(encoding="utf-8")
        for token in (
            "getBoundingClientRect",
            "popupSide",
            'event.key === "Escape"',
            "pointerdown",
            "preventScroll",
            "hashchange",
            "auditLifecycle",
            "detailLifecycleAudit",
            "runtimeDetailPortal",
        ):
            self.assertIn(token, runtime)

    def test_north_to_south_mobile_scroll_starts_on_the_primary_axis(self) -> None:
        runtime = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js"
        ).read_text(encoding="utf-8")
        for token in (
            "autoCentered",
            'canvas.dataset.primaryDirection === "north-to-south"',
            "canvas.scrollLeft",
            "(stage.scrollWidth - canvas.clientWidth) / 2",
        ):
            self.assertIn(token, runtime)

    def test_business_flow_defaults_share_the_north_to_south_core(self) -> None:
        for template_id, topology in (
            ("logic-flowchart", "decision-branch-merge"),
            ("exception-branch-flow", "exception-compensation-rejoin"),
        ):
            html = (
                TEMPLATE_ROOT / "business-flow" / f"{template_id}.html"
            ).read_text(encoding="utf-8")
            with self.subTest(template_id=template_id):
                self.assertIn('data-primary-direction="north-to-south"', html)
                self.assertIn(f'data-diagram-topology="{topology}"', html)
                self.assertEqual(2, html.count('data-route-intent="merge"'))
                self.assertIn('data-route-intent="feedback"', html)
                self.assertIn("data-route-reason=", html)

    def test_sequence_visual_uses_lifelines_without_plus_minus_controls(self) -> None:
        css = (
            SKILL_ROOT / "assets" / "contracts" / "sequence-visual" / "v1.css"
        ).read_text(encoding="utf-8")
        html = (
            TEMPLATE_ROOT / "code-sequence" / "async-callback-sequence.html"
        ).read_text(encoding="utf-8")
        self.assertIn("border-top: 2px dashed", css)
        self.assertIn("content: none !important", css)
        self.assertIn("--caption-fill:", css)
        self.assertIn("background: var(--caption-fill)", css)
        self.assertRegex(
            css,
            r"\[data-sequence-canvas\]\s+\[data-participant-id\][^{]*\{[^}]*"
            r"background:\s*color-mix",
        )
        self.assertNotRegex(css, r'content:\s*["\'][+-]["\']')
        self.assertIn('data-sequence-fragment-kind="alt"', html)
        self.assertEqual(
            4, len(re.findall(r"<i\b[^>]*data-sequence-lifeline-for=", html))
        )

    def test_table_copy_uses_cell_fit_instead_of_a_prose_slot_budget(self) -> None:
        html = (
            '<section class="template-layout"><section data-slot="layout-slot-001">'
            "<table><tbody><tr><td>一条真实业务记录中的条码</td>"
            "<td>一条真实业务记录中的库位</td><td>等待人工处理</td></tr></tbody></table>"
            "</section></section>"
        )
        self.assertEqual([], LINTER.lint_primary_canvas_budget(html))

    def test_form_placeholder_is_authored_content_not_dom_structure(self) -> None:
        canonical = '<main><input type="search" placeholder="{{canvas-attribute-001}}"></main>'
        artifact = '<main><input type="search" placeholder="搜索条码或库位"></main>'
        self.assertEqual(
            LINTER._structure_signature(canonical),
            LINTER._structure_signature(artifact),
        )

    def test_graph_level_titles_require_type_separator_and_subject(self) -> None:
        valid = (
            '<h2 data-diagram-view-title="1">'
            '<span data-diagram-view-type>时序图</span>'
            '<span data-diagram-view-separator aria-hidden="true"></span>'
            '<span data-diagram-view-subject>附件解析主链路</span>'
            "</h2>"
        )
        self.assertEqual([], LINTER.lint_diagram_view_title_contract(valid))
        for invalid in (
            valid.replace(" data-diagram-view-separator", ""),
            valid.replace(" data-diagram-view-type", ""),
            valid.replace(" data-diagram-view-subject", ""),
        ):
            self.assertTrue(LINTER.lint_diagram_view_title_contract(invalid))

if __name__ == "__main__":
    unittest.main()
