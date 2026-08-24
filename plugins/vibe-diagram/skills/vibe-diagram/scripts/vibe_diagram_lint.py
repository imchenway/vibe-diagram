#!/usr/bin/env python3
"""Validate a model-authored, self-contained Vibe Diagram HTML artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse


SKILL_ROOT = Path(__file__).resolve().parents[1]
OUTCOMES_PATH = SKILL_ROOT / "contracts" / "family-outcomes.json"
ID_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\[TODO(?::|\])|replace-with-stable-id", re.IGNORECASE)
RETIRED_RE = re.compile(
    r"DiagramDocumentSpec|data-diagram-spec|data-template-id|data-template-family|"
    r"assets/templates/|layout-slot-|vibe_diagram_render|vibe_diagram_spec|data-vd-design-summary",
    re.IGNORECASE,
)
REMOTE_CSS_RE = re.compile(r"(?:@import\s+|url\(\s*['\"]?)(?:https?:)?//", re.IGNORECASE)
NETWORK_SCRIPT_RE = re.compile(
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(|"
    r"\bimport\s*\(\s*['\"]https?://",
    re.IGNORECASE,
)
RESOURCE_ATTRS = {"src", "srcset", "poster", "action", "formaction"}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
}
STATUSES = {"observed", "inferred", "proposed", "unresolved", "verified"}
PRIORITIES = {"critical", "important", "supporting"}
VIEW_ROLES = {"primary", "supporting", "appendix"}
GEOMETRY_TAGS = {"path", "line", "polyline"}


class LintError(RuntimeError):
    pass


@dataclass
class Element:
    tag: str
    attrs: Dict[str, str]
    line: int
    hidden: bool
    view_id: str = ""
    text_parts: List[str] = field(default_factory=list)

    @property
    def identifier(self) -> str:
        return self.attrs.get("id", "")

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())


@dataclass
class StackEntry:
    element: Element
    hides_children: bool


class ArtifactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doctype = False
        self.elements: List[Element] = []
        self.stack: List[StackEntry] = []
        self.ids: Dict[str, Element] = {}
        self.errors: List[str] = []
        self.manifest_chunks: List[str] = []
        self.manifest_count = 0
        self.style_chunks: List[str] = []
        self.script_chunks: List[str] = []
        self.manifest_depth = 0
        self.style_depth = 0
        self.script_depth = 0

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            if self.doctype:
                self.errors.append("duplicate HTML doctype")
            self.doctype = True

    def _start(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]], closed: bool) -> None:
        tag = tag.lower()
        names = [name.lower() for name, _ in attrs]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            self.errors.append(f"line {self.getpos()[0]} has duplicate attributes: {', '.join(duplicates)}")
        values = {name.lower(): (value or "") for name, value in attrs}
        inherited_hidden = any(entry.hides_children for entry in self.stack)
        own_hidden = (
            "hidden" in values
            or values.get("aria-hidden", "").lower() == "true"
            or "display:none" in values.get("style", "").replace(" ", "").lower()
            or "visibility:hidden" in values.get("style", "").replace(" ", "").lower()
        )
        view_id = values.get("data-vd-view", "")
        if not view_id:
            for entry in reversed(self.stack):
                if entry.element.view_id:
                    view_id = entry.element.view_id
                    break
        element = Element(tag, values, self.getpos()[0], inherited_hidden or own_hidden, view_id)
        self.elements.append(element)
        identifier = values.get("id", "")
        if identifier:
            if identifier in self.ids:
                self.errors.append(f"duplicate element id: {identifier}")
            else:
                self.ids[identifier] = element

        is_manifest = tag == "script" and values.get("id") == "vibe-diagram-manifest"
        if is_manifest:
            self.manifest_count += 1
            if values.get("type") != "application/json":
                self.errors.append("manifest script must use type=application/json")
            self.manifest_depth += 1
        elif tag == "style":
            self.style_depth += 1
        elif tag == "script":
            if values.get("src"):
                self.errors.append("external script src is forbidden")
            self.script_depth += 1

        if not closed and tag not in VOID_ELEMENTS:
            hides_children = element.hidden or (tag == "details" and "open" not in values) or (tag == "dialog" and "open" not in values)
            self.stack.append(StackEntry(element, hides_children))

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag, attrs, True)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script":
            if self.manifest_depth:
                self.manifest_depth -= 1
            elif self.script_depth:
                self.script_depth -= 1
        elif tag == "style" and self.style_depth:
            self.style_depth -= 1
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].element.tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        for entry in self.stack:
            entry.element.text_parts.append(data)
        if self.manifest_depth:
            self.manifest_chunks.append(data)
        elif self.style_depth:
            self.style_chunks.append(data)
        elif self.script_depth:
            self.script_chunks.append(data)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LintError(f"could not read contract {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise LintError(f"contract {path.name} must be a JSON object")
    return value


def _non_empty(value: Any, label: str, errors: List[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return ""
    return value.strip()


def _identifier(value: Any, label: str, errors: List[str]) -> str:
    text = _non_empty(value, label, errors)
    if text and ID_RE.fullmatch(text) is None:
        errors.append(f"{label} must be a stable kebab-case identifier")
    return text


def _records(value: Any, label: str, errors: List[str], *, non_empty: bool = False) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        errors.append(f"{label} must be an array of objects")
        return []
    if non_empty and not value:
        errors.append(f"{label} must not be empty")
    return list(value)


def _unique_record_ids(records: Sequence[Mapping[str, Any]], label: str, errors: List[str]) -> set[str]:
    result: set[str] = set()
    for index, record in enumerate(records):
        identifier = _identifier(record.get("id"), f"{label}[{index}].id", errors)
        if identifier in result:
            errors.append(f"duplicate {label} id: {identifier}")
        if identifier:
            result.add(identifier)
    return result


def _string_list(value: Any, label: str, errors: List[str], *, non_empty: bool = False) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{label} must be an array of non-empty strings")
        return []
    result = [item.strip() for item in value]
    if non_empty and not result:
        errors.append(f"{label} must not be empty")
    if len(set(result)) != len(result):
        errors.append(f"{label} must not contain duplicate values")
    return result


def _validate_manifest(
    manifest: Any,
    parser: ArtifactParser,
    families: Mapping[str, Any],
) -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(manifest, dict):
        return ["ArtifactManifest must be a JSON object"], {}
    expected = {"$schema", "artifactId", "language", "title", "audience", "questions", "criticalFacts", "views", "evidence", "extensions"}
    if set(manifest) != expected:
        errors.append("ArtifactManifest must contain exactly the v1 core fields; extensions belong under extensions")
    if manifest.get("$schema") != "vibe-diagram/artifact-manifest@1":
        errors.append("ArtifactManifest $schema must be vibe-diagram/artifact-manifest@1")
    _identifier(manifest.get("artifactId"), "artifactId", errors)
    language = _non_empty(manifest.get("language"), "language", errors)
    title = _non_empty(manifest.get("title"), "title", errors)
    audience = _string_list(manifest.get("audience"), "audience", errors, non_empty=True)
    if "product-manager" not in audience:
        errors.append("ArtifactManifest audience must contain product-manager")
    if not isinstance(manifest.get("extensions"), dict):
        errors.append("extensions must be an object")

    questions = _records(manifest.get("questions"), "questions", errors, non_empty=True)
    facts = _records(manifest.get("criticalFacts"), "criticalFacts", errors, non_empty=True)
    views = _records(manifest.get("views"), "views", errors, non_empty=True)
    evidence = _records(manifest.get("evidence"), "evidence", errors)
    question_ids = _unique_record_ids(questions, "questions", errors)
    fact_ids = _unique_record_ids(facts, "criticalFacts", errors)
    view_ids = _unique_record_ids(views, "views", errors)
    evidence_ids = _unique_record_ids(evidence, "evidence", errors)
    del question_ids

    primary_view_elements: set[str] = set()
    declared_dom_views: set[str] = set()
    for index, view in enumerate(views):
        expected_keys = {"id", "family", "role", "elementId"}
        if set(view) != expected_keys:
            errors.append(f"views[{index}] must contain exactly id, family, role, and elementId")
        family = _identifier(view.get("family"), f"views[{index}].family", errors)
        if family and family not in families:
            errors.append(f"views[{index}] uses unsupported family: {family}")
        role = view.get("role")
        if role not in VIEW_ROLES:
            errors.append(f"views[{index}].role is invalid")
        element_id = _non_empty(view.get("elementId"), f"views[{index}].elementId", errors)
        element = parser.ids.get(element_id)
        if not element:
            errors.append(f"views[{index}] references missing element: {element_id}")
        else:
            declared_dom_views.add(element.attrs.get("data-vd-view", ""))
            if element.attrs.get("data-vd-view") != view.get("id"):
                errors.append(f"view {view.get('id')} does not match its DOM data-vd-view")
            if element.attrs.get("data-vd-family") != family:
                errors.append(f"view {view.get('id')} family does not match its DOM marker")
            if element.attrs.get("data-vd-view-role") != role:
                errors.append(f"view {view.get('id')} role does not match its DOM marker")
            if role == "primary":
                primary_view_elements.add(element_id)
    if not primary_view_elements:
        errors.append("ArtifactManifest requires at least one primary view")
    dom_view_ids = {element.attrs["data-vd-view"] for element in parser.elements if element.attrs.get("data-vd-view")}
    if dom_view_ids != view_ids or declared_dom_views != view_ids:
        errors.append("ArtifactManifest views and DOM data-vd-view markers must match exactly")

    def critical_target(target: str, label: str) -> None:
        element = parser.ids.get(target)
        if not element:
            errors.append(f"{label} references missing element: {target}")
            return
        view = next((item for item in views if item.get("id") == element.view_id), None)
        if element.hidden or not view or view.get("role") != "primary":
            errors.append(f"{label} target must be statically visible in a primary view: {target}")
        if "data-vd-critical" not in element.attrs:
            errors.append(f"{label} target must declare data-vd-critical: {target}")

    critical_questions = 0
    for index, question in enumerate(questions):
        if set(question) != {"id", "text", "priority", "answeredBy"}:
            errors.append(f"questions[{index}] has an invalid field set")
        _non_empty(question.get("text"), f"questions[{index}].text", errors)
        priority = question.get("priority")
        if priority not in PRIORITIES:
            errors.append(f"questions[{index}].priority is invalid")
        targets = _string_list(question.get("answeredBy"), f"questions[{index}].answeredBy", errors, non_empty=True)
        if priority == "critical":
            critical_questions += 1
            for target in targets:
                critical_target(target, f"questions[{index}]")
        else:
            for target in targets:
                if target not in parser.ids:
                    errors.append(f"questions[{index}] references missing element: {target}")
    if critical_questions == 0:
        errors.append("ArtifactManifest requires at least one critical question")

    for index, fact in enumerate(facts):
        if set(fact) != {"id", "statement", "status", "visibleIn", "evidenceIds"}:
            errors.append(f"criticalFacts[{index}] has an invalid field set")
        _non_empty(fact.get("statement"), f"criticalFacts[{index}].statement", errors)
        if fact.get("status") not in STATUSES:
            errors.append(f"criticalFacts[{index}].status is invalid")
        targets = _string_list(fact.get("visibleIn"), f"criticalFacts[{index}].visibleIn", errors, non_empty=True)
        for target in targets:
            critical_target(target, f"criticalFacts[{index}]")
        refs = _string_list(fact.get("evidenceIds"), f"criticalFacts[{index}].evidenceIds", errors, non_empty=True)
        for evidence_id in refs:
            if evidence_id not in evidence_ids:
                errors.append(f"criticalFacts[{index}] references unknown evidence: {evidence_id}")

    for index, item in enumerate(evidence):
        if set(item) != {"id", "status", "sourceKind", "source", "supports"}:
            errors.append(f"evidence[{index}] has an invalid field set")
        if item.get("status") not in STATUSES:
            errors.append(f"evidence[{index}].status is invalid")
        _non_empty(item.get("sourceKind"), f"evidence[{index}].sourceKind", errors)
        _non_empty(item.get("source"), f"evidence[{index}].source", errors)
        supports = _string_list(item.get("supports"), f"evidence[{index}].supports", errors, non_empty=True)
        for fact_id in supports:
            if fact_id not in fact_ids:
                errors.append(f"evidence[{index}] supports unknown critical fact: {fact_id}")

    html_elements = [element for element in parser.elements if element.tag == "html"]
    if len(html_elements) == 1 and language and html_elements[0].attrs.get("lang") != language:
        errors.append("ArtifactManifest language must match html lang")
    titles = [element.text for element in parser.elements if element.tag == "title"]
    headings = [element.text for element in parser.elements if element.tag == "h1"]
    if len(titles) != 1 or titles[0] != title:
        errors.append("ArtifactManifest title must match the document title")
    if len(headings) != 1 or headings[0] != title:
        errors.append("ArtifactManifest title must match the single h1")
    return errors, dict(manifest)


def _view_records(parser: ArtifactParser, view_id: str) -> List[Element]:
    return [element for element in parser.elements if element.view_id == view_id]


def _roles(elements: Iterable[Element]) -> List[str]:
    return [element.attrs.get("data-vd-node", "") for element in elements if element.attrs.get("data-vd-node")]


def _validate_family(view: Element, elements: List[Element], policy: Mapping[str, Any], parser: ArtifactParser) -> List[str]:
    errors: List[str] = []
    view_id = view.attrs.get("data-vd-view", "")
    family = view.attrs.get("data-vd-family", "")
    roles = _roles(elements)
    nodes = [element for element in elements if element.attrs.get("data-vd-node")]
    groups = [element for element in elements if element.attrs.get("data-vd-group")]
    edges = [element for element in elements if element.attrs.get("data-vd-edge")]
    labels = {element.attrs.get("data-vd-edge-label") for element in elements if element.attrs.get("data-vd-edge-label")}
    ids = {element.identifier for element in elements if element.identifier}

    for node in nodes:
        if not node.identifier:
            errors.append(f"view {view_id} has a data-vd-node without an id")
    for group in groups:
        if not group.identifier:
            errors.append(f"view {view_id} has a data-vd-group without an id")
    for edge in edges:
        if not edge.identifier:
            errors.append(f"view {view_id} has a data-vd-edge without an id")
            continue
        source = edge.attrs.get("data-from", "")
        target = edge.attrs.get("data-to", "")
        if source not in ids or target not in ids:
            errors.append(f"edge {edge.identifier} endpoints must exist inside view {view_id}")
        if edge.tag not in GEOMETRY_TAGS:
            errors.append(f"edge {edge.identifier} must mark a visible SVG path, line, or polyline")

    if policy.get("requires_edges") and len(nodes) > 1 and not edges:
        errors.append(f"view {view_id} family {family} requires visible directed edges")
    if policy.get("requires_groups") and not groups:
        errors.append(f"view {view_id} family {family} requires a real visible boundary or group")
    for required in policy.get("required_node_roles", []):
        if required not in roles:
            errors.append(f"view {view_id} family {family} requires node role {required}")
    any_roles = set(policy.get("required_any_node_roles", []))
    if any_roles and not any_roles.intersection(roles):
        errors.append(f"view {view_id} family {family} requires one of: {', '.join(sorted(any_roles))}")

    mode = policy.get("mode")
    if mode == "flow":
        outgoing: Dict[str, List[Element]] = {}
        for edge in edges:
            outgoing.setdefault(edge.attrs.get("data-from", ""), []).append(edge)
        for decision in [node for node in nodes if node.attrs.get("data-vd-node") == "decision"]:
            branches = outgoing.get(decision.identifier, [])
            if len(branches) < 2:
                errors.append(f"decision {decision.identifier} requires at least two outgoing branches")
            for branch in branches:
                if branch.identifier not in labels:
                    errors.append(f"decision branch {branch.identifier} requires a visible data-vd-edge-label")
    elif mode == "sequence":
        participants = [node for node in nodes if node.attrs.get("data-vd-node") == "participant"]
        if len(participants) < 2:
            errors.append(f"sequence view {view_id} requires at least two independent participants")
        lifelines = {element.attrs.get("data-vd-lifeline-for") for element in elements if element.attrs.get("data-vd-lifeline-for")}
        for participant in participants:
            if participant.identifier not in lifelines:
                errors.append(f"participant {participant.identifier} requires a visible lifeline")
        for edge in edges:
            if edge.attrs.get("data-vd-message-kind") not in {"sync", "return", "async", "self", "error", "timeout"}:
                errors.append(f"sequence edge {edge.identifier} requires a valid data-vd-message-kind")
    elif mode == "state":
        for edge in edges:
            if edge.attrs.get("data-vd-edge") != "transition":
                errors.append(f"state view edge {edge.identifier} must declare transition semantics")
    elif mode == "data":
        movement = {"reads", "writes", "emits", "consumes", "transforms", "flows"}
        for edge in edges:
            if not edge.attrs.get("data-vd-cardinality") and edge.attrs.get("data-vd-edge") not in movement:
                errors.append(f"data edge {edge.identifier} requires cardinality or data-movement meaning")
    elif mode == "matrix":
        matrices = [element for element in elements if "data-vd-matrix" in element.attrs]
        differences = [element for element in elements if "data-vd-difference" in element.attrs]
        conclusions = [element for element in elements if "data-vd-conclusion" in element.attrs]
        if not matrices or not any(element.tag == "table" for element in matrices):
            errors.append(f"comparison view {view_id} requires a real table marked data-vd-matrix")
        if not differences:
            errors.append(f"comparison view {view_id} must visibly mark important differences")
        if not conclusions:
            errors.append(f"comparison view {view_id} requires a visible conclusion")
    elif mode == "review":
        sections = [element.attrs.get("data-vd-review-section") for element in elements if element.attrs.get("data-vd-review-section")]
        required = ["current", "scenario", "repair"]
        positions = [sections.index(value) if value in sections else -1 for value in required]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            errors.append(f"code-review view {view_id} requires visible current → scenario → repair order")
    elif mode == "prototype":
        if not any("data-vd-prototype" in element.attrs for element in elements):
            errors.append(f"page-prototype view {view_id} requires data-vd-prototype")
        controls = [element for element in elements if element.tag in {"button", "input", "select", "textarea"}]
        if len(controls) < 2:
            errors.append(f"page-prototype view {view_id} requires real interactive controls")
        if not any("data-vd-responsive-state" in element.attrs for element in elements):
            errors.append(f"page-prototype view {view_id} requires an authored responsive state")

    view_titles = [element.text for element in elements if "data-vd-view-title" in element.attrs]
    if not view_titles or any("｜" not in title for title in view_titles):
        errors.append(f"view {view_id} requires a visible data-vd-view-title in diagram type｜subject form")
    return errors


def _resource_errors(parser: ArtifactParser, html_text: str) -> List[str]:
    errors: List[str] = []
    for element in parser.elements:
        attrs = element.attrs
        for name in RESOURCE_ATTRS:
            value = attrs.get(name, "").strip()
            if not value:
                continue
            if not value.startswith("data:"):
                errors.append(f"line {element.line} uses non-embedded resource {name}={value!r}")
        if element.tag == "link" and attrs.get("rel", "").lower() in {"stylesheet", "preload", "modulepreload"}:
            errors.append("external or linked style resources are forbidden")
        href = attrs.get("href", "").strip()
        if element.tag in {"use", "image"} and href and not (href.startswith("#") or href.startswith("data:")):
            errors.append(f"line {element.line} uses a non-embedded SVG href")
    styles = "\n".join(parser.style_chunks)
    scripts = "\n".join(parser.script_chunks)
    if REMOTE_CSS_RE.search(styles):
        errors.append("CSS contains a remote import or resource")
    if NETWORK_SCRIPT_RE.search(scripts):
        errors.append("runtime script contains a network request primitive")
    if "<iframe" in html_text.lower():
        errors.append("iframe is forbidden in a single-file artifact")
    return errors


def lint(path: Path, expected_family: str = "", allow_candidates: bool = False) -> List[str]:
    try:
        html_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"could not read artifact: {exc}"]
    parser = ArtifactParser()
    try:
        parser.feed(html_text)
        parser.close()
    except Exception as exc:  # HTMLParser surfaces malformed input inconsistently.
        return [f"could not parse HTML: {exc}"]
    errors = list(parser.errors)
    if not parser.doctype:
        errors.append("artifact requires <!doctype html>")
    if len([element for element in parser.elements if element.tag == "html"]) != 1:
        errors.append("artifact requires exactly one html element")
    if len([element for element in parser.elements if element.tag == "body"]) != 1:
        errors.append("artifact requires exactly one body element")
    if not any(element.attrs.get("data-vd-artifact") == "1" for element in parser.elements):
        errors.append("artifact requires data-vd-artifact=1")
    if not any("data-vd-content" in element.attrs for element in parser.elements):
        errors.append("artifact requires main data-vd-content")
    summaries = [element for element in parser.elements if "data-vd-summary" in element.attrs]
    if len(summaries) != 1 or not summaries[0].text or summaries[0].hidden:
        errors.append("artifact requires one non-empty visible summary")
    if any("data-vd-scaffold-empty" in element.attrs for element in parser.elements):
        errors.append("blank scaffold markers must be removed before delivery")
    if PLACEHOLDER_RE.search(html_text):
        errors.append("artifact contains an unresolved placeholder")
    if RETIRED_RE.search(html_text):
        errors.append("artifact references a retired template or Contract compiler concept")
    if not allow_candidates and any("data-vd-candidate" in element.attrs for element in parser.elements):
        errors.append("candidate views require an explicit exploration request and --allow-candidates")
    controls = [element for element in parser.elements if "data-vd-controls" in element.attrs]
    zoom_values = [element.attrs.get("data-vd-zoom") for element in parser.elements if element.attrs.get("data-vd-zoom")]
    if len(controls) != 1 or zoom_values != ["0.75", "0.9", "1", "fit"]:
        errors.append("title region requires one persistent 75%, 90%, 100%, fit control group")
    scripts = "\n".join(parser.script_chunks)
    styles = "\n".join(parser.style_chunks)
    for marker in ("VibeDiagramQuality", "auditAll", "data-vd-audit-status", "edge-through-node", "critical-target-not-primary-visible", "product-summary-not-visible"):
        if marker not in scripts:
            errors.append(f"shared outcome audit runtime is missing marker: {marker}")
    if "@media print" not in styles or "prefers-reduced-motion" not in styles:
        errors.append("shared shell must preserve print and reduced-motion behavior")
    errors.extend(_resource_errors(parser, html_text))

    if parser.manifest_count != 1:
        errors.append("artifact requires exactly one ArtifactManifest script")
        manifest: Dict[str, Any] = {}
    else:
        try:
            raw_manifest = json.loads("".join(parser.manifest_chunks))
        except json.JSONDecodeError as exc:
            errors.append(f"ArtifactManifest is invalid JSON: {exc}")
            raw_manifest = {}
        outcomes = _read_json(OUTCOMES_PATH)
        families = outcomes.get("families")
        if not isinstance(families, dict):
            raise LintError("family outcome contract is invalid")
        manifest_errors, manifest = _validate_manifest(raw_manifest, parser, families)
        errors.extend(manifest_errors)

        views = [element for element in parser.elements if element.attrs.get("data-vd-view")]
        for view in views:
            family = view.attrs.get("data-vd-family", "")
            policy = families.get(family)
            if not isinstance(policy, dict):
                errors.append(f"view {view.attrs.get('data-vd-view')} uses unsupported family: {family}")
                continue
            errors.extend(_validate_family(view, _view_records(parser, view.attrs.get("data-vd-view", "")), policy, parser))
        if expected_family:
            primary_families = {
                item.get("family") for item in manifest.get("views", [])
                if isinstance(item, dict) and item.get("role") == "primary"
            }
            if expected_family not in primary_families:
                errors.append(f"expected primary family {expected_family}, found {sorted(value for value in primary_families if isinstance(value, str))}")

    detail_targets = {element.attrs.get("data-vd-detail-for") for element in parser.elements if element.attrs.get("data-vd-detail-for")}
    for target in detail_targets:
        if target not in parser.ids:
            errors.append(f"detail references missing semantic element: {target}")
    dialog_ids = {element.identifier for element in parser.elements if element.tag == "dialog" and element.identifier}
    for trigger in [element for element in parser.elements if element.attrs.get("data-vd-detail-trigger")]:
        target = trigger.attrs.get("data-vd-detail-trigger", "")
        if target not in dialog_ids:
            errors.append(f"detail trigger references missing dialog: {target}")

    return sorted(set(errors))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="self-contained HTML artifact")
    parser.add_argument("--type", dest="diagram_type", default="", help="expected primary family")
    parser.add_argument("--allow-candidates", action="store_true", help="allow explicit peer design candidates")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    path = Path(args.path).expanduser().resolve()
    try:
        errors = lint(path, args.diagram_type, args.allow_candidates)
    except LintError as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "artifact": str(path),
        "status": "artifact-static-valid",
        "product_reading": "not-reviewed",
        "browser_layout": "not-verified",
        "client_runtime": "not-verified",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
