from __future__ import annotations

import hashlib
import json
import unittest
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tests.template_contract import (
    file_sha256,
    template_slots_macros_and_pairs,
    template_structure_signature,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "skills" / "vibe-diagram" / "assets" / "templates"
CONTRACT_PATH = ROOT / "contracts" / "template_migration_baseline.json"
SOURCE_CONTRACT_SHA256 = "cab7874937427e6092defb67b2e28f280d9d31022788c9c6382bbfe334f93959"
SOURCE_SNAPSHOTS_SHA256 = "cfc532f1abd6ccf7de33c25eba107739da351ce466cd27bc4c871d099c816bd1"
ROOT_KEYS = frozenset(
    {
        "schema_version",
        "signature_algorithm",
        "source_contract_sha256",
        "sequence_redesign_allowlist",
        "templates",
    }
)
ENTRY_KEYS = frozenset({"source", "canonical", "change_reason"})
SNAPSHOT_KEYS = frozenset(
    {"file_sha256", "structure_sha256", "data_slots", "macros", "slot_macro_pairs"}
)
SEQUENCE_REDESIGN_PATHS = (
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
    "feature-iteration/current-target-sequence.html",
)
EXPECTED_TEMPLATE_PATHS = (
    "business-architecture/capability-domain-map.html",
    "business-architecture/participant-boundary.html",
    "business-architecture/rule-constraint-heatmap.html",
    "business-architecture/value-chain-map.html",
    "business-flow/bpmn-light-flow.html",
    "business-flow/exception-branch-flow.html",
    "business-flow/stage-track.html",
    "business-flow/swimlane-flow.html",
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "decision-communication/decision-tree.html",
    "decision-communication/option-matrix-path.html",
    "decision-communication/recommended-path.html",
    "decision-communication/tradeoff-quadrant.html",
    "delivery-acceptance/acceptance-ledger.html",
    "delivery-acceptance/delivery-timeline.html",
    "delivery-acceptance/evidence-swimlane.html",
    "delivery-acceptance/risk-action-board.html",
    "fault-debugging/before-after-flow.html",
    "fault-debugging/bpmn-debug-flow.html",
    "fault-debugging/causal-chain.html",
    "fault-debugging/debugging-sequence.html",
    "fault-debugging/state-data-breakpoint.html",
    "feature-iteration/current-target-flow.html",
    "feature-iteration/current-target-sequence.html",
    "feature-iteration/diff-heatmap.html",
    "feature-iteration/release-rollback-track.html",
    "page-mockup/artboard-filmstrip.html",
    "page-mockup/artboard-wireframe.html",
    "page-mockup/primary-path-page-flow.html",
    "page-mockup/responsive-state-board.html",
    "state-data-model/data-flow-model.html",
    "state-data-model/er-lite.html",
    "state-data-model/lifecycle-track.html",
    "state-data-model/state-event-matrix.html",
    "state-data-model/state-machine.html",
    "system-architecture/api-integration.html",
    "system-architecture/component-breakdown.html",
    "system-architecture/data-architecture.html",
    "system-architecture/data-flow.html",
    "system-architecture/delivery-pipeline.html",
    "system-architecture/deployment-topology.html",
    "system-architecture/event-driven.html",
    "system-architecture/identity-access.html",
    "system-architecture/logical-layering.html",
    "system-architecture/network-topology.html",
    "system-architecture/observability-view.html",
    "system-architecture/resilience-view.html",
    "system-architecture/router-v6.html",
    "system-architecture/security-view.html",
    "system-architecture/system-context.html",
    "system-architecture/workload-overview.html",
    "technical-design/api-contract-swimlane.html",
    "technical-design/data-consistency-boundary.html",
    "technical-design/module-contract-data-topology.html",
    "technical-design/release-switch-track.html",
)


class _IdentityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.main_attrs: List[Dict[str, str]] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "main":
            names = [name.lower() for name, _ in attrs]
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                self.errors.append("duplicate main attributes: " + ", ".join(duplicates))
            self.main_attrs.append({name: value or "" for name, value in attrs})


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class CanonicalInventoryTests(unittest.TestCase):
    def test_duplicate_identity_attributes_are_rejected(self) -> None:
        parser = _IdentityParser()
        parser.feed(
            '<main data-template-family="safe" data-template-family="unsafe" '
            'data-template-id="sample" data-template-layout="sample"></main>'
        )
        self.assertTrue(getattr(parser, "errors", []))

    def test_macro_inventory_scans_complete_html_source(self) -> None:
        html = '<!-- {{comment_macro}} --><main data-slot="body" title="{{attr_macro}}">{{text_macro}}</main>'
        slots, macros, pairs = template_slots_macros_and_pairs(html)
        self.assertEqual(["body"], slots)
        self.assertEqual(["comment_macro", "attr_macro", "text_macro"], macros)
        self.assertEqual(
            [
                {"macro": "attr_macro", "slot": "body"},
                {"macro": "text_macro", "slot": "body"},
            ],
            pairs,
        )

    def test_frozen_source_snapshot_digest_is_immutable(self) -> None:
        contract = _contract()
        payload = json.dumps(
            {
                relative: contract["templates"][relative]["source"]
                for relative in EXPECTED_TEMPLATE_PATHS
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(SOURCE_SNAPSHOTS_SHA256, hashlib.sha256(payload).hexdigest())

    def test_exact_template_inventory_and_contract_schema(self) -> None:
        actual = tuple(
            sorted(path.relative_to(TEMPLATE_ROOT).as_posix() for path in TEMPLATE_ROOT.rglob("*.html"))
        ) if TEMPLATE_ROOT.exists() else ()
        self.assertEqual(EXPECTED_TEMPLATE_PATHS, actual)
        self.assertTrue(CONTRACT_PATH.is_file())
        contract = _contract()
        self.assertEqual(ROOT_KEYS, frozenset(contract))
        self.assertEqual(2, contract["schema_version"])
        self.assertEqual("htmlparser-events-v1", contract["signature_algorithm"])
        self.assertEqual(SOURCE_CONTRACT_SHA256, contract["source_contract_sha256"])
        self.assertEqual(list(SEQUENCE_REDESIGN_PATHS), contract["sequence_redesign_allowlist"])
        self.assertEqual(set(EXPECTED_TEMPLATE_PATHS), set(contract["templates"]))

    def test_template_identity_matches_path(self) -> None:
        for relative in EXPECTED_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                parser = _IdentityParser()
                parser.feed((TEMPLATE_ROOT / relative).read_text(encoding="utf-8"))
                self.assertEqual([], parser.errors)
                self.assertEqual(1, len(parser.main_attrs))
                attrs = parser.main_attrs[0]
                path = Path(relative)
                self.assertEqual(path.parent.name, attrs.get("data-template-family"))
                self.assertEqual(path.stem, attrs.get("data-template-id"))
                self.assertTrue(attrs.get("data-template-layout"))

    def test_contract_snapshots_match_canonical_files(self) -> None:
        contract = _contract()
        for relative in EXPECTED_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                entry = contract["templates"][relative]
                self.assertEqual(ENTRY_KEYS, frozenset(entry))
                self.assertEqual(SNAPSHOT_KEYS, frozenset(entry["source"]))
                self.assertEqual(SNAPSHOT_KEYS, frozenset(entry["canonical"]))
                path = TEMPLATE_ROOT / relative
                html = path.read_text(encoding="utf-8")
                slots, macros, pairs = template_slots_macros_and_pairs(html)
                actual = {
                    "file_sha256": file_sha256(path),
                    "structure_sha256": template_structure_signature(html),
                    "data_slots": slots,
                    "macros": macros,
                    "slot_macro_pairs": pairs,
                }
                self.assertEqual(entry["canonical"], actual)

    def test_migration_and_sequence_allowlist_rules(self) -> None:
        contract = _contract()
        allowlist = set(SEQUENCE_REDESIGN_PATHS)
        for relative, entry in contract["templates"].items():
            if relative not in allowlist:
                self.assertEqual(entry["source"], entry["canonical"], relative)
                self.assertIsNone(entry["change_reason"], relative)
            elif entry["source"] == entry["canonical"]:
                self.assertIsNone(entry["change_reason"], relative)
            else:
                self.assertIsInstance(entry["change_reason"], str, relative)
                self.assertTrue(entry["change_reason"].strip(), relative)

    def test_exactly_six_sequence_templates_have_approved_structure_changes(self) -> None:
        contract = _contract()
        changed = {
            relative
            for relative, entry in contract["templates"].items()
            if entry["source"] != entry["canonical"]
        }
        self.assertEqual(set(SEQUENCE_REDESIGN_PATHS), changed)
        self.assertTrue(
            all(
                contract["templates"][relative]["change_reason"]
                == "approved sequence interaction kernel and structured endpoint redesign"
                for relative in changed
            )
        )

    def test_each_family_has_distinct_structure_signatures(self) -> None:
        groups: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        for relative in EXPECTED_TEMPLATE_PATHS:
            family = Path(relative).parent.name
            html = (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
            groups[family][template_structure_signature(html)].append(relative)
        duplicates = [paths for family in groups.values() for paths in family.values() if len(paths) > 1]
        self.assertEqual([], duplicates)


if __name__ == "__main__":
    unittest.main()
