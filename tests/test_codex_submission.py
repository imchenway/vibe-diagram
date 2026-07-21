from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_codex_submission import build_submission, validate_submission_source
from scripts.build_packages import load_adapter, read_json_unique, read_version, render_template


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_ROOT = ROOT / "submission" / "codex"
PUBLIC_DOCS = ROOT / "docs" / "public"
REPOSITORY_URL = "https://github.com/imchenway/vibe-diagram"
PRIVACY_URL = f"{REPOSITORY_URL}/blob/main/docs/public/PRIVACY.md"
TERMS_URL = f"{REPOSITORY_URL}/blob/main/docs/public/TERMS.md"
LOGO_SOURCE = Path("submission/codex/assets/vibe-diagram-logo.svg")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CodexSubmissionTests(unittest.TestCase):
    def test_submission_cli_runs_from_the_repository_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/build_codex_submission.py", "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual("blocked", payload["readiness_state"])
        self.assertEqual(5, payload["positive_test_count"])
        self.assertEqual(3, payload["negative_test_count"])

    def test_submission_source_is_complete_but_explicitly_blocked_on_user_actions(self) -> None:
        record = validate_submission_source(ROOT)
        self.assertEqual("blocked", record["readiness_state"])
        self.assertEqual(5, record["positive_test_count"])
        self.assertEqual(3, record["negative_test_count"])
        self.assertEqual(
            [
                "apps-management-write-access",
            ],
            record["blockers"],
        )

        listing = read_json_unique(SUBMISSION_ROOT / "listing.json")
        self.assertEqual(1, listing["schema_version"])
        self.assertEqual("skills-only", listing["submission_type"])
        self.assertEqual("Vibe Diagram", listing["listing"]["name"])
        self.assertEqual(REPOSITORY_URL, listing["listing"]["website_url"])
        self.assertEqual(f"{REPOSITORY_URL}/issues", listing["listing"]["support_url"])
        self.assertEqual(PRIVACY_URL, listing["listing"]["privacy_policy_url"])
        self.assertEqual(TERMS_URL, listing["listing"]["terms_of_service_url"])
        self.assertEqual(LOGO_SOURCE.as_posix(), listing["listing"]["logo_source"])
        self.assertEqual(3, len(listing["listing"]["starter_prompts"]))
        self.assertEqual("verified-individual", listing["publisher"]["identity_verification"])
        self.assertEqual("approved-by-publisher", listing["publisher"]["legal_text_approval"])
        self.assertEqual([], listing["availability"]["countries_or_regions"])
        self.assertEqual("all-portal-supported-regions", listing["availability"]["status"])

    def test_submission_cases_are_exact_reviewer_ready_positive_and_negative_sets(self) -> None:
        payload = read_json_unique(SUBMISSION_ROOT / "test-cases.json")
        self.assertEqual(1, payload["schema_version"])
        positives = payload["positive"]
        negatives = payload["negative"]
        self.assertEqual(["P1", "P2", "P3", "P4", "P5"], [case["id"] for case in positives])
        self.assertEqual(["N1", "N2", "N3"], [case["id"] for case in negatives])
        for case in positives:
            self.assertEqual(
                {"id", "prompt", "expected_behavior", "expected_result_shape", "fixture"},
                set(case),
            )
            self.assertTrue(all(isinstance(value, str) and value.strip() for value in case.values()))
        for case in negatives:
            self.assertEqual(
                {
                    "id",
                    "prompt",
                    "expected_behavior",
                    "expected_result_shape",
                    "fixture",
                    "why_not_complete",
                },
                set(case),
            )
            self.assertTrue(all(isinstance(value, str) and value.strip() for value in case.values()))

    def test_submission_listing_is_separate_from_the_runtime_verified_plugin_payload(self) -> None:
        spec = load_adapter(ROOT, "codex")
        manifest = render_template(
            read_json_unique(ROOT / "adapters" / "codex" / spec.manifest_template),
            read_version(ROOT),
        )
        self.assertEqual(
            {
                "name",
                "version",
                "description",
                "author",
                "license",
                "skills",
                "interface",
            },
            set(manifest),
        )
        self.assertEqual({"name": "imchenway"}, manifest["author"])
        self.assertEqual(
            ["Use Vibe Diagram to create a self-contained HTML diagram for this request."],
            manifest["interface"]["defaultPrompt"],
        )
        listing = read_json_unique(SUBMISSION_ROOT / "listing.json")
        self.assertEqual(3, len(listing["listing"]["starter_prompts"]))
        self.assertEqual(LOGO_SOURCE.as_posix(), listing["listing"]["logo_source"])
        logo = ROOT / LOGO_SOURCE
        self.assertTrue(logo.is_file())
        self.assertFalse(logo.is_symlink())
        self.assertIn("<svg", logo.read_text(encoding="utf-8"))

    def test_public_policy_and_support_documents_are_publishable_and_home_clean(self) -> None:
        expected = {
            "PRIVACY.md": ("隐私政策", "不会运营后端服务"),
            "TERMS.md": ("使用条款", "Apache-2.0"),
            "SUPPORT.md": ("支持", "GitHub Issues"),
        }
        for name, markers in expected.items():
            with self.subTest(name=name):
                path = PUBLIC_DOCS / name
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                text = path.read_text(encoding="utf-8")
                for marker in markers:
                    self.assertIn(marker, text)
                self.assertNotIn(str(Path.home()), text)
                self.assertNotIn("[TODO:", text)

    def test_submission_build_is_deterministic_and_contains_the_exact_codex_skill_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = base / "first"
            second = base / "second"
            first_report = build_submission(ROOT, first)
            second_report = build_submission(ROOT, second)

            self.assertEqual(first_report, second_report)
            archive_name = f"vibe-diagram-{read_version(ROOT)}.zip"
            first_archive = first / archive_name
            second_archive = second / archive_name
            self.assertEqual(_sha256(first_archive), _sha256(second_archive))
            self.assertEqual(first_archive.read_bytes(), second_archive.read_bytes())
            self.assertEqual(_sha256(first / "vibe-diagram-logo.svg"), _sha256(second / "vibe-diagram-logo.svg"))
            self.assertEqual(first_report, json.loads((first / "submission-report.json").read_text(encoding="utf-8")))

            with zipfile.ZipFile(first_archive) as archive:
                names = archive.namelist()
                self.assertEqual(sorted(names, key=lambda value: value.encode("utf-8")), names)
                self.assertIn("vibe-diagram/SKILL.md", names)
                self.assertIn("vibe-diagram/agents/openai.yaml", names)
                self.assertEqual(83, len(names))
                for info in archive.infolist():
                    self.assertEqual((1980, 1, 1, 0, 0, 0), info.date_time)
                    self.assertEqual(zipfile.ZIP_STORED, info.compress_type)
                    self.assertEqual(0o100644 << 16, info.external_attr)
                self.assertEqual(
                    (ROOT / "skills" / "vibe-diagram" / "SKILL.md").read_bytes(),
                    archive.read("vibe-diagram/SKILL.md"),
                )
                self.assertEqual(
                    (ROOT / "adapters" / "codex" / "files" / "agents" / "openai.yaml").read_bytes(),
                    archive.read("vibe-diagram/agents/openai.yaml"),
                )

            self.assertEqual("package-static-valid", first_report["validation_scope"])
            self.assertEqual("unverified", first_report["runtime_validation"])
            self.assertEqual("blocked", first_report["submission_readiness"])
            self.assertEqual(83, first_report["bundle"]["file_count"])


if __name__ == "__main__":
    unittest.main()
