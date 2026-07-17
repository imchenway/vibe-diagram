from __future__ import annotations

import os
import unittest
from typing import Optional

from tests.test_documentation_contract import (
    BROWSER_EVIDENCE,
    CLIENT_LABELS,
    COMPATIBILITY,
    FIXTURES,
    SEQUENCE_TEMPLATES,
    _macos_status,
    _read_evidence,
    _validate_browser_evidence,
)


REQUIRED_CHECK_GROUPS = {
    "modes": {
        "width_auto",
        "width_contained",
        "width_wide",
        "height_auto",
        "height_flow",
        "height_scroll",
    },
    "short": {"toolbar_hidden", "no_nested_vertical_scroll"},
    "wide": {
        "full_width",
        "safe_page_margins",
        "no_page_horizontal_overflow",
        "four_scale_controls_work",
        "viewport_anchor_preserved",
        "minimum_effective_text_12px",
    },
    "long": {
        "internal_vertical_scroll",
        "participants_sticky",
        "horizontal_alignment_preserved",
        "focus_not_obscured",
    },
    "mobile": {
        "toolbar_disabled",
        "sticky_disabled",
        "ledger_readable",
        "no_page_horizontal_overflow",
    },
    "no_js": {"enhancement_absent", "toolbar_absent", "structured_route_readable"},
    "print": {"toolbar_hidden", "sticky_reset", "overflow_expanded", "content_not_clipped"},
    "complex": {"overview_present", "details_linked"},
}


class MacosBrowserValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = os.environ.get("VIBE_DIAGRAM_REQUIRE_MACOS_BROWSER_EVIDENCE")
        self.assertIn(self.gate, (None, "1"))
        self.state = _macos_status(COMPATIBILITY.read_text(encoding="utf-8"))

    def _current_evidence_or_pending(self) -> Optional[dict]:
        if self.state == "Pending":
            self.assertFalse(BROWSER_EVIDENCE.exists())
            return None
        self.assertEqual("Passed", self.state)
        self.assertTrue(BROWSER_EVIDENCE.is_file())
        evidence = _read_evidence(BROWSER_EVIDENCE)
        _validate_browser_evidence(evidence)
        return evidence

    def test_pending_state_requires_evidence_absent(self) -> None:
        if self.state == "Pending":
            self.assertFalse(BROWSER_EVIDENCE.exists())
        else:
            self.assertEqual("Passed", self.state)

    def test_explicit_gate_requires_passed_current_evidence(self) -> None:
        if self.gate is None:
            self._current_evidence_or_pending()
            return
        self.assertEqual(
            ("Passed", True),
            (self.state, BROWSER_EVIDENCE.is_file()),
            "explicit browser gate requires Passed ledger state and current evidence",
        )
        _validate_browser_evidence(_read_evidence(BROWSER_EVIDENCE))

    def test_evidence_schema_is_exact(self) -> None:
        evidence = self._current_evidence_or_pending()
        if evidence is None:
            return
        self.assertEqual(
            {
                "schema_version",
                "scope",
                "platform",
                "viewports",
                "canonical_tree_sha256",
                "sequence_kernel_sha256",
                "fixtures",
                "product_templates",
                "measurements",
                "checks",
                "unverified",
            },
            set(evidence),
        )

    def test_evidence_binds_current_canonical_kernel_fixtures_and_product_templates(self) -> None:
        evidence = self._current_evidence_or_pending()
        if evidence is None:
            return
        self.assertEqual(set(FIXTURES), set(evidence["fixtures"]))
        self.assertEqual(set(SEQUENCE_TEMPLATES), set(evidence["product_templates"]))

    def test_all_required_browser_checks_are_passed(self) -> None:
        evidence = self._current_evidence_or_pending()
        if evidence is None:
            return
        self.assertEqual(set(REQUIRED_CHECK_GROUPS), set(evidence["checks"]))
        for group, keys in REQUIRED_CHECK_GROUPS.items():
            with self.subTest(group=group):
                self.assertEqual(keys, set(evidence["checks"][group]))
                self.assertTrue(all(value is True for value in evidence["checks"][group].values()))

    def test_browser_evidence_keeps_client_and_other_os_runtime_unverified(self) -> None:
        evidence = self._current_evidence_or_pending()
        if evidence is None:
            return
        self.assertEqual(
            {client: "unverified" for client in CLIENT_LABELS},
            evidence["unverified"]["clients"],
        )
        self.assertEqual(
            {"Linux": "unverified", "Windows": "unverified"},
            evidence["unverified"]["operating_systems"],
        )

    def test_compatibility_status_requires_current_browser_evidence(self) -> None:
        evidence = self._current_evidence_or_pending()
        if self.state == "Passed":
            self.assertIsNotNone(evidence)
        else:
            self.assertIsNone(evidence)


if __name__ == "__main__":
    unittest.main()
