from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tests.template_contract import (
    file_sha256,
    template_slots_macros_and_pairs,
    template_structure_signature,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "skills" / "vibe-diagram" / "scripts" / "vibe_diagram_lint.py"
TEMPLATE_PATH = (
    ROOT
    / "skills"
    / "vibe-diagram"
    / "assets"
    / "templates"
    / "code-sequence"
    / "participant-timeline.html"
)
TEMPLATE_ROOT = ROOT / "skills" / "vibe-diagram" / "assets" / "templates"
SEQUENCE_TEMPLATE_PATHS = (
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
    "feature-iteration/current-target-sequence.html",
)
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
INTERACTION_FIXTURE = FIXTURE_ROOT / "sequence-interaction-matrix.html"
NO_JS_FIXTURE = FIXTURE_ROOT / "sequence-no-js.html"
COMPLEX_FIXTURE = FIXTURE_ROOT / "sequence-complex-overview-detail.html"
CONTRACT_PATH = ROOT / "contracts" / "template_migration_baseline.json"
RELATIVE_TEMPLATE_PATH = "code-sequence/participant-timeline.html"
CHANGE_REASON = "approved sequence interaction kernel and structured endpoint redesign"


def _load_linter():
    spec = importlib.util.spec_from_file_location("sequence_template_linter", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not create linter import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _SurfaceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: List[Tuple[str, Dict[str, str]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: List[Tuple[str, Optional[str]]],
    ) -> None:
        self.elements.append((tag, {name: value or "" for name, value in attrs}))

    def with_attribute(self, attribute: str) -> List[Tuple[str, Dict[str, str]]]:
        return [(tag, attrs) for tag, attrs in self.elements if attribute in attrs]


def _canonical_snapshot(path: Path, html: str) -> dict:
    slots, macros, pairs = template_slots_macros_and_pairs(html)
    return {
        "file_sha256": file_sha256(path),
        "structure_sha256": template_structure_signature(html),
        "data_slots": slots,
        "macros": macros,
        "slot_macro_pairs": pairs,
    }


def _raw_kernel_blocks(html: str) -> Tuple[str, str]:
    style = re.findall(
        r'<style\s+data-sequence-kernel="1">.*?</style>',
        html,
        re.DOTALL,
    )
    script = re.findall(
        r'<script\s+data-sequence-kernel="1">.*?</script>',
        html,
        re.DOTALL,
    )
    if len(style) != 1 or len(script) != 1:
        raise AssertionError("expected exactly one v1 style and script kernel block")
    return style[0], script[0]


class SequenceTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.linter = _load_linter()

    def test_participant_timeline_declares_sequence_contract_v1(self) -> None:
        self.assertEqual("1", self.linter.SEQUENCE_CONTRACT_VERSION)
        canvases = self.linter.parse_sequence_canvases(self.html)
        self.assertEqual(1, len(canvases))
        canvas = canvases[0]
        self.assertEqual("participant-main", canvas.canvas_id)
        self.assertEqual("standalone", canvas.role)
        self.assertEqual("", canvas.detail_for)
        self.assertIn('data-sequence-contract="1"', self.html)
        self.assertIn('data-sequence-width="auto"', self.html)
        self.assertIn('data-sequence-height="auto"', self.html)

    def test_participant_timeline_has_unique_participants_and_valid_endpoints(self) -> None:
        self.assertEqual([], self.linter.lint_sequence_contract(self.html))
        canvas = self.linter.parse_sequence_canvases(self.html)[0]
        self.assertEqual(len(canvas.participant_ids), len(set(canvas.participant_ids)))
        self.assertGreaterEqual(len(canvas.participant_ids), 2)
        self.assertGreaterEqual(len(canvas.messages), 1)
        participants = set(canvas.participant_ids)
        for source, target, kind, semantic in canvas.messages:
            self.assertIn(source, participants)
            self.assertIn(target, participants)
            self.assertIn(kind, self.linter.SEQUENCE_MESSAGE_KINDS)
            self.assertTrue(semantic)

    def test_participant_timeline_baseline_is_readable_without_enhancement(self) -> None:
        parser = _SurfaceParser()
        parser.feed(self.html)
        parser.close()
        toolbars = parser.with_attribute("data-sequence-toolbar")
        self.assertEqual(1, len(toolbars))
        self.assertIn("hidden", toolbars[0][1])
        messages = parser.with_attribute("data-sequence-message")
        self.assertGreaterEqual(len(messages), 1)
        self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-route")))
        self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-kind")))
        self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-description")))
        canvases = parser.with_attribute("data-sequence-canvas")
        self.assertEqual(1, len(canvases))
        self.assertNotIn("data-enhanced", canvases[0][1])

    def test_participant_timeline_has_adaptive_width_height_and_print_contract(self) -> None:
        self.assertEqual(1, len(re.findall(r'<style\s+data-sequence-kernel="1">', self.html)))
        self.assertEqual(1, len(re.findall(r'<script\s+data-sequence-kernel="1">', self.html)))
        for function_name in (
            "initSequenceCanvas",
            "measureSequenceCanvas",
            "applySequenceScale",
            "preserveSequenceAnchor",
        ):
            match = re.search(
                rf"function\s+{function_name}\s*\([^)]*\)\s*\{{(?P<body>.*?)\n\s*\}}",
                self.html,
                re.DOTALL,
            )
            self.assertIsNotNone(match, function_name)
            self.assertGreater(len(match.group("body").strip()), 24, function_name)
        for required in (
            "--sequence-lane-min",
            "--sequence-min-readable-font: 16px",
            "font-size: max(var(--sequence-min-readable-font), 1em)",
            "[data-sequence-stage] [data-participant-id] strong",
            "[data-sequence-stage] [data-participant-id] span",
            "[data-sequence-stage] [data-sequence-route]",
            "[data-sequence-stage] [data-sequence-kind]",
            "[data-sequence-stage] [data-sequence-description]",
            "[data-sequence-stage] [data-sequence-phase-label]",
            "margin: -16px 0 8px 8px;",
            "getComputedStyle(document.documentElement).fontSize",
            "--sequence-page-gutter: clamp(16px, 3vw, 48px)",
            'data-sequence-wide',
            'data-sequence-overflow-x',
            'data-sequence-long',
            'CSS.supports("zoom", "1")',
            "messageKinds.has(message.dataset.messageKind)",
            "ResizeObserver",
            "requestAnimationFrame",
            "scrollIntoView",
            "scroll-padding-top: var(--sequence-sticky-header-height, 0px)",
            "scroll-margin-top: var(--sequence-sticky-header-height, 0px)",
            'canvas.style.setProperty("--sequence-sticky-header-height"',
            "participantHeader.getBoundingClientRect().height",
            "scroll-padding-top: 0 !important",
            "scroll-margin-top: 0 !important",
            "@media (max-width: 780px)",
            "@media print",
            "--sequence-lane-min: 0px",
            "@media (prefers-reduced-motion: reduce)",
            ":focus-visible",
        ):
            self.assertIn(required, self.html)
        self.assertIsNotNone(
            re.search(
                r"@media print\s*\{.*?\[data-sequence-canvas\][^{]*\{[^}]*"
                r"--sequence-lane-min:\s*0px;",
                self.html,
                re.DOTALL,
            )
        )
        self.assertNotIn("2040px", self.html)
        self.assertNotIn("repeat(12", self.html)
        self.assertNotIn("margin: -27px 0 8px 8px;", self.html)
        self.assertNotRegex(self.html, r"transform\s*:\s*scale")
        digest = self.linter.extract_sequence_kernel_digest(self.html)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_participant_timeline_keeps_visual_grammar_outside_shared_kernel(self) -> None:
        style = re.search(
            r'<style\s+data-sequence-kernel="1">(?P<body>.*?)</style>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(style)
        kernel = style.group("body")
        self.assertNotIn("[data-participant-id] {", kernel)
        self.assertNotIn("[data-participant-id]::after {", kernel)
        self.assertNotIn("[data-sequence-message]::before {", kernel)
        self.assertNotIn("[data-sequence-message]::after {", kernel)

    def test_participant_timeline_preserves_fit_mode_across_remeasurement(self) -> None:
        script = re.search(
            r'<script\s+data-sequence-kernel="1">(?P<body>.*?)</script>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(script)
        kernel = script.group("body")
        self.assertIn("var sequenceScaleModes = new WeakMap();", kernel)
        self.assertIn("var sequenceViewportAnchors = new WeakMap();", kernel)
        self.assertIn("function rememberSequenceAnchor(viewport)", kernel)
        self.assertIn("sequenceViewportAnchors.set(viewport", kernel)
        self.assertIn("sequenceScaleModes.set(canvas, mode);", kernel)
        self.assertIn('sequenceScaleModes.get(canvas) || "fit"', kernel)
        self.assertIn("function measureSequenceCanvas(canvas, preservedCenterRatio)", kernel)
        self.assertIn(
            "applySequenceScale(canvas, activeScaleMode, preservedCenterRatio);",
            kernel,
        )
        self.assertIn("sequenceViewportAnchors.get(viewport)", kernel)
        self.assertIn('viewport.addEventListener("scroll"', kernel)
        self.assertIsNotNone(
            re.search(
                r"var naturalWidth = Math\.max\(\s*"
                r"Number\(canvas\.dataset\.sequenceNaturalWidth\) \|\| 0,\s*"
                r"stage\.scrollWidth \|\| 1\s*\);",
                kernel,
            )
        )
        self.assertNotIn(
            "Number(canvas.dataset.sequenceNaturalWidth) || stage.scrollWidth || 1",
            kernel,
        )
        self.assertNotIn("canvas.dataset.sequenceScale || \"fit\"", kernel)

    def test_exact_six_sequence_template_paths(self) -> None:
        self.assertEqual(6, len(SEQUENCE_TEMPLATE_PATHS))
        self.assertEqual(tuple(sorted(SEQUENCE_TEMPLATE_PATHS)), SEQUENCE_TEMPLATE_PATHS)
        self.assertTrue(all((TEMPLATE_ROOT / relative).is_file() for relative in SEQUENCE_TEMPLATE_PATHS))

    def test_all_sequence_templates_embed_identical_v1_kernel(self) -> None:
        participant_kernel = _raw_kernel_blocks(self.html)
        participant_digest = self.linter.extract_sequence_kernel_digest(self.html)
        for relative in SEQUENCE_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual(participant_kernel, _raw_kernel_blocks(html))
                self.assertEqual(participant_digest, self.linter.extract_sequence_kernel_digest(html))

    def test_all_sequence_templates_have_distinct_structure_signatures(self) -> None:
        signatures = {
            relative: template_structure_signature((TEMPLATE_ROOT / relative).read_text(encoding="utf-8"))
            for relative in SEQUENCE_TEMPLATE_PATHS
        }
        self.assertEqual(6, len(set(signatures.values())), signatures)

    def test_all_sequence_templates_use_structured_endpoints(self) -> None:
        for relative in SEQUENCE_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual([], self.linter.lint_sequence_contract(html))
                canvases = self.linter.parse_sequence_canvases(html)
                self.assertGreaterEqual(len(canvases), 1)
                for canvas in canvases:
                    participants = set(canvas.participant_ids)
                    self.assertGreaterEqual(len(participants), 2)
                    self.assertGreaterEqual(len(canvas.messages), 1)
                    for source, target, kind, semantic in canvas.messages:
                        self.assertIn(source, participants)
                        self.assertIn(target, participants)
                        self.assertIn(kind, self.linter.SEQUENCE_MESSAGE_KINDS)
                        self.assertTrue(semantic)

    def test_all_sequence_templates_keep_mobile_no_js_and_print_fallbacks(self) -> None:
        for relative in SEQUENCE_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
                parser = _SurfaceParser()
                parser.feed(html)
                parser.close()
                messages = parser.with_attribute("data-sequence-message")
                canvases = parser.with_attribute("data-sequence-canvas")
                self.assertEqual(len(canvases), len(parser.with_attribute("data-sequence-toolbar")))
                self.assertTrue(all("hidden" in attrs for _, attrs in parser.with_attribute("data-sequence-toolbar")))
                self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-route")))
                self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-kind")))
                self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-description")))
                self.assertIn("@media (max-width: 780px)", html)
                self.assertIn("@media print", html)
                self.assertIn("@media (prefers-reduced-motion: reduce)", html)

    def test_exact_six_contract_entries_differ_from_source(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        changed = {
            relative
            for relative, entry in contract["templates"].items()
            if entry["source"] != entry["canonical"]
        }
        self.assertTrue(set(SEQUENCE_TEMPLATE_PATHS) <= changed)
        self.assertTrue(
            all(contract["templates"][relative]["change_reason"] == CHANGE_REASON
                for relative in SEQUENCE_TEMPLATE_PATHS)
        )

    def test_non_sequence_contract_entries_remain_source_equal_canonical(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        generic_migrated = {
            relative
            for paths in contract["interaction_migration_batches"].values()
            for relative in paths
        }
        for relative, entry in contract["templates"].items():
            if relative not in SEQUENCE_TEMPLATE_PATHS and relative not in generic_migrated:
                with self.subTest(relative=relative):
                    self.assertEqual(entry["source"], entry["canonical"])
                    self.assertIsNone(entry["change_reason"])

    def test_sequence_redesign_preserves_source_slot_macro_contracts(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        for relative in SEQUENCE_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
                slots, macros, pairs = template_slots_macros_and_pairs(html)
                source = contract["templates"][relative]["source"]
                self.assertEqual(source["data_slots"], slots)
                self.assertEqual(source["macros"], macros)
                self.assertEqual(source["slot_macro_pairs"], pairs)

    def test_async_template_keeps_publish_callback_grammar(self) -> None:
        html = (TEMPLATE_ROOT / SEQUENCE_TEMPLATE_PATHS[0]).read_text(encoding="utf-8")
        canvases = self.linter.parse_sequence_canvases(html)
        semantics = {message[3] for canvas in canvases for message in canvas.messages}
        self.assertTrue({"publish", "callback"}.issubset(semantics))

    def test_transaction_template_keeps_begin_commit_rollback_grammar(self) -> None:
        html = (TEMPLATE_ROOT / "code-sequence/transaction-boundary-sequence.html").read_text(encoding="utf-8")
        semantics = {message[3] for canvas in self.linter.parse_sequence_canvases(html) for message in canvas.messages}
        self.assertTrue({"begin", "commit", "rollback"}.issubset(semantics))
        self.assertIn("data-transaction-boundary", html)

    def test_retry_template_keeps_attempt_backoff_error_grammar(self) -> None:
        html = (TEMPLATE_ROOT / "code-sequence/retry-exception-sequence.html").read_text(encoding="utf-8")
        semantics = {message[3] for canvas in self.linter.parse_sequence_canvases(html) for message in canvas.messages}
        self.assertTrue({"attempt", "backoff", "retry-exhausted"}.issubset(semantics))
        self.assertIn("data-retry-loop", html)

    def test_debugging_template_keeps_evidence_failure_fallback_grammar(self) -> None:
        html = (TEMPLATE_ROOT / "fault-debugging/debugging-sequence.html").read_text(encoding="utf-8")
        semantics = {message[3] for canvas in self.linter.parse_sequence_canvases(html) for message in canvas.messages}
        self.assertTrue({"evidence", "failure", "fallback"}.issubset(semantics))
        parser = _SurfaceParser()
        parser.feed(html)
        parser.close()
        participant_attrs = [attrs for _, attrs in parser.with_attribute("data-participant-id")]
        self.assertTrue(parser.with_attribute("data-sequence-evidence"))
        self.assertTrue(all("data-sequence-evidence" not in attrs for attrs in participant_attrs))

    def test_current_target_template_keeps_parallel_current_target_grammar(self) -> None:
        html = (TEMPLATE_ROOT / "feature-iteration/current-target-sequence.html").read_text(encoding="utf-8")
        parser = _SurfaceParser()
        parser.feed(html)
        parser.close()
        canvases = [attrs for _, attrs in parser.with_attribute("data-sequence-canvas")]
        self.assertEqual({"current", "target"}, {attrs.get("data-sequence-variant") for attrs in canvases})
        comparison_ids = {attrs.get("data-sequence-comparison-id") for attrs in canvases}
        self.assertEqual(1, len(comparison_ids))
        self.assertNotIn("", comparison_ids)

    def test_browser_fixtures_cover_short_wide_long_mobile_print_and_complex_cases(self) -> None:
        self.assertTrue(INTERACTION_FIXTURE.is_file())
        self.assertTrue(NO_JS_FIXTURE.is_file())
        self.assertTrue(COMPLEX_FIXTURE.is_file())
        matrix = INTERACTION_FIXTURE.read_text(encoding="utf-8")
        for case in ("short", "wide", "long", "mobile", "print"):
            self.assertIn(f'data-sequence-case="{case}"', matrix)
        complex_html = COMPLEX_FIXTURE.read_text(encoding="utf-8")
        self.assertEqual([], self.linter.lint_sequence_contract(complex_html))

    def test_fixture_matrix_covers_all_width_and_height_modes(self) -> None:
        html = INTERACTION_FIXTURE.read_text(encoding="utf-8")
        parser = _SurfaceParser()
        parser.feed(html)
        parser.close()
        canvases = [attrs for _, attrs in parser.with_attribute("data-sequence-canvas")]
        self.assertEqual({"auto", "contained", "wide"}, {attrs.get("data-sequence-width") for attrs in canvases})
        self.assertEqual({"auto", "flow", "scroll"}, {attrs.get("data-sequence-height") for attrs in canvases})

    def test_wide_fixture_forces_desktop_overflow_budget(self) -> None:
        canvases = self.linter.parse_sequence_canvases(
            INTERACTION_FIXTURE.read_text(encoding="utf-8")
        )
        wide = next(canvas for canvas in canvases if canvas.canvas_id == "fixture-wide")
        self.assertGreaterEqual(len(wide.participant_ids), 7)

    def test_interaction_and_complex_fixtures_embed_exact_product_kernel(self) -> None:
        product_kernel = _raw_kernel_blocks(self.html)
        for path in (INTERACTION_FIXTURE, COMPLEX_FIXTURE):
            with self.subTest(path=path.name):
                self.assertEqual(product_kernel, _raw_kernel_blocks(path.read_text(encoding="utf-8")))

    def test_no_js_fixture_contains_no_script_and_keeps_structured_routes(self) -> None:
        html = NO_JS_FIXTURE.read_text(encoding="utf-8")
        self.assertNotRegex(html, r"<script\b")
        self.assertEqual([], self.linter.lint_sequence_contract(html))
        parser = _SurfaceParser()
        parser.feed(html)
        parser.close()
        messages = parser.with_attribute("data-sequence-message")
        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-route")))
        self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-kind")))
        self.assertEqual(len(messages), len(parser.with_attribute("data-sequence-description")))

    def test_participant_timeline_does_not_parse_visible_route_text(self) -> None:
        changed = re.sub(
            r"(<span\s+data-sequence-route[^>]*>).*?(</span>)",
            r"\1Unknown visible route\2",
            self.html,
            count=1,
            flags=re.DOTALL,
        )
        self.assertNotEqual(self.html, changed)
        self.assertEqual([], self.linter.lint_sequence_contract(changed))
        self.assertEqual(
            self.linter.parse_sequence_canvases(self.html),
            self.linter.parse_sequence_canvases(changed),
        )

    def test_participant_timeline_contract_records_reviewed_structure_change(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        entry = contract["templates"][RELATIVE_TEMPLATE_PATH]
        self.assertEqual(CHANGE_REASON, entry["change_reason"])
        self.assertNotEqual(entry["source"], entry["canonical"])
        self.assertEqual(_canonical_snapshot(TEMPLATE_PATH, self.html), entry["canonical"])


if __name__ == "__main__":
    unittest.main()
