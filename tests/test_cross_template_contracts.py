from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import build_packages


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
POLICY_PATH = SKILL_ROOT / "contracts" / "family-policies.json"
INTERACTION_PATH = ROOT / "contracts" / "interaction_contract_baseline.json"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "contracts"
POSITIVE_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "positive"
SEQUENCE_PATHS = {
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
    "feature-iteration/current-target-sequence.html",
}


def _load_linter():
    path = SKILL_ROOT / "scripts" / "vibe_diagram_lint.py"
    spec = importlib.util.spec_from_file_location("cross_template_contract_linter", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not create linter import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CrossTemplateContractTests(unittest.TestCase):
    def test_policy_covers_exactly_ten_families_and_52_non_sequence_templates(self) -> None:
        policy = build_packages.load_family_policies(POLICY_PATH)
        covered = {
            f"{family}/{template_id}.html"
            for family, definition in policy["families"].items()
            for template_id in definition["templates"]
        }
        self.assertEqual(10, len(policy["families"]))
        self.assertEqual(set(build_packages.TEMPLATE_PATHS) - SEQUENCE_PATHS, covered)
        self.assertEqual(sorted(SEQUENCE_PATHS), policy["sequence_exclusions"])

    def test_policy_parser_rejects_unknown_keys_boolean_limits_and_widening(self) -> None:
        baseline = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        mutations = []

        unknown = copy.deepcopy(baseline)
        unknown["unexpected"] = True
        mutations.append(unknown)

        boolean_limit = copy.deepcopy(baseline)
        boolean_limit["families"]["business-flow"]["limits"]["nodes"] = True
        mutations.append(boolean_limit)

        widening = copy.deepcopy(baseline)
        widening["families"]["business-flow"]["templates"]["swimlane-flow"]["limits"][
            "nodes"
        ] = widening["families"]["business-flow"]["limits"]["nodes"] + 1
        mutations.append(widening)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            for index, mutation in enumerate(mutations):
                with self.subTest(index=index):
                    path.write_text(json.dumps(mutation), encoding="utf-8")
                    with self.assertRaises(build_packages.ValidationError):
                        build_packages.load_family_policies(path)
                    with self.assertRaises(ValueError):
                        _load_linter().load_family_policies(path)

    def test_policy_parser_rejects_duplicate_json_keys(self) -> None:
        raw = POLICY_PATH.read_text(encoding="utf-8").replace(
            '"schema_version": 1,',
            '"schema_version": 1,\n  "schema_version": 1,',
            1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(build_packages.ValidationError):
                build_packages.load_family_policies(path)
            with self.assertRaises(ValueError):
                _load_linter().load_family_policies(path)

    def test_interaction_baseline_separates_static_and_runtime_evidence(self) -> None:
        baseline = build_packages.load_interaction_contract(ROOT)
        self.assertEqual("B00", baseline["scope"]["completed_batches"][0])
        self.assertEqual(
            sorted(baseline["scope"]["completed_templates"]),
            baseline["scope"]["completed_templates"],
        )
        self.assertEqual("required", baseline["evidence"]["synthetic_contracts"])
        expected_template_state = (
            "complete"
            if len(baseline["scope"]["completed_templates"]) == 52
            else "partial"
            if baseline["scope"]["completed_templates"]
            else "pending"
        )
        self.assertEqual(
            expected_template_state, baseline["evidence"]["canonical_templates"]
        )
        self.assertEqual("pending", baseline["evidence"]["browser_runtime"])
        self.assertEqual("unverified", baseline["evidence"]["client_runtime"])

    def test_completed_generic_scope_keeps_sequence_and_runtime_boundaries(self) -> None:
        baseline = build_packages.load_interaction_contract(ROOT)
        policy = build_packages.load_family_policies(POLICY_PATH)
        completed = {
            relative
            for paths in policy["migration_batches"].values()
            for relative in paths
        }
        self.assertEqual(set(build_packages.TEMPLATE_PATHS) - SEQUENCE_PATHS, completed)
        self.assertEqual(sorted(completed), baseline["scope"]["completed_templates"])
        self.assertEqual(
            ["B00", *policy["migration_batches"]],
            baseline["scope"]["completed_batches"],
        )
        self.assertEqual(sorted(SEQUENCE_PATHS), policy["sequence_exclusions"])
        self.assertEqual(
            {
                "synthetic_contracts": "required",
                "canonical_templates": "complete",
                "browser_runtime": "pending",
                "client_runtime": "unverified",
            },
            baseline["evidence"],
        )

        reference = (
            SKILL_ROOT / "references" / "adaptive-readability.md"
        ).read_text(encoding="utf-8")
        for required in (
            "All 52 canonical generic templates",
            "six sequence templates",
            "browser_runtime",
            "client_runtime",
        ):
            with self.subTest(required=required):
                self.assertIn(required, reference)

    def test_shared_runtime_assets_do_not_encode_template_families(self) -> None:
        runtime_paths = (
            SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js",
            SKILL_ROOT / "assets" / "contracts" / "progressive-disclosure" / "v1.js",
        )
        forbidden = tuple(build_packages.load_family_policies(POLICY_PATH)["families"])
        for path in runtime_paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertTrue(all(family not in text for family in forbidden))
                self.assertNotIn("textContent", text)
                self.assertNotIn("innerText", text)

    def test_progressive_disclosure_preserves_native_details_baseline(self) -> None:
        asset_root = SKILL_ROOT / "assets" / "contracts" / "progressive-disclosure"
        css = (asset_root / "v1.css").read_text(encoding="utf-8")
        javascript = (asset_root / "v1.js").read_text(encoding="utf-8")

        self.assertIn("details[data-diagram-detail]", css)
        self.assertIn("details[data-diagram-detail] > :not(summary)", css)
        self.assertIn("@media print", css)
        self.assertIn('detail.matches("details")', javascript)
        self.assertIn("detail.open = true", javascript)
        self.assertIn('data-runtime-was-open', javascript)
        self.assertIn('data-runtime-was-hidden', javascript)
        self.assertIn("detail.open = wasOpen", javascript)
        self.assertIn("detail.hidden = wasHidden", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_positive_and_negative_contract_fixtures_have_linter_builder_parity(self) -> None:
        linter = _load_linter()
        policy = build_packages.load_family_policies(POLICY_PATH)
        for name, valid in (
            ("generic-contract-valid.html", True),
            ("generic-contract-invalid.html", False),
        ):
            with self.subTest(name=name):
                html = (FIXTURE_ROOT / name).read_text(encoding="utf-8")
                lint_errors = linter.lint_generic_contract(
                    html, "business-flow", "swimlane-flow"
                )
                build_errors = build_packages.generic_contract_errors(
                    html, "business-flow", "swimlane-flow", policy
                )
                self.assertEqual(lint_errors, build_errors)
                self.assertEqual(valid, not lint_errors)

    def test_positive_visual_fixtures_cover_system_and_complex_sequence(self) -> None:
        linter = _load_linter()
        system = (POSITIVE_FIXTURE_ROOT / "system-context-positive.html").read_text(
            encoding="utf-8"
        )
        sequence = (
            POSITIVE_FIXTURE_ROOT / "complex-sequence-positive.html"
        ).read_text(encoding="utf-8")

        self.assertNotIn("{{", system + sequence)
        self.assertEqual(
            [], linter.lint_generic_contract(system, "system-architecture", "system-context")
        )
        self.assertEqual([], linter.lint_system_architecture(system))
        self.assertIn('data-architecture-topology="context-boundary"', system)
        for token in (
            "data-diagram-visible-relation-id",
            "data-diagram-landmark",
            "data-architecture-legend",
            "data-fallback-for",
        ):
            self.assertIn(token, system)

        self.assertEqual([], linter.lint_sequence_contract(sequence))
        for token in (
            "data-participant-group-id",
            "data-sequence-step-index",
            "data-sequence-fragment-kind",
            "data-sequence-outcome",
            "data-sequence-risk-id",
            "data-sequence-evidence-for",
            "data-sequence-evidence-id",
        ):
            self.assertIn(token, sequence)

    def test_generic_relation_requires_one_visible_edge_binding(self) -> None:
        html = (FIXTURE_ROOT / "generic-contract-valid.html").read_text(encoding="utf-8")
        missing = html.replace(
            ' data-diagram-visible-relation-id="request-service"', "", 1
        )
        linter = _load_linter()
        self.assertTrue(
            any(
                "visible" in error.lower()
                for error in linter.lint_generic_contract(
                    missing, "business-flow", "swimlane-flow"
                )
            )
        )

    def test_sequence_contract_is_not_double_parsed_as_generic(self) -> None:
        html = (
            SKILL_ROOT
            / "assets"
            / "templates"
            / "code-sequence"
            / "participant-timeline.html"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            [],
            _load_linter().lint_generic_contract(
                html, "code-sequence", "participant-timeline"
            ),
        )

    def test_sequence_optional_primitives_have_linter_builder_validity_parity(self) -> None:
        html = (
            SKILL_ROOT
            / "assets"
            / "templates"
            / "code-sequence"
            / "participant-timeline.html"
        ).read_text(encoding="utf-8")
        cases = {
            "valid": (html, True),
            "duplicate participant group": (
                html.replace(
                    'data-participant-group-id="execution-state"',
                    'data-participant-group-id="entry-coordination"',
                    1,
                ),
                False,
            ),
            "partial step index": (
                html.replace(' data-sequence-step-index="01"', "", 1),
                False,
            ),
            "invalid fragment kind": (
                html.replace(
                    'data-sequence-fragment-id="state-transaction"\n'
                    '                   data-sequence-fragment-kind="tx"',
                    'data-sequence-fragment-id="state-transaction"\n'
                    '                   data-sequence-fragment-kind="unknown"',
                    1,
                ),
                False,
            ),
            "missing evidence target": (
                html.replace(
                    'data-sequence-evidence-for="participant-timeline-evidence"',
                    'data-sequence-evidence-for="missing-evidence"',
                    1,
                ),
                False,
            ),
        }
        linter = _load_linter()
        for name, (candidate, expected_valid) in cases.items():
            with self.subTest(name=name):
                lint_valid = not linter.lint_sequence_contract(candidate)
                builder_valid = not build_packages._sequence_errors(candidate)
                self.assertEqual(expected_valid, lint_valid)
                self.assertEqual(lint_valid, builder_valid)


if __name__ == "__main__":
    unittest.main()
