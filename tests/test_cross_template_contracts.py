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
        self.assertEqual(["B00"], baseline["scope"]["completed_batches"])
        self.assertEqual([], baseline["scope"]["completed_templates"])
        self.assertEqual("required", baseline["evidence"]["synthetic_contracts"])
        self.assertEqual("pending", baseline["evidence"]["canonical_templates"])
        self.assertEqual("unverified", baseline["evidence"]["client_runtime"])

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


if __name__ == "__main__":
    unittest.main()
