from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PUBLIC_DOCS = ROOT / "docs" / "public"
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
    r"(?:ready|eligible) for stable promotion",
    r"可(?:直接|立即)?提升(?:为|至)?稳定版",
    r"!\[[^]]*badge[^]]*\]",
)


def _version() -> str:
    return (ROOT / "VERSION").read_text(encoding="ascii").strip()


class DocumentationContractTests(unittest.TestCase):
    def test_public_document_inventory_and_language_boundary(self) -> None:
        expected = {"PRIVACY.md", "SUPPORT.md", "TERMS.md"}
        actual = {path.name for path in PUBLIC_DOCS.iterdir() if path.is_file()}
        self.assertEqual(expected, actual)

        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", english))
        self.assertIsNotNone(re.search(r"[\u3400-\u9fff]", chinese))
        self.assertIn("README.zh-CN.md", english)

    def test_readmes_state_static_and_lane_scoped_runtime_boundaries(self) -> None:
        version = _version()
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")

        english_required = (
            "`v0.1.1` established the released update-capable standalone Skill lane",
            f"repository version `{version}` keeps current and offline checks read-only",
            "skills/vibe-diagram/",
            "plugins/vibe-diagram/",
            ".agents/plugins/marketplace.json",
            "zero third-party runtime dependencies",
            "python3.9 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/build_packages.py --check",
            "python3 scripts/build_packages.py --sync-publication",
            "package-static-valid",
            "does not prove the complete unit suite",
            "evidence remains in command or CI output",
            "GitHub-path Codex CLI evidence is limited to the standalone Skill lane",
            "does not claim aggregate compatibility",
            "curated `$skill-installer` index",
            "public Plugins Directory",
        )
        for value in english_required:
            with self.subTest(document="README.md", value=value):
                self.assertIn(value, english)

        chinese_required = (
            "`v0.1.1` 建立了已发布、具备更新能力的独立 Skill lane",
            f"仓库版本 `{version}` 让 current 与 offline 检查保持只读",
            "skills/vibe-diagram/",
            "plugins/vibe-diagram/",
            ".agents/plugins/marketplace.json",
            "零第三方运行时依赖",
            "python3.9 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/build_packages.py --check",
            "python3 scripts/build_packages.py --sync-publication",
            "package-static-valid",
            "不能证明完整 unit suite",
            "证据保留在命令或 CI 输出中",
            "GitHub-path Codex CLI 证据仅覆盖独立 Skill lane",
            "不代表四类生成包的聚合兼容性",
            "curated `$skill-installer` 索引",
            "公共 Plugins Directory",
        )
        for value in chinese_required:
            with self.subTest(document="README.zh-CN.md", value=value):
                self.assertIn(value, chinese)

    def test_readmes_publish_exact_stable_skill_lifecycle_paths(self) -> None:
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        shared = (
            "https://github.com/imchenway/vibe-diagram",
            "https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram",
            "$skill-installer",
            "skill-installer/scripts/install-skill-from-github.py",
            "--repo imchenway/vibe-diagram",
            "--path skills/vibe-diagram",
            "--ref stable",
            "--ref v0.1.1",
            "update_skill.py",
            "--force-check",
            "backups/skills",
        )
        for value in shared:
            with self.subTest(value=value):
                self.assertIn(value, english)
                self.assertIn(value, chinese)

        self.assertNotIn("v0.1.0-rc.2", english)
        self.assertNotIn("v0.1.0-rc.2", chinese)
        self.assertIn("Start a new Codex task", english)
        self.assertIn("新建一个 Codex 任务", chinese)

    def test_changelog_records_the_stable_github_skill_lane(self) -> None:
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("## [Unreleased]"))
        self.assertIn("## [0.1.0] - 2026-07-18", text)
        self.assertIn(f"## [{_version()}] - 2026-07-20", text)
        self.assertIn("0.1.1", text)
        self.assertIn("automatic update", text)
        self.assertIn("fresh Codex CLI discovery", text)
        self.assertIn("curated `$skill-installer` index", text)
        self.assertNotIn("v0.1.0-rc.2", text)
        self.assertNotIn("Release URL", text)

    def test_public_documents_do_not_overclaim_release_or_compatibility(self) -> None:
        documents = [README, README_ZH, CHANGELOG, *sorted(PUBLIC_DOCS.iterdir())]
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        for pattern in PUBLIC_OVERCLAIM_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, re.IGNORECASE))

    def test_public_overclaim_patterns_detect_each_required_claim_family(self) -> None:
        violations = (
            "This package is PUBLICLY   INSTALLABLE.",
            "The package is ready\tfor   installation.",
            "Runtime \t is   verified.",
            "The project SUPPORTS   ALL FOUR CLIENTS.",
            "现已公开 \t 可安装",
            "运行时 \t 已验证",
            "四端 \t 均已支持",
        )
        for statement in violations:
            with self.subTest(statement=statement):
                self.assertTrue(
                    any(
                        re.search(pattern, statement, re.IGNORECASE)
                        for pattern in PUBLIC_OVERCLAIM_PATTERNS
                    )
                )


if __name__ == "__main__":
    unittest.main()
