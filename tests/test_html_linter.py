from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "skills" / "vibe-diagram" / "scripts" / "vibe_diagram_lint.py"
TEMPLATE_ROOT = ROOT / "skills" / "vibe-diagram" / "assets" / "templates"


def _load_linter():
    spec = importlib.util.spec_from_file_location("canonical_vibe_diagram_lint", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not create linter import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _artifact(
    family: str = "business-flow",
    template_id: str = "bpmn-light-flow",
    layout: str = "bpmn-light-flow",
    body: str = '<section class="template-layout bpmn-light-flow"><div>Start</div></section>',
) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body><main data-diagram-type="{family}" data-template-family="{family}"
data-template-id="{template_id}" data-template-layout="{layout}"><h1>Title</h1>{body}</main></body></html>'''


def _sequence_canvas(
    *,
    canvas_id: str = "checkout",
    role: str = "standalone",
    detail_for: str = "",
    participants: tuple[str, ...] = ("caller", "service"),
    messages: tuple[tuple[str, str, str, str], ...] = (("caller", "service", "sync", "request"),),
    phases: tuple[str, ...] = (),
) -> str:
    participant_html = "".join(
        f'<div data-participant-id="{participant}">{participant}</div>'
        for participant in participants
    )
    message_html = "".join(
        f'<article data-sequence-message data-from="{source}" data-to="{target}" '
        f'data-message-kind="{kind}" data-semantic="{semantic}">'
        f'<span data-sequence-route>{source} → {target}</span></article>'
        for source, target, kind, semantic in messages
    )
    phase_html = "".join(
        f'<section data-sequence-phase-id="{phase}">{phase}</section>' for phase in phases
    )
    detail_attribute = f' data-sequence-detail-for="{detail_for}"' if detail_for else ""
    return (
        f'<section data-sequence-canvas data-sequence-contract="1" '
        f'data-sequence-id="{canvas_id}" data-sequence-role="{role}" '
        f'data-sequence-width="auto" data-sequence-height="auto"{detail_attribute}>'
        f'<header data-sequence-participants>{participant_html}</header>'
        f'<div data-sequence-stage>{phase_html}{message_html}</div></section>'
    )


class HtmlLinterTests(unittest.TestCase):
    def test_sequence_contract_requires_canvas_two_participants_and_message(self) -> None:
        linter = _load_linter()
        cases = {
            "no-canvas": "",
            "no-participants-or-messages": _sequence_canvas(participants=(), messages=()),
            "one-participant-no-messages": _sequence_canvas(
                participants=("only",), messages=()
            ),
        }
        for name, html in cases.items():
            with self.subTest(name=name):
                errors = linter.lint_sequence_contract(html)
                self.assertTrue(errors)

    def test_cli_requires_sequence_canvas_for_all_sequence_owner_templates(self) -> None:
        linter = _load_linter()
        owners = (
            ("code-sequence", "participant-timeline.html"),
            ("fault-debugging", "debugging-sequence.html"),
            ("feature-iteration", "current-target-sequence.html"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for family, name in owners:
                with self.subTest(family=family, name=name):
                    html = (TEMPLATE_ROOT / family / name).read_text(encoding="utf-8")
                    html = html.replace(" data-sequence-canvas", "")
                    path = Path(temporary) / name
                    path.write_text(html, encoding="utf-8")
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = linter.main([str(path), "--type", family])
                    self.assertEqual(1, result, stdout.getvalue())
                    self.assertIn("canvas", stdout.getvalue().lower())

    def test_diagram_type_must_match_requested_family(self) -> None:
        html = _artifact().replace(
            'data-diagram-type="business-flow"',
            'data-diagram-type="code-sequence"',
        )
        errors = _load_linter().lint_template_identity(html, "business-flow")
        self.assertTrue(any("diagram type" in error.lower() for error in errors))

    def test_template_catalog_is_loaded_from_assets_directory(self) -> None:
        linter = _load_linter()
        catalog = linter.load_template_layouts()
        self.assertEqual(58, sum(len(entries) for entries in catalog.values()))
        self.assertEqual("participant-timeline", catalog["code-sequence"]["participant-timeline"])

    def test_every_non_system_template_has_known_identity(self) -> None:
        linter = _load_linter()
        for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
            family = path.parent.name
            if family == "system-architecture":
                continue
            with self.subTest(path=path.name):
                errors = linter.lint_template_identity(path.read_text(encoding="utf-8"), family)
                self.assertEqual([], errors)

    def test_unknown_template_id_fails_in_english(self) -> None:
        errors = _load_linter().lint_template_identity(
            _artifact(template_id="unknown-flow", layout="unknown-flow"),
            "business-flow",
        )
        self.assertTrue(any("known template" in error.lower() for error in errors))
        self.assertTrue(all(not any("\u3400" <= char <= "\u9fff" for char in error) for error in errors))

    def test_layout_mismatch_fails_in_english(self) -> None:
        errors = _load_linter().lint_template_identity(
            _artifact(layout="swimlane-flow"),
            "business-flow",
        )
        self.assertTrue(any("layout" in error.lower() and "bpmn-light-flow" in error for error in errors))

    def test_horizontal_title_description_node_fails(self) -> None:
        html = _artifact(
            body='''<style>.slot{display:flex}</style><section class="template-layout bpmn-light-flow">
            <div class="slot"><b>Title</b><span>Description</span></div></section>'''
        )
        errors = _load_linter().lint_title_description_stacking(html)
        self.assertTrue(any("vertical" in error.lower() for error in errors))

    def test_system_architecture_requires_known_template_id(self) -> None:
        html = _artifact(
            family="system-architecture",
            template_id="unknown-system",
            layout="unknown-system",
            body='<svg viewBox="0 0 1600 900"><foreignObject></foreignObject></svg>',
        )
        errors = _load_linter().lint_template_identity(html, "system-architecture")
        self.assertTrue(any("known template" in error.lower() for error in errors))

    def test_system_architecture_requires_svg_and_limits_primary_evidence(self) -> None:
        html = _artifact(
            family="system-architecture",
            template_id="system-context",
            layout="boundary-hub",
            body="<div>E1 E2 E3 E4 E5 E6 E7</div>",
        )
        errors = _load_linter().lint_system_architecture(html)
        self.assertTrue(any("svg" in error.lower() for error in errors))
        self.assertTrue(any("evidence" in error.lower() for error in errors))

    def test_system_architecture_evidence_limit_counts_each_visible_marker_once(self) -> None:
        linter = _load_linter()
        six = _artifact(
            family="system-architecture",
            template_id="system-context",
            layout="boundary-hub",
            body='<svg viewBox="0 0 1600 900"><text>E1 E2 E3 E4 E5 E6</text></svg>',
        )
        seven = six.replace("E1 E2 E3 E4 E5 E6", "E1 E2 E3 E4 E5 E6 E7")
        self.assertFalse(
            any("evidence" in error.lower() for error in linter.lint_system_architecture(six))
        )
        self.assertTrue(
            any("evidence" in error.lower() for error in linter.lint_system_architecture(seven))
        )

    def test_candidate_tabs_require_explicit_allow_flag(self) -> None:
        html = _artifact(
            family="system-architecture",
            template_id="system-context",
            layout="boundary-hub",
            body='<svg viewBox="0 0 1600 900"><foreignObject><div role="tablist">Views</div></foreignObject></svg>',
        )
        linter = _load_linter()
        denied = linter.lint_system_architecture(html)
        allowed = linter.lint_system_architecture(html, allow_candidates=True)
        self.assertTrue(any("candidate" in error.lower() for error in denied))
        self.assertFalse(any("candidate" in error.lower() for error in allowed))

    def test_relative_resource_attributes_fail(self) -> None:
        errors = _load_linter().lint_self_contained_resources(
            _artifact(body='<img src="./image.png"><a href="/root/path">Link</a>')
        )
        self.assertTrue(any("resource" in error.lower() or "link" in error.lower() for error in errors))

    def test_css_relative_url_fails(self) -> None:
        errors = _load_linter().lint_self_contained_resources(
            _artifact(body='<style>.node{background:url("./image.png")}</style>')
        )
        self.assertTrue(any("css" in error.lower() for error in errors))

    def test_runtime_network_apis_fail(self) -> None:
        errors = _load_linter().lint_self_contained_resources(
            _artifact(body='<script>globalThis["fetch"]("./payload.json")</script>')
        )
        self.assertTrue(any("network" in error.lower() for error in errors))

    def test_non_network_computed_global_property_is_allowed(self) -> None:
        errors = _load_linter().lint_self_contained_resources(
            _artifact(body='<script>globalThis["theme"]="dark"</script>')
        )
        self.assertEqual([], errors)

    def test_runtime_dynamic_code_apis_fail(self) -> None:
        linter = _load_linter()
        cases = (
            '<script>eval("globalThis.theme = \'dark\'")</script>',
            '<script>new Function("globalThis.theme = \'dark\'")()</script>',
        )
        for script in cases:
            with self.subTest(script=script):
                errors = linter.lint_self_contained_resources(_artifact(body=script))
                self.assertTrue(
                    any("dynamic-code" in error.lower() for error in errors),
                    errors,
                )

    def test_runtime_resource_and_navigation_sinks_fail(self) -> None:
        linter = _load_linter()
        cases = (
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
        )
        for script in cases:
            with self.subTest(script=script):
                errors = linter.lint_self_contained_resources(_artifact(body=script))
                self.assertTrue(
                    any("network" in error.lower() for error in errors),
                    errors,
                )

    def test_meta_refresh_and_ping_fail(self) -> None:
        linter = _load_linter()
        cases = (
            '<meta http-equiv="refresh" content="0;url=./next.html">',
            '<a href="#ok" ping="./audit">Local</a>',
        )
        for fragment in cases:
            with self.subTest(fragment=fragment):
                errors = linter.lint_self_contained_resources(_artifact(body=fragment))
                self.assertTrue(errors)

    def test_sequence_duplicate_participant_fails(self) -> None:
        html = _sequence_canvas(participants=("caller", "caller"))
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("duplicate participant" in error.lower() for error in errors))

    def test_sequence_duplicate_endpoint_attribute_fails(self) -> None:
        html = _sequence_canvas().replace(
            'data-from="caller"',
            'data-from="missing" data-from="caller"',
        )
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("duplicate sequence attributes" in error.lower() for error in errors))

    def test_sequence_missing_endpoint_fails(self) -> None:
        html = _sequence_canvas(messages=(("caller", "missing", "sync", "request"),))
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("endpoint" in error.lower() for error in errors))

    def test_sequence_unknown_message_kind_fails(self) -> None:
        html = _sequence_canvas(messages=(("caller", "service", "broadcast", "request"),))
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("message kind" in error.lower() for error in errors))

    def test_sequence_self_message_requires_same_endpoint(self) -> None:
        html = _sequence_canvas(messages=(("caller", "service", "self", "reenter"),))
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("self" in error.lower() and "same endpoint" in error.lower() for error in errors))

    def test_oversized_standalone_sequence_fails_with_split_instruction(self) -> None:
        messages = tuple(
            ("caller", "service", "sync", f"request-{index}") for index in range(41)
        )
        errors = _load_linter().lint_sequence_contract(_sequence_canvas(messages=messages))
        self.assertTrue(
            any(
                "split into one overview and linked detail sequences" in error.lower()
                for error in errors
            )
        )

    def test_multiple_detail_canvases_require_linked_overview(self) -> None:
        html = _sequence_canvas(canvas_id="detail-a", role="detail", detail_for="phase-a")
        html += _sequence_canvas(canvas_id="detail-b", role="detail", detail_for="phase-b")
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("exactly one overview" in error.lower() for error in errors))

    def test_unnecessary_overview_detail_split_fails(self) -> None:
        html = _sequence_canvas(
            canvas_id="overview",
            role="overview",
            phases=("phase-a",),
        )
        html += _sequence_canvas(
            canvas_id="detail-a",
            role="detail",
            detail_for="phase-a",
        )
        errors = _load_linter().lint_sequence_contract(html)
        self.assertTrue(any("unnecessary" in error.lower() for error in errors))

    def test_linked_overview_and_details_pass(self) -> None:
        phases = tuple(f"phase-{index}" for index in range(5))
        html = _sequence_canvas(canvas_id="overview", role="overview", phases=phases)
        html += "".join(
            _sequence_canvas(
                canvas_id=f"detail-{index}",
                role="detail",
                detail_for=phase,
            )
            for index, phase in enumerate(phases)
        )
        self.assertEqual([], _load_linter().lint_sequence_contract(html))

    def test_sequence_identity_version_and_modes_fail_closed(self) -> None:
        linter = _load_linter()
        mutations = (
            ('data-sequence-id="checkout"', 'data-sequence-id=""', "sequence-id"),
            ('data-sequence-contract="1"', 'data-sequence-contract="2"', "contract"),
            ('data-sequence-role="standalone"', 'data-sequence-role="other"', "role"),
            ('data-sequence-width="auto"', 'data-sequence-width="fluid"', "width mode"),
            ('data-sequence-height="auto"', 'data-sequence-height="clipped"', "height mode"),
        )
        baseline = _sequence_canvas()
        for old, new, expected in mutations:
            with self.subTest(expected=expected):
                errors = linter.lint_sequence_contract(baseline.replace(old, new))
                self.assertTrue(any(expected in error.lower() for error in errors), errors)
        duplicate_ids = baseline + baseline
        self.assertTrue(
            any("canvas id" in error.lower() and "duplicated" in error.lower()
                for error in linter.lint_sequence_contract(duplicate_ids))
        )

    def test_sequence_kernel_requires_exact_blocks_and_version(self) -> None:
        linter = _load_linter()
        valid = '<style data-sequence-kernel="1">a{color:red}</style>'
        valid += '<script data-sequence-kernel="1">document.title="x";</script>'
        self.assertRegex(linter.extract_sequence_kernel_digest(valid), r"^[0-9a-f]{64}$")
        invalid = (
            '<script data-sequence-kernel="1">document.title="x";</script>',
            valid + '<style data-sequence-kernel="1">b{color:blue}</style>',
            valid.replace('data-sequence-kernel="1"', 'data-sequence-kernel="2"', 1),
        )
        for html in invalid:
            with self.subTest(html=html[:48]):
                with self.assertRaises(ValueError):
                    linter.extract_sequence_kernel_digest(html)

    def test_fragment_and_data_urls_remain_allowed(self) -> None:
        html = _artifact(
            body='<svg><defs><linearGradient id="g"></linearGradient></defs><rect fill="url(#g)"></rect></svg>'
            '<a href="#details">Details</a><img src="data:image/gif;base64,AAAA">'
        )
        self.assertEqual([], _load_linter().lint_self_contained_resources(html))

    def test_cli_returns_zero_for_valid_non_system_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.html"
            path.write_text(
                (
                    ROOT
                    / "skills"
                    / "vibe-diagram"
                    / "assets"
                    / "templates"
                    / "business-flow"
                    / "bpmn-light-flow.html"
                ).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--type", "business-flow", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_cli_returns_one_and_prints_errors_for_invalid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.html"
            path.write_text(_artifact(template_id="missing", layout="missing"), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--type", "business-flow", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(1, result.returncode)
        self.assertIn("ERROR", result.stdout)
        self.assertIn("known template", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
