#!/usr/bin/env python3
"""使用技能包内的完整引擎生成自包含图形，检查失败时不写入输出。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vibe_diagram_native import build, read_json
from vibe_diagram_lint import lint_text
from vibe_diagram_artifact import write_candidate


def main(argv=None) -> int:
    """生成入口同时支持原生图形源和直接编写的标准 SVG。"""
    # 用户只选择一种图形来源，覆盖清单不包含第二份拓扑。
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--input", help="原生图类 JSON 源")
    sources.add_argument("--svg", help="带语义标记的 SVG，例如实体数量关系图")
    parser.add_argument("--manifest", required=True, help="产品问题、关键事实和证据覆盖清单")
    parser.add_argument("--summary", default="", help="作者 SVG 的业务摘要；原生源使用 meta.subtitle")
    parser.add_argument("--output", required=True, help="新的独立 HTML 文件，禁止覆盖")
    args = parser.parse_args(argv)
    try:
        # 写入前完成全部检查，原文件与源输入不受失败影响。
        target = Path(args.output).expanduser().absolute()
        if target.exists() or target.is_symlink():
            raise ValueError("输出已存在，请生成独立草稿：" + str(target))
        source = Path(args.svg or args.input).expanduser().resolve()
        manifest = read_json(Path(args.manifest).expanduser().resolve())
        document = build(source, manifest, svg_mode=bool(args.svg), summary=args.summary)
        errors = lint_text(document)
        if errors:
            raise ValueError("图形未通过产物检查：\n" + "\n".join(errors))
        write_candidate(target, document.encode("utf-8"))
        print(json.dumps({"status": "artifact-static-valid", "artifact": str(target), "browser_layout": "not-verified", "product_reading": "not-reviewed", "client_runtime": "not-verified"}, ensure_ascii=False))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
