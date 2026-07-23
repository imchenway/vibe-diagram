#!/usr/bin/env python3
"""Validate a self-contained HTML diagram without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
FAMILY_POLICY_PATH = SKILL_ROOT / "contracts" / "family-policies.json"
EXPECTED_TEMPLATE_COUNT = 59
RESOURCE_ATTRIBUTES = {"src", "srcset", "poster", "action", "formaction"}
LINK_ATTRIBUTES = {"href", "xlink:href"}
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
TITLE_DESCRIPTION_NODE_RE = re.compile(
    r"<(?P<tag>[a-z0-9:-]+)\b[^>]*\bclass=[\"'](?P<class>[^\"']+)[\"'][^>]*>"
    r"\s*<b\b[^>]*>.*?</b>\s*<span\b",
    re.IGNORECASE | re.DOTALL,
)
CSS_CLASS_RULE_RE = re.compile(
    r"\.(?P<class>[A-Za-z0-9_-]+)(?:\b|[.#:{\s>+~,])[^{}]*\{(?P<body>[^{}]*)\}",
    re.IGNORECASE | re.DOTALL,
)
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})\s?|([^\r\n\f]))")
JAVASCRIPT_ESCAPE_RE = re.compile(
    r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})"
)
NETWORK_SCRIPT_PATTERNS = (
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
HORIZONTAL_CANVAS_SCROLL_RE = re.compile(
    r"(?:canvas|svg|architecture|canvas-wrap|arch)[^{]{0,120}\{[^}]*"
    r"overflow(?:-x)?\s*:\s*(?:auto|scroll)",
    re.IGNORECASE | re.DOTALL,
)
OVERSIZED_MIN_WIDTH_RE = re.compile(
    r"[{;]\s*min-width\s*:\s*(?:1[3-9]\d{2}|[2-9]\d{3})px",
    re.IGNORECASE,
)
EVIDENCE_RE = re.compile(r"\bE\d{1,3}\b")
SOURCE_PATH_RE = re.compile(
    r"(?:/Users/|/ho" r"me/|/tmp/|[A-Za-z0-9_./-]+\.[A-Za-z0-9]+:\d+)"
)
SEQUENCE_CONTRACT_VERSION = "1"
SEQUENCE_MESSAGE_KINDS = frozenset({"sync", "return", "async", "self", "error"})
SEQUENCE_FRAGMENT_KINDS = frozenset({"tx", "opt", "loop", "alt", "group"})
SEQUENCE_OUTCOMES = frozenset({"success", "failure", "partial", "empty"})
SEQUENCE_PARTICIPANT_LIMIT = 12
SEQUENCE_MESSAGE_LIMIT = 40
SEQUENCE_PHASE_LIMIT = 4
SEQUENCE_ROLES = frozenset({"standalone", "overview", "detail"})
SEQUENCE_WIDTH_MODES = frozenset({"auto", "contained", "wide"})
SEQUENCE_HEIGHT_MODES = frozenset({"auto", "flow", "scroll"})
SEQUENCE_OWNER_TEMPLATES = frozenset(
    {
        ("fault-debugging", "debugging-sequence"),
        ("feature-iteration", "current-target-sequence"),
    }
)
GENERIC_CONTRACT_VERSION = "1"
GENERIC_PROFILES = frozenset({"graph", "matrix", "timeline", "artboard", "ledger"})
GENERIC_WIDTH_MODES = frozenset({"contained", "auto", "wide"})
GENERIC_HEIGHT_MODES = frozenset({"flow", "auto", "scroll"})
GENERIC_MOBILE_MODES = frozenset({"stack", "scroll", "summary"})
GENERIC_LIMIT_KEYS = frozenset({"nodes", "relations", "groups", "details"})
GENERIC_PRIMARY_DIRECTIONS = frozenset(
    {"north-to-south", "south-to-north", "west-to-east", "east-to-west"}
)
EVIDENCE_STATUSES = frozenset({"observed", "inferred", "proposed", "unresolved"})
EVIDENCE_PLACEMENTS = frozenset(
    {"before-primary-canvas", "after-primary-canvas"}
)
EVIDENCE_SOURCE_KINDS = frozenset(
    {"file", "line", "log", "test", "command", "user", "runtime", "design", "external"}
)
SEMANTIC_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DIAGRAM_RANK_RE = re.compile(r"(?:0|[1-9]\d{0,2})")
SVG_NUMBER_SOURCE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
SVG_NUMBER_RE = re.compile(rf"^{SVG_NUMBER_SOURCE}$")
SVG_PATH_TOKEN_RE = re.compile(rf"[MLHV]|{SVG_NUMBER_SOURCE}")
HAN_CHARACTER_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
VISIBLE_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")
VISIBLE_STABLE_ID_RE = re.compile(
    r"[a-z0-9][a-z0-9._/-]*"
    r"(?:\s*(?:→|·)\s*[a-z0-9][a-z0-9._/-]*)*"
)
VISIBLE_TECHNICAL_ATOM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#_-]*")
VISIBLE_TECHNICAL_NAMES = frozenset(
    {
        "App",
        "Boot",
        "Diagram",
        "Docker",
        "Elasticsearch",
        "GitHub",
        "Java",
        "Kafka",
        "Kubernetes",
        "MongoDB",
        "MySQL",
        "Nginx",
        "Ollama",
        "OpenTelemetry",
        "PostgreSQL",
        "RabbitMQ",
        "Redis",
        "SkyWalking",
        "Spring",
        "Vibe",
        "nginx",
        "ollama",
        "pgvector",
    }
)
FAMILY_POLICY_KEYS = frozenset(
    {
        "schema_version",
        "contract_version",
        "sequence_exclusions",
        "migration_batches",
        "families",
    }
)
FAMILY_POLICY_FAMILY_KEYS = frozenset({"limits", "templates"})
FAMILY_POLICY_TEMPLATE_REQUIRED_KEYS = frozenset({"profile", "limits"})
FAMILY_POLICY_TEMPLATE_OPTIONAL_KEYS = frozenset(
    {
        "topology",
        "direction",
        "required_regions",
        "requires_branch",
        "requires_merge",
        "controls_mode",
        "requires_node_details",
        "requires_node_detail_hint_in_reading_guide",
        "requires_localized_node_labels",
        "requires_geometric_direction",
        "evidence_placement",
    }
)
EXPECTED_SEQUENCE_EXCLUSIONS = (
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
    "feature-iteration/current-target-sequence.html",
)
TEMPLATE_CONTRACT_VERSION = "2"
PRIMARY_SEQUENCE_MESSAGE_LIMIT = 12
PRIMARY_SLOT_TEXT_LIMIT = 36
STYLE_BLOCK_RE = re.compile(r"<style(?P<attrs>[^>]*)>(?P<body>.*?)</style>", re.IGNORECASE | re.DOTALL)
SCRIPT_BLOCK_RE = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.IGNORECASE | re.DOTALL)
SEQUENCE_MESSAGE_FRAGMENT_RE = re.compile(
    r"<article\b(?=[^>]*\bdata-sequence-message\b)[^>]*>.*?</article>",
    re.IGNORECASE | re.DOTALL,
)
SEQUENCE_PARTICIPANT_FRAGMENT_RE = re.compile(
    r"<div\b(?=[^>]*\bdata-participant-id\s*=)[^>]*>.*?</div>",
    re.IGNORECASE | re.DOTALL,
)
MUTABLE_STRUCTURE_ATTRIBUTES = frozenset(
    {
        "id",
        "title",
        "alt",
        "href",
        "lang",
        "for",
        "data-diagram-id",
        "data-diagram-node-id",
        "data-diagram-group-id",
        "data-diagram-relation-id",
        "data-diagram-visible-relation-id",
        "data-fallback-relation-id",
        "data-detail-for",
        "data-diagram-detail",
        "data-diagram-detail-id",
        "data-detail-close-label",
        "data-node-primary-label",
        "data-diagram-status-fit",
        "data-diagram-status-fits",
        "data-diagram-status-scroll",
        "data-fallback-for",
        "data-from",
        "data-to",
        "data-semantic",
        "data-primary-relation",
        "data-diagram-topology",
        "data-primary-direction",
        "data-diagram-rank",
        "data-diagram-region",
        "data-evidence-id",
        "data-evidence-status",
        "data-evidence-for",
        "data-evidence-source-kind",
        "data-evidence-source",
        "data-routing-confidence",
        "data-sequence-id",
        "data-sequence-detail-for",
        "data-sequence-step-index",
        "data-sequence-phase-id",
        "data-sequence-fragment-id",
        "data-sequence-risk-id",
        "data-sequence-evidence-for",
        "data-sequence-evidence-id",
        "data-participant-id",
        "data-participant-group-id",
        "data-matrix-row-id",
        "data-matrix-col-id",
        "data-matrix-row",
        "data-matrix-col",
    }
)
VISUAL_SHELL_TOKENS = (
    "radial-gradient(circleat18%3%,rgba(214,233,255,.78),transparent30rem)",
    "radial-gradient(circleat78%6%,rgba(228,246,239,.8),transparent28rem)",
    "linear-gradient(rgba(93,133,173,.045)1px,transparent1px)",
    "linear-gradient(90deg,rgba(93,133,173,.045)1px,transparent1px)",
    "linear-gradient(180deg,#fff0%,#f7fbff54%,#fbfdff100%)",
    "background-size:auto,auto,28px28px,28px28px,auto",
)


@dataclass(frozen=True)
class SequenceCanvas:
    canvas_id: str
    role: str
    detail_for: str
    participant_ids: Tuple[str, ...]
    messages: Tuple[Tuple[str, str, str, str], ...]
    phase_ids: Tuple[str, ...]


@dataclass
class _SequenceRecord:
    attrs: Dict[str, str]
    participant_ids: List[str]
    messages: List[Tuple[str, str, str, str]]
    phase_ids: List[str]
    participant_group_ids: List[str]
    message_steps: List[str]
    fragments: List[Tuple[str, str]]
    outcomes: List[str]
    risk_ids: List[str]
    evidence_links: List[str]


def _duplicates(attrs: Sequence[Tuple[str, Optional[str]]]) -> List[str]:
    names = [name.lower() for name, _ in attrs]
    return sorted({name for name in names if names.count(name) > 1})


def _read_json_unique(path: Path) -> Dict[str, Any]:
    def reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number in {path}: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _validated_limits(value: Any, label: str, *, partial: bool) -> Dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    keys = set(value)
    if (not partial and keys != GENERIC_LIMIT_KEYS) or (partial and not keys <= GENERIC_LIMIT_KEYS):
        raise ValueError(f"{label} has an invalid key set")
    result: Dict[str, int] = {}
    for key, limit in value.items():
        if type(limit) is not int or limit < 1:
            raise ValueError(f"{label}.{key} must be a positive integer")
        result[key] = limit
    return result


def _validated_migration_batches(
    value: Any, generic_templates: set[str]
) -> Dict[str, List[str]]:
    if not isinstance(value, dict) or list(value) != sorted(value):
        raise ValueError("family policy migration batches must be an ordered object")
    seen = set()
    result: Dict[str, List[str]] = {}
    for batch, paths in value.items():
        if re.fullmatch(r"B(?:0[1-9]|1[0-3])", batch) is None:
            raise ValueError(f"family policy migration batch id is invalid: {batch}")
        if (
            not isinstance(paths, list)
            or not paths
            or paths != sorted(paths)
            or len(paths) != len(set(paths))
            or not set(paths) <= generic_templates
            or seen & set(paths)
        ):
            raise ValueError(f"family policy migration batch paths are invalid: {batch}")
        seen.update(paths)
        result[batch] = paths
    return result


def load_family_policies(path: Path = FAMILY_POLICY_PATH) -> Dict[str, Any]:
    policy = _read_json_unique(path)
    if set(policy) != FAMILY_POLICY_KEYS:
        raise ValueError("family policy has an invalid root schema")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise ValueError("family policy schema_version must be integer 1")
    if policy["contract_version"] != GENERIC_CONTRACT_VERSION:
        raise ValueError("family policy contract_version is invalid")
    if policy["sequence_exclusions"] != list(EXPECTED_SEQUENCE_EXCLUSIONS):
        raise ValueError("family policy sequence exclusions are invalid")
    families = policy["families"]
    if not isinstance(families, dict) or len(families) != 10:
        raise ValueError("family policy must define exactly ten generic families")
    catalog = load_template_layouts()
    covered = set()
    for family, definition in families.items():
        if not isinstance(definition, dict) or set(definition) != FAMILY_POLICY_FAMILY_KEYS:
            raise ValueError(f"family policy definition is invalid: {family}")
        family_limits = _validated_limits(
            definition["limits"], f"families.{family}.limits", partial=False
        )
        templates = definition["templates"]
        if not isinstance(templates, dict) or not templates:
            raise ValueError(f"family policy templates must be a non-empty object: {family}")
        for template_id, template in templates.items():
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", template_id):
                raise ValueError(f"family policy template id is invalid: {family}/{template_id}")
            template_keys = set(template) if isinstance(template, dict) else set()
            if (
                not isinstance(template, dict)
                or not FAMILY_POLICY_TEMPLATE_REQUIRED_KEYS <= template_keys
                or not template_keys
                <= FAMILY_POLICY_TEMPLATE_REQUIRED_KEYS | FAMILY_POLICY_TEMPLATE_OPTIONAL_KEYS
            ):
                raise ValueError(
                    f"family policy template definition is invalid: {family}/{template_id}"
                )
            if template["profile"] not in GENERIC_PROFILES:
                raise ValueError(f"family policy profile is invalid: {family}/{template_id}")
            overrides = _validated_limits(
                template["limits"],
                f"families.{family}.templates.{template_id}.limits",
                partial=True,
            )
            if any(limit > family_limits[key] for key, limit in overrides.items()):
                raise ValueError(
                    f"family policy template limit widens its family: {family}/{template_id}"
                )
            semantic_policy_keys = template_keys & (
                FAMILY_POLICY_TEMPLATE_OPTIONAL_KEYS - {"evidence_placement"}
            )
            if semantic_policy_keys and template["profile"] != "graph":
                raise ValueError(
                    f"family policy topology fields require a graph profile: {family}/{template_id}"
                )
            topology = template.get("topology")
            direction = template.get("direction")
            if (topology is None) != (direction is None):
                raise ValueError(
                    f"family policy topology and direction must be declared together: {family}/{template_id}"
                )
            if topology is not None and (
                not isinstance(topology, str) or SEMANTIC_SLUG_RE.fullmatch(topology) is None
            ):
                raise ValueError(f"family policy topology is invalid: {family}/{template_id}")
            if direction is not None and direction not in GENERIC_PRIMARY_DIRECTIONS:
                raise ValueError(f"family policy direction is invalid: {family}/{template_id}")
            required_regions = template.get("required_regions")
            if required_regions is not None:
                if (
                    topology is None
                    or not isinstance(required_regions, list)
                    or not required_regions
                    or len(required_regions) != len(set(required_regions))
                    or any(
                        not isinstance(region, str)
                        or SEMANTIC_SLUG_RE.fullmatch(region) is None
                        for region in required_regions
                    )
                ):
                    raise ValueError(
                        f"family policy required regions are invalid: {family}/{template_id}"
                    )
            controls_mode = template.get("controls_mode")
            if controls_mode is not None and controls_mode not in {"overflow", "persistent"}:
                raise ValueError(
                    f"family policy controls_mode is invalid: {family}/{template_id}"
                )
            evidence_placement = template.get("evidence_placement")
            if (
                evidence_placement is not None
                and evidence_placement not in EVIDENCE_PLACEMENTS
            ):
                raise ValueError(
                    f"family policy evidence_placement is invalid: {family}/{template_id}"
                )
            for key in (
                "requires_branch",
                "requires_merge",
                "requires_node_details",
                "requires_localized_node_labels",
                "requires_geometric_direction",
            ):
                if key in template and (direction is None or type(template[key]) is not bool):
                    raise ValueError(
                        f"family policy {key} is invalid: {family}/{template_id}"
                    )
            if template.get("requires_geometric_direction") and direction != "north-to-south":
                raise ValueError(
                    "family policy geometric direction currently requires north-to-south: "
                    f"{family}/{template_id}"
                )
            covered.add(f"{family}/{template_id}.html")
    all_templates = {
        f"{family}/{template_id}.html"
        for family, entries in catalog.items()
        for template_id in entries
    }
    expected = all_templates - set(EXPECTED_SEQUENCE_EXCLUSIONS)
    if covered != expected:
        raise ValueError("family policy must cover the exact 53 non-sequence templates")
    _validated_migration_batches(policy["migration_batches"], expected)
    return policy


@dataclass(frozen=True)
class _GenericObjectRecord:
    object_id: str
    semantic_role: str
    rank: str
    region: str
    detail_for: str
    primary_label: str
    element_tag: str
    href: str


@dataclass(frozen=True)
class _GenericRelationRecord:
    relation_id: str
    source: str
    target: str
    kind: str
    semantic: str
    primary: str


@dataclass(frozen=True)
class _RelationBindingRecord:
    relation_id: str
    source: str
    target: str
    kind: str


@dataclass
class _GenericCanvasRecord:
    attrs: Dict[str, str]
    nodes: List[_GenericObjectRecord]
    groups: List[_GenericObjectRecord]
    relations: List[_GenericRelationRecord]
    row_ids: List[str]
    col_ids: List[str]
    cells: List[Tuple[str, str]]
    detail_ids: List[str]
    detail_targets: List[str]
    visible_relations: List[_RelationBindingRecord]
    node_bounds: Dict[str, Tuple[float, float, float, float]]
    visible_paths: Dict[str, str]

    @property
    def node_ids(self) -> List[str]:
        return [node.object_id for node in self.nodes]

    @property
    def group_ids(self) -> List[str]:
        return [group.object_id for group in self.groups]


@dataclass
class _FallbackRecord:
    fallback_for: str
    relations: List[_RelationBindingRecord]


@dataclass(frozen=True)
class _EvidenceEntryRecord:
    evidence_id: str
    status: str
    evidence_for: str
    source_kind: str
    source: str


@dataclass
class _EvidenceSlotRecord:
    ledger_count: int
    entries: List[_EvidenceEntryRecord]
    text_parts: List[str]
    before_canvas: bool


class _GenericContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canvases: List[_GenericCanvasRecord] = []
        self.fallbacks: List[_FallbackRecord] = []
        self.evidence_slots: List[_EvidenceSlotRecord] = []
        self.errors: List[str] = []
        self._canvas: Optional[_GenericCanvasRecord] = None
        self._fallback: Optional[_FallbackRecord] = None
        self._evidence_slot: Optional[_EvidenceSlotRecord] = None
        self._ledger_active = False
        self._saw_canvas = False
        self.document_lang = ""
        self.node_detail_hint_count = 0
        self.node_detail_hint_reading_guide_count = 0
        self.node_detail_hint_canvas_count = 0
        self._interaction_group_depth = 0
        self._svg_depth = 0
        self._active_node_ids: List[str] = []
        self._stack: List[Tuple[str, bool, bool, bool, bool, str, bool, bool]] = []

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        normalized = [(name.lower(), value or "") for name, value in attrs]
        values = dict(normalized)
        starts_canvas = "data-diagram-canvas" in values
        starts_fallback = "data-fallback-for" in values
        starts_evidence_slot = values.get("data-slot", "").strip() == "evidence-and-notes"
        starts_ledger = "data-evidence-ledger" in values
        starts_interaction_group = (
            values.get("data-reading-guide-group", "").strip() == "interaction"
        )
        starts_svg = tag == "svg"
        starts_node_id = ""
        if tag == "html":
            self.document_lang = values.get("lang", "").strip().lower()
        if starts_canvas:
            if self._canvas is not None:
                self.errors.append("Diagram canvases must not be nested.")
            else:
                self._canvas = _GenericCanvasRecord(
                    values, [], [], [], [], [], [], [], [], [], {}, {}
                )
                self.canvases.append(self._canvas)
            self._saw_canvas = True
        if starts_fallback:
            if self._fallback is not None:
                self.errors.append("Diagram fallbacks must not be nested.")
            else:
                self._fallback = _FallbackRecord(values["data-fallback-for"].strip(), [])
                self.fallbacks.append(self._fallback)
        if starts_evidence_slot:
            if self._evidence_slot is not None:
                self.errors.append("Evidence-and-notes slots must not be nested.")
            else:
                self._evidence_slot = _EvidenceSlotRecord(0, [], [], not self._saw_canvas)
                self.evidence_slots.append(self._evidence_slot)
        if starts_ledger:
            if self._evidence_slot is None:
                self.errors.append("A generic evidence ledger must be inside the evidence-and-notes slot.")
            elif self._ledger_active:
                self.errors.append("Generic evidence ledgers must not be nested.")
            else:
                self._ledger_active = True
                self._evidence_slot.ledger_count += 1
                if values["data-evidence-ledger"].strip() != GENERIC_CONTRACT_VERSION:
                    self.errors.append("Generic evidence ledger contract must be version 1.")
        if "data-evidence-id" in values:
            if self._evidence_slot is None or not self._ledger_active:
                self.errors.append("Generic evidence entries must be inside the evidence ledger.")
            else:
                self._evidence_slot.entries.append(
                    _EvidenceEntryRecord(
                        values["data-evidence-id"].strip(),
                        values.get("data-evidence-status", "").strip(),
                        values.get("data-evidence-for", "").strip(),
                        values.get("data-evidence-source-kind", "").strip(),
                        values.get("data-evidence-source", "").strip(),
                    )
                )
        if values.get("data-interaction-hint", "").strip() == "node-detail":
            self.node_detail_hint_count += 1
            inside_ledger = self._ledger_active or starts_ledger
            inside_interaction_group = (
                self._interaction_group_depth > 0 or starts_interaction_group
            )
            inside_svg = self._svg_depth > 0 or starts_svg
            if inside_ledger and inside_interaction_group and not inside_svg:
                self.node_detail_hint_reading_guide_count += 1
            if inside_svg:
                self.node_detail_hint_canvas_count += 1
        if "data-fallback-relation-id" in values:
            if self._fallback is None:
                self.errors.append("Fallback relation bindings must be inside data-fallback-for.")
            else:
                self._fallback.relations.append(
                    _RelationBindingRecord(
                        values["data-fallback-relation-id"].strip(),
                        values.get("data-from", "").strip(),
                        values.get("data-to", "").strip(),
                        values.get("data-relation-kind", "").strip(),
                    )
                )
        if self._canvas is not None:
            semantic = any(
                key in values
                for key in (
                    "data-diagram-node-id",
                    "data-diagram-group-id",
                    "data-diagram-relation-id",
                    "data-matrix-row-id",
                    "data-matrix-col-id",
                    "data-diagram-detail-id",
                    "data-diagram-visible-relation-id",
                )
            )
            duplicates = _duplicates(attrs) if semantic or starts_canvas else []
            if duplicates:
                self.errors.append(
                    "Duplicate generic contract attributes: " + ", ".join(duplicates) + "."
                )
            if "data-diagram-node-id" in values:
                node = _GenericObjectRecord(
                    values["data-diagram-node-id"].strip(),
                    values.get("data-semantic-role", "").strip(),
                    values.get("data-diagram-rank", "").strip(),
                    values.get("data-diagram-region", "").strip(),
                    values.get("data-detail-for", "").strip(),
                    values.get("data-node-primary-label", "").strip(),
                    tag,
                    values.get("href", "").strip(),
                )
                self._canvas.nodes.append(node)
                starts_node_id = node.object_id
                self._active_node_ids.append(starts_node_id)
                if not node.semantic_role:
                    self.errors.append("Every diagram node must declare data-semantic-role.")
            if tag == "rect" and self._active_node_ids:
                node_id = self._active_node_ids[-1]
                bounds = _parse_svg_rect_bounds(values)
                if bounds is None:
                    self.errors.append(
                        f"Diagram node {node_id} requires numeric SVG rect bounds."
                    )
                elif node_id in self._canvas.node_bounds:
                    self.errors.append(
                        f"Diagram node {node_id} must contain exactly one geometry rect."
                    )
                else:
                    self._canvas.node_bounds[node_id] = bounds
            if "data-diagram-group-id" in values:
                group = _GenericObjectRecord(
                    values["data-diagram-group-id"].strip(),
                    values.get("data-semantic-role", "").strip(),
                    values.get("data-diagram-rank", "").strip(),
                    values.get("data-diagram-region", "").strip(),
                    "",
                    "",
                    tag,
                    "",
                )
                self._canvas.groups.append(group)
                if not group.semantic_role:
                    self.errors.append("Every diagram group must declare data-semantic-role.")
            if "data-diagram-relation-id" in values:
                self._canvas.relations.append(
                    _GenericRelationRecord(
                        values["data-diagram-relation-id"].strip(),
                        values.get("data-from", "").strip(),
                        values.get("data-to", "").strip(),
                        values.get("data-relation-kind", "").strip(),
                        values.get("data-semantic", "").strip(),
                        values.get("data-primary-relation", "").strip(),
                    )
                )
            if "data-matrix-row-id" in values:
                self._canvas.row_ids.append(values["data-matrix-row-id"].strip())
            if "data-matrix-col-id" in values:
                self._canvas.col_ids.append(values["data-matrix-col-id"].strip())
            if "data-matrix-row" in values or "data-matrix-col" in values:
                self._canvas.cells.append(
                    (
                        values.get("data-matrix-row", "").strip(),
                        values.get("data-matrix-col", "").strip(),
                    )
                )
            if "data-diagram-detail-id" in values:
                detail_id = values["data-diagram-detail-id"].strip()
                self._canvas.detail_ids.append(detail_id)
                self._canvas.detail_targets.append(
                    values.get("data-detail-for", "").strip()
                )
                if tag != "details":
                    self.errors.append("Diagram node details must use native details elements.")
                if values.get("id", "").strip() != detail_id:
                    self.errors.append(
                        "Diagram node detail id must match its data-diagram-detail-id."
                    )
                if values.get("data-diagram-detail", "").strip() != detail_id:
                    self.errors.append(
                        "Diagram node detail runtime target must match its detail id."
                    )
            if "data-diagram-visible-relation-id" in values:
                is_svg_edge = tag in {"line", "path", "polygon", "polyline"}
                is_html_edge = values.get("data-visible-relation-kind") == "edge"
                if not (is_svg_edge or is_html_edge):
                    self.errors.append(
                        "Visible relation bindings must use an SVG edge or an explicit HTML edge carrier."
                    )
                self._canvas.visible_relations.append(
                    _RelationBindingRecord(
                        values["data-diagram-visible-relation-id"].strip(),
                        values.get("data-from", "").strip(),
                        values.get("data-to", "").strip(),
                        values.get("data-relation-kind", "").strip(),
                    )
                )
                if tag == "path":
                    relation_id = values["data-diagram-visible-relation-id"].strip()
                    self._canvas.visible_paths[relation_id] = values.get("d", "").strip()
        if starts_interaction_group:
            self._interaction_group_depth += 1
        if starts_svg:
            self._svg_depth += 1
        if tag not in VOID_ELEMENTS:
            self._stack.append(
                (
                    tag,
                    starts_canvas,
                    starts_fallback,
                    starts_evidence_slot,
                    starts_ledger,
                    starts_node_id,
                    starts_interaction_group,
                    starts_svg,
                )
            )

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        (
            _open_tag,
            closes_canvas,
            closes_fallback,
            closes_evidence_slot,
            closes_ledger,
            closes_node_id,
            closes_interaction_group,
            closes_svg,
        ) = self._stack.pop()
        if closes_node_id:
            if not self._active_node_ids or self._active_node_ids[-1] != closes_node_id:
                self.errors.append("Diagram node geometry nesting is invalid.")
            else:
                self._active_node_ids.pop()
        if closes_ledger:
            self._ledger_active = False
        if closes_evidence_slot:
            self._evidence_slot = None
        if closes_fallback:
            self._fallback = None
        if closes_canvas:
            self._canvas = None
        if closes_interaction_group:
            self._interaction_group_depth -= 1
        if closes_svg:
            self._svg_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._evidence_slot is not None and data.strip():
            self._evidence_slot.text_parts.append(data.strip())


def _is_template_placeholder(value: str) -> bool:
    return re.fullmatch(r"\{\{[^{}]+\}\}", value.strip()) is not None


def _parse_svg_number(value: str) -> Optional[float]:
    stripped = value.strip()
    if SVG_NUMBER_RE.fullmatch(stripped) is None:
        return None
    number = float(stripped)
    return number if math.isfinite(number) else None


def _parse_svg_rect_bounds(
    attrs: Mapping[str, str],
) -> Optional[Tuple[float, float, float, float]]:
    values = [_parse_svg_number(attrs.get(key, "")) for key in ("x", "y", "width", "height")]
    if any(value is None for value in values):
        return None
    x, y, width, height = values
    assert x is not None and y is not None and width is not None and height is not None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _parse_absolute_orthogonal_path_points(
    value: str,
) -> Optional[List[Tuple[float, float]]]:
    tokens: List[str] = []
    position = 0
    for match in SVG_PATH_TOKEN_RE.finditer(value):
        if re.fullmatch(r"[\s,]*", value[position : match.start()]) is None:
            return None
        tokens.append(match.group(0))
        position = match.end()
    if re.fullmatch(r"[\s,]*", value[position:]) is None or not tokens:
        return None

    index = 0
    command = ""
    current: Optional[Tuple[float, float]] = None
    start: Optional[Tuple[float, float]] = None
    points: List[Tuple[float, float]] = []
    while index < len(tokens):
        if tokens[index] in {"M", "L", "H", "V"}:
            command = tokens[index]
            index += 1
        if not command or index >= len(tokens) or tokens[index] in {"M", "L", "H", "V"}:
            return None
        if command in {"M", "L"}:
            if index + 1 >= len(tokens) or tokens[index + 1] in {"M", "L", "H", "V"}:
                return None
            x = _parse_svg_number(tokens[index])
            y = _parse_svg_number(tokens[index + 1])
            if x is None or y is None or (command != "M" and current is None):
                return None
            current = (x, y)
            if command == "M":
                if start is not None:
                    return None
                start = current
                command = "L"
            points.append(current)
            index += 2
        elif command == "H":
            x = _parse_svg_number(tokens[index])
            if x is None or current is None:
                return None
            current = (x, current[1])
            points.append(current)
            index += 1
        else:
            y = _parse_svg_number(tokens[index])
            if y is None or current is None:
                return None
            current = (current[0], y)
            points.append(current)
            index += 1
    if start is None or current is None or not points:
        return None
    return points


class _VisibleLanguageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[Tuple[str, str, bool]] = []
        self.document_lang = ""
        self._stack: List[Tuple[str, bool, bool]] = []

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        normalized = [(name.lower(), value or "") for name, value in attrs]
        values = dict(normalized)
        if tag == "html":
            self.document_lang = values.get("lang", "").strip().lower()
        inherited_ignored = self._stack[-1][1] if self._stack else False
        inherited_stable = self._stack[-1][2] if self._stack else False
        classes = set(values.get("class", "").split())
        ignored = (
            inherited_ignored
            or tag in {"script", "style", "template"}
            or "hidden" in values
            or values.get("aria-hidden", "").strip().lower() == "true"
            or "semantic-relation" in classes
        )
        stable_context = (
            inherited_stable
            or "fallback-region-index" in classes
            or "data-semantic-edge-route" in values
        )
        if not ignored:
            for name, value in normalized:
                if value and (
                    name in {"aria-label", "title", "alt"}
                    or name.startswith("data-diagram-status-")
                ):
                    self.parts.append((name, " ".join(value.split()), stable_context))
        if tag not in VOID_ELEMENTS:
            self._stack.append((tag, ignored, stable_context))

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._stack and not self._stack[-1][1] and data.strip():
            self.parts.append(
                ("text", " ".join(data.split()), self._stack[-1][2])
            )


def _is_allowed_technical_visible_text(value: str, stable_context: bool) -> bool:
    if stable_context and VISIBLE_STABLE_ID_RE.fullmatch(value):
        return True
    if (
        VISIBLE_STABLE_ID_RE.fullmatch(value)
        and ("/" in value or "." in value)
        and " " not in value
    ):
        return True
    atoms = [part for part in re.split(r"[\s·,/]+", value) if part]
    if not atoms:
        return False
    simple_titlecase = 0
    neutral_names = 0
    for atom in atoms:
        if VISIBLE_TECHNICAL_ATOM_RE.fullmatch(atom) is None:
            return False
        if atom in VISIBLE_TECHNICAL_NAMES:
            neutral_names += 1
            continue
        if re.fullmatch(r"\d+(?:\.\d+)*", atom):
            continue
        if re.fullmatch(r"[A-Z][A-Z0-9]{1,}", atom):
            continue
        if re.search(r"\d|[a-z][A-Z]|[A-Z].*[A-Z]|[.+#_]", atom):
            continue
        if re.fullmatch(r"[A-Z][a-z]+", atom):
            simple_titlecase += 1
            continue
        return False
    if simple_titlecase and neutral_names * 2 < len(atoms):
        return False
    return True


def _validate_visible_language(html: str, document_lang: str) -> List[str]:
    parser = _VisibleLanguageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        return [f"Could not parse visible artifact language: {exc}."]
    effective_lang = document_lang or parser.document_lang
    if not effective_lang.startswith("zh"):
        return []
    errors: List[str] = []
    for kind, value, stable_context in parser.parts:
        if VISIBLE_PLACEHOLDER_RE.search(value):
            errors.append(
                f"Chinese artifacts must not expose an unresolved visible placeholder in {kind}."
            )
        elif (
            ASCII_LETTER_RE.search(value)
            and HAN_CHARACTER_RE.search(value) is None
            and not _is_allowed_technical_visible_text(value, stable_context)
        ):
            sample = value if len(value) <= 96 else value[:93] + "..."
            errors.append(
                f"Chinese artifacts contain English-only visible {kind}: {sample!r}."
            )
    return list(dict.fromkeys(errors))


def _point_inside_bounds(
    point: Tuple[float, float],
    bounds: Tuple[float, float, float, float],
    tolerance: float = 0.001,
) -> bool:
    x, y = point
    left, top, width, height = bounds
    return (
        left - tolerance <= x <= left + width + tolerance
        and top - tolerance <= y <= top + height + tolerance
    )


def _point_on_bounds_edge(
    point: Tuple[float, float],
    bounds: Tuple[float, float, float, float],
    tolerance: float = 0.001,
) -> bool:
    if not _point_inside_bounds(point, bounds, tolerance):
        return False
    x, y = point
    left, top, width, height = bounds
    return (
        abs(x - left) <= tolerance
        or abs(x - (left + width)) <= tolerance
        or abs(y - top) <= tolerance
        or abs(y - (top + height)) <= tolerance
    )


def _point_on_south_edge(
    point: Tuple[float, float],
    bounds: Tuple[float, float, float, float],
    tolerance: float = 0.001,
) -> bool:
    x, y = point
    left, top, width, height = bounds
    return (
        left - tolerance <= x <= left + width + tolerance
        and abs(y - (top + height)) <= tolerance
    )


def _point_on_north_edge(
    point: Tuple[float, float],
    bounds: Tuple[float, float, float, float],
    tolerance: float = 0.001,
) -> bool:
    x, y = point
    left, top, width, _height = bounds
    return left - tolerance <= x <= left + width + tolerance and abs(y - top) <= tolerance


def _validate_north_to_south_geometry(
    canvas: _GenericCanvasRecord,
    primary_relations: Sequence[_GenericRelationRecord],
    topology: str,
) -> List[str]:
    errors: List[str] = []
    missing_bounds = sorted(set(canvas.node_ids) - set(canvas.node_bounds))
    if missing_bounds:
        errors.append(
            "Geometric direction requires one SVG rect bound for every diagram node: "
            + ", ".join(missing_bounds)
            + "."
        )

    centers_by_rank: Dict[int, List[float]] = {}
    for node in canvas.nodes:
        bounds = canvas.node_bounds.get(node.object_id)
        if bounds is None or DIAGRAM_RANK_RE.fullmatch(node.rank) is None:
            continue
        centers_by_rank.setdefault(int(node.rank), []).append(bounds[1] + bounds[3] / 2)
    ordered_ranks = sorted(centers_by_rank)
    for previous, current in zip(ordered_ranks, ordered_ranks[1:]):
        if max(centers_by_rank[previous]) >= min(centers_by_rank[current]):
            errors.append(
                "North-to-south geometry requires actual node Y positions to increase by rank."
            )
            break

    for relation in primary_relations:
        path_data = canvas.visible_paths.get(relation.relation_id)
        if path_data is None:
            errors.append(
                "Geometric direction requires every primary relation to use a visible SVG path: "
                f"{relation.relation_id}."
            )
            continue
        points = _parse_absolute_orthogonal_path_points(path_data)
        if points is None:
            errors.append(
                "Geometric direction paths must use valid absolute M/L/H/V commands: "
                f"{relation.relation_id}."
            )
            continue
        start, end = points[0], points[-1]
        source_bounds = canvas.node_bounds.get(relation.source)
        target_bounds = canvas.node_bounds.get(relation.target)
        if source_bounds is None or target_bounds is None:
            continue
        layered = topology == "layered-architecture"
        valid_start = (
            _point_on_south_edge(start, source_bounds)
            if layered
            else _point_on_bounds_edge(start, source_bounds)
        )
        valid_end = (
            _point_on_north_edge(end, target_bounds)
            if layered
            else _point_on_bounds_edge(end, target_bounds)
        )
        if not valid_start:
            errors.append(
                "Primary relation path must start on the permitted source node boundary: "
                f"{relation.relation_id}."
            )
        if not valid_end:
            errors.append(
                "Primary relation path must end on the permitted target node boundary: "
                f"{relation.relation_id}."
            )
        if any(
            current[1] < previous[1] - 0.001
            for previous, current in zip(points, points[1:])
        ):
            errors.append(
                "North-to-south primary relation paths must never route northward: "
                f"{relation.relation_id}."
            )
        if end[1] <= start[1]:
            errors.append(
                "North-to-south primary relation paths must visibly advance downward: "
                f"{relation.relation_id}."
            )
    return errors


def _validate_evidence_ledger(
    parser: _GenericContractParser,
    semantic_targets: set[str],
    evidence_placement: str,
) -> List[str]:
    errors: List[str] = []
    if not parser.evidence_slots:
        return ["A generic artifact requires a structured evidence-and-notes slot."]
    evidence_ids: List[str] = []
    for slot in parser.evidence_slots:
        if evidence_placement == "before-primary-canvas" and not slot.before_canvas:
            errors.append("The evidence boundary ledger must appear before the first diagram canvas.")
        if evidence_placement == "after-primary-canvas" and slot.before_canvas:
            errors.append("The evidence ledger must appear after the first diagram canvas.")
        if slot.ledger_count != 1:
            errors.append(
                "Every generic evidence-and-notes slot requires exactly one data-evidence-ledger."
            )
        if not slot.entries:
            errors.append(
                "A generic evidence ledger requires at least one structured evidence entry; bare text is not evidence."
            )
        for entry in slot.entries:
            evidence_ids.append(entry.evidence_id)
            if not entry.evidence_id or SEMANTIC_SLUG_RE.fullmatch(entry.evidence_id) is None:
                errors.append("Generic evidence ids must be non-empty semantic slugs.")
            if entry.status not in EVIDENCE_STATUSES:
                errors.append("Generic evidence status is invalid.")
            targets = entry.evidence_for.split()
            if not targets:
                errors.append("Generic evidence entries must reference at least one semantic target.")
            elif not _is_template_placeholder(entry.evidence_for):
                unknown = sorted(set(targets) - semantic_targets)
                if unknown:
                    errors.append(
                        "Generic evidence targets must reference authored semantic ids: "
                        + ", ".join(unknown)
                        + "."
                    )
            if entry.source_kind not in EVIDENCE_SOURCE_KINDS:
                errors.append("Generic evidence source kind is invalid.")
            if not entry.source:
                errors.append("Generic evidence source must be non-empty.")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("Generic evidence ids must be unique within a document.")
    return errors


def _validate_directional_graph(
    canvas: _GenericCanvasRecord,
    definition: Mapping[str, Any],
    document_lang: str,
) -> List[str]:
    if "direction" not in definition:
        return []
    errors: List[str] = []
    attrs = canvas.attrs
    if attrs.get("data-diagram-topology", "").strip() != definition["topology"]:
        errors.append("Diagram topology must match its trusted template policy.")
    if attrs.get("data-primary-direction", "").strip() != definition["direction"]:
        errors.append("Diagram primary direction must match its trusted template policy.")
    controls_mode = definition.get("controls_mode")
    if controls_mode is not None and attrs.get("data-diagram-controls-mode", "").strip() != controls_mode:
        errors.append("Diagram controls mode must match its trusted template policy.")
    objects = canvas.nodes + canvas.groups
    ranks: Dict[str, int] = {}
    for item in objects:
        if DIAGRAM_RANK_RE.fullmatch(item.rank) is None:
            errors.append("Directional graph nodes and groups require integer data-diagram-rank values.")
        else:
            ranks[item.object_id] = int(item.rank)
        if SEMANTIC_SLUG_RE.fullmatch(item.region) is None:
            errors.append("Directional graph nodes and groups require semantic data-diagram-region values.")
    group_regions = [group.region for group in canvas.groups if group.region]
    if len(group_regions) != len(set(group_regions)):
        errors.append("Directional graph group regions must be unique within a canvas.")
    required_regions = set(definition.get("required_regions", []))
    missing_regions = sorted(required_regions - set(group_regions))
    if missing_regions:
        errors.append(
            "Directional graph groups do not cover required policy regions: "
            + ", ".join(missing_regions)
            + "."
        )
    unknown_node_regions = sorted(
        {node.region for node in canvas.nodes if node.region and node.region not in set(group_regions)}
    )
    if unknown_node_regions:
        errors.append(
            "Directional graph node regions must reference authored group regions: "
            + ", ".join(unknown_node_regions)
            + "."
        )
    primary_relations: List[_GenericRelationRecord] = []
    for relation in canvas.relations:
        if relation.primary not in {"true", "false"}:
            errors.append(
                "Directional graph relations must declare data-primary-relation as true or false."
            )
        elif relation.primary == "true":
            primary_relations.append(relation)
    if not primary_relations:
        errors.append("A directional graph requires at least one authored primary relation.")
    for relation in primary_relations:
        source_rank = ranks.get(relation.source)
        target_rank = ranks.get(relation.target)
        if source_rank is None or target_rank is None:
            errors.append("Primary relation endpoints must have authored diagram ranks.")
        elif source_rank >= target_rank:
            errors.append(
                "Primary relations must advance from a lower authored rank to a higher authored rank."
            )
    outgoing: Dict[str, set[str]] = {}
    incoming: Dict[str, set[str]] = {}
    for relation in primary_relations:
        outgoing.setdefault(relation.source, set()).add(relation.target)
        incoming.setdefault(relation.target, set()).add(relation.source)
    has_branch = any(len(targets) > 1 for targets in outgoing.values())
    has_merge = any(len(sources) > 1 for sources in incoming.values())
    if "requires_branch" in definition and has_branch != definition["requires_branch"]:
        errors.append("Directional graph primary relations do not satisfy the branch policy.")
    if "requires_merge" in definition and has_merge != definition["requires_merge"]:
        errors.append("Directional graph primary relations do not satisfy the merge policy.")
    if definition.get("requires_geometric_direction"):
        errors.extend(
            _validate_north_to_south_geometry(
                canvas,
                primary_relations,
                str(definition["topology"]),
            )
        )
    if definition.get("requires_node_details"):
        detail_ids = canvas.detail_ids
        detail_targets = canvas.detail_targets
        node_targets = [node.detail_for for node in canvas.nodes]
        if len(detail_ids) != len(set(detail_ids)):
            errors.append("Diagram node detail ids must be unique within a canvas.")
        if any(SEMANTIC_SLUG_RE.fullmatch(value) is None for value in node_targets):
            errors.append("Every diagram node requires one semantic data-detail-for target.")
        if any(SEMANTIC_SLUG_RE.fullmatch(value) is None for value in detail_targets):
            errors.append("Every native detail block must point back to one semantic node id.")
        if set(node_targets) != set(detail_ids) or len(node_targets) != len(detail_ids):
            errors.append("Diagram nodes and native detail blocks must form a one-to-one mapping.")
        if set(detail_targets) != set(canvas.node_ids) or len(detail_targets) != len(canvas.nodes):
            errors.append("Native detail blocks and diagram nodes must form a reverse one-to-one mapping.")
        reverse_targets = dict(zip(detail_ids, detail_targets))
        for node in canvas.nodes:
            if node.element_tag != "a" or node.href != f"#{node.detail_for}":
                errors.append(
                    "Every detailed diagram node must remain a native link to its detail block."
                )
            if reverse_targets.get(node.detail_for) != node.object_id:
                errors.append(
                    "Every detailed diagram node and native detail block must point to each other."
                )
    if definition.get("requires_localized_node_labels"):
        if any(not node.primary_label for node in canvas.nodes):
            errors.append("Every localized diagram node requires data-node-primary-label.")
        if document_lang.startswith("zh"):
            for node in canvas.nodes:
                if _is_template_placeholder(node.primary_label):
                    errors.append(
                        "Chinese artifacts must resolve every diagram node primary-label placeholder."
                    )
                elif node.primary_label and HAN_CHARACTER_RE.search(node.primary_label) is None:
                    errors.append(
                        "Chinese artifacts require Chinese primary labels on every diagram node."
                    )
    return errors


def generic_contract_errors(
    html: str,
    family: str,
    template_id: str,
    policy: Mapping[str, Any],
) -> List[str]:
    relative = f"{family}/{template_id}.html"
    if relative in set(policy["sequence_exclusions"]):
        return []
    definition = policy["families"].get(family, {}).get("templates", {}).get(template_id)
    if definition is None:
        return [f"No generic contract policy exists for {family}/{template_id}."]
    parser = _GenericContractParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        return [f"Could not parse generic diagram contract: {exc}."]
    errors = list(parser.errors)
    errors.extend(_validate_visible_language(html, parser.document_lang))
    if definition.get("requires_node_detail_hint_in_reading_guide"):
        if parser.node_detail_hint_count != 1:
            errors.append(
                "Detailed architecture templates require exactly one node-detail interaction hint."
            )
        if parser.node_detail_hint_reading_guide_count != 1:
            errors.append(
                "The node-detail interaction hint must be inside the interaction group of the evidence reading guide."
            )
        if parser.node_detail_hint_canvas_count:
            errors.append(
                "The node-detail interaction hint must not float inside the primary SVG canvas."
            )
    if not parser.canvases:
        errors.append("Generic diagram contract requires at least one canvas.")
        return errors
    family_limits = policy["families"][family]["limits"]
    limits = {**family_limits, **definition["limits"]}
    canvas_ids = [canvas.attrs.get("data-diagram-id", "").strip() for canvas in parser.canvases]
    if "" in canvas_ids:
        errors.append("Every diagram canvas requires a non-empty data-diagram-id.")
    if len(canvas_ids) != len(set(canvas_ids)):
        errors.append("Diagram canvas ids must be unique.")
    semantic_targets = set(canvas_ids)
    for canvas in parser.canvases:
        attrs = canvas.attrs
        canvas_id = attrs.get("data-diagram-id", "").strip()
        if attrs.get("data-diagram-contract") != GENERIC_CONTRACT_VERSION:
            errors.append("Diagram canvas contract must be version 1.")
        if attrs.get("data-diagram-profile") != definition["profile"]:
            errors.append("Diagram canvas profile must match its trusted family policy.")
        if attrs.get("data-diagram-width") not in GENERIC_WIDTH_MODES:
            errors.append("Diagram canvas width mode is invalid.")
        if attrs.get("data-diagram-height") not in GENERIC_HEIGHT_MODES:
            errors.append("Diagram canvas height mode is invalid.")
        if attrs.get("data-diagram-mobile") not in GENERIC_MOBILE_MODES:
            errors.append("Diagram canvas mobile fallback mode is invalid.")
        semantic_ids = canvas.node_ids + canvas.group_ids
        if any(not value for value in semantic_ids):
            errors.append("Diagram node and group ids must be non-empty.")
        if len(semantic_ids) != len(set(semantic_ids)):
            errors.append("Diagram node and group ids must be unique within a canvas.")
        semantic_targets.update(semantic_ids)
        semantic_targets.update(canvas.detail_ids)
        endpoints = set(semantic_ids)
        relation_ids = []
        declared_relations: Dict[str, _GenericRelationRecord] = {}
        for relation in canvas.relations:
            relation_ids.append(relation.relation_id)
            if not all(
                (
                    relation.relation_id,
                    relation.source,
                    relation.target,
                    relation.kind,
                    relation.semantic,
                )
            ):
                errors.append("Every diagram relation requires id, endpoints, kind, and semantic.")
            elif relation.source not in endpoints or relation.target not in endpoints:
                errors.append("Diagram relation endpoints must reference authored nodes or groups.")
            declared_relations[relation.relation_id] = relation
            semantic_targets.add(relation.relation_id)
        if len(relation_ids) != len(set(relation_ids)):
            errors.append("Diagram relation ids must be unique within a canvas.")
        visible_relation_ids = [binding.relation_id for binding in canvas.visible_relations]
        if any(not relation_id for relation_id in visible_relation_ids):
            errors.append("Visible relation bindings must use non-empty relation ids.")
        if len(visible_relation_ids) != len(set(visible_relation_ids)):
            errors.append("Visible relation bindings must be unique within a canvas.")
        missing_visible = sorted(set(relation_ids) - set(visible_relation_ids))
        extra_visible = sorted(set(visible_relation_ids) - set(relation_ids))
        if missing_visible:
            errors.append(
                "Every diagram relation requires one visible edge binding: "
                + ", ".join(missing_visible)
                + "."
            )
        if extra_visible:
            errors.append(
                "Visible edge bindings must reference authored diagram relations: "
                + ", ".join(extra_visible)
                + "."
            )
        for binding in canvas.visible_relations:
            declared = declared_relations.get(binding.relation_id)
            if declared is None:
                continue
            if not all((binding.source, binding.target, binding.kind)):
                errors.append("Visible relation bindings require structured endpoints and kind.")
            elif (binding.source, binding.target, binding.kind) != (
                declared.source,
                declared.target,
                declared.kind,
            ):
                errors.append(
                    "Visible relation endpoints and kind must match the authored diagram relation."
                )
        errors.extend(_validate_directional_graph(canvas, definition, parser.document_lang))
        if definition["profile"] == "matrix":
            rows, columns = set(canvas.row_ids), set(canvas.col_ids)
            if not rows or not columns or not canvas.cells:
                errors.append("Matrix profile requires authored row axes, column axes, and cells.")
            for row, column in canvas.cells:
                if row not in rows or column not in columns:
                    errors.append("Matrix cells must reference authored row and column axes.")
        counts = {
            "nodes": len(canvas.node_ids),
            "relations": len(canvas.relations),
            "groups": len(canvas.group_ids),
            "details": len(canvas.detail_ids),
        }
        for key, count in counts.items():
            if count > limits[key]:
                errors.append(f"Diagram canvas exceeds the {key} complexity budget.")
        fallbacks = [fallback for fallback in parser.fallbacks if fallback.fallback_for == canvas_id]
        if canvas_id and not fallbacks:
            errors.append("Every diagram canvas requires a matching data-fallback-for baseline.")
        if len(fallbacks) > 1:
            errors.append("Every diagram canvas may have only one matching data-fallback-for baseline.")
        for fallback in fallbacks:
            fallback_ids = [binding.relation_id for binding in fallback.relations]
            if len(fallback_ids) != len(set(fallback_ids)):
                errors.append("Fallback relation ids must be unique within a canvas fallback.")
            for binding in fallback.relations:
                declared = declared_relations.get(binding.relation_id)
                if not all((binding.relation_id, binding.source, binding.target, binding.kind)):
                    errors.append("Fallback relation bindings require id, endpoints, and kind.")
                elif declared is None:
                    errors.append("Fallback relation bindings must reference authored diagram relations.")
                elif (binding.source, binding.target, binding.kind) != (
                    declared.source,
                    declared.target,
                    declared.kind,
                ):
                    errors.append(
                        "Fallback relation endpoints and kind must match the authored diagram relation."
                    )
            if "direction" in definition:
                missing_fallback = sorted(set(relation_ids) - set(fallback_ids))
                extra_fallback = sorted(set(fallback_ids) - set(relation_ids))
                if missing_fallback:
                    errors.append(
                        "Directional graph fallbacks must bind every authored relation: "
                        + ", ".join(missing_fallback)
                        + "."
                    )
                if extra_fallback:
                    errors.append(
                        "Directional graph fallback bindings reference unknown relations: "
                        + ", ".join(extra_fallback)
                        + "."
                    )
    errors.extend(
        _validate_evidence_ledger(
            parser,
            semantic_targets,
            definition.get("evidence_placement", "before-primary-canvas"),
        )
    )
    return list(dict.fromkeys(errors))


def lint_generic_contract(
    html: str,
    family: str,
    template_id: str,
    policy: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    trusted = load_family_policies() if policy is None else policy
    return generic_contract_errors(html, family, template_id, trusted)


def lint_adaptive_kernel(html: str) -> List[str]:
    errors = []
    paths = {
        "style": SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.css",
        "script": SKILL_ROOT / "assets" / "contracts" / "adaptive-viewport" / "v1.js",
    }
    for tag, path in paths.items():
        expected = path.read_text(encoding="utf-8").rstrip("\n")
        matches = re.findall(
            rf'<{tag} data-adaptive-viewport-kernel="1">\n(.*?)\n</{tag}>',
            html,
            flags=re.DOTALL,
        )
        if len(matches) != 1:
            errors.append(f"Migrated generic template requires exactly one adaptive {tag} kernel.")
        elif matches[0] != expected:
            errors.append(f"Migrated generic template adaptive {tag} kernel has drifted.")
    return errors


def lint_progressive_kernel(html: str) -> List[str]:
    errors = []
    paths = {
        "style": SKILL_ROOT / "assets" / "contracts" / "progressive-disclosure" / "v1.css",
        "script": SKILL_ROOT / "assets" / "contracts" / "progressive-disclosure" / "v1.js",
    }
    for tag, path in paths.items():
        expected = path.read_text(encoding="utf-8").rstrip("\n")
        matches = re.findall(
            rf'<{tag} data-progressive-disclosure-kernel="1">\n(.*?)\n</{tag}>',
            html,
            flags=re.DOTALL,
        )
        if len(matches) != 1:
            errors.append(
                f"Detailed diagram template requires exactly one progressive {tag} kernel."
            )
        elif matches[0] != expected:
            errors.append(f"Detailed diagram template progressive {tag} kernel has drifted.")
    return errors


class HtmlSignals(HTMLParser):
    """Collect identity, layout, style, script, and resource signals."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: List[str] = []
        self.tag_counts: Dict[str, int] = {}
        self.roles: List[str] = []
        self.classes: List[str] = []
        self.attrs: Dict[str, List[str]] = {}
        self.main_attrs: List[Dict[str, str]] = []
        self.attribute_events: List[Tuple[str, str, str]] = []
        self.elements: List[Tuple[str, Dict[str, str]]] = []
        self.styles: List[str] = []
        self.scripts: List[str] = []
        self.errors: List[str] = []
        self._style_depth = 0
        self._script_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: List[Tuple[str, Optional[str]]],
    ) -> None:
        tag = tag.lower()
        self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1
        duplicates = _duplicates(attrs)
        if duplicates:
            self.errors.append(f"Duplicate attributes on {tag}: {', '.join(duplicates)}")
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        self.elements.append((tag, attrs_map))
        if tag == "main":
            self.main_attrs.append(attrs_map)
        if tag == "meta" and attrs_map.get("http-equiv", "").strip().casefold() == "refresh":
            self.errors.append("Meta refresh navigation is forbidden")
        if tag in {"iframe", "object", "embed"}:
            self.errors.append(f"Embedded container is forbidden: {tag}")
        for name, value in attrs:
            name = name.lower()
            value = value or ""
            self.attrs.setdefault(name, []).append(value)
            self.attribute_events.append((tag, name, value))
            if name == "ping" and value.strip():
                self.errors.append("Ping navigation is forbidden")
            elif name == "role":
                self.roles.append(value)
            elif name == "class":
                self.classes.extend(value.split())
            elif name == "style":
                self.styles.append(value)
        if tag == "style":
            self._style_depth += 1
        if tag == "script":
            if attrs_map.get("type", "").strip().lower() == "module":
                self.errors.append("JavaScript module loading is forbidden")
            self._script_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style":
            self._style_depth = max(0, self._style_depth - 1)
        elif tag == "script":
            self._script_depth = max(0, self._script_depth - 1)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data)
        if self._style_depth:
            self.styles.append(data)
        if self._script_depth:
            self.scripts.append(data)

    @property
    def text(self) -> str:
        return " ".join(part.strip() for part in self.text_parts if part.strip())

    def attr_values(self, name: str) -> List[str]:
        return self.attrs.get(name.lower(), [])


def _parse(html: str) -> HtmlSignals:
    parser = HtmlSignals()
    parser.feed(html)
    parser.close()
    return parser


class _SequenceParser(HTMLParser):
    """Parse sequence semantics only from structured data attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: List[_SequenceRecord] = []
        self.errors: List[str] = []
        self.document_evidence_ids: List[str] = []
        self._active: List[_SequenceRecord] = []
        self._stack: List[Tuple[str, bool]] = []

    def _start(
        self,
        tag: str,
        attrs: List[Tuple[str, Optional[str]]],
        push: bool,
    ) -> None:
        tag = tag.lower()
        duplicates = _duplicates(attrs)
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        if "data-sequence-evidence-id" in attrs_map:
            evidence_id = attrs_map["data-sequence-evidence-id"].strip()
            self.document_evidence_ids.append(evidence_id)
            if tag != "details":
                self.errors.append("Sequence evidence ids must use native details elements.")
        is_canvas = "data-sequence-canvas" in attrs_map
        sequence_endpoint_attributes = {
            "data-from",
            "data-to",
            "data-message-kind",
            "data-semantic",
            "data-participant-id",
        }
        if duplicates and any(
            name.startswith("data-sequence") or name in sequence_endpoint_attributes
            for name in duplicates
        ):
            self.errors.append(
                f"Duplicate sequence attributes on {tag}: {', '.join(duplicates)}."
            )
        if is_canvas:
            if self._active:
                self.errors.append("Sequence canvases must not be nested.")
            record = _SequenceRecord(attrs_map, [], [], [], [], [], [], [], [], [])
            self.records.append(record)
            self._active.append(record)
        if self._active:
            record = self._active[-1]
            if "data-participant-id" in attrs_map:
                record.participant_ids.append(attrs_map["data-participant-id"].strip())
            if "data-participant-group-id" in attrs_map:
                record.participant_group_ids.append(
                    attrs_map["data-participant-group-id"].strip()
                )
            if "data-sequence-message" in attrs_map:
                record.messages.append(
                    (
                        attrs_map.get("data-from", "").strip(),
                        attrs_map.get("data-to", "").strip(),
                        attrs_map.get("data-message-kind", "").strip(),
                        attrs_map.get("data-semantic", "").strip(),
                    )
                )
                record.message_steps.append(
                    attrs_map.get("data-sequence-step-index", "").strip()
                )
            if "data-sequence-phase-id" in attrs_map:
                record.phase_ids.append(attrs_map["data-sequence-phase-id"].strip())
            if (
                "data-sequence-fragment-id" in attrs_map
                or "data-sequence-fragment-kind" in attrs_map
            ):
                record.fragments.append(
                    (
                        attrs_map.get("data-sequence-fragment-id", "").strip(),
                        attrs_map.get("data-sequence-fragment-kind", "").strip(),
                    )
                )
            if "data-sequence-outcome" in attrs_map:
                record.outcomes.append(attrs_map["data-sequence-outcome"].strip())
            if "data-sequence-risk-id" in attrs_map:
                record.risk_ids.append(attrs_map["data-sequence-risk-id"].strip())
            if "data-sequence-evidence-for" in attrs_map:
                record.evidence_links.append(
                    attrs_map["data-sequence-evidence-for"].strip()
                )
        if push and tag not in VOID_ELEMENTS:
            self._stack.append((tag, is_canvas))
        elif is_canvas:
            self.errors.append("A sequence canvas must not be a void or self-closing element.")
            self._active.pop()

    def handle_starttag(
        self,
        tag: str,
        attrs: List[Tuple[str, Optional[str]]],
    ) -> None:
        self._start(tag, attrs, push=True)

    def handle_startendtag(
        self,
        tag: str,
        attrs: List[Tuple[str, Optional[str]]],
    ) -> None:
        self._start(tag, attrs, push=False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return
        open_tag, closes_canvas = self._stack.pop()
        if open_tag != tag:
            self.errors.append(f"Malformed sequence markup: expected </{open_tag}>, got </{tag}>.")
        if closes_canvas and self._active:
            self._active.pop()

    def finish(self) -> None:
        if self._active:
            self.errors.append("A sequence canvas is not closed.")


def _parse_sequence_records(html: str) -> _SequenceParser:
    parser = _SequenceParser()
    parser.feed(html)
    parser.close()
    parser.finish()
    return parser


def parse_sequence_canvases(html: str) -> Tuple[SequenceCanvas, ...]:
    """Return structured sequence canvases without reading visible route text."""

    parser = _parse_sequence_records(html)
    if parser.errors:
        raise ValueError("; ".join(parser.errors))
    return tuple(
        SequenceCanvas(
            canvas_id=record.attrs.get("data-sequence-id", "").strip(),
            role=record.attrs.get("data-sequence-role", "").strip(),
            detail_for=record.attrs.get("data-sequence-detail-for", "").strip(),
            participant_ids=tuple(record.participant_ids),
            messages=tuple(record.messages),
            phase_ids=tuple(record.phase_ids),
        )
        for record in parser.records
    )


def _decode_css_escapes(value: str) -> str:
    def replace(match: re.Match) -> str:
        if match.group(1):
            codepoint = int(match.group(1), 16)
            return chr(codepoint) if codepoint and codepoint <= 0x10FFFF else "\ufffd"
        return match.group(2) or "\ufffd"

    return CSS_ESCAPE_RE.sub(replace, value)


def _decode_javascript_escapes(value: str) -> str:
    def replace(match: re.Match) -> str:
        codepoint = int(next(group for group in match.groups() if group is not None), 16)
        return chr(codepoint) if codepoint <= 0x10FFFF else "\ufffd"

    return JAVASCRIPT_ESCAPE_RE.sub(replace, value)


def _allowed_embedded_reference(value: str) -> bool:
    value = value.strip()
    return not value or value.startswith("#") or value.startswith("data:")


def load_template_layouts(
    template_root: Path = TEMPLATE_ROOT,
) -> Dict[str, Dict[str, str]]:
    """Read family, id, and layout from packaged assets and fail closed."""

    paths = sorted(template_root.rglob("*.html"), key=lambda path: path.relative_to(template_root).as_posix())
    if len(paths) != EXPECTED_TEMPLATE_COUNT:
        raise ValueError(f"Expected {EXPECTED_TEMPLATE_COUNT} template assets, found {len(paths)}")
    catalog: Dict[str, Dict[str, str]] = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"Template assets must not be symlinks: {path}")
        parser = _parse(path.read_text(encoding="utf-8"))
        if parser.errors:
            raise ValueError(f"Invalid template {path}: {'; '.join(parser.errors)}")
        if len(parser.main_attrs) != 1:
            raise ValueError(f"Template must contain exactly one main element: {path}")
        attrs = parser.main_attrs[0]
        family = attrs.get("data-template-family", "").strip()
        template_id = attrs.get("data-template-id", "").strip()
        layout = attrs.get("data-template-layout", "").strip()
        if not family or not template_id or not layout:
            raise ValueError(f"Template identity is incomplete: {path}")
        if family != path.parent.name or template_id != path.stem:
            raise ValueError(f"Template identity does not match path: {path}")
        family_entries = catalog.setdefault(family, {})
        if template_id in family_entries:
            raise ValueError(f"Duplicate template identity: {family}/{template_id}")
        family_entries[template_id] = layout
    return catalog


class _StructureSignatureParser(HTMLParser):
    """Record DOM structure while ignoring authored text and semantic identifiers."""

    def __init__(self, drop_attributes: Iterable[str] = ()) -> None:
        super().__init__(convert_charrefs=True)
        self.events: List[Tuple[Any, ...]] = []
        self._drop_attributes = frozenset(name.lower() for name in drop_attributes)

    @staticmethod
    def _controlled_sequence_style(value: str) -> str:
        declarations = []
        for declaration in value.split(";"):
            declaration = declaration.strip()
            if not declaration:
                continue
            if ":" not in declaration:
                return value
            name, raw_value = (part.strip().lower() for part in declaration.split(":", 1))
            if name not in {"--sequence-start", "--sequence-span"}:
                return value
            if re.fullmatch(r"(?:[1-9]|1[0-2])", raw_value) is None:
                return value
            declarations.append((name, "_"))
        if not declarations or len(declarations) != len(set(name for name, _value in declarations)):
            return value
        return ";".join(f"{name}:{raw_value}" for name, raw_value in sorted(declarations))

    def _attrs(
        self,
        attrs: Sequence[Tuple[str, Optional[str]]],
    ) -> Tuple[Tuple[str, str], ...]:
        normalized = []
        names = {name.lower() for name, _value in attrs}
        is_sequence_message = "data-sequence-message" in names
        for name, value in attrs:
            name = name.lower()
            if name in self._drop_attributes:
                continue
            if is_sequence_message and name == "style":
                normalized.append((name, self._controlled_sequence_style(value or "")))
            elif name.startswith("aria-") or name in MUTABLE_STRUCTURE_ATTRIBUTES:
                normalized.append((name, "_"))
            else:
                normalized.append((name, value or ""))
        return tuple(sorted(normalized))

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.events.append(("start", tag.lower(), self._attrs(attrs)))

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.events.append(("empty", tag.lower(), self._attrs(attrs)))

    def handle_endtag(self, tag: str) -> None:
        self.events.append(("end", tag.lower()))

    def handle_decl(self, decl: str) -> None:
        self.events.append(("decl", decl.strip().lower()))


class _PrimarySlotTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: List[Tuple[str, bool, bool, str]] = []
        self.text: Dict[str, List[str]] = {}

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        classes = set(values.get("class", "").split())
        parent_primary = self._stack[-1][1] if self._stack else False
        parent_details = self._stack[-1][2] if self._stack else False
        parent_slot = self._stack[-1][3] if self._stack else ""
        primary = parent_primary or "template-layout" in classes
        in_details = parent_details or tag.lower() == "details"
        slot = values.get("data-slot", "").strip() or parent_slot
        self._stack.append((tag.lower(), primary, in_details, slot))
        if primary and not in_details and slot:
            self.text.setdefault(slot, [])

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._stack:
            return
        _tag, primary, in_details, slot = self._stack[-1]
        if primary and not in_details and slot:
            self.text.setdefault(slot, []).append(data)


def _structure_signature(html: str, drop_attributes: Iterable[str] = ()) -> str:
    parser = _StructureSignatureParser(drop_attributes)
    parser.feed(html)
    parser.close()
    payload = json.dumps(parser.events, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _block_inventory(pattern: re.Pattern[str], html: str) -> List[Tuple[str, str]]:
    return [
        (re.sub(r"\s+", " ", match.group("attrs").strip()), match.group("body"))
        for match in pattern.finditer(html)
    ]


def _prototype_signatures(pattern: re.Pattern[str], html: str) -> List[str]:
    return [
        _structure_signature(match.group(0), drop_attributes={"data-slot"})
        for match in pattern.finditer(html)
    ]


def _collapse_sequence_prototypes(html: str) -> str:
    html = SEQUENCE_PARTICIPANT_FRAGMENT_RE.sub(
        "<vibe-sequence-participant></vibe-sequence-participant>", html
    )
    html = SEQUENCE_MESSAGE_FRAGMENT_RE.sub(
        "<vibe-sequence-message></vibe-sequence-message>", html
    )
    html = re.sub(
        r"(?:<vibe-sequence-participant></vibe-sequence-participant>\s*)+",
        "<vibe-sequence-participant></vibe-sequence-participant>",
        html,
    )
    return re.sub(
        r"(?:<vibe-sequence-message></vibe-sequence-message>\s*)+",
        "<vibe-sequence-message></vibe-sequence-message>",
        html,
    )


def lint_visual_shell(html: str) -> List[str]:
    """Require the two gradients, 28px grid, and page gradient visual shell."""

    css = "\n".join(body for _attrs, body in _block_inventory(STYLE_BLOCK_RE, html))
    normalized = re.sub(r"\s+", "", css).lower()
    missing = [token for token in VISUAL_SHELL_TOKENS if token.lower() not in normalized]
    if not missing:
        return []
    return ["The locked visual shell has drifted or is incomplete: " + ", ".join(missing) + "."]


def lint_template_conformance(html: str, diagram_type: str) -> List[str]:
    """Compare an artifact with its declared canonical template instead of trusting identity."""

    identity_errors = lint_template_identity(html, diagram_type)
    if identity_errors:
        return identity_errors
    parsed = _parse(html)
    attrs = parsed.main_attrs[0]
    template_id = attrs.get("data-template-id", "").strip()
    if attrs.get("data-template-contract-version", "").strip() != TEMPLATE_CONTRACT_VERSION:
        return [f"Template contract version must be {TEMPLATE_CONTRACT_VERSION}."]
    template_path = TEMPLATE_ROOT / diagram_type / f"{template_id}.html"
    canonical = template_path.read_text(encoding="utf-8")
    errors: List[str] = []
    if _block_inventory(STYLE_BLOCK_RE, html) != _block_inventory(STYLE_BLOCK_RE, canonical):
        errors.append("Style blocks must match the declared canonical template exactly.")
    if _block_inventory(SCRIPT_BLOCK_RE, html) != _block_inventory(SCRIPT_BLOCK_RE, canonical):
        errors.append("Script blocks must match the declared canonical template exactly.")
    artifact_slots = Counter(parsed.attr_values("data-slot"))
    canonical_slots = Counter(_parse(canonical).attr_values("data-slot"))
    if artifact_slots != canonical_slots:
        errors.append("The canonical template slot inventory has drifted.")
    is_sequence = "data-sequence-canvas" in canonical
    if is_sequence:
        for label, pattern in (
            ("participant", SEQUENCE_PARTICIPANT_FRAGMENT_RE),
            ("message", SEQUENCE_MESSAGE_FRAGMENT_RE),
        ):
            allowed = set(_prototype_signatures(pattern, canonical))
            actual = _prototype_signatures(pattern, html)
            if any(signature not in allowed for signature in actual):
                errors.append(f"A sequence {label} does not match a canonical prototype.")
        artifact_structure = _structure_signature(_collapse_sequence_prototypes(html))
        canonical_structure = _structure_signature(_collapse_sequence_prototypes(canonical))
    else:
        artifact_structure = _structure_signature(html)
        canonical_structure = _structure_signature(canonical)
    if artifact_structure != canonical_structure:
        errors.append("The artifact DOM structure does not match the declared canonical template.")
    return errors


def lint_primary_canvas_budget(html: str) -> List[str]:
    """Keep the first visible canvas concise while leaving native details unrestricted."""

    errors: List[str] = []
    if "data-sequence-canvas" in html:
        sequence = _parse_sequence_records(html)
        for record in sequence.records:
            role = record.attrs.get("data-sequence-role", "standalone").strip()
            if role != "detail" and len(record.messages) > PRIMARY_SEQUENCE_MESSAGE_LIMIT:
                errors.append(
                    f"A primary sequence canvas may contain at most {PRIMARY_SEQUENCE_MESSAGE_LIMIT} messages; use mapped overview and detail canvases."
                )
    parser = _PrimarySlotTextParser()
    parser.feed(html)
    parser.close()
    baseline_text: Dict[str, str] = {}
    identity = _parse(html)
    if len(identity.main_attrs) == 1:
        attrs = identity.main_attrs[0]
        family = attrs.get("data-template-family", "").strip()
        template_id = attrs.get("data-template-id", "").strip()
        template_path = TEMPLATE_ROOT / family / f"{template_id}.html"
        if template_path.is_file() and not template_path.is_symlink():
            baseline_parser = _PrimarySlotTextParser()
            baseline_parser.feed(template_path.read_text(encoding="utf-8"))
            baseline_parser.close()
            for slot, parts in baseline_parser.text.items():
                value = re.sub(r"\{\{[^{}]+\}\}", "", " ".join(parts))
                baseline_text[slot] = re.sub(r"\s+", " ", value).strip()
    for slot, parts in parser.text.items():
        visible = re.sub(r"\{\{[^{}]+\}\}", "", " ".join(parts))
        visible = re.sub(r"\s+", " ", visible).strip()
        allowed = len(baseline_text.get(slot, "")) + PRIMARY_SLOT_TEXT_LIMIT
        if len(visible) > allowed:
            errors.append(
                f'Primary canvas slot "{slot}" exceeds the {PRIMARY_SLOT_TEXT_LIMIT}-character authored presentation budget.'
            )
        if SOURCE_PATH_RE.search(visible):
            errors.append(f'Primary canvas slot "{slot}" must move source paths into mapped details.')
    return errors


def lint_title_description_stacking(html: str) -> List[str]:
    """Require title/body node pairs to use vertical rather than row flex."""

    title_description_classes = set()
    for match in TITLE_DESCRIPTION_NODE_RE.finditer(html):
        title_description_classes.update(match.group("class").split())
    if not title_description_classes:
        return []
    css_rules: Dict[str, List[str]] = {}
    for match in CSS_CLASS_RULE_RE.finditer(html):
        css_rules.setdefault(match.group("class"), []).append(match.group("body"))
    horizontal = sorted(
        class_name
        for class_name in title_description_classes
        for body in css_rules.get(class_name, [])
        if re.search(r"(?:^|;)\s*display\s*:\s*flex\s*(?:;|$)", body, re.IGNORECASE)
        and not re.search(
            r"(?:^|;)\s*flex-direction\s*:\s*column\s*(?:;|$)",
            body,
            re.IGNORECASE,
        )
    )
    if not horizontal:
        return []
    return [
        "Node titles and descriptions must be stacked vertically; "
        + ", ".join(f".{name}" for name in horizontal)
        + " uses row flex without flex-direction: column."
    ]


def lint_visible_svg_relation_bindings(html: str) -> List[str]:
    """Require every authored architecture relation to bind to one SVG edge."""

    parser = _parse(html)
    declared = {
        attrs["data-diagram-relation-id"].strip(): (
            attrs.get("data-from", "").strip(),
            attrs.get("data-to", "").strip(),
            attrs.get("data-relation-kind", "").strip(),
        )
        for _tag, attrs in parser.elements
        if "data-diagram-relation-id" in attrs
    }
    visible_records = [
        (
            attrs["data-diagram-visible-relation-id"].strip(),
            attrs.get("data-from", "").strip(),
            attrs.get("data-to", "").strip(),
            attrs.get("data-relation-kind", "").strip(),
        )
        for tag, attrs in parser.elements
        if tag in {"line", "path", "polygon", "polyline"}
        and "data-diagram-visible-relation-id" in attrs
    ]
    visible = [record[0] for record in visible_records]
    errors = []
    if any(not value for value in visible):
        errors.append("Visible SVG relation bindings must use non-empty relation ids.")
    if len(visible) != len(set(visible)):
        errors.append("Visible SVG relation bindings must be unique.")
    missing = sorted(set(declared) - set(visible))
    extra = sorted(set(visible) - set(declared))
    if missing:
        errors.append("Every architecture relation requires a visible SVG path binding: " + ", ".join(missing) + ".")
    if extra:
        errors.append("Visible SVG path bindings must reference authored architecture relations: " + ", ".join(extra) + ".")
    for relation_id, source, target, kind in visible_records:
        if relation_id not in declared:
            continue
        if not all((source, target, kind)):
            errors.append(
                f"Visible SVG relation path requires structured endpoints and kind: {relation_id}."
            )
            continue
        expected_source, expected_target, expected_kind = declared[relation_id]
        if (source, target) != (expected_source, expected_target):
            errors.append(
                f"Visible SVG relation path endpoints must match the authored architecture relation: {relation_id}."
            )
        if kind != expected_kind:
            errors.append(
                f"Visible SVG relation path kind must match the authored architecture relation: {relation_id}."
            )
    return errors


def lint_system_architecture(
    html: str,
    allow_candidates: bool = False,
) -> List[str]:
    """Apply presentation-specific density and candidate-view gates."""

    parser = _parse(html)
    errors = lint_title_description_stacking(html)
    errors.extend(lint_visible_svg_relation_bindings(html))
    if parser.tag_counts.get("svg", 0) == 0:
        errors.append("The primary system architecture canvas must contain an SVG diagram.")
    if not allow_candidates and "tablist" in parser.roles:
        errors.append("Candidate tabs require explicit calibration mode approval.")
    if HORIZONTAL_CANVAS_SCROLL_RE.search(html) or OVERSIZED_MIN_WIDTH_RE.search(html):
        errors.append("The architecture canvas must not depend on horizontal scrolling or oversized min-width.")
    node_count = sum(
        1
        for class_name in parser.classes
        if class_name in {"node", "card", "evidence", "evidence-button", "fact-card"}
    )
    grammars = " ".join(parser.attr_values("data-diagram-grammar"))
    if node_count >= 18 and "system-architecture-presentation" not in grammars:
        errors.append("Excessive node density requires an explicit presentation grammar or a split view.")
    evidence_count = len(EVIDENCE_RE.findall(parser.text))
    source_count = len(SOURCE_PATH_RE.findall(parser.text))
    if evidence_count > 6 or source_count > 6:
        errors.append("Move dense evidence and source paths out of the primary architecture canvas.")
    return errors


def lint_template_identity(html: str, diagram_type: str) -> List[str]:
    """Require an artifact to identify one known packaged template and layout."""

    parser = _parse(html)
    errors = list(parser.errors)
    if len(parser.main_attrs) != 1:
        errors.append("The artifact must contain exactly one main element with template identity.")
        return errors
    attrs = parser.main_attrs[0]
    family = attrs.get("data-template-family", "").strip()
    declared_type = attrs.get("data-diagram-type", "").strip()
    template_id = attrs.get("data-template-id", "").strip()
    layout = attrs.get("data-template-layout", "").strip()
    if family != diagram_type:
        errors.append(f'Template family must equal the requested diagram type "{diagram_type}".')
    if declared_type != diagram_type:
        errors.append(f'Diagram type must equal the requested diagram type "{diagram_type}".')
    catalog = load_template_layouts()
    expected_layout = catalog.get(diagram_type, {}).get(template_id)
    if expected_layout is None:
        errors.append(f'Template id "{template_id or "<missing>"}" must name a known template for {diagram_type}.')
        return errors
    if layout != expected_layout:
        errors.append(
            f'Template layout for "{template_id}" must be "{expected_layout}", not "{layout or "<missing>"}".'
        )
    return errors


def lint_sequence_contract(html: str) -> List[str]:
    """Validate structured sequence identities, endpoints, limits, and split linkage."""

    parser = _parse_sequence_records(html)
    errors = list(parser.errors)
    canvases = [
        SequenceCanvas(
            canvas_id=record.attrs.get("data-sequence-id", "").strip(),
            role=record.attrs.get("data-sequence-role", "").strip(),
            detail_for=record.attrs.get("data-sequence-detail-for", "").strip(),
            participant_ids=tuple(record.participant_ids),
            messages=tuple(record.messages),
            phase_ids=tuple(record.phase_ids),
        )
        for record in parser.records
    ]
    if not canvases:
        errors.append("A sequence artifact must contain at least one data-sequence-canvas.")
    evidence_ids = parser.document_evidence_ids
    if any(not evidence_id for evidence_id in evidence_ids):
        errors.append("Sequence evidence ids must be non-empty.")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("Sequence evidence ids must be unique within a document.")
    evidence_targets = set(evidence_ids)
    canvas_ids = [canvas.canvas_id for canvas in canvases]
    for index, (record, canvas) in enumerate(zip(parser.records, canvases), start=1):
        label = canvas.canvas_id or f"canvas-{index}"
        contract = record.attrs.get("data-sequence-contract", "").strip()
        width = record.attrs.get("data-sequence-width", "").strip()
        height = record.attrs.get("data-sequence-height", "").strip()
        if not canvas.canvas_id:
            errors.append(f"Sequence {label} must declare a non-empty data-sequence-id.")
        elif canvas_ids.count(canvas.canvas_id) > 1:
            errors.append(f'Sequence canvas id "{canvas.canvas_id}" is duplicated.')
        if contract != SEQUENCE_CONTRACT_VERSION:
            errors.append(
                f'Sequence {label} contract must be "{SEQUENCE_CONTRACT_VERSION}".'
            )
        if canvas.role not in SEQUENCE_ROLES:
            errors.append(f"Sequence {label} role must be standalone, overview, or detail.")
        if width not in SEQUENCE_WIDTH_MODES:
            errors.append(f"Sequence {label} width mode must be auto, contained, or wide.")
        if height not in SEQUENCE_HEIGHT_MODES:
            errors.append(f"Sequence {label} height mode must be auto, flow, or scroll.")
        if canvas.role == "detail" and not canvas.detail_for:
            errors.append(f"Detail sequence {label} must declare data-sequence-detail-for.")
        if canvas.role in {"standalone", "overview"} and canvas.detail_for:
            errors.append(f"Sequence {label} with role {canvas.role} must not declare detail-for.")
        if any(not participant for participant in canvas.participant_ids):
            errors.append(f"Sequence {label} participant ids must be non-empty.")
        if len(canvas.participant_ids) < 2:
            errors.append(f"Sequence {label} must declare at least two participants.")
        if not canvas.messages:
            errors.append(f"Sequence {label} must declare at least one primary message.")
        duplicate_participants = sorted(
            {
                participant
                for participant in canvas.participant_ids
                if participant and canvas.participant_ids.count(participant) > 1
            }
        )
        if duplicate_participants:
            errors.append(
                f"Sequence {label} has duplicate participant ids: "
                + ", ".join(duplicate_participants)
                + "."
            )
        if any(not phase for phase in canvas.phase_ids):
            errors.append(f"Sequence {label} phase ids must be non-empty.")
        duplicate_phases = sorted(
            {phase for phase in canvas.phase_ids if phase and canvas.phase_ids.count(phase) > 1}
        )
        if duplicate_phases:
            errors.append(
                f"Sequence {label} has duplicate phase ids: " + ", ".join(duplicate_phases) + "."
            )
        participant_group_ids = record.participant_group_ids
        if any(not group_id for group_id in participant_group_ids):
            errors.append(f"Sequence {label} participant group ids must be non-empty.")
        if len(participant_group_ids) != len(set(participant_group_ids)):
            errors.append(f"Sequence {label} participant group ids must be unique.")
        message_steps = record.message_steps
        if any(message_steps):
            if any(not step for step in message_steps):
                errors.append(
                    f"Sequence {label} must give every message a step index when step indexing is used."
                )
            non_empty_steps = [step for step in message_steps if step]
            if len(non_empty_steps) != len(set(non_empty_steps)):
                errors.append(f"Sequence {label} message step indices must be unique.")
            if any(re.fullmatch(r"\d{1,3}", step) is None for step in non_empty_steps):
                errors.append(
                    f"Sequence {label} message step indices must use one to three digits."
                )
        fragment_ids = [fragment_id for fragment_id, _kind in record.fragments]
        for fragment_id, kind in record.fragments:
            if not fragment_id or not kind:
                errors.append(
                    f"Sequence {label} fragments require both stable ids and kinds."
                )
            elif kind not in SEQUENCE_FRAGMENT_KINDS:
                errors.append(f"Sequence {label} fragment kind is not supported: {kind}.")
        if len(fragment_ids) != len(set(fragment_ids)):
            errors.append(f"Sequence {label} fragment ids must be unique.")
        for outcome in record.outcomes:
            if outcome not in SEQUENCE_OUTCOMES:
                errors.append(f"Sequence {label} outcome is not supported: {outcome or '<missing>'}.")
        if any(not risk_id for risk_id in record.risk_ids):
            errors.append(f"Sequence {label} risk ids must be non-empty.")
        if len(record.risk_ids) != len(set(record.risk_ids)):
            errors.append(f"Sequence {label} risk ids must be unique.")
        for evidence_for in record.evidence_links:
            if not evidence_for or evidence_for not in evidence_targets:
                errors.append(
                    f"Sequence {label} evidence link must reference a native document evidence detail."
                )
        participants = set(canvas.participant_ids)
        for message_index, (source, target, kind, semantic) in enumerate(canvas.messages, start=1):
            if not source or not target or source not in participants or target not in participants:
                errors.append(
                    f"Sequence {label} message {message_index} endpoint must reference a declared participant."
                )
            if kind not in SEQUENCE_MESSAGE_KINDS:
                errors.append(f"Sequence {label} message {message_index} has an unknown message kind.")
            if not semantic:
                errors.append(f"Sequence {label} message {message_index} must declare data-semantic.")
            if kind == "self" and source != target:
                errors.append(
                    f"Sequence {label} self message {message_index} must use the same endpoint."
                )
            if kind in SEQUENCE_MESSAGE_KINDS - {"self"} and source and source == target:
                errors.append(
                    f"Sequence {label} non-self message {message_index} must use different endpoints."
                )
        participant_over = len(canvas.participant_ids) > SEQUENCE_PARTICIPANT_LIMIT
        message_over = len(canvas.messages) > SEQUENCE_MESSAGE_LIMIT
        phase_over = len(canvas.phase_ids) > SEQUENCE_PHASE_LIMIT
        if canvas.role in {"standalone", "detail"} and (
            participant_over or message_over or phase_over
        ):
            errors.append(
                f"Sequence {label} exceeds the complexity budget; "
                "split into one overview and linked detail sequences."
            )
        if canvas.role == "overview" and (participant_over or message_over):
            errors.append(
                f"Overview sequence {label} exceeds its participant or message complexity budget."
            )

    standalones = [canvas for canvas in canvases if canvas.role == "standalone"]
    overviews = [canvas for canvas in canvases if canvas.role == "overview"]
    details = [canvas for canvas in canvases if canvas.role == "detail"]
    if standalones and (overviews or details):
        errors.append("Standalone sequences must not be mixed with overview or detail sequences.")
    if details and len(overviews) != 1:
        errors.append("Documents with detail sequences must contain exactly one overview sequence.")
    if len(overviews) > 1:
        errors.append("A sequence document must not contain more than one overview sequence.")
    if overviews:
        overview = overviews[0]
        detail_phases = [detail.detail_for for detail in details if detail.detail_for]
        for detail in details:
            if detail.detail_for and detail.detail_for not in set(overview.phase_ids):
                errors.append(
                    f'Detail sequence {detail.canvas_id or "<missing>"} references unknown overview phase '
                    f'"{detail.detail_for}".'
                )
        for phase in overview.phase_ids:
            if phase and phase not in detail_phases:
                errors.append(f'Overview phase "{phase}" must have at least one linked detail sequence.')
        if not details:
            errors.append("An overview sequence must have linked detail sequences.")
        else:
            detail_participants = {
                participant for detail in details for participant in detail.participant_ids if participant
            }
            detail_message_count = sum(len(detail.messages) for detail in details)
            split_is_needed = (
                len(detail_participants) > SEQUENCE_PARTICIPANT_LIMIT
                or detail_message_count > SEQUENCE_MESSAGE_LIMIT
                or len(overview.phase_ids) > SEQUENCE_PHASE_LIMIT
            )
            if not split_is_needed:
                errors.append(
                    "The overview and detail split is unnecessary within the sequence complexity budget."
                )
    return _deduplicate(errors)


def _sequence_kernel_block(html: str, tag: str) -> str:
    pattern = re.compile(
        rf"<{tag}\b(?P<attrs>[^>]*)>(?P<body>.*?)</{tag}\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    blocks = []
    for match in pattern.finditer(html):
        attrs = match.group("attrs")
        if re.search(r"\bdata-sequence-kernel\b", attrs, re.IGNORECASE):
            version = re.search(
                r"\bdata-sequence-kernel\s*=\s*([\"'])(?P<version>.*?)\1",
                attrs,
                re.IGNORECASE | re.DOTALL,
            )
            blocks.append((version.group("version") if version else "", match.group("body")))
    if len(blocks) != 1:
        raise ValueError(f"Expected exactly one sequence kernel {tag} block, found {len(blocks)}.")
    version, body = blocks[0]
    if version != SEQUENCE_CONTRACT_VERSION:
        raise ValueError(f"Sequence kernel {tag} version must be {SEQUENCE_CONTRACT_VERSION}.")
    return body


def extract_sequence_kernel_digest(html: str) -> str:
    """Hash the exact shared sequence kernel style and script contents."""

    style = _sequence_kernel_block(html, "style").encode("utf-8")
    script = _sequence_kernel_block(html, "script").encode("utf-8")
    payload = b"sequence-kernel-v1\0" + style + b"\0" + script
    return hashlib.sha256(payload).hexdigest()


def lint_self_contained_resources(html: str) -> List[str]:
    """Reject resources or runtime APIs that can leave the single HTML file."""

    parser = _parse(html)
    errors = list(parser.errors)
    for tag, name, value in parser.attribute_events:
        if name == "srcset" and value.strip():
            errors.append("The srcset resource candidate list is forbidden.")
        elif name in RESOURCE_ATTRIBUTES and not _allowed_embedded_reference(value):
            errors.append(f"External or relative resource is forbidden: {tag}[{name}]={value}")
        elif name in LINK_ATTRIBUTES and not _allowed_embedded_reference(value):
            errors.append(f"External or relative link is forbidden: {tag}[{name}]={value}")
    for css in parser.styles:
        normalized = _decode_css_escapes(css)
        if re.search(r"@import\b", normalized, re.IGNORECASE):
            errors.append("CSS @import is forbidden.")
        if re.search(r"(?:-webkit-)?image-set\s*\(", normalized, re.IGNORECASE):
            errors.append("CSS image-set resources are forbidden.")
        for match in CSS_URL_RE.finditer(normalized):
            if not _allowed_embedded_reference(match.group(2)):
                errors.append(f"External or relative CSS url is forbidden: {match.group(2)}")
    script = _decode_javascript_escapes("\n".join(parser.scripts))
    for pattern in NETWORK_SCRIPT_PATTERNS:
        if pattern.search(script):
            errors.append(f"Runtime network or dynamic-code API is forbidden: {pattern.pattern}")
    return errors


def _deduplicate(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a self-contained HTML diagram.")
    parser.add_argument("path", type=Path, help="HTML artifact to validate")
    parser.add_argument("--type", required=True, dest="diagram_type", help="diagram family")
    parser.add_argument(
        "--allow-candidates",
        action="store_true",
        help="allow candidate tabs for an explicitly requested calibration atlas",
    )
    args = parser.parse_args(argv)
    try:
        html = args.path.read_text(encoding="utf-8")
        errors = lint_self_contained_resources(html)
        errors.extend(_validate_visible_language(html, ""))
        errors.extend(lint_template_identity(html, args.diagram_type))
        errors.extend(lint_visual_shell(html))
        errors.extend(lint_template_conformance(html, args.diagram_type))
        errors.extend(lint_primary_canvas_budget(html))
        if args.diagram_type == "system-architecture":
            errors.extend(lint_system_architecture(html, allow_candidates=args.allow_candidates))
        else:
            errors.extend(lint_title_description_stacking(html))
        identity = _parse(html)
        requires_sequence = args.diagram_type == "code-sequence" or any(
            (
                attrs.get("data-template-family", "").strip(),
                attrs.get("data-template-id", "").strip(),
            )
            in SEQUENCE_OWNER_TEMPLATES
            for attrs in identity.main_attrs
        )
        if requires_sequence or "data-sequence-canvas" in html:
            errors.extend(lint_sequence_contract(html))
        policy = load_family_policies()
        completed = {
            relative
            for paths in policy["migration_batches"].values()
            for relative in paths
        }
        for attrs in identity.main_attrs:
            family = attrs.get("data-template-family", "").strip()
            template_id = attrs.get("data-template-id", "").strip()
            if f"{family}/{template_id}.html" in completed:
                errors.extend(lint_generic_contract(html, family, template_id, policy))
                errors.extend(lint_adaptive_kernel(html))
                definition = policy["families"][family]["templates"][template_id]
                if definition.get("requires_node_details"):
                    errors.extend(lint_progressive_kernel(html))
    except (OSError, UnicodeError, ValueError) as exc:
        errors = [str(exc)]
    errors = _deduplicate(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.path}")
    print("EVIDENCE: static-contract-valid; browser-rendering=not-verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
