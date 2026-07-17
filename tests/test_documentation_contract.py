from __future__ import annotations

import hashlib
import importlib.util
import math
import copy
import re
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_packages import (
    ValidationError,
    assemble_build_tree,
    read_json_unique,
    tree_record,
    validate_publication_tree,
)
from tests.template_contract import file_sha256


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
COMPATIBILITY = ROOT / "docs" / "compatibility.md"
ADR = ROOT / "docs" / "adr" / "0001-canonical-core-generated-packages.md"
ADR_MARKETPLACE = ROOT / "docs" / "adr" / "0002-codex-marketplace-generated-projection.md"
STATIC_EVIDENCE = ROOT / "docs" / "static-validation.json"
BROWSER_EVIDENCE = ROOT / "docs" / "macos-browser-validation.json"
LOCAL_CODEX_RUNTIME_EVIDENCE = (
    ROOT / "docs" / "runtime" / "macos-codex-app-local-marketplace.json"
)
GITHUB_CODEX_RUNTIME_EVIDENCE = (
    ROOT / "docs" / "runtime" / "macos-codex-app-github-sources.json"
)
CANONICAL = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = CANONICAL / "assets" / "templates"
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
CLIENT_LABELS = ("Codex", "Claude Code", "Gemini CLI", "GitHub Copilot CLI")
CLIENT_KEYS = ("claude", "codex", "copilot", "gemini")
SEQUENCE_TEMPLATES = (
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
    "feature-iteration/current-target-sequence.html",
)
FIXTURES = (
    "sequence-complex-overview-detail.html",
    "sequence-interaction-matrix.html",
    "sequence-no-js.html",
)
PUBLIC_OVERCLAIM_PATTERNS = (
    r"production.ready",
    r"works with all four clients",
    r"officially supported",
    r"fully compatible",
    r"\bpublicly\s+installable\b",
    r"\bready\s+for\s+installation\b",
    r"\bruntime\s+is\s+verified\b",
    r"\bsupports\s+all\s+four\s+clients\b",
    r"现已公开\s*可安装",
    r"运行时\s*已验证",
    r"四端\s*均已支持",
    r"runtime\s*[:=]?\s*passed",
    r"released on",
    r"https?://[^\s)]*/releases",
    r"/plugin\s+install",
    r"available (?:now )?to install",
    r"现在(?:即可|可以)安装",
    r"all GitHub users",
    r"所有\s*GitHub\s*用户",
    r"The tracked\s+`plugins/vibe-diagram/`",
    r"受跟踪的\s*`plugins/vibe-diagram/`",
    r"(?:ready|eligible) for stable promotion",
    r"可(?:直接|立即)?提升(?:为|至)?稳定版",
    r"!\[[^]]*badge[^]]*\]",
)


def _version() -> str:
    return (ROOT / "VERSION").read_text(encoding="ascii").strip()


def _compatibility_rows(text: str) -> dict[str, list[str]]:
    expected_header = [
        "Client",
        "Static package",
        "Install",
        "Discovery",
        "Invocation",
        "HTML delivery",
        "Upgrade/uninstall",
    ]
    table_rows: list[list[str]] = []
    header_count = 0
    separator_count = 0
    for line in text.splitlines():
        if re.fullmatch(r" {0,3}\|.*\|\s*", line) is None:
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if columns == expected_header:
            header_count += 1
        elif len(columns) == len(expected_header) and all(
            re.fullmatch(r":?-{3,}:?", column) is not None for column in columns
        ):
            separator_count += 1
        else:
            table_rows.append(columns)
    if header_count != 1 or separator_count != 1:
        raise AssertionError("compatibility ledger must contain one exact table header")
    if len(table_rows) != 4:
        raise AssertionError("compatibility ledger must contain exactly four client rows")
    rows: dict[str, list[str]] = {}
    for columns in table_rows:
        if len(columns) != len(expected_header) or columns[0] not in CLIENT_LABELS:
            raise AssertionError(f"unknown or malformed compatibility row: {columns!r}")
        if columns[0] in rows:
            raise AssertionError(f"duplicate compatibility row: {columns[0]}")
        rows[columns[0]] = columns[1:]
    if set(rows) != set(CLIENT_LABELS):
        raise AssertionError("compatibility ledger must contain exactly four client rows")
    return rows


def _macos_status(text: str) -> str:
    matches = re.findall(r"(?m)^macOS sequence interaction: (Pending|Passed)$", text)
    if len(matches) != 1:
        raise AssertionError("compatibility ledger must contain exactly one macOS status row")
    return matches[0]


def _load_linter():
    path = CANONICAL / "scripts" / "vibe_diagram_lint.py"
    spec = importlib.util.spec_from_file_location("documentation_contract_linter", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load canonical linter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_evidence(path: Path) -> dict:
    return read_json_unique(path)


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _require_schema_version(value: object, label: str, expected: int = 1) -> None:
    if type(value) is not int or value != expected:
        raise AssertionError(
            f"{label} schema_version must be the exact integer {expected}"
        )


def _all_true_exact(value: object, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise AssertionError(f"invalid {label} keys")
    if any(item is not True for item in value.values()):
        raise AssertionError(f"all {label} checks must be true")


def _valid_browser_evidence_fixture() -> dict:
    product_flags = {
        "desktop_rendered": True,
        "enhancement_initialized": True,
        "structured_routes_visible": True,
        "mobile_ledger_readable": True,
        "print_content_not_clipped": True,
    }
    checks = {
        "modes": {
            "width_auto": True,
            "width_contained": True,
            "width_wide": True,
            "height_auto": True,
            "height_flow": True,
            "height_scroll": True,
        },
        "short": {"toolbar_hidden": True, "no_nested_vertical_scroll": True},
        "wide": {
            "full_width": True,
            "safe_page_margins": True,
            "no_page_horizontal_overflow": True,
            "four_scale_controls_work": True,
            "viewport_anchor_preserved": True,
            "minimum_effective_text_12px": True,
        },
        "long": {
            "internal_vertical_scroll": True,
            "participants_sticky": True,
            "horizontal_alignment_preserved": True,
            "focus_not_obscured": True,
        },
        "mobile": {
            "toolbar_disabled": True,
            "sticky_disabled": True,
            "ledger_readable": True,
            "no_page_horizontal_overflow": True,
        },
        "no_js": {
            "enhancement_absent": True,
            "toolbar_absent": True,
            "structured_route_readable": True,
        },
        "print": {
            "toolbar_hidden": True,
            "sticky_reset": True,
            "overflow_expanded": True,
            "content_not_clipped": True,
        },
        "complex": {"overview_present": True, "details_linked": True},
    }
    linter = _load_linter()
    kernel = linter.extract_sequence_kernel_digest(
        (TEMPLATE_ROOT / SEQUENCE_TEMPLATES[0]).read_text(encoding="utf-8")
    )
    return {
        "schema_version": 1,
        "scope": "macos-local-sequence-interaction",
        "platform": {
            "os": "macOS",
            "browser": "Google Chrome",
            "browser_version": "synthetic-contract-fixture",
        },
        "viewports": {"desktop": "1440x900", "mobile": "390x844"},
        "canonical_tree_sha256": tree_record(CANONICAL).tree_sha256,
        "sequence_kernel_sha256": kernel,
        "fixtures": {name: file_sha256(FIXTURE_ROOT / name) for name in FIXTURES},
        "product_templates": {
            relative: {"sha256": file_sha256(TEMPLATE_ROOT / relative), **product_flags}
            for relative in SEQUENCE_TEMPLATES
        },
        "measurements": {
            "wide": {
                "anchor_message_id": "synthetic-message",
                "center_ratio_before": 0.5,
                "center_ratio_after_scale": 0.51,
                "center_ratio_after_resize": 0.49,
                "minimum_effective_text_px": 12.0,
                "left_margin_px": 16.0,
                "right_margin_px": 16.0,
                "page_scroll_width_px": 390.0,
                "page_client_width_px": 390.0,
            },
            "long": {
                "computed_position": "sticky",
                "participant_top_before_px": 10.0,
                "participant_top_after_px": 10.5,
                "header_height_px": 44.0,
                "scroll_padding_top_px": 44.0,
            },
            "print": {"clipped_element_count": 0},
        },
        "checks": checks,
        "unverified": {
            "clients": {client: "unverified" for client in CLIENT_LABELS},
            "operating_systems": {"Linux": "unverified", "Windows": "unverified"},
        },
    }


def _validate_browser_evidence(evidence: object) -> None:
    if not isinstance(evidence, dict):
        raise AssertionError("browser evidence must be an object")
    expected_top = {
        "schema_version",
        "scope",
        "platform",
        "viewports",
        "canonical_tree_sha256",
        "sequence_kernel_sha256",
        "fixtures",
        "product_templates",
        "measurements",
        "checks",
        "unverified",
    }
    if set(evidence) != expected_top:
        raise AssertionError("invalid browser evidence keys")
    _require_schema_version(evidence["schema_version"], "browser evidence")
    if evidence["scope"] != "macos-local-sequence-interaction":
        raise AssertionError("invalid browser evidence scope")
    platform = evidence["platform"]
    if not isinstance(platform, dict) or set(platform) != {"os", "browser", "browser_version"}:
        raise AssertionError("invalid platform schema")
    if platform["os"] != "macOS" or platform["browser"] != "Google Chrome":
        raise AssertionError("invalid browser platform")
    if not isinstance(platform["browser_version"], str) or not platform["browser_version"].strip():
        raise AssertionError("browser version must be non-empty")
    if evidence["viewports"] != {"desktop": "1440x900", "mobile": "390x844"}:
        raise AssertionError("invalid viewport contract")
    if evidence["canonical_tree_sha256"] != tree_record(CANONICAL).tree_sha256:
        raise AssertionError("browser evidence canonical hash is stale")

    fixtures = evidence["fixtures"]
    expected_fixtures = {name: file_sha256(FIXTURE_ROOT / name) for name in FIXTURES}
    if fixtures != expected_fixtures:
        raise AssertionError("browser evidence fixture hash is stale")
    products = evidence["product_templates"]
    if not isinstance(products, dict) or set(products) != set(SEQUENCE_TEMPLATES):
        raise AssertionError("invalid browser product template inventory")
    product_keys = {
        "sha256",
        "desktop_rendered",
        "enhancement_initialized",
        "structured_routes_visible",
        "mobile_ledger_readable",
        "print_content_not_clipped",
    }
    for relative, record in products.items():
        if not isinstance(record, dict) or set(record) != product_keys:
            raise AssertionError(f"invalid product evidence schema: {relative}")
        if record["sha256"] != file_sha256(TEMPLATE_ROOT / relative):
            raise AssertionError(f"stale product evidence: {relative}")
        if any(record[key] is not True for key in product_keys - {"sha256"}):
            raise AssertionError(f"product browser checks must pass: {relative}")

    linter = _load_linter()
    kernel_digests = {
        linter.extract_sequence_kernel_digest(
            (TEMPLATE_ROOT / relative).read_text(encoding="utf-8")
        )
        for relative in SEQUENCE_TEMPLATES
    }
    if kernel_digests != {evidence["sequence_kernel_sha256"]}:
        raise AssertionError("browser evidence sequence kernel hash is stale")

    measurements = evidence["measurements"]
    if not isinstance(measurements, dict) or set(measurements) != {"wide", "long", "print"}:
        raise AssertionError("invalid browser measurement groups")
    wide = measurements["wide"]
    wide_keys = {
        "anchor_message_id",
        "center_ratio_before",
        "center_ratio_after_scale",
        "center_ratio_after_resize",
        "minimum_effective_text_px",
        "left_margin_px",
        "right_margin_px",
        "page_scroll_width_px",
        "page_client_width_px",
    }
    if not isinstance(wide, dict) or set(wide) != wide_keys:
        raise AssertionError("invalid wide measurement schema")
    if not isinstance(wide["anchor_message_id"], str) or not wide["anchor_message_id"].strip():
        raise AssertionError("wide anchor message must be non-empty")
    numeric_wide = wide_keys - {"anchor_message_id"}
    if any(not _is_number(wide[key]) for key in numeric_wide):
        raise AssertionError("wide measurements must be numeric")
    ratios = (
        wide["center_ratio_before"],
        wide["center_ratio_after_scale"],
        wide["center_ratio_after_resize"],
    )
    if any(value < 0 or value > 1 for value in ratios):
        raise AssertionError("wide center ratios must be normalized")
    if any(abs(value - ratios[0]) > 0.02 for value in ratios[1:]):
        raise AssertionError("wide viewport anchor was not preserved")
    if wide["minimum_effective_text_px"] < 12:
        raise AssertionError("wide effective text is below 12px")
    if wide["left_margin_px"] < 16 or wide["right_margin_px"] < 16:
        raise AssertionError("wide safe page margins are below 16px")
    if wide["page_scroll_width_px"] > wide["page_client_width_px"]:
        raise AssertionError("wide page has horizontal overflow")

    long = measurements["long"]
    long_keys = {
        "computed_position",
        "participant_top_before_px",
        "participant_top_after_px",
        "header_height_px",
        "scroll_padding_top_px",
    }
    if not isinstance(long, dict) or set(long) != long_keys:
        raise AssertionError("invalid long measurement schema")
    if long["computed_position"] != "sticky":
        raise AssertionError("long participant header is not sticky")
    if any(not _is_number(long[key]) for key in long_keys - {"computed_position"}):
        raise AssertionError("long measurements must be numeric")
    if abs(long["participant_top_after_px"] - long["participant_top_before_px"]) > 1:
        raise AssertionError("sticky participant top drifted")
    if long["scroll_padding_top_px"] < long["header_height_px"]:
        raise AssertionError("scroll padding does not clear the participant header")
    print_measurement = measurements["print"]
    if (
        not isinstance(print_measurement, dict)
        or set(print_measurement) != {"clipped_element_count"}
        or type(print_measurement["clipped_element_count"]) is not int
        or print_measurement["clipped_element_count"] != 0
    ):
        raise AssertionError("print output contains clipped elements")

    checks = evidence["checks"]
    if not isinstance(checks, dict) or set(checks) != {
        "modes", "short", "wide", "long", "mobile", "no_js", "print", "complex"
    }:
        raise AssertionError("invalid browser check groups")
    expected_checks = {
        "modes": {
            "width_auto", "width_contained", "width_wide",
            "height_auto", "height_flow", "height_scroll",
        },
        "short": {"toolbar_hidden", "no_nested_vertical_scroll"},
        "wide": {
            "full_width", "safe_page_margins", "no_page_horizontal_overflow",
            "four_scale_controls_work", "viewport_anchor_preserved",
            "minimum_effective_text_12px",
        },
        "long": {
            "internal_vertical_scroll", "participants_sticky",
            "horizontal_alignment_preserved", "focus_not_obscured",
        },
        "mobile": {
            "toolbar_disabled", "sticky_disabled", "ledger_readable",
            "no_page_horizontal_overflow",
        },
        "no_js": {"enhancement_absent", "toolbar_absent", "structured_route_readable"},
        "print": {"toolbar_hidden", "sticky_reset", "overflow_expanded", "content_not_clipped"},
        "complex": {"overview_present", "details_linked"},
    }
    for group, keys in expected_checks.items():
        _all_true_exact(checks[group], keys, group)

    expected_unverified = {
        "clients": {client: "unverified" for client in CLIENT_LABELS},
        "operating_systems": {"Linux": "unverified", "Windows": "unverified"},
    }
    if evidence["unverified"] != expected_unverified:
        raise AssertionError("browser evidence extrapolates beyond the verified scope")


def _validate_local_codex_runtime_evidence(evidence: object) -> None:
    if not isinstance(evidence, dict):
        raise AssertionError("local Codex runtime evidence must be an object")
    expected_top = {
        "schema_version",
        "scope",
        "observed_at_utc",
        "client",
        "installation",
        "lifecycle",
        "artifacts",
        "boundaries",
    }
    if set(evidence) != expected_top:
        raise AssertionError("invalid local Codex runtime evidence keys")
    _require_schema_version(evidence["schema_version"], "local Codex runtime evidence")
    if evidence["scope"] != "macos-codex-app-local-repository-marketplace":
        raise AssertionError("invalid local Codex runtime evidence scope")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", evidence["observed_at_utc"]) is None:
        raise AssertionError("invalid local Codex runtime observation timestamp")

    client = evidence["client"]
    if not isinstance(client, dict) or set(client) != {
        "os",
        "application",
        "bundle_id",
        "app_version",
        "app_build",
        "bundled_codex_version",
        "surface",
    }:
        raise AssertionError("invalid local Codex client schema")
    if client["os"] != "macOS" or client["application"] != "Codex":
        raise AssertionError("invalid local Codex client identity")
    if client["bundle_id"] != "com.openai.codex":
        raise AssertionError("invalid Codex bundle identity")
    for key in ("app_version", "app_build", "bundled_codex_version"):
        if not isinstance(client[key], str) or not client[key].strip():
            raise AssertionError(f"local Codex {key} must be non-empty")
    if client["surface"] != "app-bundled-codex-runtime":
        raise AssertionError("invalid local Codex runtime surface")

    installation = evidence["installation"]
    expected_installation_keys = {
        "entry",
        "source",
        "marketplace_name",
        "plugin_id",
        "plugin_version",
        "cache_path",
        "source_plugin_tree_sha256",
        "installed_plugin_tree_sha256",
    }
    if not isinstance(installation, dict) or set(installation) != expected_installation_keys:
        raise AssertionError("invalid local Codex installation schema")
    if installation["entry"] != "local-repository-marketplace":
        raise AssertionError("invalid local Codex installation entry")
    if installation["source"] != "repository-root":
        raise AssertionError("invalid local Codex marketplace source")
    if installation["marketplace_name"] != "imchenway":
        raise AssertionError("invalid local Codex marketplace name")
    if installation["plugin_id"] != "vibe-diagram@imchenway":
        raise AssertionError("invalid local Codex plugin id")
    if installation["plugin_version"] != _version():
        raise AssertionError("local Codex plugin version is stale")
    if installation["cache_path"] != "<codex-home>/plugins/cache/imchenway/vibe-diagram/0.1.0-rc.1":
        raise AssertionError("invalid local Codex cache path")
    current_plugin_hash = tree_record(ROOT / "plugins" / "vibe-diagram").tree_sha256
    if installation["source_plugin_tree_sha256"] != current_plugin_hash:
        raise AssertionError("local Codex source plugin hash is stale")
    if installation["installed_plugin_tree_sha256"] != current_plugin_hash:
        raise AssertionError("installed local Codex plugin did not match the source projection")

    lifecycle = evidence["lifecycle"]
    if not isinstance(lifecycle, dict) or set(lifecycle) != {
        "install",
        "discovery",
        "invocation",
        "html_delivery",
        "upgrade",
        "uninstall",
    }:
        raise AssertionError("invalid local Codex lifecycle schema")
    for action, expected_status in {
        "install": "passed",
        "discovery": "passed",
        "invocation": "passed",
        "html_delivery": "passed",
        "upgrade": "unverified",
        "uninstall": "unverified",
    }.items():
        record = lifecycle[action]
        if not isinstance(record, dict) or set(record) != {"status", "evidence"}:
            raise AssertionError(f"invalid local Codex lifecycle record: {action}")
        if record["status"] != expected_status:
            raise AssertionError(f"invalid local Codex lifecycle status: {action}")
        if not isinstance(record["evidence"], str) or not record["evidence"].strip():
            raise AssertionError(f"missing local Codex lifecycle evidence: {action}")

    artifacts = evidence["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "request_path",
        "request_sha256",
        "request_record",
        "html_path",
        "html_sha256",
        "linter",
        "remote_resource_scan",
        "visual_qa",
        "screenshot_sizes",
        "effective_viewports",
    }:
        raise AssertionError("invalid local Codex artifact schema")
    request_path = ROOT / artifacts["request_path"]
    html_path = ROOT / artifacts["html_path"]
    if artifacts["request_path"] != "docs/runtime/fixtures/codex-app-vibe-diagram-request.md":
        raise AssertionError("invalid local Codex request path")
    if artifacts["html_path"] != "docs/runtime/outputs/codex-app-plugin-smoke.html":
        raise AssertionError("invalid local Codex HTML path")
    if artifacts["request_sha256"] != file_sha256(request_path):
        raise AssertionError("local Codex request hash is stale")
    if artifacts["request_record"] != (
        "public-normalized reproduction; only the privacy-path prohibition wording "
        "changed after execution; observed facts and output requirements are unchanged"
    ):
        raise AssertionError("invalid local Codex request record boundary")
    if artifacts["html_sha256"] != file_sha256(html_path):
        raise AssertionError("local Codex HTML hash is stale")
    if artifacts["linter"] != "passed" or artifacts["remote_resource_scan"] != "passed":
        raise AssertionError("local Codex HTML static checks did not pass")
    if artifacts["screenshot_sizes"] != {"desktop": "1440x900", "narrow": "500x844"}:
        raise AssertionError("invalid local Codex visual QA screenshot sizes")
    if artifacts["effective_viewports"] != {"desktop": "1440x813", "narrow": "500x757"}:
        raise AssertionError("invalid local Codex effective visual QA viewports")
    visual_qa = artifacts["visual_qa"]
    if not isinstance(visual_qa, dict) or set(visual_qa) != {
        "status",
        "blocking_issues",
        "observation",
    }:
        raise AssertionError("invalid local Codex visual QA record")
    if visual_qa["status"] != "reviewed" or visual_qa["blocking_issues"] != 0:
        raise AssertionError("local Codex visual QA has blocking issues")
    if not isinstance(visual_qa["observation"], str) or not visual_qa["observation"].strip():
        raise AssertionError("local Codex visual QA observation is missing")

    if evidence["boundaries"] != {
        "app_ui_confirmation": "unverified",
        "github_repository": "unverified",
        "github_marketplace_install": "unverified",
        "github_skill_install": "unverified",
    }:
        raise AssertionError("local Codex evidence extrapolates beyond the observed surface")


def _validate_github_codex_runtime_evidence(evidence: object) -> None:
    if not isinstance(evidence, dict) or set(evidence) != {
        "schema_version",
        "scope",
        "observed_at_utc",
        "client",
        "release",
        "installations",
        "aggregate",
    }:
        raise AssertionError("invalid GitHub Codex runtime evidence schema")
    _require_schema_version(evidence["schema_version"], "GitHub Codex runtime evidence")
    if evidence["scope"] != "macos-codex-app-github-sources":
        raise AssertionError("invalid GitHub Codex runtime evidence scope")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", evidence["observed_at_utc"]) is None:
        raise AssertionError("invalid GitHub Codex runtime observation timestamp")

    client = evidence["client"]
    if not isinstance(client, dict) or set(client) != {
        "os",
        "application",
        "bundle_id",
        "app_version",
        "app_build",
        "bundled_codex_version",
        "surface",
    }:
        raise AssertionError("invalid GitHub Codex client schema")
    if client["os"] != "macOS" or client["application"] != "Codex":
        raise AssertionError("invalid GitHub Codex client identity")
    if client["bundle_id"] != "com.openai.codex":
        raise AssertionError("invalid GitHub Codex bundle identity")
    if client["surface"] != "app-bundled-codex-runtime":
        raise AssertionError("invalid GitHub Codex runtime surface")
    for key in ("app_version", "app_build", "bundled_codex_version"):
        if not isinstance(client[key], str) or not client[key].strip():
            raise AssertionError(f"GitHub Codex {key} must be non-empty")

    if evidence["release"] != {
        "repository": "https://github.com/imchenway/vibe-diagram",
        "tag": "v0.1.0-rc.1",
        "commit": "31dff0c170ef33ae779890330d58cf689a6b95e7",
        "main_actions": "success",
        "tag_actions": "success",
    }:
        raise AssertionError("invalid GitHub Codex release binding")

    installations = evidence["installations"]
    if not isinstance(installations, dict) or set(installations) != {
        "github_marketplace_plugin",
        "github_skill_path",
    }:
        raise AssertionError("invalid GitHub Codex installation entries")

    expected_lifecycle = {
        "install": "passed",
        "discovery": "passed",
        "invocation": "passed",
        "html_delivery": "passed",
        "upgrade": "unverified",
        "uninstall": "passed",
    }
    for entry_name, entry in installations.items():
        if not isinstance(entry, dict) or set(entry) != {
            "entry",
            "source_url",
            "ref",
            "installed_path",
            "source_tree_sha256",
            "installed_tree_sha256",
            "lifecycle",
            "artifacts",
        }:
            raise AssertionError(f"invalid GitHub Codex installation schema: {entry_name}")
        lifecycle = entry["lifecycle"]
        if not isinstance(lifecycle, dict) or set(lifecycle) != set(expected_lifecycle):
            raise AssertionError(f"invalid GitHub Codex lifecycle schema: {entry_name}")
        for action, status in expected_lifecycle.items():
            record = lifecycle[action]
            if not isinstance(record, dict) or set(record) != {"status", "evidence"}:
                raise AssertionError(f"invalid GitHub Codex lifecycle record: {entry_name}/{action}")
            if record["status"] != status:
                raise AssertionError(f"invalid GitHub Codex lifecycle status: {entry_name}/{action}")
            if not isinstance(record["evidence"], str) or not record["evidence"].strip():
                raise AssertionError(f"missing GitHub Codex lifecycle evidence: {entry_name}/{action}")

    plugin = installations["github_marketplace_plugin"]
    if plugin["entry"] != "repo-marketplace":
        raise AssertionError("invalid GitHub marketplace entry")
    if plugin["source_url"] != "https://github.com/imchenway/vibe-diagram.git":
        raise AssertionError("invalid GitHub marketplace source")
    if plugin["ref"] != "v0.1.0-rc.1":
        raise AssertionError("invalid GitHub marketplace ref")
    if plugin["installed_path"] != "<codex-home>/plugins/cache/imchenway/vibe-diagram/0.1.0-rc.1":
        raise AssertionError("invalid GitHub marketplace installed path")
    plugin_hash = tree_record(ROOT / "plugins" / "vibe-diagram").tree_sha256
    if plugin["source_tree_sha256"] != plugin_hash or plugin["installed_tree_sha256"] != plugin_hash:
        raise AssertionError("GitHub marketplace plugin tree hash is stale")

    skill = installations["github_skill_path"]
    if skill["entry"] != "github-skill-path":
        raise AssertionError("invalid GitHub skill entry")
    if skill["source_url"] != "https://github.com/imchenway/vibe-diagram/tree/v0.1.0-rc.1/skills/vibe-diagram":
        raise AssertionError("invalid GitHub skill source")
    if skill["ref"] != "v0.1.0-rc.1":
        raise AssertionError("invalid GitHub skill ref")
    if skill["installed_path"] != "<codex-home>/skills/vibe-diagram":
        raise AssertionError("invalid GitHub skill installed path")
    canonical_hash = tree_record(CANONICAL).tree_sha256
    if skill["source_tree_sha256"] != canonical_hash or skill["installed_tree_sha256"] != canonical_hash:
        raise AssertionError("GitHub skill tree hash is stale")

    expected_artifacts = {
        "github_marketplace_plugin": {
            "request_path": "docs/runtime/fixtures/codex-app-github-plugin-request.md",
            "html_path": "docs/runtime/outputs/codex-app-github-plugin-smoke.html",
            "actual_skill_id": "vibe-diagram:vibe-diagram",
        },
        "github_skill_path": {
            "request_path": "docs/runtime/fixtures/codex-app-github-skill-request.md",
            "html_path": "docs/runtime/outputs/codex-app-github-skill-smoke.html",
            "actual_skill_id": "vibe-diagram",
        },
    }
    for entry_name, paths in expected_artifacts.items():
        artifacts = installations[entry_name]["artifacts"]
        if not isinstance(artifacts, dict) or set(artifacts) != {
            "request_path",
            "request_sha256",
            "html_path",
            "html_sha256",
            "actual_skill_id",
            "linter",
            "remote_resource_scan",
        }:
            raise AssertionError(f"invalid GitHub Codex artifacts: {entry_name}")
        for key, value in paths.items():
            if artifacts[key] != value:
                raise AssertionError(f"invalid GitHub Codex artifact binding: {entry_name}/{key}")
        if artifacts["request_sha256"] != file_sha256(ROOT / artifacts["request_path"]):
            raise AssertionError(f"stale GitHub Codex request hash: {entry_name}")
        if artifacts["html_sha256"] != file_sha256(ROOT / artifacts["html_path"]):
            raise AssertionError(f"stale GitHub Codex HTML hash: {entry_name}")
        if artifacts["linter"] != "passed" or artifacts["remote_resource_scan"] != "passed":
            raise AssertionError(f"GitHub Codex HTML checks did not pass: {entry_name}")

    if evidence["aggregate"] != {
        "stable_gate_units": 24,
        "passed_units": 10,
        "unexecuted_units": 14,
        "app_ui_surface": "unverified",
        "linux": "unverified",
        "windows": "unverified",
        "stable_promotion": "blocked",
    }:
        raise AssertionError("GitHub Codex evidence extrapolates beyond the observed surface")


class DocumentationContractTests(unittest.TestCase):
    def test_public_document_inventory_and_language_boundary(self) -> None:
        for path in (README, README_ZH, CHANGELOG, COMPATIBILITY, ADR, ADR_MARKETPLACE):
            self.assertTrue(path.is_file(), path)
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", english))
        self.assertIsNotNone(re.search(r"[\u3400-\u9fff]", chinese))
        self.assertIn("README.zh-CN.md", english)
        self.assertNotIn("skills/vibe-diagram/SKILL.zh", chinese)

    def test_readmes_state_repository_artifact_and_validation_contracts(self) -> None:
        version = _version()
        required = (
            "skills/vibe-diagram/",
            "plugins/vibe-diagram/",
            ".agents/plugins/marketplace.json",
            "build/codex/",
            "build/claude/",
            "build/gemini/",
            "build/copilot/",
            "python3.9 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/build_packages.py --check",
            "python3 scripts/build_packages.py --sync-publication",
            "zero third-party runtime dependencies",
            "Apache-2.0",
            f"{version} release-candidate snapshot",
            "Unreleased",
            "runtime validation remains `Unverified`",
            "`static_validation: passed`",
            "package-static-valid",
            "only means the builder production preflight passed",
            "does not prove the complete unit suite, the two-build deterministic check, transaction failure matrix, static evidence recomputation, or the second complete suite",
            "docs/static-validation.json",
            "only editable source",
            "builder-only generated projection",
            "only publication write entry point",
            "read-only",
            "public Codex source structures",
            "GitHub installation is scoped to the pinned RC",
            "2 installation entries x 2 macOS surfaces x 6 lifecycle actions = 24",
            "10 GitHub-source real-client evidence units have passed",
            "14 real-client evidence units remain unexecuted",
            "Linux and Windows remain `Unverified`",
        )
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        for value in required:
            with self.subTest(value=value, document="README.md"):
                self.assertIn(value, english)
        chinese_required = (
            "skills/vibe-diagram/",
            "plugins/vibe-diagram/",
            ".agents/plugins/marketplace.json",
            "build/codex/",
            "build/claude/",
            "build/gemini/",
            "build/copilot/",
            "python3.9 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/build_packages.py --check",
            "python3 scripts/build_packages.py --sync-publication",
            "零第三方运行时依赖",
            "Apache-2.0",
            f"{version} release-candidate snapshot",
            "Unreleased",
            "运行时验证仍为 `Unverified`",
            "`static_validation: passed`",
            "package-static-valid",
            "仅表示 builder production preflight 已通过",
            "不能证明完整 unit suite、two-build deterministic check、transaction failure matrix、static evidence 重算或第二轮完整 suite",
            "docs/static-validation.json",
            "唯一可编辑事实源",
            "builder-only 生成投影",
            "唯一 publication 写入口",
            "只读",
            "两种 Codex 公开来源结构",
            "GitHub 安装仅面向固定 RC 标签",
            "2 种安装入口 x 2 个 macOS 客户端表面 x 6 个生命周期动作 = 24",
            "10 个 GitHub 来源真实客户端证据单元已通过",
            "14 个真实客户端证据单元仍未执行",
            "Linux 与 Windows 仍为 `Unverified`",
        )
        for value in chinese_required:
            with self.subTest(value=value, document="README.zh-CN.md"):
                self.assertIn(value, chinese)

    def test_readmes_publish_exact_pinned_github_install_and_uninstall_paths(self) -> None:
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        shared = (
            "https://github.com/imchenway/vibe-diagram",
            "codex plugin marketplace add imchenway/vibe-diagram --ref v0.1.0-rc.1",
            "codex plugin add vibe-diagram@imchenway",
            "codex plugin remove vibe-diagram@imchenway",
            "codex plugin marketplace remove imchenway",
            "https://github.com/imchenway/vibe-diagram/tree/v0.1.0-rc.1/skills/vibe-diagram",
            "$skill-installer",
        )
        for value in shared:
            with self.subTest(value=value, document="README.md"):
                self.assertIn(value, english)
            with self.subTest(value=value, document="README.zh-CN.md"):
                self.assertIn(value, chinese)
        self.assertIn("GitHub runtime validation is scoped to the App-bundled Codex runtime", english)
        self.assertIn("GitHub 运行时验证仅覆盖 App 内置 Codex 运行时", chinese)

    def test_build_report_and_evidence_keep_artifact_and_process_proof_separate(self) -> None:
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        compatibility = COMPATIBILITY.read_text(encoding="utf-8")
        self.assertNotIn(
            "hashes, deterministic assembly, and transaction checks passed",
            english,
        )
        self.assertNotIn("hash、确定性组装和事务语义", chinese)
        self.assertIn(
            "`Static package: Passed` 表示当前 canonical、manifest、文件集、hash 与 Codex publication 在静态工件层相互一致",
            compatibility,
        )
        self.assertIn(
            "`docs/static-validation.json` 只绑定当前 artifact、package 与 publication hash",
            compatibility,
        )
        self.assertIn(
            "完整 unit suite、two-build deterministic check、transaction failure matrix、evidence recomputation 与 second full suite 是另行执行的流程证据",
            compatibility,
        )
        self.assertIn(
            "这些流程不能由 build report 或 evidence JSON 单独证明",
            compatibility,
        )
        self.assertNotIn("hash、确定性构建与事务检查", compatibility)

    def test_public_docs_do_not_overclaim_release_or_compatibility(self) -> None:
        documents = [README, README_ZH, CHANGELOG, COMPATIBILITY, ADR, ADR_MARKETPLACE]
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        for pattern in PUBLIC_OVERCLAIM_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, re.IGNORECASE))

    def test_public_overclaim_patterns_detect_each_required_claim_family(self) -> None:
        violations = {
            "publicly-installable": "This package is PUBLICLY   INSTALLABLE.",
            "ready-for-installation": "The package is ready\tfor   installation.",
            "runtime-is-verified": "Runtime \t is   verified.",
            "supports-all-four": "The project SUPPORTS   ALL FOUR CLIENTS.",
            "public-install-zh": "现已公开 \t 可安装",
            "runtime-verified-zh": "运行时 \t 已验证",
            "four-clients-supported-zh": "四端 \t 均已支持",
        }
        for label, statement in violations.items():
            with self.subTest(label=label):
                matches = [
                    pattern
                    for pattern in PUBLIC_OVERCLAIM_PATTERNS
                    if re.search(pattern, statement, re.IGNORECASE)
                ]
                self.assertTrue(matches, statement)

    def test_changelog_is_an_unreleased_version_derived_snapshot(self) -> None:
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("## [Unreleased]"))
        self.assertIn(f"{_version()} release-candidate snapshot", text)
        self.assertIn("builder-only Codex publication projection", text)
        self.assertIn("10 GitHub-source real-client evidence units have passed", text)
        self.assertIn("14 real-client evidence units remain unexecuted", text)
        self.assertIsNone(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text))
        self.assertNotIn("Release URL", text)

    def test_compatibility_ledger_has_exact_columns_and_conservative_states(self) -> None:
        text = COMPATIBILITY.read_text(encoding="utf-8")
        self.assertIn(
            "| Client | Static package | Install | Discovery | Invocation | HTML delivery | Upgrade/uninstall |",
            text,
        )
        rows = _compatibility_rows(text)
        self.assertEqual(set(CLIENT_LABELS), set(rows))
        static_states = set()
        for client, states in rows.items():
            with self.subTest(client=client):
                self.assertEqual(6, len(states))
                self.assertIn(states[0], {"Pending", "Passed"})
                self.assertEqual(["Unverified"] * 5, states[1:])
                static_states.add(states[0])
        self.assertEqual(1, len(static_states), "all four static packages advance as one transaction")
        self.assertIn(_macos_status(text), {"Pending", "Passed"})
        self.assertIn("not a vendor CLI validator result", text)
        self.assertIn("Linux and Windows remain Unverified", text)
        self.assertIn("Unreleased 0.1.0-rc.1 release-candidate snapshot", text)
        self.assertIn("plugins/vibe-diagram/", text)
        self.assertIn(".agents/plugins/marketplace.json", text)
        self.assertIn("builder-only", text)
        self.assertIn("--sync-publication", text)
        self.assertIn("--check", text)
        self.assertIn("2 installation entries x 2 macOS surfaces x 6 lifecycle actions = 24", text)
        self.assertIn("10 GitHub-source real-client evidence units have passed", text)
        self.assertIn("14 real-client evidence units remain unexecuted", text)
        self.assertIn("GitHub marketplace: Install = Passed; Discovery = Passed; Invocation = Passed; HTML delivery = Passed; Upgrade = Unverified; Uninstall = Passed", text)
        self.assertIn("GitHub skill path: Install = Passed; Discovery = Passed; Invocation = Passed; HTML delivery = Passed; Upgrade = Unverified; Uninstall = Passed", text)
        self.assertIn("Codex App UI confirmation = Unverified", text)

    def test_local_codex_runtime_evidence_is_scoped_and_recomputable(self) -> None:
        self.assertTrue(LOCAL_CODEX_RUNTIME_EVIDENCE.is_file())
        _validate_local_codex_runtime_evidence(
            _read_evidence(LOCAL_CODEX_RUNTIME_EVIDENCE)
        )

    def test_github_codex_runtime_evidence_is_scoped_and_recomputable(self) -> None:
        self.assertTrue(GITHUB_CODEX_RUNTIME_EVIDENCE.is_file())
        _validate_github_codex_runtime_evidence(
            _read_evidence(GITHUB_CODEX_RUNTIME_EVIDENCE)
        )

    def test_static_package_passed_requires_current_recomputable_evidence(self) -> None:
        rows = _compatibility_rows(COMPATIBILITY.read_text(encoding="utf-8"))
        state = next(iter(rows.values()))[0]
        if state == "Pending":
            self.assertFalse(STATIC_EVIDENCE.exists())
            return

        self.assertEqual("Passed", state)
        self.assertTrue(STATIC_EVIDENCE.is_file())
        evidence = _read_evidence(STATIC_EVIDENCE)
        self.assertEqual(
            {
                "schema_version",
                "package_version",
                "runtime_validation",
                "build_report_sha256",
                "canonical_tree_sha256",
                "clients",
                "codex_publication",
            },
            set(evidence),
        )
        _require_schema_version(evidence["schema_version"], "static evidence", expected=2)
        self.assertEqual(_version(), evidence["package_version"])
        self.assertEqual("unverified", evidence["runtime_validation"])
        self.assertEqual(set(CLIENT_KEYS), set(evidence["clients"]))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "build"
            destination.mkdir()
            report = assemble_build_tree(ROOT, destination)
            report_bytes = (destination / "build-report.json").read_bytes()
        _require_schema_version(report["schema_version"], "build report")
        self.assertEqual(hashlib.sha256(report_bytes).hexdigest(), evidence["build_report_sha256"])
        self.assertEqual(report["canonical"]["tree_sha256"], evidence["canonical_tree_sha256"])
        for client in CLIENT_KEYS:
            record = evidence["clients"][client]
            self.assertEqual({"manifest_sha256", "package_tree_sha256"}, set(record))
            self.assertEqual(report["clients"][client]["manifest_sha256"], record["manifest_sha256"])
            self.assertEqual(
                report["clients"][client]["package"]["tree_sha256"],
                record["package_tree_sha256"],
            )
        publication = validate_publication_tree(ROOT, ROOT)
        self.assertEqual(_version(), publication["package_version"])
        self.assertEqual("unverified", publication["runtime_validation"])
        publication_evidence = evidence["codex_publication"]
        self.assertEqual(
            {"manifest_sha256", "package_tree_sha256", "marketplace_sha256"},
            set(publication_evidence),
        )
        self.assertEqual(
            publication["plugin_manifest_sha256"],
            publication_evidence["manifest_sha256"],
        )
        self.assertEqual(
            publication["plugin_tree_sha256"],
            publication_evidence["package_tree_sha256"],
        )
        self.assertEqual(
            publication["marketplace_sha256"],
            publication_evidence["marketplace_sha256"],
        )
        self.assertEqual(
            evidence["clients"]["codex"]["manifest_sha256"],
            publication_evidence["manifest_sha256"],
        )
        self.assertEqual(
            evidence["clients"]["codex"]["package_tree_sha256"],
            publication_evidence["package_tree_sha256"],
        )

    def test_macos_status_requires_current_evidence_without_runtime_extrapolation(self) -> None:
        text = COMPATIBILITY.read_text(encoding="utf-8")
        state = _macos_status(text)
        if state == "Pending":
            self.assertFalse(BROWSER_EVIDENCE.exists())
            return

        self.assertTrue(BROWSER_EVIDENCE.is_file())
        _validate_browser_evidence(_read_evidence(BROWSER_EVIDENCE))

    def test_evidence_json_rejects_duplicate_keys_nonfinite_and_nonobject_roots(self) -> None:
        invalid_documents = (
            '{"schema_version":1,"schema_version":1}',
            '{"schema_version":NaN}',
            '{"schema_version":1e999}',
            '{"schema_version":{"nested":-1e999}}',
            "[]",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            for content in invalid_documents:
                with self.subTest(content=content):
                    path.write_text(content + "\n", encoding="utf-8")
                    with self.assertRaises(ValidationError):
                        _read_evidence(path)

    def test_browser_evidence_validator_rejects_schema_type_threshold_and_scope_drift(self) -> None:
        valid = _valid_browser_evidence_fixture()
        _validate_browser_evidence(valid)
        mutations = {
            "schema-version": lambda value: value.__setitem__("schema_version", 999),
            "schema-version-float": lambda value: value.__setitem__("schema_version", 1.0),
            "scope-type": lambda value: value.__setitem__("scope", 42),
            "platform-null": lambda value: value.__setitem__("platform", None),
            "viewports-list": lambda value: value.__setitem__("viewports", []),
            "measurements-garbage": lambda value: value.__setitem__("measurements", "garbage"),
            "checks-list": lambda value: value.__setitem__("checks", []),
            "product-flags-missing": lambda value: value["product_templates"].__setitem__(
                SEQUENCE_TEMPLATES[0],
                {"sha256": file_sha256(TEMPLATE_ROOT / SEQUENCE_TEMPLATES[0])},
            ),
            "anchor-drift": lambda value: value["measurements"]["wide"].__setitem__(
                "center_ratio_after_scale", 0.75
            ),
            "text-too-small": lambda value: value["measurements"]["wide"].__setitem__(
                "minimum_effective_text_px", 11.9
            ),
            "sticky-drift": lambda value: value["measurements"]["long"].__setitem__(
                "participant_top_after_px", 12.0
            ),
            "print-clipped": lambda value: value["measurements"].__setitem__(
                "print", {"clipped_element_count": 1}
            ),
            "print-count-bool": lambda value: value["measurements"].__setitem__(
                "print", {"clipped_element_count": False}
            ),
            "false-check": lambda value: value["checks"]["mobile"].__setitem__(
                "ledger_readable", False
            ),
            "runtime-extrapolation": lambda value: value["unverified"]["clients"].__setitem__(
                "Codex", "verified"
            ),
            "infinite-wide-measurement": lambda value: value["measurements"]["wide"].__setitem__(
                "minimum_effective_text_px", float("inf")
            ),
            "infinite-long-measurement": lambda value: value["measurements"]["long"].__setitem__(
                "participant_top_before_px", float("inf")
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(valid)
                mutate(candidate)
                with self.assertRaises(AssertionError):
                    _validate_browser_evidence(candidate)

    def test_evidence_schema_versions_require_exact_integers(self) -> None:
        _require_schema_version(1, "synthetic")
        for invalid in (1.0, True, False, "1"):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                _require_schema_version(invalid, "synthetic")
        _require_schema_version(2, "synthetic v2", expected=2)
        for invalid in (1, 2.0, True, False, "2"):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                _require_schema_version(invalid, "synthetic v2", expected=2)

    def test_compatibility_parser_rejects_duplicate_client_and_macos_state_rows(self) -> None:
        text = COMPATIBILITY.read_text(encoding="utf-8")
        duplicate_client = text + "\n| Codex | Pending | Unverified | Unverified | Unverified | Unverified | Unverified |\n"
        with self.assertRaises(AssertionError):
            _compatibility_rows(duplicate_client)
        unknown_client = text + "\n| Fake Client | Passed | Passed | Passed | Passed | Passed | Passed |\n"
        with self.assertRaises(AssertionError):
            _compatibility_rows(unknown_client)
        indented_duplicate = text + "\n   | Codex | Pending | Unverified | Unverified | Unverified | Unverified | Unverified |\n"
        with self.assertRaises(AssertionError):
            _compatibility_rows(indented_duplicate)
        duplicate_macos = text + "\nmacOS sequence interaction: Pending\n"
        with self.assertRaises(AssertionError):
            _macos_status(duplicate_macos)

    def test_adr_records_canonical_generation_transaction_tradeoff_and_rollback(self) -> None:
        text = ADR.read_text(encoding="utf-8")
        for required in (
            "single canonical",
            "generated packages",
            "No symlinks",
            "no hand-maintained mirrors",
            "all four clients",
            "Trade-offs",
            "Rollback",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
