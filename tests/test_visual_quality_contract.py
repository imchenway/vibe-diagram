from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import scripts.build_packages as builder


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates" / "system-architecture"


def _load_linter():
    path = SKILL_ROOT / "scripts" / "vibe_diagram_lint.py"
    spec = importlib.util.spec_from_file_location("vibe_diagram_lint_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LINTER = _load_linter()


class VisualQualityContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        policy_path = SKILL_ROOT / "contracts" / "family-policies.json"
        cls.builder_policy = builder.load_family_policies(policy_path)
        cls.linter_policy = LINTER.load_family_policies(policy_path)
        cls.workload = (TEMPLATE_ROOT / "workload-overview.html").read_text(
            encoding="utf-8"
        )
        cls.layering = (TEMPLATE_ROOT / "logical-layering.html").read_text(
            encoding="utf-8"
        )

    def assert_rejected_by_both(
        self,
        html: str,
        template_id: str,
        expected_fragment: str,
    ) -> None:
        results = (
            builder.generic_contract_errors(
                html,
                "system-architecture",
                template_id,
                self.builder_policy,
            ),
            LINTER.generic_contract_errors(
                html,
                "system-architecture",
                template_id,
                self.linter_policy,
            ),
        )
        for errors in results:
            self.assertTrue(
                any(expected_fragment in error for error in errors),
                f"{expected_fragment!r} not found in {errors!r}",
            )

    def test_rich_architecture_templates_satisfy_quality_contract(self) -> None:
        for template_id, html in (
            ("workload-overview", self.workload),
            ("logical-layering", self.layering),
        ):
            with self.subTest(template_id=template_id):
                self.assertEqual(
                    [],
                    builder.generic_contract_errors(
                        html,
                        "system-architecture",
                        template_id,
                        self.builder_policy,
                    ),
                )
                self.assertEqual(
                    [],
                    LINTER.generic_contract_errors(
                        html,
                        "system-architecture",
                        template_id,
                        self.linter_policy,
                    ),
                )

    def test_missing_node_icon_fails_closed(self) -> None:
        mutated = self.workload.replace(" data-node-icon", "", 1)
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "requires exactly one icon marker",
        )

    def test_non_emoji_node_icon_fails_closed_after_filling(self) -> None:
        mutated = self.workload.replace("{{canvas-text-011}}", "A", 1)
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "must resolve to an emoji",
        )

    def test_auxiliary_node_must_remain_a_native_detail_link(self) -> None:
        mutated = self.workload.replace(
            '<a class="module-chip" data-diagram-detail-trigger="auxiliary"',
            '<span class="module-chip" data-diagram-detail-trigger="auxiliary"',
            1,
        )
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "must remain a native link",
        )

    def test_orphan_auxiliary_detail_fails_closed(self) -> None:
        mutated = self.workload.replace(
            'data-diagram-detail="layout-detail-013"',
            'data-diagram-detail="layout-detail-999"',
            1,
        )
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "Auxiliary node links and native detail blocks",
        )

    def test_overlapping_primary_nodes_fail_closed(self) -> None:
        mutated = self.workload.replace(
            '<rect class="arch-node node-observed layout-tone-02" x="320" y="338"',
            '<rect class="arch-node node-observed layout-tone-02" x="320" y="250"',
            1,
        )
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "Diagram nodes must not overlap",
        )

    def test_short_relation_and_bad_arrowhead_fail_closed(self) -> None:
        short_relation = self.workload.replace(
            'd="M784 300V338"',
            'd="M784 300V310"',
            1,
        )
        self.assert_rejected_by_both(
            short_relation,
            "workload-overview",
            "shorter than the readable minimum",
        )
        missing_marker = self.workload.replace(
            ' marker-end="url(#workload-arrow-blue)" '
            'data-diagram-visible-relation-id="layout-relation-002"',
            ' data-diagram-visible-relation-id="layout-relation-002"',
            1,
        )
        self.assert_rejected_by_both(
            missing_marker,
            "workload-overview",
            "requires a resolvable SVG arrowhead marker",
        )

    def test_relation_route_crossing_an_unrelated_node_fails_closed(self) -> None:
        mutated = self.workload.replace(
            'd="M1248 400H1360"',
            'd="M1248 400V600H1500V300H1360"',
            1,
        )
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "Relation route must not cross diagram node layout-node-007",
        )

    def test_canvas_utilization_threshold_is_policy_owned(self) -> None:
        mutated = self.workload.replace(
            'data-max-top-whitespace-ratio="0.02"',
            'data-max-top-whitespace-ratio="0.20"',
            1,
        )
        self.assert_rejected_by_both(
            mutated,
            "workload-overview",
            "runtime threshold data-max-top-whitespace-ratio must match policy",
        )

    def test_artifact_shell_uses_screenshot_free_computed_audit(self) -> None:
        runtime = (
            SKILL_ROOT / "assets" / "contracts" / "artifact-shell" / "v1.js"
        ).read_text(encoding="utf-8")
        for token in (
            "VibeDiagramQuality",
            "data-computed-layout-audit",
            "route-crosses-node",
            "route-target-not-anchored",
            "ResizeObserver",
        ):
            self.assertIn(token, runtime)
        for rejected_mechanism in ("toDataURL(", "html2canvas", "pixelmatch"):
            self.assertNotIn(rejected_mechanism, runtime)


if __name__ == "__main__":
    unittest.main()
