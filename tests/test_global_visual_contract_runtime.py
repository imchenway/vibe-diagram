from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "skills" / "vibe-diagram" / "assets" / "contracts"
ARTIFACT_SHELL_ROOT = CONTRACT_ROOT / "artifact-shell"
SEMANTIC_RELATIONS_ROOT = CONTRACT_ROOT / "semantic-relations"


class GlobalVisualContractRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_path = ARTIFACT_SHELL_ROOT / "v1.js"
        cls.shell_style_path = ARTIFACT_SHELL_ROOT / "v1.css"
        cls.relation_style_path = SEMANTIC_RELATIONS_ROOT / "v1.css"
        cls.runtime = cls.runtime_path.read_text(encoding="utf-8")
        cls.shell_style = cls.shell_style_path.read_text(encoding="utf-8")
        cls.relation_style = cls.relation_style_path.read_text(encoding="utf-8")

    def test_relation_ledger_is_secondary_and_has_no_primary_arrow_carrier(self) -> None:
        self.assertIn("border-block-start: 1px dashed", self.relation_style)
        self.assertIn("background: transparent", self.relation_style)
        self.assertIn('content: "↪"', self.relation_style)
        self.assertIn("content: none", self.relation_style)
        route_indicator = re.search(
            r"\[data-semantic-edge-route\] i\s*\{(?P<body>.*?)\}",
            self.relation_style,
            re.DOTALL,
        )
        self.assertIsNotNone(route_indicator)
        assert route_indicator is not None
        self.assertNotIn("background:", route_indicator.group("body"))

    def test_declared_relations_require_rendered_geometric_carriers(self) -> None:
        for token in (
            'const declaredRelationSelector = "[data-diagram-relation-id]"',
            "svg path[data-diagram-visible-relation-id]",
            "svg line[data-diagram-visible-relation-id]",
            "svg polyline[data-diagram-visible-relation-id]",
            "svg polygon[data-diagram-visible-relation-id]",
            ".filter(isRendered)",
            'addIssue("missing-geometric-carrier", relationId)',
            'addIssue("declared-route-not-audited", relationId)',
        ):
            self.assertIn(token, self.runtime)
        self.assertIn(
            "primaryStage.querySelectorAll(geometricCarrierSelector)",
            self.runtime,
        )
        self.assertNotIn(
            "canvas.querySelectorAll(geometricCarrierSelector)",
            self.runtime,
        )

    def test_hidden_primary_stage_requires_one_equivalent_fallback_per_relation(self) -> None:
        for token in (
            'const fallbackCarrierSelector = [',
            '"[data-fallback-relation-id]"',
            "'[data-visible-relation-kind=\"edge\"][data-diagram-visible-relation-id]'",
            'canvas.querySelector(":scope > [data-diagram-stage]") || canvas',
            "if (!isRendered(primaryStage))",
            "fallbackRoot && isRendered(fallbackRoot)",
            "fallbackRoot.querySelectorAll(fallbackCarrierSelector)",
            "carrier.dataset.fallbackRelationId",
            'addIssue("fallback-relation-duplicate", relationId)',
            'addIssue("fallback-relation-not-declared", relationId)',
            'addIssue("fallback-relation-not-equivalent", relationId)',
        ):
            self.assertIn(token, self.runtime)
        hidden_branch = self.runtime[
            self.runtime.index("if (!isRendered(primaryStage))"):
            self.runtime.index(
                "const carriers = Array.from(primaryStage.querySelectorAll",
            )
        ]
        self.assertIn("return;", hidden_branch)
        self.assertNotIn("geometricCarrierSelector", hidden_branch)

    def test_visible_architecture_landmarks_override_semantic_node_rects(self) -> None:
        for token in (
            'canvas.querySelectorAll("[data-architecture-landmark-for]")',
            "landmark.dataset.architectureLandmarkFor",
            "nodeRects.set(nodeId, (surface || landmark).getBoundingClientRect())",
            'landmark.querySelectorAll("text, foreignObject")',
            'addIssue("node-content-overflow", nodeId || "unnamed-landmark")',
        ):
            self.assertIn(token, self.runtime)
        self.assertLess(
            self.runtime.index(
                "nodeRects.set(nodeId, (surface || landmark).getBoundingClientRect())"
            ),
            self.runtime.index(
                'const labels = Array.from(canvas.querySelectorAll("svg text"))'
            ),
        )

    def test_every_rendered_diagram_node_is_checked_for_content_overflow(self) -> None:
        for token in (
            'canvas.querySelectorAll("[data-diagram-node-id]")',
            'node.querySelectorAll("*")',
            'node.querySelectorAll("text, foreignObject")',
            "escapesBounds(surfaceRect, contentRect, 2)",
            'addIssue("node-content-overflow", nodeId)',
        ):
            self.assertIn(token, self.runtime)

    def test_svg_details_auxiliary_fill_and_empty_triggers_fail_closed(self) -> None:
        for token in (
            'const detailTriggerSelector = "[data-diagram-detail-trigger]"',
            'localNameOf(trigger) !== "a"',
            '"detail-trigger-target-empty"',
            'addIssue("detail-trigger-empty", detailId)',
            'trigger.querySelector("rect, path, polygon, circle, ellipse")',
            "surfaceStyle.fill",
        ):
            self.assertIn(token, self.runtime)

    def test_native_detail_links_open_and_reflect_their_details_target(self) -> None:
        for token in (
            "const enhanceDetailLinks = () =>",
            "detail.open = true",
            'detail.addEventListener("toggle"',
            'trigger.setAttribute("aria-expanded"',
            "enhanceDetailLinks();",
        ):
            self.assertIn(token, self.runtime)

    def test_hidden_controls_do_not_reserve_a_reading_guide_column(self) -> None:
        for token in (
            '[data-reading-guide-controls][data-interaction-capability="none"]',
            "display: none",
            '[data-diagram-reading-guide="1"][data-reading-guide-controls-state="empty"]',
            "grid-template-columns: minmax(0, 1fr)",
        ):
            self.assertIn(token, self.shell_style)
        for token in (
            "reflectReadingGuideCapability",
            "data-reading-guide-controls",
            "guide.dataset.readingGuideControlsState",
            "controlRegion.dataset.interactionCapability",
        ):
            self.assertIn(token, self.runtime)

    def test_runtime_javascript_has_valid_syntax(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node is unavailable")
        completed = subprocess.run(
            [node, "--check", str(self.runtime_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
