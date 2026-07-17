from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


CONTENT_ATTRIBUTES = {
    "aria-label",
    "aria-description",
    "title",
    "alt",
    "data-slot",
    "data-body",
    "data-label",
    "data-description",
    "data-content",
    "data-details",
}
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
MACRO_PATTERN = re.compile(r"\{\{\s*([^{}\s]+?)\s*\}\}")


class _TemplateLayoutParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: List[Sequence[object]] = []
        self.root_count = 0
        self._stack: List[str] = []

    @staticmethod
    def _is_root(tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> bool:
        if tag != "section":
            return False
        class_value = next((value or "" for name, value in attrs if name == "class"), "")
        return "template-layout" in class_value.split()

    @staticmethod
    def _attrs(attrs: Sequence[Tuple[str, Optional[str]]]) -> Tuple[Tuple[str, str], ...]:
        normalized = []
        for name, value in attrs:
            normalized_value = "_" if name in CONTENT_ATTRIBUTES or name.startswith("aria-") else value or ""
            normalized.append((name, normalized_value))
        return tuple(sorted(normalized))

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if self._is_root(tag, attrs):
            self.root_count += 1
            if self._stack:
                raise ValueError("template-layout roots must not be nested")
            self._stack.append(tag)
            return
        if not self._stack:
            return
        self.events.append(("start", tag, self._attrs(attrs)))
        if tag not in VOID_ELEMENTS:
            self._stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if self._is_root(tag, attrs):
            self.root_count += 1
            raise ValueError("template-layout root must not be self-closing")
        if self._stack:
            self.events.append(("empty", tag, self._attrs(attrs)))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return
        if self._stack[-1] != tag:
            raise ValueError(f"mismatched closing tag: expected {self._stack[-1]}, got {tag}")
        if len(self._stack) > 1:
            self.events.append(("end", tag))
        self._stack.pop()

    def finish(self) -> None:
        if self.root_count != 1:
            raise ValueError(f"expected exactly one template-layout root, found {self.root_count}")
        if self._stack:
            raise ValueError("template-layout root is not closed")


def template_structure_signature(html: str) -> str:
    """Hash template-layout DOM events while ignoring human-facing text."""

    parser = _TemplateLayoutParser()
    parser.feed(html)
    parser.close()
    parser.finish()
    payload = json.dumps(parser.events, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _SlotMacroParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data_slots: List[str] = []
        self.macros: List[str] = []
        self.slot_macro_pairs: List[Dict[str, str]] = []
        self._stack: List[Tuple[str, str]] = []

    def _record_macros(self, value: str, slot: str) -> None:
        for match in MACRO_PATTERN.finditer(value):
            macro = match.group(1)
            self.macros.append(macro)
            self.slot_macro_pairs.append({"macro": macro, "slot": slot})

    def _start(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]], push: bool) -> None:
        parent_slot = self._stack[-1][1] if self._stack else ""
        own_slot = next((value or "" for name, value in attrs if name == "data-slot"), "")
        current_slot = own_slot or parent_slot
        if own_slot:
            self.data_slots.append(own_slot)
        for _, value in attrs:
            if value:
                self._record_macros(value, current_slot)
        if push and tag not in VOID_ELEMENTS:
            self._stack.append((tag, current_slot))

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag.lower(), attrs, push=True)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag.lower(), attrs, push=False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in VOID_ELEMENTS:
            return
        if not self._stack:
            raise ValueError(f"unexpected closing tag: {tag}")
        if self._stack[-1][0] != tag:
            raise ValueError(f"mismatched closing tag: expected {self._stack[-1][0]}, got {tag}")
        self._stack.pop()

    def handle_data(self, data: str) -> None:
        slot = self._stack[-1][1] if self._stack else ""
        self._record_macros(data, slot)

    def finish(self) -> None:
        if self._stack:
            raise ValueError(f"unclosed tag: {self._stack[-1][0]}")


def template_slots_macros_and_pairs(
    html: str,
) -> Tuple[List[str], List[str], List[Dict[str, str]]]:
    parser = _SlotMacroParser()
    parser.feed(html)
    parser.close()
    parser.finish()
    macros = [match.group(1) for match in MACRO_PATTERN.finditer(html)]
    return parser.data_slots, macros, parser.slot_macro_pairs


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
