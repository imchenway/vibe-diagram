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
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
FAMILY_POLICY_PATH = SKILL_ROOT / "contracts" / "family-policies.json"
TEMPLATE_ROUTING_PATH = SKILL_ROOT / "contracts" / "template-routing.json"
EXPECTED_TEMPLATE_COUNT = 31
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
ROUTING_FAMILY_KEYS = frozenset(
    {"default_template", "ready_templates", "blocked_templates"}
)
CODE_REVIEW_ROUTE_KEYS = frozenset({"family", "template", "primary_relation"})
EVIDENCE_STATUSES = frozenset({"observed", "inferred", "proposed", "unresolved"})
EVIDENCE_PLACEMENTS = frozenset(
    {"before-primary-canvas", "after-primary-canvas", "inside-primary-canvas"}
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
EMOJI_RE = re.compile(r"[\u2600-\u27bf\U0001f1e6-\U0001faff]")
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
        "requires_localized_node_labels",
        "requires_geometric_direction",
        "evidence_placement",
        "quality",
    }
)
QUALITY_POLICY_KEYS = frozenset(
    {
        "requires_node_icons",
        "requires_auxiliary_details",
        "requires_node_nonoverlap",
        "requires_boundary_anchors",
        "requires_routes_clear_nodes",
        "max_top_whitespace_ratio",
        "max_bottom_whitespace_ratio",
        "min_horizontal_utilization_ratio",
        "uniform_width_regions",
        "uniform_gap_regions",
        "full_width_regions",
        "min_full_width_ratio",
        "min_relation_length",
        "min_distinct_relation_colors",
        "min_arrowhead_size",
        "max_arrowhead_size",
    }
)
EXPECTED_SEQUENCE_EXCLUSIONS = (
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
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
        "placeholder",
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
        "data-semantic-role",
        "data-reading-guide",
        "data-guide-relations",
        "data-relation-kind",
        "data-visible-relation-kind",
        "data-node-primary-label",
        "data-message-kind",
        "data-sequence-outcome",
        "data-branch-outcome",
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
        "data-sequence-message-id",
        "data-sequence-detail-for",
        "data-sequence-detail",
        "data-sequence-detail-trigger",
        "data-sequence-lifeline-for",
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
        if re.fullmatch(r"B(?:0[1-9]|1[0-5])", batch) is None:
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
    if not isinstance(families, dict) or len(families) != 7:
        raise ValueError("family policy must define exactly seven generic families")
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
                "requires_node_details",
                "requires_localized_node_labels",
            ):
                if key in template and type(template[key]) is not bool:
                    raise ValueError(
                        f"family policy {key} is invalid: {family}/{template_id}"
                    )
            for key in (
                "requires_branch",
                "requires_merge",
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
            quality = template.get("quality")
            if quality is not None:
                if not isinstance(quality, Mapping) or set(quality) - QUALITY_POLICY_KEYS:
                    raise ValueError(
                        f"family policy quality contract is invalid: {family}/{template_id}"
                    )
                for flag in (
                    "requires_node_icons",
                    "requires_auxiliary_details",
                    "requires_node_nonoverlap",
                    "requires_boundary_anchors",
                    "requires_routes_clear_nodes",
                ):
                    if flag in quality and type(quality[flag]) is not bool:
                        raise ValueError(
                            f"family policy quality flag {flag} is invalid: "
                            f"{family}/{template_id}"
                        )
                for ratio in (
                    "max_top_whitespace_ratio",
                    "max_bottom_whitespace_ratio",
                    "min_horizontal_utilization_ratio",
                    "min_full_width_ratio",
                ):
                    value = quality.get(ratio)
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not 0 <= value <= 1
                    ):
                        raise ValueError(
                            f"family policy quality ratio {ratio} is invalid: "
                            f"{family}/{template_id}"
                        )
                for length in (
                    "min_relation_length",
                    "min_arrowhead_size",
                    "max_arrowhead_size",
                ):
                    value = quality.get(length)
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or value <= 0
                    ):
                        raise ValueError(
                            f"family policy quality length {length} is invalid: "
                            f"{family}/{template_id}"
                        )
                color_count = quality.get("min_distinct_relation_colors")
                if color_count is not None and (
                    type(color_count) is not int or color_count < 1
                ):
                    raise ValueError(
                        "family policy distinct relation color count is invalid: "
                        f"{family}/{template_id}"
                    )
                known_regions = set(required_regions or [])
                for region_key in (
                    "uniform_width_regions",
                    "uniform_gap_regions",
                    "full_width_regions",
                ):
                    configured = quality.get(region_key)
                    if configured is not None and (
                        not isinstance(configured, list)
                        or not configured
                        or len(configured) != len(set(configured))
                        or any(
                            not isinstance(region, str)
                            or region not in known_regions
                            for region in configured
                        )
                    ):
                        raise ValueError(
                            f"family policy quality regions {region_key} are invalid: "
                            f"{family}/{template_id}"
                        )
                minimum_arrow = quality.get("min_arrowhead_size")
                maximum_arrow = quality.get("max_arrowhead_size")
                if (
                    minimum_arrow is not None
                    and maximum_arrow is not None
                    and minimum_arrow > maximum_arrow
                ):
                    raise ValueError(
                        f"family policy arrowhead range is invalid: {family}/{template_id}"
                    )
            covered.add(f"{family}/{template_id}.html")
    all_templates = {
        f"{family}/{template_id}.html"
        for family, entries in catalog.items()
        for template_id in entries
    }
    expected = all_templates - set(EXPECTED_SEQUENCE_EXCLUSIONS)
    if covered != expected:
        raise ValueError("family policy must cover the exact 54 non-sequence templates")
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


@dataclass(frozen=True)
class _DetailTriggerRecord:
    kind: str
    detail_for: str
    element_tag: str
    href: str
    owner_node_id: str


@dataclass(frozen=True)
class _VisiblePathQualityRecord:
    path_data: str
    stroke: str
    marker_end: str


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
    detail_triggers: List[_DetailTriggerRecord] = field(default_factory=list)
    runtime_detail_ids: List[str] = field(default_factory=list)
    node_icon_counts: Dict[str, int] = field(default_factory=dict)
    node_title_counts: Dict[str, int] = field(default_factory=dict)
    node_summary_counts: Dict[str, int] = field(default_factory=dict)
    node_icon_texts: Dict[str, List[str]] = field(default_factory=dict)
    node_title_texts: Dict[str, List[str]] = field(default_factory=dict)
    node_summary_texts: Dict[str, List[str]] = field(default_factory=dict)
    viewbox: Optional[Tuple[float, float, float, float]] = None
    boundary_bounds: Dict[str, Tuple[float, float, float, float]] = field(
        default_factory=dict
    )
    visible_path_quality: Dict[str, _VisiblePathQualityRecord] = field(
        default_factory=dict
    )
    marker_sizes: Dict[str, Tuple[float, float]] = field(default_factory=dict)

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
    inside_canvas: bool


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
        self._active_group_regions: List[str] = []
        self._active_node_text_targets: List[Tuple[str, str]] = []
        self._stack: List[
            Tuple[str, bool, bool, bool, bool, str, str, str, bool, bool]
        ] = []

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
        starts_group_region = ""
        starts_node_text_kind = ""
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
                self._evidence_slot = _EvidenceSlotRecord(
                    0,
                    [],
                    [],
                    not self._saw_canvas,
                    self._canvas is not None
                    or bool(values.get("data-reading-guide-for", "").strip()),
                )
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
            elif "data-architecture-landmark-for" in values:
                starts_node_id = values["data-architecture-landmark-for"].strip()
                if starts_node_id:
                    self._active_node_ids.append(starts_node_id)
            for marker, kind, counts in (
                ("data-node-icon", "icon", self._canvas.node_icon_counts),
                ("data-node-title", "title", self._canvas.node_title_counts),
                ("data-node-summary", "summary", self._canvas.node_summary_counts),
            ):
                if marker not in values:
                    continue
                if not self._active_node_ids:
                    self.errors.append(f"{marker} must be inside a diagram node.")
                    continue
                node_id = self._active_node_ids[-1]
                counts[node_id] = counts.get(node_id, 0) + 1
                starts_node_text_kind = kind
                self._active_node_text_targets.append((node_id, kind))
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
                starts_group_region = group.region
                self._active_group_regions.append(group.region)
                if not group.semantic_role:
                    self.errors.append("Every diagram group must declare data-semantic-role.")
            if "data-diagram-detail-trigger" in values:
                self._canvas.detail_triggers.append(
                    _DetailTriggerRecord(
                        values["data-diagram-detail-trigger"].strip(),
                        values.get("data-detail-for", "").strip(),
                        tag,
                        values.get("href", "").strip(),
                        self._active_node_ids[-1] if self._active_node_ids else "",
                    )
                )
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
            if "data-diagram-detail" in values:
                runtime_detail_id = values["data-diagram-detail"].strip()
                self._canvas.runtime_detail_ids.append(runtime_detail_id)
                if tag != "details":
                    self.errors.append("Diagram details must use native details elements.")
                if not runtime_detail_id or values.get("id", "").strip() != runtime_detail_id:
                    self.errors.append(
                        "Every runtime diagram detail id must match its native details id."
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
                    path_data = values.get("d", "").strip()
                    self._canvas.visible_paths[relation_id] = path_data
                    self._canvas.visible_path_quality[relation_id] = (
                        _VisiblePathQualityRecord(
                            path_data,
                            values.get("stroke", "").strip(),
                            values.get("marker-end", "").strip(),
                        )
                    )
            if tag == "svg" and "data-architecture-canvas" in values:
                viewbox = _parse_svg_viewbox(values.get("viewbox", ""))
                if viewbox is None:
                    self.errors.append(
                        "Architecture canvases require a numeric positive SVG viewBox."
                    )
                else:
                    self._canvas.viewbox = viewbox
            if tag == "marker":
                marker_id = values.get("id", "").strip()
                marker_width = _parse_svg_number(values.get("markerwidth", ""))
                marker_height = _parse_svg_number(values.get("markerheight", ""))
                if marker_id and marker_width is not None and marker_height is not None:
                    self._canvas.marker_sizes[marker_id] = (marker_width, marker_height)
            if (
                tag == "rect"
                and "data-architecture-boundary" in values
                and self._active_group_regions
            ):
                bounds = _parse_svg_rect_bounds(values)
                region = self._active_group_regions[-1]
                if bounds is None:
                    self.errors.append(
                        f"Architecture boundary {region or '<missing>'} requires numeric bounds."
                    )
                elif region in self._canvas.boundary_bounds:
                    self.errors.append(
                        f"Architecture region {region or '<missing>'} requires one boundary."
                    )
                else:
                    self._canvas.boundary_bounds[region] = bounds
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
                    starts_group_region,
                    starts_node_text_kind,
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
            closes_group_region,
            closes_node_text_kind,
            closes_interaction_group,
            closes_svg,
        ) = self._stack.pop()
        if closes_node_text_kind:
            if (
                self._active_node_text_targets
                and self._active_node_text_targets[-1][1] == closes_node_text_kind
            ):
                self._active_node_text_targets.pop()
            else:
                self.errors.append("Diagram node text marker nesting is inconsistent.")
        if closes_node_id:
            if not self._active_node_ids or self._active_node_ids[-1] != closes_node_id:
                self.errors.append("Diagram node geometry nesting is invalid.")
            else:
                self._active_node_ids.pop()
        if closes_group_region:
            if (
                self._active_group_regions
                and self._active_group_regions[-1] == closes_group_region
            ):
                self._active_group_regions.pop()
            else:
                self.errors.append("Diagram group geometry stack is inconsistent.")
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
        if self._canvas is not None and self._active_node_text_targets and data.strip():
            node_id, kind = self._active_node_text_targets[-1]
            targets = {
                "icon": self._canvas.node_icon_texts,
                "title": self._canvas.node_title_texts,
                "summary": self._canvas.node_summary_texts,
            }[kind]
            targets.setdefault(node_id, []).append(data.strip())
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


def _parse_svg_viewbox(value: str) -> Optional[Tuple[float, float, float, float]]:
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    numbers = [_parse_svg_number(part) for part in parts]
    if any(number is None for number in numbers):
        return None
    x, y, width, height = numbers
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


def _bounds_overlap(
    first: Tuple[float, float, float, float],
    second: Tuple[float, float, float, float],
    tolerance: float = 0.001,
) -> bool:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    return (
        min(first_x + first_width, second_x + second_width)
        - max(first_x, second_x)
        > tolerance
        and min(first_y + first_height, second_y + second_height)
        - max(first_y, second_y)
        > tolerance
    )


def _orthogonal_segment_crosses_bounds(
    start: Tuple[float, float],
    end: Tuple[float, float],
    bounds: Tuple[float, float, float, float],
    tolerance: float = 0.001,
) -> bool:
    left, top, width, height = bounds
    right, bottom = left + width, top + height
    if abs(start[0] - end[0]) <= tolerance:
        x = start[0]
        low, high = sorted((start[1], end[1]))
        return (
            left + tolerance < x < right - tolerance
            and max(low, top + tolerance) < min(high, bottom - tolerance)
        )
    if abs(start[1] - end[1]) <= tolerance:
        y = start[1]
        low, high = sorted((start[0], end[0]))
        return (
            top + tolerance < y < bottom - tolerance
            and max(low, left + tolerance) < min(high, right - tolerance)
        )
    return True


def _node_text(
    values: Mapping[str, List[str]],
    node_id: str,
) -> str:
    return " ".join(values.get(node_id, [])).strip()


def _validate_quality_contract(
    canvas: _GenericCanvasRecord,
    definition: Mapping[str, Any],
) -> List[str]:
    quality = definition.get("quality")
    if not quality:
        return []
    errors: List[str] = []
    tolerance = 0.001

    runtime_detail_ids = canvas.runtime_detail_ids
    if len(runtime_detail_ids) != len(set(runtime_detail_ids)):
        errors.append("Runtime diagram detail ids must be unique within a canvas.")
    trigger_targets = [trigger.detail_for for trigger in canvas.detail_triggers]
    if len(trigger_targets) != len(set(trigger_targets)):
        errors.append("Every diagram detail trigger requires one unique detail target.")
    for trigger in canvas.detail_triggers:
        if trigger.kind not in {"primary", "auxiliary"}:
            errors.append("Diagram detail trigger kind must be primary or auxiliary.")
        if (
            trigger.element_tag != "a"
            or not trigger.detail_for
            or trigger.href != f"#{trigger.detail_for}"
        ):
            errors.append(
                "Every diagram detail trigger must remain a native link to its detail block."
            )
        if trigger.detail_for not in set(runtime_detail_ids):
            errors.append("Every diagram detail trigger must target one native detail block.")

    if quality.get("requires_node_icons"):
        for node in canvas.nodes:
            node_id = node.object_id
            if canvas.node_icon_counts.get(node_id, 0) != 1:
                errors.append(f"Diagram node {node_id} requires exactly one icon marker.")
            if canvas.node_title_counts.get(node_id, 0) != 1:
                errors.append(f"Diagram node {node_id} requires exactly one title marker.")
            if canvas.node_summary_counts.get(node_id, 0) != 1:
                errors.append(f"Diagram node {node_id} requires exactly one summary marker.")
            icon = _node_text(canvas.node_icon_texts, node_id)
            title = _node_text(canvas.node_title_texts, node_id)
            summary = _node_text(canvas.node_summary_texts, node_id)
            if not icon or not title or not summary:
                errors.append(
                    f"Diagram node {node_id} requires non-empty icon, title, and summary content."
                )
            elif icon == title or icon == summary:
                errors.append(
                    f"Diagram node {node_id} icon must not replace its title or summary."
                )
            if icon and not _is_template_placeholder(icon) and EMOJI_RE.search(icon) is None:
                errors.append(
                    f"Diagram node {node_id} icon must resolve to an emoji or pictographic symbol."
                )

    if quality.get("requires_auxiliary_details"):
        auxiliary = [
            trigger
            for trigger in canvas.detail_triggers
            if trigger.kind == "auxiliary"
        ]
        if not auxiliary:
            errors.append("This template requires independently detailed auxiliary nodes.")
        auxiliary_targets = {trigger.detail_for for trigger in auxiliary}
        primary_targets = set(canvas.detail_ids)
        expected_auxiliary = set(runtime_detail_ids) - primary_targets
        if auxiliary_targets != expected_auxiliary:
            errors.append(
                "Auxiliary node links and native detail blocks must form a one-to-one mapping."
            )
        if len(auxiliary) > 64:
            errors.append(
                "Auxiliary node details exceed the bounded interaction budget of 64."
            )

    if quality.get("requires_node_nonoverlap"):
        bounded_nodes = [
            (node.object_id, canvas.node_bounds[node.object_id])
            for node in canvas.nodes
            if node.object_id in canvas.node_bounds
        ]
        for index, (first_id, first_bounds) in enumerate(bounded_nodes):
            for second_id, second_bounds in bounded_nodes[index + 1 :]:
                if _bounds_overlap(first_bounds, second_bounds):
                    errors.append(
                        f"Diagram nodes must not overlap: {first_id}, {second_id}."
                    )

    relation_bindings = {
        binding.relation_id: binding for binding in canvas.visible_relations
    }
    if quality.get("requires_boundary_anchors") or quality.get(
        "requires_routes_clear_nodes"
    ):
        for relation_id, path_data in canvas.visible_paths.items():
            points = _parse_absolute_orthogonal_path_points(path_data)
            binding = relation_bindings.get(relation_id)
            if points is None or binding is None:
                errors.append(
                    f"Quality-checked relation requires an authored orthogonal path: {relation_id}."
                )
                continue
            if quality.get("requires_boundary_anchors"):
                source_bounds = canvas.node_bounds.get(binding.source)
                target_bounds = canvas.node_bounds.get(binding.target)
                if source_bounds is None or target_bounds is None:
                    errors.append(
                        f"Quality-checked relation endpoints require node bounds: {relation_id}."
                    )
                else:
                    if not _point_on_bounds_edge(points[0], source_bounds):
                        errors.append(
                            f"Relation must start on its source node boundary: {relation_id}."
                        )
                    if not _point_on_bounds_edge(points[-1], target_bounds):
                        errors.append(
                            f"Relation must end on its target node boundary: {relation_id}."
                        )
            if quality.get("requires_routes_clear_nodes"):
                for node_id, bounds in canvas.node_bounds.items():
                    if node_id in {binding.source, binding.target}:
                        continue
                    if any(
                        _orthogonal_segment_crosses_bounds(start, end, bounds)
                        for start, end in zip(points, points[1:])
                    ):
                        errors.append(
                            f"Relation route must not cross diagram node {node_id}: {relation_id}."
                        )

    if canvas.viewbox is not None and canvas.boundary_bounds:
        view_x, view_y, view_width, view_height = canvas.viewbox
        left = min(bounds[0] for bounds in canvas.boundary_bounds.values())
        top = min(bounds[1] for bounds in canvas.boundary_bounds.values())
        right = max(
            bounds[0] + bounds[2] for bounds in canvas.boundary_bounds.values()
        )
        bottom = max(
            bounds[1] + bounds[3] for bounds in canvas.boundary_bounds.values()
        )
        measured_ratios = {
            "max_top_whitespace_ratio": max(0.0, top - view_y) / view_height,
            "max_bottom_whitespace_ratio": max(
                0.0, view_y + view_height - bottom
            )
            / view_height,
            "min_horizontal_utilization_ratio": max(0.0, right - left)
            / view_width,
        }
        canvas_attributes = {
            "max_top_whitespace_ratio": "data-max-top-whitespace-ratio",
            "max_bottom_whitespace_ratio": "data-max-bottom-whitespace-ratio",
            "min_horizontal_utilization_ratio": "data-min-horizontal-utilization-ratio",
        }
        for key, measured in measured_ratios.items():
            configured = quality.get(key)
            if configured is None:
                continue
            authored = _parse_svg_number(
                canvas.attrs.get(canvas_attributes[key], "")
            )
            if authored is None or abs(authored - float(configured)) > tolerance:
                errors.append(
                    f"Canvas runtime threshold {canvas_attributes[key]} must match policy."
                )
            if key.startswith("max_") and measured > float(configured) + tolerance:
                errors.append(f"Canvas exceeds the policy threshold {key}.")
            if key.startswith("min_") and measured + tolerance < float(configured):
                errors.append(f"Canvas does not meet the policy threshold {key}.")
    elif any(
        key in quality
        for key in (
            "max_top_whitespace_ratio",
            "max_bottom_whitespace_ratio",
            "min_horizontal_utilization_ratio",
            "full_width_regions",
        )
    ):
        errors.append(
            "Canvas utilization quality requires an SVG viewBox and authored region boundaries."
        )

    for region in quality.get("uniform_width_regions", []):
        widths = [
            canvas.node_bounds[node.object_id][2]
            for node in canvas.nodes
            if node.region == region and node.object_id in canvas.node_bounds
        ]
        if len(widths) < 2 or max(widths) - min(widths) > tolerance:
            errors.append(
                f"Diagram nodes in region {region} must use one uniform width."
            )

    for region in quality.get("uniform_gap_regions", []):
        bounds = sorted(
            (
                canvas.node_bounds[node.object_id]
                for node in canvas.nodes
                if node.region == region and node.object_id in canvas.node_bounds
            ),
            key=lambda item: item[1],
        )
        gaps = [
            current[1] - (previous[1] + previous[3])
            for previous, current in zip(bounds, bounds[1:])
        ]
        if (
            len(gaps) < 2
            or any(gap <= 0 for gap in gaps)
            or max(gaps) - min(gaps) > tolerance
        ):
            errors.append(
                f"Diagram nodes in region {region} must use one positive vertical gap."
            )

    full_width_ratio = float(quality.get("min_full_width_ratio", 1.0))
    if canvas.viewbox is not None:
        for region in quality.get("full_width_regions", []):
            bounds = canvas.boundary_bounds.get(region)
            if bounds is None or bounds[2] / canvas.viewbox[2] + tolerance < full_width_ratio:
                errors.append(
                    f"Diagram region {region} must meet the full-width ratio policy."
                )

    minimum_relation_length = quality.get("min_relation_length")
    if minimum_relation_length is not None:
        for relation_id, path_data in canvas.visible_paths.items():
            points = _parse_absolute_orthogonal_path_points(path_data)
            if points is None:
                continue
            path_length = sum(
                abs(end[0] - start[0]) + abs(end[1] - start[1])
                for start, end in zip(points, points[1:])
            )
            if path_length + tolerance < float(minimum_relation_length):
                errors.append(
                    f"Relation path is shorter than the readable minimum: {relation_id}."
                )

    minimum_colors = quality.get("min_distinct_relation_colors")
    if minimum_colors is not None:
        colors = {
            record.stroke.lower()
            for record in canvas.visible_path_quality.values()
            if record.stroke
        }
        if len(colors) < int(minimum_colors):
            errors.append(
                "Relation paths do not provide the required number of distinct colors."
            )

    minimum_arrow = quality.get("min_arrowhead_size")
    maximum_arrow = quality.get("max_arrowhead_size")
    if minimum_arrow is not None or maximum_arrow is not None:
        for relation_id, record in canvas.visible_path_quality.items():
            match = re.fullmatch(r"url\(#([^)]+)\)", record.marker_end)
            marker = canvas.marker_sizes.get(match.group(1)) if match else None
            if marker is None:
                errors.append(
                    f"Relation requires a resolvable SVG arrowhead marker: {relation_id}."
                )
                continue
            if minimum_arrow is not None and min(marker) + tolerance < float(
                minimum_arrow
            ):
                errors.append(
                    f"Relation arrowhead is smaller than the readable minimum: {relation_id}."
                )
            if maximum_arrow is not None and max(marker) - tolerance > float(
                maximum_arrow
            ):
                errors.append(
                    f"Relation arrowhead exceeds the readable maximum: {relation_id}."
                )

    return list(dict.fromkeys(errors))


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
        if evidence_placement == "inside-primary-canvas" and not slot.inside_canvas:
            errors.append("The evidence boundary ledger must appear inside its diagram canvas.")
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
        primary_triggers = [
            trigger
            for trigger in canvas.detail_triggers
            if trigger.kind == "primary"
        ]
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
        if (
            len(primary_triggers) != len(canvas.nodes)
            or {trigger.owner_node_id for trigger in primary_triggers}
            != set(canvas.node_ids)
        ):
            errors.append(
                "Every detailed diagram node requires exactly one owned primary detail trigger."
            )
        reverse_targets = dict(zip(detail_ids, detail_targets))
        for node in canvas.nodes:
            triggers = [
                trigger
                for trigger in primary_triggers
                if trigger.owner_node_id == node.object_id
            ]
            if (
                len(triggers) != 1
                or triggers[0].detail_for != node.detail_for
                or triggers[0].element_tag != "a"
                or triggers[0].href != f"#{node.detail_for}"
            ):
                errors.append(
                    "Every detailed diagram node must own one native link to its detail block."
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
        errors.extend(_validate_quality_contract(canvas, definition))
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
            definition.get("evidence_placement", "inside-primary-canvas"),
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


class _ArtifactShellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_count = 0
        self.guide_count = 0
        self.title_copy_count = 0
        self.controls_container_count = 0
        self.title_order = -1
        self.canvas_orders: List[int] = []
        self.canvas_ids: List[str] = []
        self.guide_records: List[Dict[str, Any]] = []
        self.control_sets: List[Tuple[str, List[str]]] = []
        self.controls_outside_title: List[str] = []
        self.controls_inside_guide = 0
        self.content_text: List[str] = []
        self.content_attributes: List[Tuple[str, str]] = []
        self.content_identifiers: List[Tuple[str, str]] = []
        self.content_slots: List[str] = []
        self._order = 0
        self._stack: List[
            Tuple[str, bool, bool, bool, bool, bool, int, str, int]
        ] = []

    def _flags(self) -> Tuple[bool, bool, bool, bool, bool, int, str, int]:
        if not self._stack:
            return False, False, False, False, False, -1, "", -1
        (
            _,
            title,
            guide,
            controls,
            main,
            content,
            control_set,
            canvas_id,
            guide_index,
        ) = self._stack[-1]
        return (
            title,
            guide,
            controls,
            main,
            content,
            control_set,
            canvas_id,
            guide_index,
        )

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self._order += 1
        values = {name.lower(): value or "" for name, value in attrs}
        (
            parent_title,
            parent_guide,
            parent_controls,
            parent_main,
            parent_content,
            parent_control_set,
            parent_canvas_id,
            parent_guide_index,
        ) = self._flags()
        starts_title = values.get("data-artifact-shell-title", "").strip() == "1"
        starts_guide = values.get("data-diagram-reading-guide", "").strip() == "1"
        starts_controls_container = "data-artifact-shell-controls" in values
        starts_canvas = (
            "data-diagram-canvas" in values or "data-sequence-canvas" in values
        )
        in_title = parent_title or starts_title
        in_guide = parent_guide or starts_guide
        in_controls = parent_controls or starts_controls_container
        in_main = parent_main or tag.lower() == "main"
        in_content = (parent_content and not starts_guide) or (
            parent_main and not (in_title or in_guide)
        )
        control_set = parent_control_set
        canvas_id = parent_canvas_id
        guide_index = parent_guide_index

        if starts_canvas:
            canvas_id = (
                values.get("data-diagram-id", "").strip()
                or values.get("data-sequence-id", "").strip()
            )
            self.canvas_orders.append(self._order)
            self.canvas_ids.append(canvas_id)

        if starts_title:
            self.title_count += 1
            self.title_order = self._order
            if tag.lower() != "header":
                self.content_attributes.append(("artifact-shell-title-tag", tag.lower()))
        if starts_guide:
            self.guide_count += 1
            self.guide_records.append(
                {
                    "for": values.get("data-reading-guide-for", "").strip(),
                    "canvas": canvas_id,
                    "order": self._order,
                    "groups": [],
                    "evidence": [],
                }
            )
            guide_index = len(self.guide_records) - 1
            if (
                tag.lower() != "section"
                or values.get("data-slot", "").strip() != "evidence-and-notes"
                or values.get("data-evidence-ledger", "").strip() != "1"
            ):
                self.content_attributes.append(("artifact-shell-guide-tag", tag.lower()))
        if "data-diagram-title-copy" in values and in_title:
            self.title_copy_count += 1
        if starts_controls_container:
            self.controls_container_count += 1
        if (
            "data-reading-guide-group" in values
            and in_guide
            and guide_index >= 0
        ):
            guide_group = values["data-reading-guide-group"].strip()
            self.guide_records[guide_index]["groups"].append(guide_group)
        if "data-evidence-id" in values and in_guide and guide_index >= 0:
            self.guide_records[guide_index]["evidence"].append(
                (
                    values["data-evidence-id"].strip(),
                    values.get("data-evidence-status", "").strip(),
                    values.get("data-evidence-source-kind", "").strip(),
                )
            )

        control_kind = ""
        if "data-diagram-controls" in values:
            control_kind = "diagram"
        elif "data-sequence-toolbar" in values:
            control_kind = "sequence"
        if control_kind:
            self.control_sets.append((control_kind, []))
            control_set = len(self.control_sets) - 1
            if not (in_title and in_controls):
                self.controls_outside_title.append(control_kind)
            if in_guide:
                self.controls_inside_guide += 1
        if "data-diagram-zoom-control" in values and control_set >= 0:
            self.control_sets[control_set][1].append(
                values["data-diagram-zoom-control"].strip()
            )
        if "data-sequence-scale" in values and control_set >= 0:
            self.control_sets[control_set][1].append(
                values["data-sequence-scale"].strip()
            )

        if in_content:
            slot = values.get("data-slot", "").strip()
            if slot:
                self.content_slots.append(slot)
            for name in (
                "aria-label",
                "aria-description",
                "title",
                "alt",
                "data-node-primary-label",
                "data-detail-close-label",
                "data-label",
                "data-description",
                "data-semantic",
                "data-semantic-role",
                "data-relation-kind",
                "data-reading-guide",
            ):
                value = values.get(name, "").strip()
                if value:
                    self.content_attributes.append((name, value))
            for name in (
                "data-diagram-node-id",
                "data-diagram-group-id",
                "data-diagram-detail",
                "data-diagram-detail-id",
                "data-diagram-visible-relation-id",
                "data-diagram-relation-id",
                "data-fallback-relation-id",
                "data-from",
                "data-to",
                "data-detail-for",
                "data-architecture-landmark-for",
                "data-architecture-supporting-content-for",
                "data-participant-id",
                "data-participant-group-id",
                "data-sequence-id",
                "data-sequence-controls",
                "data-sequence-phase-id",
                "data-sequence-fragment-id",
                "data-sequence-comparison-id",
                "data-sequence-risk-id",
                "data-sequence-evidence-id",
                "data-sequence-evidence-for",
                "data-matrix-row-id",
                "data-matrix-row",
                "data-matrix-col-id",
                "data-matrix-col",
                "data-architecture-rank-id",
                "data-architecture-branch-id",
                "data-architecture-merge-id",
                "data-architecture-peer-group",
                "data-architecture-boundary",
            ):
                value = values.get(name, "").strip()
                if value:
                    self.content_identifiers.append((name, value))
            if any(
                name in values
                for name in (
                    "data-diagram-node-id",
                    "data-diagram-detail",
                    "data-sequence-evidence-id",
                )
            ):
                value = values.get("id", "").strip()
                if value:
                    self.content_identifiers.append(("id", value))
            href = values.get("href", "").strip()
            if href.startswith("#"):
                self.content_identifiers.append(("href", href))

        if tag.lower() not in VOID_ELEMENTS:
            self._stack.append(
                (
                    tag.lower(),
                    in_title,
                    in_guide,
                    in_controls,
                    in_main,
                    in_content,
                    control_set,
                    canvas_id,
                    guide_index,
                )
            )

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._stack and self._stack[-1][5] and data.strip():
            self.content_text.append(data)


def artifact_shell_errors(html: str, *, require_content_neutral: bool = False) -> List[str]:
    parser = _ArtifactShellParser()
    parser.feed(html)
    parser.close()
    errors: List[str] = []
    if parser.title_count != 1 or parser.title_copy_count != 1:
        errors.append("Artifact shell requires exactly one title and summary region.")
    if parser.controls_container_count != 1:
        errors.append("Artifact shell requires exactly one title-side control region.")
    if (
        parser.title_order < 0
        or not parser.canvas_orders
        or not parser.title_order < min(parser.canvas_orders)
    ):
        errors.append("Artifact shell order must place the title before every canvas.")
    if any(not canvas_id for canvas_id in parser.canvas_ids):
        errors.append("Artifact shell canvases must expose stable identifiers.")
    evidence_ids: List[str] = []
    guide_targets: List[str] = []
    for record in parser.guide_records:
        if not record["for"] or record["for"] != record["canvas"]:
            errors.append(
                "Every local reading guide must directly identify its containing canvas."
            )
        guide_targets.append(record["for"])
        groups = record["groups"]
        if (
            not groups
            or len(groups) != len(set(groups))
            or any(SEMANTIC_SLUG_RE.fullmatch(group) is None for group in groups)
        ):
            errors.append(
                "Every local reading guide must declare unique semantic groups."
            )
        evidence = record["evidence"]
        evidence_ids.extend(entry[0] for entry in evidence)
        if any(
            not evidence_id
            or SEMANTIC_SLUG_RE.fullmatch(evidence_id) is None
            or status not in EVIDENCE_STATUSES
            or source_kind not in EVIDENCE_SOURCE_KINDS
            for evidence_id, status, source_kind in evidence
        ):
            errors.append(
                "Local reading-guide evidence entries must use valid semantic ids, statuses, and source kinds."
            )
    if len(guide_targets) != len(set(guide_targets)):
        errors.append("A canvas may own at most one local reading guide.")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("Local reading-guide evidence identifiers must be unique.")
    if not parser.control_sets:
        errors.append("Artifact title requires at least one zoom control set.")
    expected_modes = ["0.75", "0.9", "1", "fit"]
    for kind, modes in parser.control_sets:
        if modes != expected_modes:
            errors.append(
                f"Every {kind} zoom control set must expose 75%, 90%, 100%, and Auto in that order."
            )
    if parser.controls_outside_title or parser.controls_inside_guide:
        errors.append("All zoom controls must live in the title-side control region.")
    if any(
        name == "artifact-shell-title-tag" for name, _value in parser.content_attributes
    ):
        errors.append("Artifact shell title marker must be on a header.")
    if any(
        name == "artifact-shell-guide-tag" for name, _value in parser.content_attributes
    ):
        errors.append(
            "Artifact shell reading guide must be a version-1 evidence-and-notes section."
        )
    if require_content_neutral:
        if any(
            re.fullmatch(r"\s*\{\{canvas-text-\d{3}\}\}\s*", text) is None
            for text in parser.content_text
        ):
            errors.append(
                "Canonical template content surfaces may contain only neutral canvas-text placeholders."
            )
        if any(
            re.fullmatch(r"\{\{canvas-attribute-\d{3}\}\}", value) is None
            for name, value in parser.content_attributes
            if not name.startswith("artifact-shell-")
        ):
            errors.append(
                "Canonical template content attributes may contain only neutral canvas-attribute placeholders."
            )
        if any(re.fullmatch(r"layout-slot-\d{3}", slot) is None for slot in parser.content_slots):
            errors.append(
                "Canonical template content slots must use neutral layout-slot identifiers."
            )
        identifier_patterns = {
            "data-diagram-node-id": r"layout-node-\d{3}",
            "data-diagram-group-id": r"layout-group-\d{3}",
            "data-diagram-detail": r"layout-detail-\d{3}",
            "data-diagram-detail-id": r"layout-detail-\d{3}",
            "data-diagram-visible-relation-id": r"layout-relation-\d{3}",
            "data-diagram-relation-id": r"layout-relation-\d{3}",
            "data-fallback-relation-id": r"layout-relation-\d{3}",
            "data-from": r"layout-(?:node|participant|group)-\d{3}",
            "data-to": r"layout-(?:node|participant|group)-\d{3}",
            "data-detail-for": r"layout-(?:node|detail)-\d{3}",
            "data-architecture-landmark-for": r"layout-node-\d{3}",
            "data-architecture-supporting-content-for": r"layout-node-\d{3}",
            "data-participant-id": r"layout-participant-\d{3}",
            "data-participant-group-id": r"layout-participant-group-\d{3}",
            "data-sequence-id": r"layout-sequence-\d{3}",
            "data-sequence-controls": r"layout-sequence-\d{3}",
            "data-sequence-phase-id": r"layout-phase-\d{3}",
            "data-sequence-fragment-id": r"layout-fragment-\d{3}",
            "data-sequence-comparison-id": r"layout-comparison-\d{3}",
            "data-sequence-risk-id": r"layout-risk-\d{3}",
            "data-sequence-evidence-id": r"layout-evidence-\d{3}",
            "data-sequence-evidence-for": r"layout-evidence-\d{3}",
            "data-matrix-row-id": r"layout-row-\d{3}",
            "data-matrix-row": r"layout-row-\d{3}",
            "data-matrix-col-id": r"layout-col-\d{3}",
            "data-matrix-col": r"layout-col-\d{3}",
            "data-architecture-rank-id": r"layout-rank-\d{3}",
            "data-architecture-branch-id": r"layout-branch-\d{3}",
            "data-architecture-merge-id": r"layout-merge-\d{3}",
            "data-architecture-peer-group": r"layout-peer-group-\d{3}",
            "data-architecture-boundary": r"layout-boundary-\d{3}",
            "id": r"layout-(?:node|detail|evidence)-\d{3}",
            "href": r"#layout-(?:node|detail|evidence)-\d{3}",
        }
        if any(
            re.fullmatch(identifier_patterns[name], value) is None
            for name, value in parser.content_identifiers
        ):
            errors.append(
                "Canonical template identifiers and references must use neutral layout identifiers."
            )
    return list(dict.fromkeys(errors))


def lint_artifact_shell_kernel(html: str) -> List[str]:
    errors = []
    root = SKILL_ROOT / "assets" / "contracts" / "artifact-shell"
    runtime = (root / "v1.js").read_text(encoding="utf-8")
    required_runtime_tokens = (
        "VibeDiagramQuality",
        "data-computed-layout-audit",
        "auditLifecycle",
        "route-crosses-node",
        "route-target-not-anchored",
        "ResizeObserver",
    )
    if any(token not in runtime for token in required_runtime_tokens):
        errors.append("Artifact shell computed-layout audit runtime is incomplete.")
    if any(token in runtime for token in ("toDataURL(", "html2canvas", "pixelmatch")):
        errors.append(
            "Artifact shell quality audit must use computed geometry, not screenshot comparison."
        )
    kernels = (
        ("style", "data-artifact-shell-kernel", root / "v1.css"),
        ("script", "data-artifact-shell-preview-kernel", root / "v1.js"),
    )
    for tag, marker, path in kernels:
        expected = path.read_text(encoding="utf-8").rstrip("\n")
        matches = re.findall(
            rf'<{tag} {marker}="1">\n(.*?)\n</{tag}>',
            html,
            flags=re.DOTALL,
        )
        if len(matches) != 1:
            errors.append(
                f"Every template requires exactly one artifact shell {tag} kernel."
            )
        elif matches[0] != expected:
            errors.append(f"Artifact shell {tag} kernel has drifted.")
    return errors


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


def lint_semantic_relations_kernel(html: str) -> List[str]:
    expected = (
        SKILL_ROOT / "assets" / "contracts" / "semantic-relations" / "v1.css"
    ).read_text(encoding="utf-8").rstrip("\n")
    matches = re.findall(
        r'<style data-semantic-relations-kernel="1">\n(.*?)\n</style>',
        html,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        return [
            "Every migrated generic template requires exactly one semantic-relations style kernel."
        ]
    if matches[0] != expected:
        return ["Migrated generic template semantic-relations style kernel has drifted."]
    return []


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


def load_template_routing(
    path: Path = TEMPLATE_ROUTING_PATH,
) -> Dict[str, Any]:
    """Load the fail-closed routing allowlist used by scaffold and delivery lint."""

    routing = _read_json_unique(path)
    if set(routing) != {"schema_version", "code_review_routes", "families"}:
        raise ValueError("template routing contract has an invalid root schema")
    if type(routing["schema_version"]) is not int or routing["schema_version"] != 2:
        raise ValueError("template routing schema_version must be integer 2")
    catalog = load_template_layouts()
    families = routing["families"]
    if not isinstance(families, dict) or set(families) != set(catalog):
        raise ValueError("template routing must cover the exact diagram family catalog")
    for family, definition in families.items():
        if not isinstance(definition, dict) or set(definition) != ROUTING_FAMILY_KEYS:
            raise ValueError(f"template routing family definition is invalid: {family}")
        default_template = definition["default_template"]
        ready = definition["ready_templates"]
        blocked = definition["blocked_templates"]
        if (
            not isinstance(default_template, str)
            or not isinstance(ready, list)
            or not isinstance(blocked, list)
            or ready != sorted(ready)
            or blocked != sorted(blocked)
            or len(ready) != len(set(ready))
            or len(blocked) != len(set(blocked))
            or set(ready) & set(blocked)
            or set(ready) | set(blocked) != set(catalog[family])
            or default_template not in set(ready)
        ):
            raise ValueError(f"template routing inventory is invalid: {family}")
    routes = routing["code_review_routes"]
    expected_routes = {
        "cause-evidence",
        "control-branch",
        "exception-compensation",
        "path-contract-drift",
        "state-lifecycle",
        "time-concurrency",
    }
    if not isinstance(routes, dict) or set(routes) != expected_routes:
        raise ValueError("code-review routes must cover the exact supported relation kinds")
    for kind, route in routes.items():
        if not isinstance(route, dict) or set(route) != CODE_REVIEW_ROUTE_KEYS:
            raise ValueError(f"code-review route definition is invalid: {kind}")
        family = route["family"]
        template = route["template"]
        if (
            not isinstance(family, str)
            or not isinstance(template, str)
            or not isinstance(route["primary_relation"], str)
            or not route["primary_relation"].strip()
            or family == "code-review"
            or family not in families
            or template not in families[family]["ready_templates"]
        ):
            raise ValueError(f"code-review route target is not ready: {kind}")
    return routing


def template_routing_errors(
    html: str,
    diagram_type: str,
    routing: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Reject delivery through a template that has not passed the true-diagram gate."""

    trusted = load_template_routing() if routing is None else routing
    parser = _parse(html)
    if len(parser.main_attrs) != 1:
        return []
    template_id = parser.main_attrs[0].get("data-template-id", "").strip()
    family = trusted["families"].get(diagram_type)
    if family is None or template_id in set(family["ready_templates"]):
        return []
    default_template = family["default_template"]
    return [
        f'Template "{diagram_type}/{template_id}" is blocked from delivery until its '
        f'true-diagram migration is complete; use the ready default "{default_template}".'
    ]


def true_diagram_errors(
    html: str,
    diagram_type: str,
    routing: Optional[Mapping[str, Any]] = None,
    policy: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Require ready non-sequence templates to draw relations on the primary canvas."""

    trusted_routing = load_template_routing() if routing is None else routing
    identity = _parse(html)
    if len(identity.main_attrs) != 1:
        return []
    template_id = identity.main_attrs[0].get("data-template-id", "").strip()
    family_routing = trusted_routing["families"].get(diagram_type)
    if (
        family_routing is None
        or template_id not in set(family_routing["ready_templates"])
        or diagram_type == "code-sequence"
    ):
        return []
    trusted_policy = load_family_policies() if policy is None else policy
    definition = trusted_policy["families"][diagram_type]["templates"][template_id]
    parser = _GenericContractParser()
    parser.feed(html)
    parser.close()
    errors: List[str] = []
    for canvas in parser.canvases:
        declared = {relation.relation_id for relation in canvas.relations}
        geometric = set(canvas.visible_paths)
        missing = sorted(declared - geometric)
        if missing:
            errors.append(
                "Ready templates must bind every authored relation to one primary SVG path: "
                + ", ".join(missing)
                + "."
            )
        non_path = sorted(
            binding.relation_id
            for binding in canvas.visible_relations
            if binding.relation_id not in geometric
        )
        if non_path:
            errors.append(
                "HTML relationship ledgers cannot satisfy the primary visible-relation contract: "
                + ", ".join(non_path)
                + "."
            )
        if definition["profile"] in {"graph", "timeline"}:
            missing_bounds = sorted(set(canvas.node_ids) - set(canvas.node_bounds))
            if missing_bounds:
                errors.append(
                    "Ready graph and timeline templates require measurable SVG geometry for every node: "
                    + ", ".join(missing_bounds)
                    + "."
                )
            missing_markers = sorted(
                relation_id
                for relation_id, record in canvas.visible_path_quality.items()
                if not record.marker_end
            )
            if missing_markers:
                errors.append(
                    "Ready graph and timeline routes require visible arrowhead markers: "
                    + ", ".join(missing_markers)
                    + "."
                )
    return list(dict.fromkeys(errors))


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
        # A table is a structured UI/data surface whose aggregate descendant copy is
        # not a single prose slot. Individual cell fit remains a computed-layout gate.
        if any(tag == "table" for tag, _primary, _details, _slot in self._stack):
            return
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
    is_code_review = (
        diagram_type == "code-review" and template_id == "code-review-package"
    )
    errors.extend(
        artifact_shell_errors(
            canonical,
            require_content_neutral=not is_code_review,
        )
    )
    if _block_inventory(STYLE_BLOCK_RE, html) != _block_inventory(STYLE_BLOCK_RE, canonical):
        errors.append("Style blocks must match the declared canonical template exactly.")
    if _block_inventory(SCRIPT_BLOCK_RE, html) != _block_inventory(SCRIPT_BLOCK_RE, canonical):
        errors.append("Script blocks must match the declared canonical template exactly.")
    if is_code_review:
        return errors
    artifact_slots = Counter(parsed.attr_values("data-slot"))
    canonical_slots = Counter(_parse(canonical).attr_values("data-slot"))
    if artifact_slots != canonical_slots:
        errors.append("The canonical template slot inventory has drifted.")
    is_sequence = bool(_parse(canonical).attr_values("data-sequence-canvas"))
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
    identity = _parse(html)
    if identity.attr_values("data-sequence-canvas"):
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


def lint_sequence_visual_contract(html: str) -> List[str]:
    """Validate the visual carriers and native details of a ready sequence template."""

    signals = _parse(html)
    errors: List[str] = []
    participant_ids = [
        attrs.get("data-participant-id", "").strip()
        for _tag, attrs in signals.elements
        if "data-participant-id" in attrs
    ]
    message_ids = [
        attrs.get("data-sequence-message-id", "").strip()
        for _tag, attrs in signals.elements
        if "data-sequence-message" in attrs
    ]
    object_ids = participant_ids + message_ids
    if any(not object_id for object_id in object_ids):
        errors.append("Ready sequence participants and messages require stable object ids.")
    if len(object_ids) != len(set(object_ids)):
        errors.append("Ready sequence participant and message object ids must be unique.")

    lifeline_ids = [
        attrs.get("data-sequence-lifeline-for", "").strip()
        for _tag, attrs in signals.elements
        if "data-sequence-lifeline-for" in attrs
    ]
    if sorted(lifeline_ids) != sorted(participant_ids):
        errors.append(
            "Ready sequences require exactly one explicit lifeline for every participant."
        )
    if not re.search(
        r"\[data-sequence-lifeline-for\]\s*\{[^}]*"
        r"border-(?:inline-start|left)\s*:\s*(?:2|[3-9]|\d{2,})px\s+dashed\b",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        errors.append(
            "Ready sequence lifelines must be at least 2px dashed visual carriers."
        )
    if not re.search(
        r"\[data-sequence-canvas\]\s+\[data-participant-id\]\s*\{[^}]*"
        r"background\s*:\s*color-mix\(",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        errors.append(
            "Ready sequence participants require non-white semantic accent backgrounds."
        )
    if not re.search(
        r"\[data-sequence-canvas\]\s+\.seq-caption\s*\{[^}]*"
        r"background\s*:\s*var\(--caption-fill\)",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        errors.append(
            "Ready sequence message captions require semantic message-kind backgrounds."
        )

    message_fragments = tuple(SEQUENCE_MESSAGE_FRAGMENT_RE.finditer(html))
    if len(message_fragments) != len(message_ids):
        errors.append("Ready sequence message elements must be parseable as native articles.")
    for index, match in enumerate(message_fragments, start=1):
        arrow_count = sum(
            "seq-arrow" in class_value.split()
            for _quote, class_value in re.findall(
                r"<span\b[^>]*\bclass\s*=\s*([\"'])(.*?)\1",
                match.group(0),
                re.IGNORECASE | re.DOTALL,
            )
        )
        if arrow_count != 1:
            errors.append(
                f"Ready sequence message {index} must contain exactly one .seq-arrow carrier."
            )
    if re.search(
        r"\[data-sequence-message\][^{,]*::(?:before|after)\s*\{",
        html,
        re.IGNORECASE,
    ):
        errors.append(
            "Ready sequence messages must not use legacy pseudo-element arrow renderers."
        )

    trigger_targets: List[str] = []
    for tag, attrs in signals.elements:
        if "data-sequence-detail-trigger" not in attrs:
            continue
        target = attrs.get("data-detail-for", "").strip()
        trigger_targets.append(target)
        if tag != "a" or not target or attrs.get("href", "").strip() != f"#{target}":
            errors.append(
                "Ready sequence detail triggers must be native links to their details target."
            )
    detail_targets: List[str] = []
    detail_object_ids: List[str] = []
    for tag, attrs in signals.elements:
        if "data-sequence-detail" not in attrs:
            continue
        detail_id = attrs.get("data-sequence-detail", "").strip()
        detail_targets.append(detail_id)
        detail_object_ids.append(attrs.get("data-sequence-detail-for", "").strip())
        if (
            tag != "details"
            or not detail_id
            or attrs.get("id", "").strip() != detail_id
            or attrs.get("data-diagram-detail", "").strip() != detail_id
        ):
            errors.append(
                "Ready sequence details must use native details with aligned stable ids."
            )
    if sorted(trigger_targets) != sorted(detail_targets):
        errors.append("Every ready sequence detail must have exactly one native trigger.")
    if sorted(detail_object_ids) != sorted(object_ids):
        errors.append(
            "Every ready sequence participant and message must map to exactly one detail."
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


class _MarkupIntegrityParser(HTMLParser):
    """Reject attribute debris that browsers silently accept as empty components."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: List[str] = []
        self._svg_depth = 0
        self._foreign_object_depth = 0

    def _check_attrs(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        numeric = sorted({name for name, _value in attrs if re.fullmatch(r"\d+", name)})
        if numeric:
            self.errors.append(
                f"Malformed numeric attribute on <{tag}>: {', '.join(numeric)}."
            )

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self._check_attrs(tag, attrs)
        normalized_tag = tag.lower()
        values = {name.lower(): value or "" for name, value in attrs}
        classes = set(values.get("class", "").split())
        if normalized_tag == "svg":
            self._svg_depth += 1
        elif normalized_tag == "foreignobject" and self._svg_depth:
            self._foreign_object_depth += 1
        elif (
            normalized_tag == "span"
            and "semantic-relation" in classes
            and self._svg_depth
            and not self._foreign_object_depth
        ):
            self.errors.append(
                "Semantic relation carriers must remain outside SVG so browsers "
                "do not terminate the SVG namespace before visible routes."
            )

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "foreignobject" and self._foreign_object_depth:
            self._foreign_object_depth -= 1
        elif normalized_tag == "svg" and self._svg_depth:
            self._svg_depth -= 1


def lint_markup_integrity(html: str) -> List[str]:
    parser = _MarkupIntegrityParser()
    parser.feed(html)
    parser.close()
    errors = list(parser.errors)
    if re.search(r"\{\{canvas-(?:text|attribute)-\d{3}\}\}\d+", html):
        errors.append(
            "A neutral canvas placeholder has an orphan numeric suffix."
        )
    return errors


class _RouteContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.routes: List[Dict[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "path" and "data-diagram-visible-relation-id" in values:
            self.routes.append(values)


def _orthogonal_turn_count(path_data: str) -> Optional[int]:
    commands = [
        token.upper()
        for token in re.findall(r"[A-Za-z]", path_data)
        if token.upper() in {"H", "V", "L"}
    ]
    if "C" in path_data.upper() or "Q" in path_data.upper() or "A" in path_data.upper():
        return None
    if not commands:
        return 0
    normalized: List[str] = []
    for command in commands:
        if command == "L":
            return None
        if not normalized or normalized[-1] != command:
            normalized.append(command)
    return max(0, len(normalized) - 1)


def lint_route_contract(html: str) -> List[str]:
    """Enforce bend budgets on routes that opt into the 0.1.10 route contract."""

    parser = _RouteContractParser()
    parser.feed(html)
    parser.close()
    errors: List[str] = []
    for route in parser.routes:
        intent = route.get("data-route-intent", "").strip()
        if not intent:
            continue
        relation_id = route.get("data-diagram-visible-relation-id", "unknown")
        turns = _orthogonal_turn_count(route.get("d", ""))
        if intent == "direct" and turns != 0:
            errors.append(f"Direct route {relation_id} must have zero bends.")
        elif intent in {"branch", "merge"} and turns is not None and turns > 1:
            errors.append(
                f"{intent.title()} route {relation_id} may have at most one bend."
            )
        elif intent == "feedback" and not route.get("data-route-reason", "").strip():
            errors.append(
                f"Feedback route {relation_id} must declare data-route-reason."
            )
    return errors


DIAGRAM_VIEW_TITLE_RE = re.compile(
    r"<h(?P<level>[1-6])\b(?P<attrs>[^>]*)"
    r"\bdata-diagram-view-title\s*=\s*([\"'])1\3[^>]*>"
    r"(?P<body>.*?)</h(?P=level)>",
    re.IGNORECASE | re.DOTALL,
)


def lint_diagram_view_title_contract(html: str) -> List[str]:
    """Validate graph-level titles as “diagram type｜title” composites."""

    heading_openings = re.findall(
        r"<h[1-6]\b[^<>]*>",
        html,
        re.IGNORECASE,
    )
    declared = sum(
        bool(re.search(r"\bdata-diagram-view-title\s*=\s*([\"'])1\1", opening, re.IGNORECASE))
        for opening in heading_openings
    )
    blocks = tuple(DIAGRAM_VIEW_TITLE_RE.finditer(html))
    errors: List[str] = []
    if 'data-code-review-package="1"' in html:
        expected = 2
        expected_level = "2"
    else:
        expected = 1
        expected_level = "1"
    if declared != expected:
        errors.append(
            f"Diagram title contract requires exactly {expected} structured graph-level title(s)."
        )
    if declared != len(blocks):
        errors.append("Diagram view title declarations must be on complete heading elements.")
        return errors
    part_patterns = {
        "type": re.compile(
            r"<span\b(?=[^>]*\bdata-diagram-view-type(?:\s|=|>))[^>]*>.*?</span>",
            re.IGNORECASE | re.DOTALL,
        ),
        "separator": re.compile(
            r"<span\b(?=[^>]*\bdata-diagram-view-separator(?:\s|=|>))"
            r"(?=[^>]*\baria-hidden\s*=\s*([\"'])true\1)[^>]*>.*?</span>",
            re.IGNORECASE | re.DOTALL,
        ),
        "subject": re.compile(
            r"<span\b(?=[^>]*\bdata-diagram-view-subject(?:\s|=|>))[^>]*>.*?</span>",
            re.IGNORECASE | re.DOTALL,
        ),
    }
    for index, block in enumerate(blocks, start=1):
        if expected_level is not None and block.group("level") != expected_level:
            errors.append(
                f"Diagram view title {index} must use an h{expected_level} heading."
            )
        body = block.group("body")
        type_parts = tuple(part_patterns["type"].finditer(body))
        separators = tuple(part_patterns["separator"].finditer(body))
        subject_parts = tuple(part_patterns["subject"].finditer(body))
        if (
            len(type_parts) != 1
            or len(separators) != 1
            or len(subject_parts) != 1
        ):
            errors.append(
                f"Diagram view title {index} requires one type, separator, and subject."
            )
            continue
        if not (
            type_parts[0].start()
            < separators[0].start()
            < subject_parts[0].start()
        ):
            errors.append(
                f'Diagram view title {index} must use the “diagram type｜title” order.'
            )
    return errors


def lint_guide_relation_binding_contract(html: str) -> List[str]:
    """Require standalone graph legends to bind every real relation exactly once."""

    if (
        re.search(r"<[^>]+\bdata-sequence-canvas(?:\s|=|>)", html, re.IGNORECASE)
        or 'data-code-review-package="1"' in html
    ):
        return []
    element_openings = re.findall(r"<[A-Za-z][A-Za-z0-9:-]*\b[^<>]*>", html)
    visible = [
        match.groups()
        for opening in element_openings
        if (match := re.search(
            r'\bdata-diagram-visible-relation-id\s*=\s*(["\'])([^"\']+)\1',
            opening,
            re.IGNORECASE,
        ))
    ]
    visible_ids = [value for _quote, value in visible]
    if not visible_ids:
        return []
    openings = re.findall(
        r'<span\b(?=[^>]*\bdata-reading-guide-item(?:\s|=|>))'
        r'(?=[^>]*\bdata-line-kind\s*=)[^>]*>',
        html,
        re.IGNORECASE,
    )
    errors: List[str] = []
    mappings: List[str] = []
    for index, opening in enumerate(openings, start=1):
        match = re.search(
            r'\bdata-guide-relations\s*=\s*(["\'])(.*?)\1',
            opening,
            re.IGNORECASE | re.DOTALL,
        )
        if not match or not match.group(2).strip():
            errors.append(f"Reading-guide relation item {index} requires an explicit binding.")
            continue
        mappings.append(match.group(2).strip())
    if errors or any("{{" in mapping for mapping in mappings):
        return errors
    bound = [relation_id for mapping in mappings for relation_id in mapping.split()]
    unknown = sorted(set(bound) - set(visible_ids))
    missing = sorted(set(visible_ids) - set(bound))
    duplicates = sorted(
        relation_id for relation_id in set(bound) if bound.count(relation_id) > 1
    )
    if unknown:
        errors.append("Reading-guide bindings reference unknown relations: " + ", ".join(unknown) + ".")
    if missing:
        errors.append("Reading-guide bindings do not cover relations: " + ", ".join(missing) + ".")
    if duplicates:
        errors.append("Reading-guide bindings repeat relations: " + ", ".join(duplicates) + ".")
    return errors


class _CodeReviewPackageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.package_count = 0
        self.finding_tabs: List[str] = []
        self.view_tabs: List[str] = []
        self.definitions: List[Dict[str, Any]] = []
        self.fallbacks: List[Dict[str, Any]] = []
        self.active_canvases: List[Dict[str, Any]] = []
        self.iframes = 0
        self.errors: List[str] = []
        self._definition: Optional[Dict[str, Any]] = None
        self._view: Optional[Dict[str, Any]] = None
        self._fallback: Optional[Dict[str, Any]] = None
        self._fallback_view: Optional[Dict[str, Any]] = None
        self._active_canvas: Optional[Dict[str, Any]] = None
        self._stack: List[
            Tuple[
                Optional[Dict[str, Any]],
                Optional[Dict[str, Any]],
                Optional[Dict[str, Any]],
                Optional[Dict[str, Any]],
                Optional[Dict[str, Any]],
            ]
        ] = []

    @staticmethod
    def _view_record(values: Mapping[str, str], view_id: str) -> Dict[str, Any]:
        return {
            "id": view_id,
            "reuse_family": values.get("data-reuse-family", "").strip(),
            "reuse_template": values.get("data-reuse-template", "").strip(),
            "topologies": set(),
            "nodes": [],
            "relations": [],
            "participants": [],
            "view_boxes": [],
        }

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        previous = (
            self._definition,
            self._view,
            self._fallback,
            self._fallback_view,
            self._active_canvas,
        )
        if tag.lower() not in VOID_ELEMENTS:
            self._stack.append(previous)
        if values.get("data-code-review-package") == "1":
            self.package_count += 1
        if tag.lower() == "iframe":
            self.iframes += 1
        finding_tab = values.get("data-review-finding-tab", "").strip()
        if finding_tab:
            self.finding_tabs.append(finding_tab)
        if "data-review-view-tab" in values:
            self.view_tabs.append(values.get("data-review-view", "").strip())
        canvas_id = values.get("data-diagram-id", "").strip()
        if canvas_id in {"code-review-current", "code-review-repair"}:
            self._active_canvas = {
                "id": canvas_id,
                "controls_mode": values.get(
                    "data-diagram-controls-mode", ""
                ).strip(),
                "topologies": [],
                "nodes": [],
                "relations": [],
                "participants": [],
                "view_boxes": [],
            }
            self.active_canvases.append(self._active_canvas)
        definition_id = values.get("data-review-definition", "").strip()
        if definition_id:
            if self._definition is not None:
                self.errors.append("Code-review definitions must not be nested.")
            self._definition = {
                "id": definition_id,
                "kind": values.get("data-review-kind", "").strip(),
                "route_family": values.get("data-review-route-family", "").strip(),
                "route_template": values.get("data-review-route-template", "").strip(),
                "views": [],
                "scenario_count": 0,
            }
            self.definitions.append(self._definition)
        if self._definition is not None:
            if values.get("data-review-scenario-definition") == "1":
                self._definition["scenario_count"] += 1
            view_id = values.get("data-review-view", "").strip()
            if view_id:
                if self._view is not None:
                    self.errors.append("Code-review views must not be nested.")
                self._view = self._view_record(values, view_id)
                self._definition["views"].append(self._view)
            if self._view is not None:
                topology = values.get("data-review-topology", "").strip()
                if topology:
                    self._view["topologies"].add(topology)
                if "data-diagram-node-id" in values:
                    self._view["nodes"].append(
                        (
                            values["data-diagram-node-id"].strip(),
                            values.get("data-node-theme", "").strip(),
                        )
                    )
                participant_id = values.get("data-participant-id", "").strip()
                if participant_id:
                    self._view["participants"].append(
                        (
                            participant_id,
                            values.get("data-participant-role", "").strip(),
                            values.get("data-participant-x", "").strip(),
                            values.get("data-participant-y", "").strip(),
                            values.get("data-participant-width", "").strip(),
                            values.get("data-participant-height", "").strip(),
                        )
                    )
                relation_id = values.get(
                    "data-diagram-visible-relation-id", ""
                ).strip()
                if relation_id:
                    self._view["relations"].append(
                        (
                            relation_id,
                            values.get("data-from", "").strip(),
                            values.get("data-to", "").strip(),
                            values.get("data-relation-kind", "").strip(),
                            values.get("d", "").strip(),
                        )
                    )
                if tag.lower() == "svg":
                    self._view["view_boxes"].append(values.get("viewbox", "").strip())
        fallback_id = values.get("data-review-fallback-finding", "").strip()
        if fallback_id:
            self._fallback = {"id": fallback_id, "views": [], "scenario_count": 0}
            self.fallbacks.append(self._fallback)
        if self._fallback is not None:
            if values.get("data-review-fallback-scenario") == "1":
                self._fallback["scenario_count"] += 1
            fallback_view_id = values.get(
                "data-review-fallback-view", ""
            ).strip()
            if fallback_view_id:
                self._fallback_view = self._view_record(values, fallback_view_id)
                self._fallback["views"].append(self._fallback_view)
            if self._fallback_view is not None:
                topology = values.get("data-review-topology", "").strip()
                if topology:
                    self._fallback_view["topologies"].add(topology)
                if "data-diagram-node-id" in values:
                    self._fallback_view["nodes"].append(
                        values["data-diagram-node-id"].strip()
                    )
                participant_id = values.get("data-participant-id", "").strip()
                if participant_id:
                    self._fallback_view["participants"].append(participant_id)
                if "data-diagram-visible-relation-id" in values:
                    self._fallback_view["relations"].append(
                        values["data-diagram-visible-relation-id"].strip()
                    )
        if self._active_canvas is not None:
            topology = values.get("data-review-topology", "").strip()
            if topology:
                self._active_canvas["topologies"].append(topology)
            if "data-diagram-node-id" in values:
                self._active_canvas["nodes"].append(
                    (
                        values["data-diagram-node-id"].strip(),
                        values.get("data-node-theme", "").strip(),
                    )
                )
            if "data-diagram-visible-relation-id" in values:
                self._active_canvas["relations"].append(
                    (
                        values.get("data-relation-kind", "").strip(),
                        values.get("d", "").strip(),
                    )
                )
            participant_id = values.get("data-participant-id", "").strip()
            if participant_id:
                self._active_canvas["participants"].append(
                    (
                        values.get("data-participant-role", "").strip(),
                        values.get("data-participant-x", "").strip(),
                        values.get("data-participant-y", "").strip(),
                        values.get("data-participant-width", "").strip(),
                        values.get("data-participant-height", "").strip(),
                    )
                )
            if tag.lower() == "svg":
                self._active_canvas["view_boxes"].append(
                    values.get("viewbox", "").strip()
                )

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in VOID_ELEMENTS or not self._stack:
            return
        (
            self._definition,
            self._view,
            self._fallback,
            self._fallback_view,
            self._active_canvas,
        ) = self._stack.pop()


def _review_route_points(path_data: str) -> List[Tuple[float, float]]:
    tokens = re.findall(r"[MHV]|-?\d+(?:\.\d+)?", path_data)
    points: List[Tuple[float, float]] = []
    cursor_x = 0.0
    cursor_y = 0.0
    index = 0
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command == "M" and index + 1 < len(tokens):
            cursor_x = float(tokens[index])
            cursor_y = float(tokens[index + 1])
            index += 2
        elif command == "H" and index < len(tokens):
            cursor_x = float(tokens[index])
            index += 1
        elif command == "V" and index < len(tokens):
            cursor_y = float(tokens[index])
            index += 1
        else:
            return []
        points.append((cursor_x, cursor_y))
    return points


def lint_code_review_package(
    html: str,
    routing: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    trusted = load_template_routing() if routing is None else routing
    parser = _CodeReviewPackageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        return [f"Could not parse code-review package: {exc}."]
    errors = list(parser.errors)
    if parser.package_count != 1:
        errors.append("Code-review package requires exactly one package root.")
    if parser.iframes:
        errors.append("Code-review package must remain a single file without iframes.")
    if not 1 <= len(parser.definitions) <= 12:
        errors.append("Code-review package requires 1 to 12 finding definitions.")
    definition_ids = [definition["id"] for definition in parser.definitions]
    if len(definition_ids) != len(set(definition_ids)):
        errors.append("Code-review finding identifiers must be unique.")
    if parser.finding_tabs != definition_ids:
        errors.append(
            "Code-review finding navigation must match definition order exactly."
        )
    if parser.view_tabs:
        errors.append(
            "Code-review current and repair views must remain visible instead of using view tabs."
        )
    if (
        [canvas["id"] for canvas in parser.active_canvases]
        != ["code-review-current", "code-review-repair"]
        or [canvas["controls_mode"] for canvas in parser.active_canvases]
        != ["persistent", "persistent"]
    ):
        errors.append(
            "Code-review package requires persistent current and repair canvases in order."
        )
    routes = trusted["code_review_routes"]
    for definition in parser.definitions:
        kind = definition["kind"]
        route = routes.get(kind)
        if route is None:
            errors.append(
                f'Code-review finding "{definition["id"]}" has an unresolved relation kind.'
            )
            continue
        expected_route = (route["family"], route["template"])
        declared_route = (
            definition["route_family"],
            definition["route_template"],
        )
        if declared_route != expected_route:
            errors.append(
                f'Code-review finding "{definition["id"]}" does not match its routed template.'
            )
        views = definition["views"]
        if [view["id"] for view in views] != ["current", "repair"]:
            errors.append(
                f'Code-review finding "{definition["id"]}" requires current and repair views.'
            )
            continue
        if definition["scenario_count"] != 1:
            errors.append(
                f'Code-review finding "{definition["id"]}" requires one factual scenario.'
            )
        signatures = []
        for view in views:
            if (view["reuse_family"], view["reuse_template"]) != expected_route:
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "does not reuse the routed family and template."
                )
            if view["topologies"] != {kind}:
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "does not declare exactly one routed topology."
                )
            node_ids = [node_id for node_id, _theme in view["nodes"]]
            if not node_ids or len(node_ids) != len(set(node_ids)):
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "requires unique visual nodes."
                )
            if not view["relations"]:
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "requires visible directed relations."
                )
            node_set = set(node_ids)
            if any(
                not relation_id
                or source not in node_set
                or target not in node_set
                or not relation_kind
                or not path_data
                for relation_id, source, target, relation_kind, path_data in view["relations"]
            ):
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "contains an invalid relation endpoint or path."
                )
            if any(
                not points
                or any(
                    abs(target_x - source_x) + abs(target_y - source_y) < 35
                    for (source_x, source_y), (target_x, target_y)
                    in zip(points, points[1:])
                )
                for _relation_id, _source, _target, _relation_kind, path_data
                in view["relations"]
                for points in [_review_route_points(path_data)]
            ):
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "contains an elbow route without visible turn clearance."
                )
            participant_ids = [
                participant_id
                for participant_id, _role, _x, _y, _width, _height
                in view["participants"]
            ]
            expected_participants = 4 if kind == "time-concurrency" else 0
            if (
                len(participant_ids) != expected_participants
                or len(participant_ids) != len(set(participant_ids))
                or any(
                    not role or not x or not y or not width or not height
                    for _participant_id, role, x, y, width, height
                    in view["participants"]
                )
            ):
                errors.append(
                    f'Code-review finding "{definition["id"]}" view "{view["id"]}" '
                    "has an invalid semantic participant inventory."
                )
            signatures.append(
                (
                    tuple(view["view_boxes"]),
                    tuple(theme for _node_id, theme in view["nodes"]),
                    tuple(
                        (role, x, y, width, height)
                        for _participant_id, role, x, y, width, height
                        in view["participants"]
                    ),
                    tuple(
                        (relation_kind, path_data)
                        for _relation_id, _source, _target, relation_kind, path_data
                        in view["relations"]
                    ),
                )
            )
        if len(signatures) == 2 and signatures[0] != signatures[1]:
            errors.append(
                f'Code-review finding "{definition["id"]}" current and repair views '
                "must use the same topology geometry."
            )
    fallback_by_id = {fallback["id"]: fallback for fallback in parser.fallbacks}
    if list(fallback_by_id) != definition_ids:
        errors.append(
            "Code-review no-script and print fallbacks must match finding order exactly."
        )
    for definition in parser.definitions:
        fallback = fallback_by_id.get(definition["id"])
        if fallback is None:
            continue
        route = routes.get(definition["kind"])
        if route is None:
            continue
        expected_route = (route["family"], route["template"])
        views = fallback["views"]
        if [view["id"] for view in views] != ["current", "repair"]:
            errors.append(
                f'Code-review fallback "{definition["id"]}" requires both views.'
            )
            continue
        if fallback["scenario_count"] != 1:
            errors.append(
                f'Code-review fallback "{definition["id"]}" requires one factual scenario.'
            )
        for view in views:
            if (
                (view["reuse_family"], view["reuse_template"]) != expected_route
                or view["topologies"] != {definition["kind"]}
                or not view["nodes"]
                or not view["relations"]
                or len(view["participants"])
                != (4 if definition["kind"] == "time-concurrency" else 0)
            ):
                errors.append(
                    f'Code-review fallback "{definition["id"]}" is incomplete or misrouted.'
                )
    if parser.definitions:
        first = parser.definitions[0]
        first_views = first["views"]
        mirrors = len(first_views) == 2 and len(parser.active_canvases) == 2
        if mirrors:
            for active, view in zip(parser.active_canvases, first_views):
                expected_signature = (
                    tuple(view["view_boxes"]),
                    tuple(theme for _node_id, theme in view["nodes"]),
                    tuple(
                        (role, x, y, width, height)
                        for _participant_id, role, x, y, width, height
                        in view["participants"]
                    ),
                    tuple(
                        (relation_kind, path_data)
                        for _relation_id, _source, _target, relation_kind, path_data
                        in view["relations"]
                    ),
                )
                active_signature = (
                    tuple(active["view_boxes"]),
                    tuple(theme for _node_id, theme in active["nodes"]),
                    tuple(active["participants"]),
                    tuple(active["relations"]),
                )
                if active["topologies"] != [first["kind"]] or active_signature != expected_signature:
                    mirrors = False
                    break
        if not mirrors:
            errors.append(
                "Code-review paired canvases must initially mirror the first current and repair views."
            )
    title_controls = re.search(
        r"<div\b[^>]*\bdata-artifact-shell-controls(?:\s|=|>)",
        html,
        re.IGNORECASE,
    )
    finding_nav = re.search(
        r"<nav\b[^>]*\bclass\s*=\s*([\"'])[^\"']*\breview-finding-nav\b[^\"']*\1",
        html,
        re.IGNORECASE,
    )
    comparison = re.search(
        r"<section\b[^>]*\bclass\s*=\s*([\"'])[^\"']*\breview-comparison\b[^\"']*\1",
        html,
        re.IGNORECASE,
    )
    current_canvas = re.search(
        r"<[^>]+\bdata-diagram-id\s*=\s*([\"'])code-review-current\1",
        html,
        re.IGNORECASE,
    )
    repair_canvas = re.search(
        r"<[^>]+\bdata-diagram-id\s*=\s*([\"'])code-review-repair\1",
        html,
        re.IGNORECASE,
    )
    active_scenario = re.search(
        r"<section\b[^>]*\bdata-review-scenario(?:\s|=|>)",
        html,
        re.IGNORECASE,
    )
    current_guide = re.search(
        r"<section\b[^>]*\bdata-diagram-reading-guide\s*=\s*([\"'])1\1"
        r"[^>]*\bdata-reading-guide-for\s*=\s*([\"'])code-review-current\2",
        html,
        re.IGNORECASE,
    )
    repair_guide = re.search(
        r"<section\b[^>]*\bdata-diagram-reading-guide\s*=\s*([\"'])1\1"
        r"[^>]*\bdata-reading-guide-for\s*=\s*([\"'])code-review-repair\2",
        html,
        re.IGNORECASE,
    )
    if (
        not title_controls
        or not finding_nav
        or not comparison
        or not current_canvas
        or not current_guide
        or not active_scenario
        or not repair_canvas
        or not repair_guide
        or not (
            title_controls.start()
            < finding_nav.start()
            < comparison.start()
            < current_canvas.start()
            < current_guide.start()
            < active_scenario.start()
            < repair_canvas.start()
            < repair_guide.start()
        )
    ):
        errors.append(
            "Code-review DOM order must be title-side controls, vertical finding rail, then current local guide and diagram, factual scenario, and repair local guide and diagram."
        )
    if len(
        re.findall(
            r"<[^>]+\bdata-diagram-controls\s*=\s*([\"'])code-review-pair\1",
            html,
            re.IGNORECASE,
        )
    ) != 1:
        errors.append("Code-review paired canvases require one shared control group.")
    if "data-artifact-shell-controls" not in html:
        errors.append(
            "Code-review shared controls must live in the artifact title region."
        )
    normalized_css = re.sub(r"\s+", "", html).lower()
    review_canvas_rule = re.search(
        r"\.review-canvas\[data-diagram-canvas\]\{(?P<body>[^}]*)\}",
        normalized_css,
    )
    review_canvas_css = review_canvas_rule.group("body") if review_canvas_rule else ""
    if (
        review_canvas_rule is None
        or "block-size:auto" not in review_canvas_css
        or "max-block-size:none" not in review_canvas_css
        or "overflow:visible" not in review_canvas_css
        or "overscroll-behavior:auto" not in review_canvas_css
        or re.search(r"overflow-[xy]:(?:auto|scroll)", review_canvas_css)
    ):
        errors.append(
            "Code-review canvases must grow with the page without nested scrolling."
        )
    if (
        re.search(
            r"\.review-layout\{[^}]*display:grid;[^}]*grid-template-columns:"
            r"minmax\(15rem,18rem\)minmax\(0,1fr\)",
            normalized_css,
        )
        is None
        or re.search(
            r"\.review-finding-nav\{[^}]*display:grid;[^}]*grid-template-columns:1fr",
            normalized_css,
        )
        is None
    ):
        errors.append(
            "Code-review layout requires one vertical finding rail beside the three-part reader."
        )
    if re.search(
        r"<div\b[^>]*\bdata-reading-guide-heading(?:\s|=|>)",
        html,
        re.IGNORECASE,
    ):
        errors.append("Code-review package must not render a reading-guide heading card.")
    shell_parser = _ArtifactShellParser()
    shell_parser.feed(html)
    shell_parser.close()
    review_guides = {
        record["for"]: record
        for record in shell_parser.guide_records
        if record["for"] in {"code-review-current", "code-review-repair"}
    }
    expected_evidence_states = {
        ("observed", "file"),
        ("observed", "test"),
        ("unresolved", "runtime"),
    }
    for canvas_id in ("code-review-current", "code-review-repair"):
        record = review_guides.get(canvas_id)
        if record is None:
            errors.append(
                f"Code-review canvas {canvas_id} requires one local relation-and-evidence guide."
            )
            continue
        if Counter(record["groups"]) != Counter({"relations": 1, "evidence": 1}):
            errors.append(
                f"Code-review canvas {canvas_id} requires exactly the relations and evidence guide groups."
            )
        evidence = record["evidence"]
        if (
            len(evidence) != 3
            or {(status, source_kind) for _id, status, source_kind in evidence}
            != expected_evidence_states
        ):
            errors.append(
                f"Code-review canvas {canvas_id} requires observed implementation, completed check, and unresolved runtime evidence states."
            )
    for attribute in ("data-review-current-title", "data-review-repair-title"):
        visible_title = re.search(
            rf"<h2\b[^>]*\b{attribute}(?:\s|=|>)[^>]*>(?P<body>.*?)</h2>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if visible_title and "｜" in re.sub(r"<[^>]+>", "", visible_title.group("body")):
            errors.append(
                "Code-review visible diagram headings must omit the topology type prefix."
            )
    title_match = re.search(
        r"<h1\b[^>]*>(?P<body>.*?)</h1>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        title_text = re.sub(r"<[^>]+>", "", title_match.group("body")).strip()
        if "{{" not in title_text:
            title_parts = [part.strip() for part in title_text.split("｜")]
            if len(title_parts) != 2 or not all(title_parts):
                errors.append(
                    "Code-review page title must use the code review｜title description form."
                )
    if len(re.findall(r"<script\b[^>]*\bdata-code-review-kernel", html)) != 1:
        errors.append("Code-review package requires exactly one interaction kernel.")
    required_fallback_tokens = (
        "html:not(.review-enhanced)",
        "@media print",
        ".review-static-fallback",
    )
    if any(token not in html for token in required_fallback_tokens):
        errors.append("Code-review package is missing no-script or print expansion.")
    return _deduplicate(errors)


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
        errors = lint_markup_integrity(html)
        errors.extend(lint_route_contract(html))
        errors.extend(lint_diagram_view_title_contract(html))
        errors.extend(lint_guide_relation_binding_contract(html))
        errors.extend(lint_self_contained_resources(html))
        errors.extend(_validate_visible_language(html, ""))
        errors.extend(lint_template_identity(html, args.diagram_type))
        routing = load_template_routing()
        errors.extend(template_routing_errors(html, args.diagram_type, routing))
        errors.extend(lint_visual_shell(html))
        errors.extend(artifact_shell_errors(html))
        errors.extend(lint_artifact_shell_kernel(html))
        errors.extend(lint_template_conformance(html, args.diagram_type))
        is_code_review = (
            args.diagram_type == "code-review"
            and 'data-template-id="code-review-package"' in html
        )
        if not is_code_review:
            errors.extend(lint_primary_canvas_budget(html))
        if is_code_review:
            errors.extend(lint_code_review_package(html, routing))
        if args.diagram_type == "system-architecture":
            errors.extend(lint_system_architecture(html, allow_candidates=args.allow_candidates))
        elif not is_code_review:
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
        if requires_sequence or identity.attr_values("data-sequence-canvas"):
            errors.extend(lint_sequence_contract(html))
            ready_sequence = any(
                attrs.get("data-template-id", "").strip()
                in set(
                    routing["families"]
                    .get(attrs.get("data-template-family", "").strip(), {})
                    .get("ready_templates", [])
                )
                for attrs in identity.main_attrs
            )
            if ready_sequence:
                errors.extend(lint_sequence_visual_contract(html))
        policy = load_family_policies()
        if not is_code_review:
            errors.extend(
                true_diagram_errors(
                    html,
                    args.diagram_type,
                    routing=routing,
                    policy=policy,
                )
            )
        completed = {
            relative
            for paths in policy["migration_batches"].values()
            for relative in paths
        }
        for attrs in identity.main_attrs:
            family = attrs.get("data-template-family", "").strip()
            template_id = attrs.get("data-template-id", "").strip()
            if f"{family}/{template_id}.html" in completed:
                if not is_code_review:
                    errors.extend(lint_generic_contract(html, family, template_id, policy))
                errors.extend(lint_adaptive_kernel(html))
                errors.extend(lint_semantic_relations_kernel(html))
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
