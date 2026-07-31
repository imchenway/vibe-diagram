#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_PATH = ROOT / "skills" / "vibe-diagram" / "scripts" / "vibe_diagram_scaffold.py"
OUTPUT_PATH = (
    ROOT
    / "skills"
    / "vibe-diagram"
    / "assets"
    / "templates"
    / "code-review"
    / "code-review-package.html"
)


def _scaffold_module():
    spec = importlib.util.spec_from_file_location("vibe_diagram_scaffold", SCAFFOLD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载代码审查图族生成器")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    module = _scaffold_module()
    rendered = module._render_code_review_package(module._canonical_review_spec())
    if args.check:
        if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            print("ERROR: 代码审查 canonical 模板与生成器不一致")
            return 1
        print("OK: 代码审查 canonical 模板与生成器一致")
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"OK: 已生成 {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
