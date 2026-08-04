#!/usr/bin/env python3
"""把全部 canonical 模板迁移到标题缩放与图内阅读指南结构。"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
SHELL_ROOT = SKILL_ROOT / "assets" / "contracts" / "artifact-shell"
ADAPTIVE_ROOT = SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport"


def _matching_end(html: str, start: int, tag: str) -> int:
    token = re.compile(rf"</?{tag}\b[^>]*>", re.IGNORECASE)
    depth = 0
    for match in token.finditer(html, start):
        if match.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1
    raise ValueError(f"找不到 {tag} 的闭合标签")


def _remove_interaction_group(controls: str) -> str:
    match = re.search(
        r"<div\b[^>]*\bdata-reading-guide-group\s*=\s*([\"'])interaction\1[^>]*>",
        controls,
        re.IGNORECASE,
    )
    if not match:
        return controls
    end = _matching_end(controls, match.start(), "div")
    return controls[: match.start()] + controls[end:]


def _title_controls(controls: str) -> str:
    controls = _remove_interaction_group(controls)
    open_end = controls.find(">") + 1
    opening = controls[:open_end]
    opening = re.sub(
        r"\s+data-reading-guide-controls(?:\s*=\s*([\"']).*?\1)?",
        " data-artifact-shell-controls",
        opening,
        count=1,
        flags=re.IGNORECASE,
    )
    opening = re.sub(
        r"\s+data-interaction-capability\s*=\s*([\"']).*?\1",
        "",
        opening,
        flags=re.IGNORECASE,
    )
    return opening + controls[open_end:]


def _local_guide(guide: str, canvas_id: str, index: int) -> str:
    open_end = guide.find(">") + 1
    opening = guide[:open_end]
    opening = re.sub(
        r"\s+data-reading-guide-controls-state\s*=\s*([\"']).*?\1",
        "",
        opening,
        flags=re.IGNORECASE,
    )
    opening = opening[:-1] + f' data-reading-guide-for="{canvas_id}">'
    suffix = re.sub(r"[^a-zA-Z0-9_-]+", "-", canvas_id).strip("-") or f"canvas-{index}"
    body = guide[open_end:]
    body = re.sub(
        r'data-evidence-id="([^"]+)"',
        lambda match: f'data-evidence-id="{match.group(1)}-{suffix}"',
        body,
    )
    return opening + body


def _remove_reading_guide_headings(html: str) -> str:
    pattern = re.compile(
        r"<div\b[^>]*\bdata-reading-guide-heading(?:\s|=|>)[^>]*>",
        re.IGNORECASE,
    )
    while True:
        match = pattern.search(html)
        if not match:
            return html
        end = _matching_end(html, match.start(), "div")
        line_start = html.rfind("\n", 0, match.start()) + 1
        line_end = html.find("\n", end)
        if (
            not html[line_start : match.start()].strip()
            and line_end >= 0
            and not html[end:line_end].strip()
        ):
            html = html[:line_start] + html[line_end + 1 :]
        else:
            html = html[: match.start()] + html[end:]


def _sync_kernel(html: str, tag: str, marker: str, source: str) -> str:
    pattern = re.compile(
        rf'(<{tag}\s+{marker}="1">\n).*?(\n</{tag}>)',
        re.DOTALL,
    )
    rendered, count = pattern.subn(
        lambda match: match.group(1) + source.rstrip("\n") + match.group(2),
        html,
        count=1,
    )
    if count != 1:
        raise ValueError(f"缺少唯一 {marker} 内核")
    return rendered


def _structure_standalone_title(html: str) -> str:
    if 'data-code-review-package="1"' in html:
        return html
    if re.search(
        r'<h1\b(?=[^>]*\bdata-slot\s*=\s*(["\'])title\1)'
        r'(?=[^>]*\bdata-diagram-view-title\s*=\s*(["\'])1\2)[^>]*>',
        html,
        re.IGNORECASE,
    ):
        return html
    source = '<h1 data-slot="title">{{title}}</h1>'
    target = (
        '<h1 data-slot="title" data-diagram-view-title="1">'
        '<span data-diagram-view-type>{{diagram-type}}</span>'
        '<span data-diagram-view-separator aria-hidden="true"></span>'
        '<span data-diagram-view-subject>{{title}}</span></h1>'
    )
    if target in html:
        return html
    if source in html:
        return html.replace(source, target, 1)
    filled = re.search(
        r'<h1\b(?=[^>]*\bdata-slot\s*=\s*(["\'])title\1)[^>]*>(.*?)</h1>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not filled:
        raise ValueError("standalone artifact is missing its page title")
    rendered = (
        '<h1 data-slot="title" data-diagram-view-title="1">'
        '<span data-diagram-view-type>{{diagram-type}}</span>'
        '<span data-diagram-view-separator aria-hidden="true"></span>'
        f'<span data-diagram-view-subject>{filled.group(2)}</span></h1>'
    )
    return html[: filled.start()] + rendered + html[filled.end() :]


def _bind_standalone_guide_items(html: str) -> str:
    if (
        'data-code-review-package="1"' in html
        or re.search(r"<[^>]+\bdata-sequence-canvas(?:\s|=|>)", html, re.IGNORECASE)
    ):
        return html
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        opening = match.group(0)
        if "data-guide-relations" in opening:
            return opening
        counter += 1
        return opening[:-1] + f' data-guide-relations="{{{{reading-guide-relation-{counter:02d}}}}}">'

    return re.sub(
        r'<span\b(?=[^>]*\bdata-reading-guide-item(?:\s|=|>))'
        r'(?=[^>]*\bdata-line-kind\s*=)[^>]*>',
        replace,
        html,
        flags=re.IGNORECASE,
    )


def _ensure_persistent_control_mode(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        opening = match.group(0)
        if (
            "data-diagram-controls-mode" in opening
            or 'data-diagram-control-scope="embedded"' in opening
        ):
            return opening
        return opening[:-1] + ' data-diagram-controls-mode="persistent">'

    return re.sub(
        r"<(?:div|section)\b(?=[^>]*\bdata-diagram-canvas(?:\s|=|>))[^>]*>",
        replace,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _move_generic_guides_into_stages(html: str) -> str:
    if 'data-code-review-package="1"' in html:
        return html

    def grid_surface_opening(opening: str) -> str:
        if "data-diagram-grid-surface" in opening:
            return opening
        return opening[:-1] + ' data-diagram-grid-surface="1">'

    canvas_pattern = re.compile(
        r"<(?:div|section)\b(?=[^>]*\bdata-diagram-canvas(?:\s|=|>))[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    canvases = list(canvas_pattern.finditer(html))
    for canvas_match in reversed(canvases):
        canvas_end = _matching_end(html, canvas_match.start(), canvas_match.group(0)[1:].split(None, 1)[0])
        canvas = html[canvas_match.start() : canvas_end]
        guide_match = re.search(
            r"<section\b[^>]*\bdata-diagram-reading-guide\s*=\s*([\"'])1\1[^>]*>",
            canvas,
            re.IGNORECASE,
        )
        stage_match = re.search(
            r"<(?:div|section)\b[^>]*\bdata-diagram-stage(?:\s|=|>)[^>]*>",
            canvas,
            re.IGNORECASE | re.DOTALL,
        )
        if not guide_match or not stage_match:
            continue
        if guide_match.start() > stage_match.start():
            stage_tag = stage_match.group(0)[1:].split(None, 1)[0]
            stage_end = _matching_end(canvas, stage_match.start(), stage_tag)
            if guide_match.start() < stage_end:
                opening = grid_surface_opening(stage_match.group(0))
                canvas = (
                    canvas[: stage_match.start()]
                    + opening
                    + canvas[stage_match.end() :]
                )
                html = html[: canvas_match.start()] + canvas + html[canvas_end:]
            continue
        guide_end = _matching_end(canvas, guide_match.start(), "section")
        guide = canvas[guide_match.start() : guide_end]
        canvas = canvas[: guide_match.start()] + canvas[guide_end:]
        stage_match = re.search(
            r"<(?:div|section)\b[^>]*\bdata-diagram-stage(?:\s|=|>)[^>]*>",
            canvas,
            re.IGNORECASE | re.DOTALL,
        )
        if not stage_match:
            raise ValueError("diagram canvas lost its stage during guide migration")
        opening = grid_surface_opening(stage_match.group(0))
        canvas = (
            canvas[: stage_match.start()]
            + opening
            + canvas[stage_match.end() :]
        )
        insert_at = stage_match.start() + len(opening)
        canvas = (
            canvas[:insert_at]
            + "\n    "
            + guide.strip()
            + "\n"
            + canvas[insert_at:]
        )
        html = html[: canvas_match.start()] + canvas + html[canvas_end:]
    return html


def _mark_sequence_guide_surfaces(html: str) -> str:
    canvas_pattern = re.compile(
        r"<(?:div|section)\b(?=[^>]*\bdata-sequence-canvas(?:\s|=|>))[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    for canvas_match in reversed(list(canvas_pattern.finditer(html))):
        canvas_tag = canvas_match.group(0)[1:].split(None, 1)[0]
        canvas_end = _matching_end(html, canvas_match.start(), canvas_tag)
        canvas = html[canvas_match.start() : canvas_end]
        if not re.search(
            r"<section\b[^>]*\bdata-diagram-reading-guide\s*=\s*([\"'])1\1[^>]*>",
            canvas,
            re.IGNORECASE,
        ):
            continue
        opening = canvas_match.group(0)
        if "data-diagram-grid-surface" in opening:
            continue
        opening = opening[:-1] + ' data-diagram-grid-surface="1">'
        html = html[: canvas_match.start()] + opening + html[canvas_match.end() :]
    return html


def _migrate_template(
    path: Path,
    shell_css: str,
    shell_js: str,
    adaptive_css: str,
    adaptive_js: str,
) -> bool:
    original = path.read_text(encoding="utf-8")
    html = original

    guide_match = re.search(
        r"<section\b[^>]*\bdata-diagram-reading-guide\s*=\s*([\"'])1\1[^>]*>",
        html,
        re.IGNORECASE,
    )
    body_start = html.find("<body")
    body = html[body_start:] if body_start >= 0 else html
    title_controls_present = "data-artifact-shell-controls" in body
    if guide_match and not title_controls_present:
        guide_end = _matching_end(html, guide_match.start(), "section")
        guide = html[guide_match.start() : guide_end]

        controls_match = re.search(
            r"<div\b[^>]*\bdata-reading-guide-controls(?:\s|=|>)",
            guide,
            re.IGNORECASE,
        )
        if not controls_match:
            raise ValueError(f"{path} 缺少旧缩放容器")
        controls_end = _matching_end(guide, controls_match.start(), "div")
        controls = guide[controls_match.start() : controls_end]
        guide_without_controls = (
            guide[: controls_match.start()] + guide[controls_end:]
        )

        html = html[: guide_match.start()] + html[guide_end:]
        title_match = re.search(
            r"<header\b[^>]*\bdata-artifact-shell-title\s*=\s*([\"'])1\1[^>]*>",
            html,
            re.IGNORECASE,
        )
        if not title_match:
            raise ValueError(f"{path} 缺少标题区域")
        title_end = _matching_end(html, title_match.start(), "header")
        title_close = html.rfind("</header>", title_match.start(), title_end)
        html = (
            html[:title_close]
            + "\n    "
            + _title_controls(controls).strip()
            + "\n  "
            + html[title_close:]
        )

        canvas_pattern = re.compile(
            r"<(?:div|section)\b(?=[^>]*\bdata-(?:diagram|sequence)-canvas(?:\s|=|>))[^>]*>",
            re.IGNORECASE | re.DOTALL,
        )
        canvases = list(canvas_pattern.finditer(html))
        if not canvases:
            raise ValueError(f"{path} 缺少主画布")
        insertions: list[tuple[int, str]] = []
        for index, canvas in enumerate(canvases, start=1):
            opening = canvas.group(0)
            identity = re.search(
                r'\bdata-(?:diagram-id|sequence-id)\s*=\s*"([^"]+)"',
                opening,
                re.IGNORECASE,
            )
            if not identity:
                raise ValueError(f"{path} 的第 {index} 张画布缺少稳定标识")
            local = _local_guide(guide_without_controls, identity.group(1), index)
            insertions.append((canvas.end(), "\n    " + local.strip() + "\n"))
        for offset, content in reversed(insertions):
            html = html[:offset] + content + html[offset:]

    html = _remove_reading_guide_headings(html)
    html = _structure_standalone_title(html)
    html = _bind_standalone_guide_items(html)
    html = _move_generic_guides_into_stages(html)
    html = _mark_sequence_guide_surfaces(html)
    html = html.replace(
        'data-diagram-controls-mode="overflow"',
        'data-diagram-controls-mode="persistent"',
    )
    html = _ensure_persistent_control_mode(html)
    html = html.replace(
        "if (toolbar) toolbar.hidden = !overflowX || !supportsZoom;",
        "if (toolbar) toolbar.hidden = !supportsZoom;",
    )
    html = _sync_kernel(
        html,
        "style",
        "data-artifact-shell-kernel",
        shell_css,
    )
    html = _sync_kernel(
        html,
        "script",
        "data-artifact-shell-preview-kernel",
        shell_js,
    )
    if 'data-adaptive-viewport-kernel="1"' in html:
        html = _sync_kernel(
            html,
            "style",
            "data-adaptive-viewport-kernel",
            adaptive_css,
        )
        html = _sync_kernel(
            html,
            "script",
            "data-adaptive-viewport-kernel",
            adaptive_js,
        )
    html = "\n".join(line.rstrip() for line in html.splitlines())
    if original.endswith("\n"):
        html += "\n"
    if html == original:
        return False
    path.write_text(html, encoding="utf-8")
    return True


def _sync_code_review_package(path: Path) -> bool:
    module_path = SKILL_ROOT / "scripts" / "vibe_diagram_scaffold.py"
    spec = importlib.util.spec_from_file_location(
        "vibe_diagram_scaffold_for_shell_migration",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载代码审查生成器")
    module = importlib.util.module_from_spec(spec)
    original_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = original_bytecode_setting

    original = path.read_text(encoding="utf-8")
    html = module._render_code_review_package(module._canonical_review_spec())
    if html == original:
        return False
    path.write_text(html, encoding="utf-8")
    return True


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        action="append",
        type=Path,
        help="额外迁移一份已生成的单文件 HTML，可重复指定",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    shell_css = (SHELL_ROOT / "v1.css").read_text(encoding="utf-8")
    shell_js = (SHELL_ROOT / "v1.js").read_text(encoding="utf-8")
    adaptive_css = (ADAPTIVE_ROOT / "v1.css").read_text(encoding="utf-8")
    adaptive_js = (ADAPTIVE_ROOT / "v1.js").read_text(encoding="utf-8")
    changed = 0
    targets = (
        [path.resolve() for path in args.artifact]
        if args.artifact
        else sorted(TEMPLATE_ROOT.rglob("*.html"))
    )
    for path in targets:
        if not path.exists():
            raise FileNotFoundError(path)
        changed += int(
            _migrate_template(
                path,
                shell_css,
                shell_js,
                adaptive_css,
                adaptive_js,
            )
        )
        if 'data-code-review-package="1"' in path.read_text(encoding="utf-8"):
            changed += int(_sync_code_review_package(path))
    print(f"已完成 {changed} 次外壳或代码审查内核更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
