from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from tests.test_canonical_inventory import EXPECTED_TEMPLATE_PATHS


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
REFERENCE_ROOT = SKILL_ROOT / "references"
BASELINE_PATH = ROOT / "contracts" / "reference_migration_baseline.json"
REFERENCE_NAMES = (
    "business-architecture.md",
    "business-flow.md",
    "code-sequence.md",
    "decision-communication.md",
    "delivery-acceptance.md",
    "fault-debugging.md",
    "feature-iteration.md",
    "page-mockup.md",
    "state-data-model.md",
    "system-architecture.md",
    "technical-design.md",
)
RUNTIME_WORKFLOW_NAME = "runtime-workflow.md"
ADAPTIVE_REFERENCE_NAME = "adaptive-readability.md"
ALL_REFERENCE_NAMES = (*REFERENCE_NAMES, ADAPTIVE_REFERENCE_NAME, RUNTIME_WORKFLOW_NAME)
SEQUENCE_REFERENCE_NAMES = {
    "code-sequence.md",
    "fault-debugging.md",
    "feature-iteration.md",
}
FORBIDDEN_HOST_TERMS = (
    "Codex",
    "Claude",
    "Gemini",
    "Copilot",
    "Telegram",
    "Vibego",
    "Hypha",
    "LicenseRef-Proprietary",
    "file://",
    "~/.codex",
    "~/.claude",
    "~/.gemini",
)


def _read_skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _read_runtime_workflow() -> str:
    return (REFERENCE_ROOT / RUNTIME_WORKFLOW_NAME).read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    self_closing = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not self_closing:
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    result = {}
    for line in self_closing.group(1).splitlines():
        if ":" not in line:
            raise AssertionError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_has_only_name_and_description(self) -> None:
        frontmatter = _frontmatter(_read_skill())
        self.assertEqual({"name", "description"}, set(frontmatter))
        self.assertEqual("vibe-diagram", frontmatter["name"])
        self.assertRegex(frontmatter["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(frontmatter["name"]), 64)
        self.assertTrue(frontmatter["description"])
        self.assertLessEqual(len(frontmatter["description"]), 1024)

    def test_description_is_specific_and_trigger_oriented(self) -> None:
        description = _frontmatter(_read_skill())["description"].lower()
        self.assertTrue(description.startswith("use when"))
        for term in (
            "architecture",
            "workflow",
            "sequence",
            "state",
            "data",
            "debugging",
            "feature iteration",
            "page mockup",
            "technical design",
            "decision communication",
            "delivery acceptance",
        ):
            self.assertIn(term, description)
        self.assertNotIn("every answer", description)

    def test_core_stays_under_500_lines_and_routes_to_references(self) -> None:
        text = _read_skill()
        self.assertLessEqual(len(text.splitlines()), 500)
        expected_headings = (
            "# Vibe Diagram",
            "## Update gate",
            "## Runtime workflow",
            "## Reference index",
        )
        positions = [text.index(heading) for heading in expected_headings]
        self.assertEqual(sorted(positions), positions)
        for name in ALL_REFERENCE_NAMES:
            self.assertIn(f"references/{name}", text)

        runtime = _read_runtime_workflow()
        runtime_headings = (
            "# Vibe Diagram Runtime Workflow",
            "## Scope and activation",
            "## Artifact contract",
            "## Capability-based delivery",
            "## Candidate atlas calibration mode",
            "## Automatic routing",
            "## Shared diagram grammar",
            "## Layout, arrows, and collision control",
            "## Visual quality and accessibility",
            "## Evidence and uncertainty",
            "## Pre-delivery checks",
        )
        runtime_positions = [runtime.index(heading) for heading in runtime_headings]
        self.assertEqual(sorted(runtime_positions), runtime_positions)

    def test_update_gate_runs_before_loading_runtime_workflow(self) -> None:
        text = _read_skill()
        command = "scripts/update_skill.py"
        runtime = f"references/{RUNTIME_WORKFLOW_NAME}"
        self.assertIn("on every invocation", text.lower())
        self.assertIn("--check-and-update", text)
        self.assertLess(text.index(command), text.index(runtime))
        self.assertIn("continue with the installed version", text)

    def test_exact_reference_inventory(self) -> None:
        actual = tuple(sorted(path.name for path in REFERENCE_ROOT.glob("*.md"))) if REFERENCE_ROOT.exists() else ()
        self.assertEqual(tuple(sorted(ALL_REFERENCE_NAMES)), actual)

    def test_reference_template_paths_resolve(self) -> None:
        referenced = set()
        pattern = re.compile(r"\.\./assets/templates/([a-z0-9-]+/[a-z0-9-]+\.html)")
        for name in REFERENCE_NAMES:
            text = (REFERENCE_ROOT / name).read_text(encoding="utf-8")
            for relative in pattern.findall(text):
                referenced.add(relative)
                self.assertTrue((SKILL_ROOT / "assets" / "templates" / relative).is_file())
        self.assertEqual(set(EXPECTED_TEMPLATE_PATHS), referenced)

    def test_reference_full_file_hashes_match_frozen_baseline(self) -> None:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        for name in REFERENCE_NAMES:
            with self.subTest(name=name):
                actual = hashlib.sha256((REFERENCE_ROOT / name).read_bytes()).hexdigest()
                self.assertEqual(baseline["references"][name], actual)

    def test_reference_baseline_inventory_is_exact(self) -> None:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {"schema_version", "source_skill_content_sha256", "references"},
            set(baseline),
        )
        self.assertEqual(1, baseline["schema_version"])
        self.assertEqual(
            "6d123fce6a33df73e04f8f953d9429c24cc833897291ca30dad62ecf611dfb48",
            baseline["source_skill_content_sha256"],
        )
        self.assertEqual(set(REFERENCE_NAMES), set(baseline["references"]))
        for digest in baseline["references"].values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_adaptive_reference_keeps_runtime_and_semantics_separate(self) -> None:
        text = (REFERENCE_ROOT / ADAPTIVE_REFERENCE_NAME).read_text(encoding="utf-8")
        for token in (
            "adaptive-viewport@1",
            "semantic-relations@1",
            "progressive disclosure",
            "family-policies.json",
            "must not infer families",
            "data-fallback-for",
        ):
            self.assertIn(token, text.lower())

    def test_artifact_contract_is_html_first(self) -> None:
        text = _read_runtime_workflow()
        self.assertIn("self-contained single-file HTML", text)
        self.assertRegex(text, r"PNG.*SVG.*explicitly requests")
        self.assertIn("must not replace the HTML artifact", text)

    def test_delivery_branches_only_on_capabilities(self) -> None:
        section = _read_runtime_workflow().split("## Capability-based delivery", 1)[1].split("\n## ", 1)[0]
        expected = {"can_write_file", "can_attach_file", "can_open_local_link", "text_only"}
        actual = set(re.findall(r"(?m)^- `([^`]+)`:", section))
        self.assertEqual(expected, actual)
        for host in FORBIDDEN_HOST_TERMS:
            self.assertNotIn(host, section)

    def test_migrated_references_preserve_non_negotiable_domain_rules(self) -> None:
        delivery = (REFERENCE_ROOT / "delivery-acceptance.md").read_text(encoding="utf-8")
        self.assertIn("Every user requirement or acceptance criterion must have an independent R# lane", delivery)
        self.assertIn("No evidence means warn or blocked", delivery)
        self.assertIn("A whole-suite gate must not replace per-requirement evidence", delivery)

        debugging = (REFERENCE_ROOT / "fault-debugging.md").read_text(encoding="utf-8")
        self.assertIn("current implementation chain is the primary canvas", debugging)
        for token in ("E#", "H#", "R#"):
            self.assertIn(token, debugging)
        self.assertIn("repair, verification, and rollback beside the fault point", debugging)

        state_data = (REFERENCE_ROOT / "state-data-model.md").read_text(encoding="utf-8")
        self.assertIn("source, unit, enumeration, nullability, idempotency key, and version", state_data)
        self.assertIn("concurrency, consistency, compensation, retry, undo, and soft-delete", state_data)

    def test_output_language_follows_user_with_english_fallback(self) -> None:
        text = _read_runtime_workflow()
        self.assertIn("Follow the user's language", text)
        self.assertIn("use English when the language cannot be determined", text)

    def test_host_and_vibego_terms_are_absent(self) -> None:
        text = _read_skill() + "\n" + "\n".join(
            (REFERENCE_ROOT / name).read_text(encoding="utf-8") for name in ALL_REFERENCE_NAMES
        )
        for term in FORBIDDEN_HOST_TERMS:
            self.assertNotIn(term, text)

    def test_canonical_text_is_english(self) -> None:
        text = _read_skill() + "\n" + "\n".join(
            (REFERENCE_ROOT / name).read_text(encoding="utf-8") for name in ALL_REFERENCE_NAMES
        )
        self.assertIsNone(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))

    def test_sequence_references_define_structured_endpoints(self) -> None:
        for name in SEQUENCE_REFERENCE_NAMES:
            text = (REFERENCE_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("## Sequence interaction contract", text)
            for token in (
                "data-participant-id",
                "data-from",
                "data-to",
                "data-message-kind",
                "data-semantic",
                "sync",
                "return",
                "async",
                "self",
                "error",
            ):
                self.assertIn(token, text)

    def test_sequence_references_define_adaptive_canvas_modes(self) -> None:
        for name in SEQUENCE_REFERENCE_NAMES:
            text = (REFERENCE_ROOT / name).read_text(encoding="utf-8")
            self.assertIn('data-sequence-width="auto|contained|wide"', text)
            self.assertIn('data-sequence-height="auto|flow|scroll"', text)
            for token in ("Fit width", "75%", "90%", "100%", "12 CSS px", "clamp(520px, 75vh, 900px)"):
                self.assertIn(token, text)
            for token in ("mobile", "JavaScript", "print", "sticky participant header"):
                self.assertIn(token, text)

    def test_sequence_references_define_overview_detail_budget(self) -> None:
        for name in SEQUENCE_REFERENCE_NAMES:
            text = (REFERENCE_ROOT / name).read_text(encoding="utf-8")
            for token in ("12 semantic participants", "40 primary sequence messages", "4 major sequence phases", "overview sequence", "detail sequence"):
                self.assertIn(token, text)
            self.assertIn("must not merge semantically different participants", text)

    def test_sequence_references_forbid_visible_text_route_parsing(self) -> None:
        for name in SEQUENCE_REFERENCE_NAMES:
            text = (REFERENCE_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("Never infer endpoints from visible route text", text)
        for name in set(REFERENCE_NAMES) - SEQUENCE_REFERENCE_NAMES:
            text = (REFERENCE_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("data-sequence-width", text)
            self.assertNotIn("data-message-kind", text)


if __name__ == "__main__":
    unittest.main()
