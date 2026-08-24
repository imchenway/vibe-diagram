#!/usr/bin/env python3
"""Initialize a content-neutral, self-contained Vibe Diagram artifact."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SHELL_CSS = SKILL_ROOT / "assets" / "shell" / "v1.css"
SHELL_JS = SKILL_ROOT / "assets" / "shell" / "v1.js"
LANG_RE = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*")
RETIRED_FLAGS = {"--spec", "--template", "--review-kind", "--review-spec", "--standard"}


class ScaffoldError(RuntimeError):
    pass


def _retired_flag(argv: list[str]) -> str | None:
    for value in argv:
        flag = value.split("=", 1)[0]
        if flag in RETIRED_FLAGS:
            return flag
    return None


def _read_asset(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ScaffoldError(f"could not read shared shell asset {path.name}: {exc}") from exc


def _manifest(title: str, language: str) -> str:
    payload = {
        "$schema": "vibe-diagram/artifact-manifest@1",
        "artifactId": "replace-with-stable-id",
        "language": language,
        "title": title,
        "audience": ["product-manager"],
        "questions": [],
        "criticalFacts": [],
        "views": [],
        "evidence": [],
        "extensions": {},
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).replace("</", "<\\/")


def _shell_copy(language: str) -> dict[str, str]:
    if language.lower().startswith("zh"):
        return {"zoom_label": "图形缩放", "fit": "适配"}
    return {"zoom_label": "Diagram zoom", "fit": "Fit"}


def render(title: str, language: str, css: str, script: str) -> str:
    safe_title = html.escape(title, quote=True)
    safe_language = html.escape(language, quote=True)
    copy = _shell_copy(language)
    return f'''<!doctype html>
<html lang="{safe_language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style data-vd-shell="1">
{css.rstrip()}
  </style>
  <style data-vd-author-style="1">
  /* Author the visual grammar for the current evidence here. */
  </style>
</head>
<body>
  <div data-vd-artifact="1">
    <header data-vd-title-region>
      <div data-vd-title-copy>
        <h1>{safe_title}</h1>
        <p data-vd-summary data-vd-scaffold-empty></p>
      </div>
      <div data-vd-controls role="group" aria-label="{html.escape(copy['zoom_label'], quote=True)}" data-vd-zoom-request="fit">
        <button type="button" data-vd-zoom="0.75" aria-pressed="false">75%</button>
        <button type="button" data-vd-zoom="0.9" aria-pressed="false">90%</button>
        <button type="button" data-vd-zoom="1" aria-pressed="false">100%</button>
        <button type="button" data-vd-zoom="fit" aria-pressed="true">{html.escape(copy['fit'])}</button>
      </div>
    </header>
    <main data-vd-content data-vd-scaffold-empty>
      <!-- Directly author one or more semantic HTML/SVG views here. -->
    </main>
    <output data-vd-audit-output aria-live="polite"></output>
  </div>
  <script id="vibe-diagram-manifest" type="application/json">
{_manifest(title, language)}
  </script>
  <script data-vd-shell="1">
{script.rstrip()}
  </script>
</body>
</html>
'''


def parse_args(argv: list[str]) -> argparse.Namespace:
    retired = _retired_flag(argv)
    if retired:
        raise ScaffoldError(
            f"{retired} belongs to the retired template/Contract compiler. "
            "Initialize a blank artifact and author the final HTML/SVG directly."
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new artifact path; existing files are refused")
    parser.add_argument("--title", required=True, help="localized artifact title")
    parser.add_argument("--lang", required=True, help="BCP 47-style language tag, for example zh-CN")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(list(sys.argv[1:] if argv is None else argv))
        title = args.title.strip()
        if not title or any(ord(char) < 32 for char in title):
            raise ScaffoldError("--title must be non-empty visible text")
        language = args.lang.strip()
        if LANG_RE.fullmatch(language) is None:
            raise ScaffoldError("--lang must be a simple BCP 47-style language tag")
        output = Path(args.output).expanduser().resolve()
        if output.exists():
            raise ScaffoldError(f"refusing to overwrite existing output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            render(title, language, _read_asset(SHELL_CSS), _read_asset(SHELL_JS)),
            encoding="utf-8",
            newline="\n",
        )
        print(str(output))
        return 0
    except ScaffoldError as exc:
        print(f"vibe-diagram scaffold failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"vibe-diagram scaffold failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
