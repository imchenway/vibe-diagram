from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROOT_FILES = frozenset(
    {
        ".gitattributes",
        ".gitignore",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "CONTEXT.md",
        "LICENSE",
        "VERSION",
        "release/github-skill.json",
        "scripts/release_github_skill.py",
    }
)
EXPECTED_GITATTRIBUTES = (
    b"plugins/vibe-diagram/skills/vibe-diagram/VERSION export-ignore\n"
)
APACHE_2_0_SHA256 = (
    "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
)
STRICT_SEMVER = re.compile(
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
EXPECTED_GITIGNORE_PATTERNS = (
    "build/",
    ".build.staging-*/",
    ".build.backup/",
    ".publication.staging-*/",
    ".publication.backup/",
    "__pycache__/",
    "*.py[cod]",
    ".DS_Store",
    ".coverage",
    ".pytest_cache/",
    ".idea/",
    "submission/codex/build/",
    "docs/*",
    "!docs/public/",
    "!docs/public/**",
)
EXPECTED_GITIGNORE = ("\n".join(EXPECTED_GITIGNORE_PATTERNS) + "\n").encode("ascii")
EXPECTED_STATIC_VALIDATION_WORKFLOW = b"""name: Static validation

on:
  pull_request:
  push:
    branches:
      - main
    tags:
      - "v*"

permissions:
  contents: read

jobs:
  release-verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: python39
        uses: actions/setup-python@v5
        with:
          python-version: "3.9"
      - id: python314
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Run read-only release verification
        env:
          RELEASE_STATE_DIR: ${{ runner.temp }}/vibe-diagram-release
        run: |
          PYTHONDONTWRITEBYTECODE=1 "${{ steps.python314.outputs.python-path }}" \\
            scripts/release_github_skill.py verify \\
            --version "$(tr -d '\\n' < VERSION)" \\
            --current-python "${{ steps.python314.outputs.python-path }}" \\
            --state-dir "$RELEASE_STATE_DIR" \\
            --json
          git diff --exit-code
          test -z "$(git status --porcelain)"
          test -z "$(git ls-files --others --ignored --exclude-standard)"
"""

EXPECTED_PUBLIC_DOCS = {
    "docs/public/PRIVACY.md",
    "docs/public/SUPPORT.md",
    "docs/public/TERMS.md",
}


class RepositoryContractTests(unittest.TestCase):
    def test_public_document_inventory_is_exact(self) -> None:
        docs_root = ROOT / "docs" / "public"
        actual = {
            path.relative_to(ROOT).as_posix()
            for path in docs_root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        self.assertEqual(EXPECTED_PUBLIC_DOCS, actual)

    def test_required_root_files_exist(self) -> None:
        missing = sorted(name for name in REQUIRED_ROOT_FILES if not (ROOT / name).exists())
        self.assertEqual([], missing)

    def test_required_root_inputs_are_regular_non_symlink_files(self) -> None:
        invalid = sorted(
            name
            for name in REQUIRED_ROOT_FILES
            if not (ROOT / name).is_file() or (ROOT / name).is_symlink()
        )
        self.assertEqual([], invalid)

    def test_version_is_single_line_strict_semver(self) -> None:
        raw = (ROOT / "VERSION").read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(1, raw.count(b"\n"))
        version = raw.decode("ascii").removesuffix("\n")
        self.assertIsNotNone(STRICT_SEMVER.fullmatch(version))
        for invalid in ("1.0.0-01", "1.0.0-alpha.01"):
            with self.subTest(invalid=invalid):
                self.assertIsNone(STRICT_SEMVER.fullmatch(invalid))

    def test_canonical_version_matches_repository_version(self) -> None:
        self.assertEqual(
            (ROOT / "VERSION").read_bytes(),
            (ROOT / "skills" / "vibe-diagram" / "VERSION").read_bytes(),
        )

    def test_license_is_exact_apache_2_0_text(self) -> None:
        raw = (ROOT / "LICENSE").read_bytes()
        text = raw.decode("utf-8")
        self.assertEqual(11357, len(raw))
        self.assertEqual(APACHE_2_0_SHA256, hashlib.sha256(raw).hexdigest())
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0, January 2004", text)
        self.assertIn("http://www.apache.org/licenses/", text)
        for section in range(1, 10):
            self.assertRegex(text, rf"(?m)^\s*{section}\. ")

    def test_gitignore_bytes_and_noncomment_patterns_are_exact(self) -> None:
        raw = (ROOT / ".gitignore").read_bytes()
        self.assertEqual(EXPECTED_GITIGNORE, raw)
        patterns = tuple(
            line.strip()
            for line in raw.decode("ascii").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "!"))
        )
        self.assertEqual(
            tuple(
                pattern
                for pattern in EXPECTED_GITIGNORE_PATTERNS
                if not pattern.startswith("!")
            ),
            patterns,
        )

    def test_release_archive_exports_only_the_canonical_version_marker(self) -> None:
        self.assertEqual(EXPECTED_GITATTRIBUTES, (ROOT / ".gitattributes").read_bytes())

    def test_publication_targets_are_real_non_symlink_paths(self) -> None:
        plugin = ROOT / "plugins" / "vibe-diagram"
        catalog = ROOT / ".agents" / "plugins" / "marketplace.json"
        self.assertTrue(plugin.is_dir())
        self.assertFalse(plugin.is_symlink())
        self.assertTrue(catalog.is_file())
        self.assertFalse(catalog.is_symlink())

    def test_static_validation_workflow_contract(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "static-validation.yml"
        self.assertTrue(workflow.is_file())
        self.assertFalse(workflow.is_symlink())
        raw = workflow.read_bytes()
        self.assertEqual(EXPECTED_STATIC_VALIDATION_WORKFLOW, raw)
        text = raw.decode("utf-8")

        self.assertRegex(text, r"(?m)^on:\s*$")
        self.assertRegex(text, r"(?m)^  pull_request:\s*$")
        self.assertRegex(text, r"(?m)^  push:\s*$")
        self.assertRegex(text, r"(?m)^    branches:\s*\n      - main\s*$")
        self.assertRegex(text, r'(?m)^    tags:\s*\n      - ["\']v\*["\']\s*$')
        self.assertRegex(text, r"(?m)^permissions:\s*\n  contents: read\s*$")

        versions = set(re.findall(r'(?m)^          python-version: ["\'](3\.(?:9|14))["\']\s*$', text))
        self.assertEqual({"3.9", "3.14"}, versions)
        self.assertIn(
            "scripts/release_github_skill.py verify",
            text,
        )
        self.assertIn("--current-python", text)
        self.assertIn("--state-dir \"$RELEASE_STATE_DIR\"", text)
        self.assertIn("${{ runner.temp }}/vibe-diagram-release", text)

        check = "scripts/release_github_skill.py verify"
        diff = "git diff --exit-code"
        porcelain = 'test -z "$(git status --porcelain)"'
        ignored = 'test -z "$(git ls-files --others --ignored --exclude-standard)"'
        self.assertIn(check, text)
        self.assertIn(diff, text)
        self.assertIn(porcelain, text)
        self.assertIn(ignored, text)
        self.assertLess(text.index(check), text.index(diff))
        self.assertLess(text.index(diff), text.index(porcelain))
        self.assertLess(text.index(porcelain), text.index(ignored))

        lowered = text.lower()
        for forbidden in (
            "sync-publication",
            "codex",
            "gh api",
            "git push",
            "gh release",
            "create-release",
            "marketplace publish",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    def test_public_product_sources_do_not_embed_private_home_path_markers(self) -> None:
        files = [
            ROOT / "README.md",
            ROOT / "README.zh-CN.md",
            ROOT / "CHANGELOG.md",
        ]
        for directory in ("skills", "adapters", "contracts", "scripts", "docs"):
            for path in (ROOT / directory).rglob("*"):
                if not path.is_file():
                    continue
                files.append(path)
        findings = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for marker in (str(Path.home()), "/home/", "~/"):
                if marker in text:
                    findings.append(f"{path.relative_to(ROOT)}:{marker}")
        self.assertEqual([], sorted(findings))

    def test_publication_source_set_does_not_embed_current_home_path(self) -> None:
        private_home = str(Path.home())
        self.assertNotIn(private_home, {"", "/"})
        findings = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if relative.parts[0] in {".git", ".idea", "build"}:
                continue
            if "__pycache__" in relative.parts or relative.name == ".DS_Store":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if private_home in text:
                findings.append(str(relative))
        self.assertEqual([], sorted(findings))

    def test_context_uses_the_parser_visible_major_sequence_phase_attribute(self) -> None:
        text = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
        self.assertIn("`data-sequence-phase-id`", text)
        self.assertNotIn("`data-sequence-phase`", text)


if __name__ == "__main__":
    unittest.main()
