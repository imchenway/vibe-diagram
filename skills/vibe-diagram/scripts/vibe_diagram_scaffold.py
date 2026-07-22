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
IDENTITY_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _canonical_template(family: str, template_id: str) -> Path:
    if IDENTITY_RE.fullmatch(family) is None or IDENTITY_RE.fullmatch(template_id) is None:
        raise ValueError("family and template must be lowercase hyphenated identifiers")
    path = TEMPLATE_ROOT / family / f"{template_id}.html"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unknown canonical template: {family}/{template_id}")
    if path.parent.parent != TEMPLATE_ROOT or path.parent.name != family:
        raise ValueError("canonical template path escaped the template root")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Copy one canonical Vibe Diagram template.")
    parser.add_argument("--type", required=True, dest="family", help="diagram family")
    parser.add_argument("--template", required=True, dest="template_id", help="template id")
    parser.add_argument("--output", required=True, type=Path, help="new HTML artifact path")
    args = parser.parse_args(argv)
    try:
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
