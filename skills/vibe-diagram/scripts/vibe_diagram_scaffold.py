#!/usr/bin/env python3
"""Create a diagram artifact by copying one canonical template exactly."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import List, Optional


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
TEMPLATE_ROUTING_PATH = SKILL_ROOT / "contracts" / "template-routing.json"
IDENTITY_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
NATIVE_STANDARD = "native"
DEPRECATED_FAMILIES = {
    "delivery-acceptance": (
        "deprecated for one release cycle: route acceptance steps to "
        "business-flow/logic-flowchart and requirement-to-evidence traceability "
        "to decision-communication/option-matrix-path"
    ),
}
DEPRECATED_TEMPLATES = {
    ("feature-iteration", "release-rollback-track"): (
        "deprecated for one release cycle: route release, observation, gate, and rollback "
        "to business-flow/logic-flowchart; use state-data-model/state-machine only when "
        "the user explicitly requests a state machine"
    ),
    ("business-architecture", "value-chain-map"): (
        "deprecated as the business-architecture default: use capability-domain-map, "
        "or route trigger/order/decision/exception prompts to business-flow/logic-flowchart"
    ),
    ("technical-design", "release-switch-track"): (
        "deprecated for one release cycle: use technical-design/technical-design-package; "
        "release and rollback remain one view inside the complete design package"
    ),
    ("technical-design", "data-consistency-boundary"): (
        "deprecated as a standalone diagram type: use "
        "technical-design/technical-design-package and place Outbox transaction, "
        "delivery, consumption, recovery, and consistency concerns in its mapped views"
    ),
}


def _canonical_template(family: str, template_id: str) -> Path:
    if IDENTITY_RE.fullmatch(family) is None or IDENTITY_RE.fullmatch(template_id) is None:
        raise ValueError("family and template must be lowercase hyphenated identifiers")
    path = TEMPLATE_ROOT / family / f"{template_id}.html"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unknown canonical template: {family}/{template_id}")
    if path.parent.parent != TEMPLATE_ROOT or path.parent.name != family:
        raise ValueError("canonical template path escaped the template root")
    return path


def _require_ready_template(family: str, template_id: str) -> None:
    if family in DEPRECATED_FAMILIES:
        raise ValueError(f"{family} is {DEPRECATED_FAMILIES[family]}")
    deprecation = DEPRECATED_TEMPLATES.get((family, template_id))
    if deprecation:
        raise ValueError(f"{family}/{template_id} is {deprecation}")
    routing = json.loads(TEMPLATE_ROUTING_PATH.read_text(encoding="utf-8"))
    definition = routing.get("families", {}).get(family)
    if not isinstance(definition, dict):
        raise ValueError(f"diagram family is not routed: {family}")
    ready = definition.get("ready_templates")
    default_template = definition.get("default_template")
    if (
        not isinstance(ready, list)
        or not isinstance(default_template, str)
        or template_id not in ready
    ):
        raise ValueError(
            f"template is blocked until its true-diagram migration is complete: "
            f"{family}/{template_id}; ready default: {default_template}"
        )


def _require_supported_standard(standard: str) -> None:
    normalized = standard.strip().lower()
    if normalized != NATIVE_STANDARD:
        raise ValueError(
            f'strict standard "{standard}" is not implemented by the canonical template catalog; '
            "refusing to substitute a Vibe Diagram native template"
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Copy one canonical Vibe Diagram template.")
    parser.add_argument("--type", required=True, dest="family", help="diagram family")
    parser.add_argument("--template", required=True, dest="template_id", help="template id")
    parser.add_argument(
        "--standard",
        default=NATIVE_STANDARD,
        help="authoring standard; only native is currently implemented",
    )
    parser.add_argument("--output", required=True, type=Path, help="new HTML artifact path")
    args = parser.parse_args(argv)
    try:
        _require_supported_standard(args.standard)
        _require_ready_template(args.family, args.template_id)
        source = _canonical_template(args.family, args.template_id)
        output = args.output.expanduser()
        if output.exists() or output.is_symlink():
            raise ValueError(f"refusing to overwrite existing output: {output}")
        if output.suffix.lower() != ".html":
            raise ValueError("output must use the .html suffix")
        if not output.parent.is_dir():
            raise ValueError(f"output parent does not exist: {output.parent}")
        payload = source.read_bytes()
        output.write_bytes(payload)
        print(
            json.dumps(
                {
                    "status": "created",
                    "family": args.family,
                    "template": args.template_id,
                    "standard": NATIVE_STANDARD,
                    "output": str(output.resolve()),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
