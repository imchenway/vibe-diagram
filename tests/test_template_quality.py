from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

from tests.test_canonical_inventory import EXPECTED_TEMPLATE_PATHS, TEMPLATE_ROOT


HAN_PATTERN = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\U00020000-\U0002a6df\U0002a700-\U0002b73f"
    r"\U0002b740-\U0002b81f\U0002b820-\U0002ceaf"
    r"\U0002ceb0-\U0002ebef\U0002f800-\U0002fa1f"
    r"\U00030000-\U0003134f\U00031350-\U000323af]"
)
CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_ESCAPE_PATTERN = re.compile(r"\\(?:([0-9a-fA-F]{1,6})\s?|([^\r\n\f]))")
RUNTIME_NETWORK_PATTERNS = (
    re.compile(r"\bfetch\b"),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\b"),
    re.compile(r"\bEventSource\b"),
    re.compile(r"\bsendBeacon\b"),
    re.compile(r"\bimportScripts\b"),
    re.compile(r"\bimport\s*\("),
    re.compile(r"\bWorker\b"),
    re.compile(r"\b(?:eval|Function)\b"),
    re.compile(r"\bnew\s+Image\s*\(", re.IGNORECASE),
    re.compile(
        r"(?:\.\s*(?:src|srcset|href|poster|action|formaction)"
        r"|\[\s*['\"](?:src|srcset|href|poster|action|formaction)['\"]\s*\])\s*=",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:window|document|self|globalThis)\s*"
        r"(?:\.\s*(?:location|open)|\[\s*['\"](?:location|open)['\"]\s*\])",
        re.IGNORECASE,
    ),
    re.compile(r"\blocation\s*\.\s*(?:assign|replace)\s*\(", re.IGNORECASE),
    re.compile(r"https?:|(?<!:)//", re.IGNORECASE),
)
RESOURCE_ATTRIBUTES = {"src", "srcset", "poster", "action", "formaction"}
LINK_ATTRIBUTES = {"href", "xlink:href"}


def _allowed_embedded_reference(value: str) -> bool:
    value = value.strip()
    return not value or value.startswith("#") or value.startswith("data:")


def _decode_css_escapes(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group(1):
            codepoint = int(match.group(1), 16)
            return chr(codepoint) if codepoint and codepoint <= 0x10FFFF else "\ufffd"
        return match.group(2) or "\ufffd"

    return CSS_ESCAPE_PATTERN.sub(replace, value)


def _decode_javascript_escapes(value: str) -> str:
    pattern = re.compile(
        r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})"
    )

    def replace(match: re.Match[str]) -> str:
        codepoint = int(next(group for group in match.groups() if group is not None), 16)
        return chr(codepoint) if codepoint <= 0x10FFFF else "\ufffd"

    return pattern.sub(replace, value)


class _QualityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: List[str] = []
        self.has_doctype = False
        self.has_html_en = False
        self.has_viewport = False
        self.has_main = False
        self.has_h1 = False
        self._script_depth = 0
        self._style_depth = 0
        self.scripts: List[str] = []
        self.styles: List[str] = []

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        names = [name.lower() for name, _ in attrs]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            self.errors.append(f"duplicate attributes on {tag}: {', '.join(duplicates)}")
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        if tag == "html" and attrs_map.get("lang") == "en":
            self.has_html_en = True
        if tag == "meta" and attrs_map.get("name", "").lower() == "viewport":
            self.has_viewport = True
        if tag == "meta" and attrs_map.get("http-equiv", "").strip().casefold() == "refresh":
            self.errors.append("meta refresh navigation is forbidden")
        self.has_main = self.has_main or tag == "main"
        self.has_h1 = self.has_h1 or tag == "h1"
        if tag in {"iframe", "object", "embed"}:
            self.errors.append(f"embedded container is forbidden: {tag}")
        for name, value in attrs_map.items():
            if name == "ping" and value.strip():
                self.errors.append("ping navigation is forbidden")
            elif name == "srcset" and value.strip():
                self.errors.append("srcset is forbidden because candidate lists are not self-contained")
                continue
            if name in RESOURCE_ATTRIBUTES and not _allowed_embedded_reference(value):
                self.errors.append(f"external or relative resource is forbidden: {name}={value}")
            if name in LINK_ATTRIBUTES and not _allowed_embedded_reference(value):
                self.errors.append(f"external or relative link is forbidden: {name}={value}")
            if name == "style":
                self.styles.append(value)
        if tag == "script":
            if attrs_map.get("type", "").strip().lower() == "module":
                self.errors.append("JavaScript module loading is forbidden")
            self._script_depth += 1
        if tag == "style":
            self._style_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script":
            self._script_depth -= 1
        if tag == "style":
            self._style_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._script_depth:
            self.scripts.append(data)
        if self._style_depth:
            self.styles.append(data)

    def finish(self) -> None:
        for css in self.styles:
            normalized_css = _decode_css_escapes(css)
            if re.search(r"@import\b", normalized_css, re.IGNORECASE):
                self.errors.append("CSS @import is forbidden")
            if re.search(r"(?:-webkit-)?image-set\s*\(", normalized_css, re.IGNORECASE):
                self.errors.append("CSS image-set is forbidden")
            for match in CSS_URL_PATTERN.finditer(normalized_css):
                if not _allowed_embedded_reference(match.group(2)):
                    self.errors.append(f"external or relative CSS url is forbidden: {match.group(2)}")
        script = _decode_javascript_escapes("\n".join(self.scripts))
        for pattern in RUNTIME_NETWORK_PATTERNS:
            if pattern.search(script):
                self.errors.append(f"runtime network API is forbidden: {pattern.pattern}")


class TemplateQualityTests(unittest.TestCase):
    def test_han_gate_covers_ideographic_zero_and_compatibility_supplement(self) -> None:
        self.assertIsNotNone(HAN_PATTERN.search("\u3007"))
        self.assertIsNotNone(HAN_PATTERN.search("\U0002f800"))

    def test_computed_commented_and_escaped_network_apis_are_rejected(self) -> None:
        samples = (
            '<script>globalThis["fetch"]("./x")</script>',
            '<script>fetch/*comment*/("./x")</script>',
            r'<script>window["f\u0065tch"]("./x")</script>',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                parser = _QualityParser()
                parser.feed(sample)
                parser.close()
                parser.finish()
                self.assertTrue(parser.errors)

    def test_non_network_computed_global_property_is_allowed(self) -> None:
        parser = _QualityParser()
        parser.feed('<script>globalThis["theme"]="dark"</script>')
        parser.close()
        parser.finish()
        self.assertEqual([], parser.errors)

    def test_runtime_resource_navigation_meta_refresh_and_ping_are_rejected(self) -> None:
        samples = (
            '<script>new Image().src="./pixel.png"</script>',
            '<script>const node={};node.src="./pixel.png"</script>',
            '<script>const node={};node["src"]="./pixel.png"</script>',
            '<script>window.location="./next.html"</script>',
            '<script>window["location"]="./next.html"</script>',
            '<script>document.location="./next.html"</script>',
            '<script>location.assign("./next.html")</script>',
            '<script>location.replace("./next.html")</script>',
            '<script>window.open("./next.html")</script>',
            '<script>globalThis["open"]("./next.html")</script>',
            '<meta http-equiv="refresh" content="0;url=./next.html">',
            '<a href="#ok" ping="./audit">Local</a>',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                parser = _QualityParser()
                parser.feed(sample)
                parser.close()
                parser.finish()
                self.assertTrue(parser.errors)

    def test_css_escaped_and_image_set_resources_are_rejected(self) -> None:
        samples = (
            r'<style>@\69mport "./dependency.css";</style>',
            r'<style>.node{background:\75rl("./asset.png")}</style>',
            r'<style>.node{background-image:image-set("./asset.png" 1x)}</style>',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                parser = _QualityParser()
                parser.feed(sample)
                parser.close()
                parser.finish()
                self.assertTrue(parser.errors)

    def test_duplicate_resource_attributes_are_rejected(self) -> None:
        parser = _QualityParser()
        parser.feed('<img src="./remote.png" src="data:image/gif;base64,AAAA">')
        parser.close()
        parser.finish()
        self.assertTrue(any("duplicate" in error.lower() for error in parser.errors))

    def test_srcset_with_embedded_relative_candidate_is_rejected(self) -> None:
        parser = _QualityParser()
        parser.feed('<img srcset="data:image/svg+xml,%3Csvg%3E 1x, ./remote.png 2x">')
        parser.close()
        parser.finish()
        self.assertTrue(any("srcset" in error for error in parser.errors))

    def test_static_module_script_is_rejected(self) -> None:
        parser = _QualityParser()
        parser.feed('<script type="module">import "./dependency.js";</script>')
        parser.close()
        parser.finish()
        self.assertTrue(any("module" in error.lower() for error in parser.errors))

    def test_templates_are_complete_english_single_files(self) -> None:
        for relative in EXPECTED_TEMPLATE_PATHS:
            with self.subTest(relative=relative):
                raw = (TEMPLATE_ROOT / relative).read_bytes()
                html = raw.decode("utf-8")
                parser = _QualityParser()
                parser.feed(html)
                parser.close()
                parser.finish()
                self.assertTrue(parser.has_doctype)
                self.assertTrue(parser.has_html_en)
                self.assertTrue(parser.has_viewport)
                self.assertTrue(parser.has_main)
                self.assertTrue(parser.has_h1)
                self.assertIsNone(HAN_PATTERN.search(html))
                self.assertNotIn("http://", html.lower())
                self.assertNotIn("https://", html.lower())
                self.assertNotIn("//cdn", html.lower())
                self.assertEqual([], parser.errors)

    def test_canonical_tree_has_no_symlinks_or_cache_files(self) -> None:
        skill_root = TEMPLATE_ROOT.parents[2]
        bad = []
        if skill_root.exists():
            for path in skill_root.rglob("*"):
                if path.is_symlink() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                    bad.append(path.relative_to(skill_root).as_posix())
        self.assertEqual([], sorted(bad))


if __name__ == "__main__":
    unittest.main()
