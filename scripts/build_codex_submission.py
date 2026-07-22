#!/usr/bin/env python3
"""Validate and assemble a deterministic Codex skills-only submission bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_packages import (
    ValidationError,
    assemble_client_package,
    load_adapter,
    read_json_unique,
    read_version,
    render_template,
    sha256_file,
    tree_record,
    validate_manifest,
)


SUBMISSION_RELATIVE = Path("submission/codex")
LISTING_RELATIVE = SUBMISSION_RELATIVE / "listing.json"
LOGO_RELATIVE = Path("submission/codex/assets/vibe-diagram-logo.svg")
PUBLIC_DOCS = {
    "PRIVACY.md": ("隐私政策", "不会运营后端服务"),
    "TERMS.md": ("使用条款", "Apache-2.0"),
    "SUPPORT.md": ("支持", "GitHub Issues"),
}
REQUIRED_BLOCKERS = {
    "apps-management-write-access",
}


def _fail(message: str) -> ValidationError:
    return ValidationError(message)


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise _fail(f"{label} has an invalid field set")


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{label} must be a non-empty string")
    return value


def _require_https(value: Any, label: str) -> str:
    text = _require_non_empty_string(value, label)
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc:
        raise _fail(f"{label} must be an absolute https URL")
    return text


def _require_string_list(value: Any, label: str, *, count: int | None = None) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise _fail(f"{label} must be an array of non-empty strings")
    if count is not None and len(value) != count:
        raise _fail(f"{label} must contain exactly {count} entries")
    return value


def validate_submission_source(root: Path) -> dict[str, Any]:
    """Validate repository-side submission material without claiming public readiness."""

    root = root.resolve()
    listing = read_json_unique(root / LISTING_RELATIVE)
    _require_exact_keys(
        listing,
        {
            "schema_version",
            "submission_type",
            "listing",
            "publisher",
            "availability",
            "bundle",
            "readiness",
        },
        "submission listing",
    )
    if listing["schema_version"] != 1 or listing["submission_type"] != "skills-only":
        raise _fail("submission listing identity is invalid")

    details = listing["listing"]
    if not isinstance(details, Mapping):
        raise _fail("submission listing.listing must be an object")
    _require_exact_keys(
        details,
        {
            "name",
            "short_description",
            "long_description",
            "category",
            "website_url",
            "support_url",
            "privacy_policy_url",
            "terms_of_service_url",
            "logo_source",
            "starter_prompts",
            "release_notes",
        },
        "submission listing.listing",
    )
    for field in ("name", "short_description", "long_description", "category", "release_notes"):
        _require_non_empty_string(details[field], f"listing.{field}")
    for field in (
        "website_url",
        "support_url",
        "privacy_policy_url",
        "terms_of_service_url",
    ):
        _require_https(details[field], f"listing.{field}")
    _require_string_list(details["starter_prompts"], "listing.starter_prompts", count=3)
    if details["logo_source"] != LOGO_RELATIVE.as_posix():
        raise _fail("listing.logo_source must point to the canonical Codex adapter logo")

    publisher = listing["publisher"]
    if not isinstance(publisher, Mapping):
        raise _fail("submission publisher must be an object")
    _require_exact_keys(
        publisher,
        {"developer_name", "identity_verification", "legal_text_approval"},
        "submission publisher",
    )
    _require_non_empty_string(publisher["developer_name"], "publisher.developer_name")
    if publisher["identity_verification"] != "verified-individual":
        raise _fail("publisher identity must record the verified individual publisher")
    if publisher["legal_text_approval"] != "approved-by-publisher":
        raise _fail("public legal text must record publisher approval")

    availability = listing["availability"]
    if not isinstance(availability, Mapping):
        raise _fail("submission availability must be an object")
    _require_exact_keys(
        availability,
        {"countries_or_regions", "status"},
        "submission availability",
    )
    if availability["countries_or_regions"] != []:
        raise _fail("portal-wide availability must not add a publisher-defined region list")
    if availability["status"] != "all-portal-supported-regions":
        raise _fail("availability must cover all regions supported by the submission portal")

    bundle = listing["bundle"]
    if bundle != {
        "source": "build/codex/skills/vibe-diagram",
        "archive_prefix": "vibe-diagram",
    }:
        raise _fail("submission bundle contract is invalid")

    readiness = listing["readiness"]
    if not isinstance(readiness, Mapping):
        raise _fail("submission readiness must be an object")
    _require_exact_keys(readiness, {"state", "blockers"}, "submission readiness")
    blockers = _require_string_list(readiness["blockers"], "readiness.blockers")
    if readiness["state"] != "blocked" or set(blockers) != REQUIRED_BLOCKERS:
        raise _fail("submission readiness must fail closed on all unresolved user/runtime actions")

    logo = root / LOGO_RELATIVE
    if not logo.is_file() or logo.is_symlink() or "<svg" not in logo.read_text(encoding="utf-8"):
        raise _fail("Codex submission logo must be a real local SVG file")

    for name, markers in PUBLIC_DOCS.items():
        path = root / "docs" / "public" / name
        if not path.is_file() or path.is_symlink():
            raise _fail(f"missing public document: {name}")
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                raise _fail(f"public document {name} is missing marker: {marker}")
        if str(Path.home()) in text or "[TODO:" in text:
            raise _fail(f"public document {name} contains private or placeholder content")

    spec = load_adapter(root, "codex")
    manifest = render_template(
        read_json_unique(root / "adapters" / "codex" / spec.manifest_template),
        read_version(root),
    )
    validate_manifest("codex", manifest, read_version(root))
    return {
        "readiness_state": readiness["state"],
        "blockers": sorted(blockers),
    }


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _zip_skill_tree(source: Path, archive: Path) -> list[dict[str, Any]]:
    files = sorted(
        (path for path in source.rglob("*") if path.is_file() and not path.is_symlink()),
        key=lambda path: path.relative_to(source).as_posix().encode("utf-8"),
    )
    records = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
        for path in files:
            relative = path.relative_to(source).as_posix()
            name = f"vibe-diagram/{relative}"
            data = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            output.writestr(info, data)
            records.append(
                {
                    "path": name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    return records


def build_submission(root: Path, output: Path) -> dict[str, Any]:
    """Create a deterministic review candidate without claiming runtime/public readiness."""

    root = root.resolve()
    output = output.resolve()
    source_record = validate_submission_source(root)
    if output.exists() or output.is_symlink():
        raise _fail(f"submission output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    version = read_version(root)
    spec = load_adapter(root, "codex")

    with tempfile.TemporaryDirectory() as temporary:
        package_root = Path(temporary) / "vibe-diagram"
        assemble_client_package(root, package_root, spec, version)
        skill_root = package_root / spec.skills_output
        skill_record = tree_record(skill_root)
        try:
            output.mkdir()
            archive = output / f"vibe-diagram-{version}.zip"
            files = _zip_skill_tree(skill_root, archive)
            shutil.copyfile(root / LOGO_RELATIVE, output / "vibe-diagram-logo.svg")
            report = {
                "schema_version": 1,
                "package_version": version,
                "validation_scope": "package-static-valid",
                "runtime_validation": "unverified",
                "submission_readiness": source_record["readiness_state"],
                "blockers": source_record["blockers"],
                "listing_sha256": sha256_file(root / LISTING_RELATIVE),
                "logo_sha256": sha256_file(root / LOGO_RELATIVE),
                "bundle": {
                    "archive": archive.name,
                    "archive_sha256": sha256_file(archive),
                    "file_count": skill_record.file_count,
                    "tree_sha256": skill_record.tree_sha256,
                    "files": files,
                },
            }
            (output / "submission-report.json").write_bytes(_json_bytes(report))
            return report
        except Exception:
            shutil.rmtree(output, ignore_errors=True)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate source material only")
    parser.add_argument("--output", type=Path, help="new output directory for the candidate bundle")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.check == (args.output is not None):
        parser.error("choose exactly one of --check or --output")
    if args.check:
        print(json.dumps(validate_submission_source(root), sort_keys=True))
    else:
        print(json.dumps(build_submission(root, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
