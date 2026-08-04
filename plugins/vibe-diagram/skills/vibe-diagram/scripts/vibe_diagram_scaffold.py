#!/usr/bin/env python3
"""Create a diagram artifact from the canonical Vibe Diagram catalog."""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
TEMPLATE_ROUTING_PATH = SKILL_ROOT / "contracts" / "template-routing.json"
IDENTITY_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
LANGUAGE_TAG_RE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")
NATIVE_STANDARD = "native"
CODE_REVIEW_FAMILY = "code-review"
CODE_REVIEW_TEMPLATE = "code-review-package"
CODE_REVIEW_FINDING_LIMIT = 12
DEPRECATED_FAMILIES = {
    "delivery-acceptance": (
        "deprecated for one release cycle: route acceptance steps to "
        "business-flow/logic-flowchart and requirement-to-evidence traceability "
        "to decision-communication/option-matrix-path"
    ),
}
DEPRECATED_TEMPLATES = {
    ("feature-iteration", "release-rollback-track"): (
        "deprecated for one release cycle: route release, observation, gate, and rollback "
        "to business-flow/logic-flowchart; use state-data-model/state-machine only when "
        "the user explicitly requests a state machine"
    ),
    ("business-architecture", "value-chain-map"): (
        "deprecated as the business-architecture default: use capability-domain-map, "
        "or route trigger/order/decision/exception prompts to business-flow/logic-flowchart"
    ),
    ("technical-design", "release-switch-track"): (
        "deprecated for one release cycle: use technical-design/technical-design-package; "
        "release and rollback remain one view inside the complete design package"
    ),
    ("technical-design", "data-consistency-boundary"): (
        "deprecated as a standalone diagram type: use "
        "technical-design/technical-design-package and place Outbox transaction, "
        "delivery, consumption, recovery, and consistency concerns in its mapped views"
    ),
}


TopologyNode = Tuple[int, int, int, int, str]
TopologyEdge = Tuple[int, int, str, int, int, str]


CODE_REVIEW_TOPOLOGIES: Dict[str, Dict[str, Any]] = {
    "architecture-boundary": {
        "view_box": "0 0 960 650",
        "nodes": (
            (360, 245, 240, 100, "center"),
            (30, 75, 210, 90, "boundary"),
            (720, 75, 210, 90, "boundary"),
            (30, 455, 210, 90, "boundary"),
            (720, 455, 210, 90, "boundary"),
            (360, 525, 240, 90, "outcome"),
        ),
        "edges": (
            (1, 0, "M240 120H300V270H360", 300, 210, "dependency"),
            (2, 0, "M720 120H660V270H600", 660, 210, "dependency"),
            (3, 0, "M240 500H300V320H360", 300, 410, "ownership"),
            (4, 0, "M720 500H660V320H600", 660, 410, "ownership"),
            (0, 5, "M480 345V525", 515, 435, "outcome"),
        ),
    },
    "cause-evidence": {
        "view_box": "0 0 1040 520",
        "nodes": (
            (20, 210, 160, 100, "evidence"),
            (220, 210, 160, 100, "cause"),
            (420, 210, 160, 100, "impact"),
            (620, 210, 160, 100, "remediation"),
            (820, 210, 160, 100, "verification"),
        ),
        "edges": (
            (0, 1, "M180 260H220", 200, 190, "supports"),
            (1, 2, "M380 260H420", 400, 190, "causes"),
            (2, 3, "M580 260H620", 600, 190, "motivates"),
            (3, 4, "M780 260H820", 800, 190, "verifies"),
        ),
    },
    "control-branch": {
        "view_box": "0 0 960 740",
        "nodes": (
            (350, 25, 260, 75, "entry"),
            (350, 150, 260, 95, "decision"),
            (40, 330, 240, 95, "branch"),
            (680, 330, 240, 95, "branch"),
            (350, 505, 260, 90, "merge"),
            (350, 645, 260, 70, "outcome"),
        ),
        "edges": (
            (0, 1, "M480 100V150", 515, 128, "next"),
            (1, 2, "M350 198H160V330", 255, 290, "branch"),
            (1, 3, "M610 198H800V330", 705, 290, "branch"),
            (2, 4, "M160 425V465H480V505", 320, 458, "merge"),
            (3, 4, "M800 425V465H480V505", 640, 458, "merge"),
            (4, 5, "M480 595V645", 515, 625, "outcome"),
        ),
    },
    "exception-compensation": {
        "view_box": "0 0 960 650",
        "nodes": (
            (20, 75, 180, 80, "entry"),
            (250, 75, 180, 80, "operation"),
            (480, 75, 180, 80, "operation"),
            (730, 75, 200, 80, "outcome"),
            (250, 300, 180, 90, "exception"),
            (480, 470, 180, 90, "compensation"),
        ),
        "edges": (
            (0, 1, "M200 115H250", 225, 55, "next"),
            (1, 2, "M430 115H480", 455, 55, "next"),
            (2, 3, "M660 115H730", 695, 55, "success"),
            (1, 4, "M340 155V300", 378, 228, "exception"),
            (4, 5, "M430 345H570V470", 500, 330, "compensation"),
            (5, 3, "M660 515H830V155", 760, 338, "rejoin"),
        ),
    },
    "path-contract-drift": {
        "view_box": "0 0 1040 650",
        "nodes": (
            (20, 265, 160, 90, "entry"),
            (280, 90, 190, 85, "path-a"),
            (520, 90, 190, 85, "path-a"),
            (280, 445, 190, 85, "path-b"),
            (520, 445, 190, 85, "path-b"),
            (790, 265, 100, 90, "merge"),
            (930, 265, 100, 90, "outcome"),
        ),
        "edges": (
            (0, 1, "M180 290H220V132H280", 235, 225, "path-a"),
            (1, 2, "M470 132H520", 495, 70, "handoff"),
            (2, 5, "M710 132H750V290H790", 760, 220, "join"),
            (0, 3, "M180 330H220V487H280", 235, 425, "path-b"),
            (3, 4, "M470 487H520", 495, 425, "handoff"),
            (4, 5, "M710 487H750V330H790", 760, 425, "drift"),
            (5, 6, "M890 310H930", 910, 245, "outcome"),
        ),
    },
    "state-lifecycle": {
        "view_box": "0 0 960 650",
        "nodes": (
            (20, 245, 170, 90, "initial"),
            (270, 90, 190, 90, "state"),
            (700, 90, 230, 90, "state"),
            (700, 430, 230, 90, "terminal"),
            (270, 430, 190, 90, "retry"),
            (20, 430, 170, 90, "terminal"),
        ),
        "edges": (
            (0, 1, "M190 270H230V135H270", 230, 202, "start"),
            (1, 2, "M460 135H700", 580, 118, "transition"),
            (2, 3, "M815 180V430", 852, 305, "complete"),
            (2, 4, "M700 150H600V475H460", 585, 298, "retry"),
            (4, 1, "M365 430V180", 402, 305, "feedback"),
            (4, 5, "M270 475H190", 230, 410, "cutoff"),
        ),
    },
    "time-concurrency": {
        "view_box": "0 0 960 820",
        "participants": (
            (20, 18, 180, 67, "participant-a"),
            (270, 18, 180, 67, "participant-b"),
            (520, 18, 180, 67, "participant-c"),
            (770, 18, 180, 67, "participant-d"),
        ),
        "nodes": (
            (20, 120, 180, 88, "message-a"),
            (270, 235, 180, 88, "message-b"),
            (520, 350, 180, 88, "message-c"),
            (770, 465, 180, 88, "message-d"),
            (520, 580, 180, 88, "message-c"),
            (270, 695, 180, 88, "message-b"),
        ),
        "edges": (
            (0, 1, "M200 164H235V279H270", 330, 222, "call"),
            (1, 2, "M450 279H485V394H520", 580, 337, "interleave"),
            (2, 3, "M700 394H735V509H770", 830, 452, "call"),
            (3, 4, "M770 509H735V624H700", 735, 570, "return"),
            (4, 5, "M520 624H485V739H450", 485, 685, "late-return"),
            (5, 1, "M360 695V323", 410, 510, "overlap"),
        ),
    },
}


CODE_REVIEW_BASE_CSS = r"""
:root{--ink:#102033;--muted:#5a6c80;--paper:#fbfdff;--panel:#fff;--line:#8db3d8;--blue:#176fb3;--blue-soft:#eaf4ff;--green:#11815d;--green-soft:#eaf8f2;--amber:#a66a00;--amber-soft:#fff6df;--red:#ac3d46;--red-soft:#fff0f1;--violet:#6954be;--violet-soft:#f2efff;--shadow:0 16px 42px rgba(20,57,92,.1)}
*{box-sizing:border-box}html{color-scheme:light}body{margin:0;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",Arial,sans-serif;background:radial-gradient(circle at 18% 3%,rgba(214,233,255,.78),transparent 30rem),radial-gradient(circle at 78% 6%,rgba(228,246,239,.8),transparent 28rem),linear-gradient(rgba(93,133,173,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(93,133,173,.045) 1px,transparent 1px),linear-gradient(180deg,#fff 0%,#f7fbff 54%,#fbfdff 100%);background-size:auto,auto,28px 28px,28px 28px,auto;overflow-x:clip}
main{width:min(96rem,calc(100vw - 2rem));margin:0 auto;padding:1.4rem 0 4rem}h1{max-width:40ch;margin:0 0 .5rem;font-size:clamp(1.7rem,3vw,2.35rem);line-height:1.16;letter-spacing:-.025em}.summary{max-width:82ch;margin:0;color:var(--muted);font-size:.96rem;line-height:1.65}
.review-workspace{display:block;margin-top:1rem}.review-canvas>[data-diagram-reading-guide="1"]{margin:.75rem .75rem .35rem}.review-layout{display:grid;grid-template-columns:minmax(15rem,18rem) minmax(0,1fr);gap:1rem;margin-top:.85rem;align-items:start}
.review-finding-nav{position:sticky;top:.75rem;display:grid;grid-template-columns:1fr;gap:.5rem;max-block-size:calc(100vh - 1.5rem);padding:.65rem;overflow:auto;border:1px solid rgba(109,159,205,.58);border-radius:1rem;background:rgba(255,255,255,.95);box-shadow:var(--shadow)}.review-finding-tab{display:grid;grid-template-columns:auto minmax(0,1fr);inline-size:100%;min-inline-size:0;min-block-size:3.7rem;gap:.65rem;align-items:center;padding:.62rem .72rem;border:1px solid #c7d9ea;border-radius:.78rem;background:linear-gradient(180deg,#fff,#f7fbff);box-shadow:0 .12rem .35rem rgba(20,57,92,.06);color:#405a73;font:inherit;text-align:left;cursor:pointer;transition:border-color .16s ease,background-color .16s ease,box-shadow .16s ease,transform .16s ease}.review-finding-tab:hover{border-color:#8fb8dc;background:#f0f7fe;box-shadow:0 .22rem .55rem rgba(20,57,92,.11);transform:translateY(-1px)}.review-finding-tab[aria-selected="true"]{border-color:#3a83c3;background:#eaf4ff;box-shadow:inset .24rem 0 #176fb3,0 0 0 2px rgba(23,111,179,.13),0 .25rem .65rem rgba(20,57,92,.12);color:#174f7d}.review-severity{display:inline-grid;min-inline-size:2.25rem;min-block-size:2.1rem;place-items:center;border:1px solid #9ebbd4;border-radius:.5rem;background:#fff;color:#315c80;font-size:.76rem;font-weight:900}.review-finding-tab[aria-selected="true"] .review-severity{border-color:#5d97c8;background:#f8fcff;color:#0f5d98}.review-finding-copy{min-inline-size:0;font-size:.82rem;font-weight:850;line-height:1.35;overflow-wrap:anywhere}
.review-comparison{display:grid;grid-template-columns:minmax(0,1fr);gap:1.15rem;min-width:0;align-items:start}.review-active,.review-scenario{min-width:0;border:1px solid rgba(109,159,205,.58);border-radius:1rem;background:#fff;box-shadow:var(--shadow);overflow:hidden}.review-active[data-review-active-view="repair"]{border-color:rgba(124,105,190,.55)}.review-active-heading{padding:.8rem 1rem 1rem;border-bottom:1px solid #d9e6f1}.review-view-label,.review-scenario-label{display:flex;inline-size:100%;min-block-size:3rem;align-items:center;justify-content:center;margin:0 0 .75rem;padding:.58rem .85rem;border:1px solid #8fb8dc;border-radius:.72rem;background:var(--blue-soft);color:#165d95;font-size:1.08rem;font-weight:900;line-height:1.25;text-align:center}.review-active[data-review-active-view="repair"] .review-view-label{border-color:#b1a5dd;background:var(--violet-soft);color:#59459f}.review-active-heading h2{margin:0;font-size:1.12rem;line-height:1.3}.review-active-heading p{margin:.32rem 0 0;color:var(--muted);font-size:.86rem;line-height:1.55}
.review-scenario{border-color:rgba(196,122,74,.58);background:linear-gradient(180deg,#fff,#fffaf4)}.review-scenario-heading{padding:.8rem 1rem .25rem}.review-scenario-label{border-color:#e0b17f;background:#fff3e3;color:#8a4e13}.review-scenario-heading h2{margin:0;font-size:1.1rem;line-height:1.3}.review-scenario-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;padding:.75rem 1rem 1rem}.review-scenario-item{min-width:0;padding:.8rem .85rem;border:1px solid #ead3bc;border-radius:.75rem;background:#fff}.review-scenario-item h3{margin:0 0 .32rem;color:#8b4d10;font-size:.86rem}.review-scenario-item p{margin:0;color:#4e6073;font-size:.84rem;line-height:1.58;overflow-wrap:anywhere}
.review-canvas[data-diagram-canvas]{block-size:auto;max-block-size:none;border:0;border-radius:0;background:linear-gradient(rgba(42,105,159,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(42,105,159,.04) 1px,transparent 1px),linear-gradient(180deg,#fff,#f9fcff);background-size:24px 24px,24px 24px,auto;overflow:visible;overscroll-behavior:auto}.review-canvas [data-line-kind="line-01"] [data-line-swatch]::before{border-color:var(--blue);border-block-start-style:solid}.review-canvas [data-line-kind="line-01"] [data-line-swatch]::after{border-inline-start-color:var(--blue)}.review-canvas [data-line-kind="line-02"] [data-line-swatch]::before{border-color:var(--red);border-block-start-style:solid}.review-canvas [data-line-kind="line-02"] [data-line-swatch]::after{border-inline-start-color:var(--red)}.review-canvas [data-line-kind="line-03"] [data-line-swatch]::before{border-color:var(--amber);border-block-start-style:solid}.review-canvas [data-line-kind="line-03"] [data-line-swatch]::after{border-inline-start-color:var(--amber)}.review-canvas [data-line-kind="line-04"] [data-line-swatch]::before{border-color:var(--violet);border-block-start-style:dashed}.review-canvas [data-line-kind="line-04"] [data-line-swatch]::after{border-inline-start-color:var(--violet)}.review-canvas[data-diagram-canvas] [data-evidence-source-kind="file"]::before{border-color:#76a8d6;background:#fff}.review-canvas[data-diagram-canvas] [data-evidence-source-kind="test"]::before{border-color:#58a88e;background:var(--green-soft)}.review-canvas[data-diagram-canvas] [data-evidence-status="unresolved"]::before{border-color:#c58a24;border-style:solid;background:var(--amber-soft)}.review-graph{position:relative;display:block;inline-size:min(100%,65rem);min-inline-size:0;block-size:auto;min-block-size:0;aspect-ratio:960/650;margin-inline:auto;background:transparent}.review-graph[data-review-topology="cause-evidence"]{aspect-ratio:1040/520}.review-graph[data-review-topology="path-contract-drift"]{aspect-ratio:1040/650}.review-graph[data-review-topology="control-branch"]{aspect-ratio:960/740}.review-graph[data-review-topology="time-concurrency"]{aspect-ratio:960/820}.review-graph svg{display:block;inline-size:100%;block-size:100%}.review-route{fill:none;stroke:var(--blue);stroke-width:3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.review-route[data-relation-kind*="exception"],.review-route[data-relation-kind*="drift"],.review-route[data-relation-kind*="overlap"]{stroke:var(--red)}.review-route[data-relation-kind*="compensation"],.review-route[data-relation-kind*="cutoff"]{stroke:var(--amber)}.review-route[data-relation-kind*="feedback"],.review-route[data-relation-kind*="retry"]{stroke:var(--violet);stroke-dasharray:8 7}.review-node-shape{fill:#fff;stroke:#76a8d6;stroke-width:2;vector-effect:non-scaling-stroke}.review-node[data-node-theme="decision"] .review-node-shape,.review-node[data-node-theme="merge"] .review-node-shape{fill:var(--amber-soft);stroke:#c58a24}.review-node[data-node-theme="exception"] .review-node-shape{fill:var(--red-soft);stroke:#d47b7b}.review-node[data-node-theme="compensation"] .review-node-shape,.review-node[data-node-theme="retry"] .review-node-shape{fill:var(--violet-soft);stroke:#8d7bd4}.review-node[data-node-theme="outcome"] .review-node-shape,.review-node[data-node-theme="terminal"] .review-node-shape,.review-node[data-node-theme="verification"] .review-node-shape{fill:var(--green-soft);stroke:#58a88e}.review-node-copy{display:grid;height:100%;place-content:center;padding:.42rem .6rem;color:var(--ink);text-align:center;overflow:hidden}.review-node-copy b{font-size:1.05rem;line-height:1.18}.review-node-copy span{display:block;margin-top:.2rem;color:var(--muted);font-size:.76rem;line-height:1.3;overflow-wrap:anywhere}.review-graph[data-review-topology="path-contract-drift"] .review-node-copy,.review-graph[data-review-topology="time-concurrency"] .review-node-copy{padding:.2rem .4rem}.review-graph[data-review-topology="path-contract-drift"] .review-node-copy b,.review-graph[data-review-topology="time-concurrency"] .review-node-copy b{font-size:.98rem;line-height:1.15}.review-graph[data-review-topology="path-contract-drift"] .review-node-copy span,.review-graph[data-review-topology="time-concurrency"] .review-node-copy span{font-size:.72rem;line-height:1.2}.review-route-label{fill:#294963;stroke:#fff;stroke-width:8px;paint-order:stroke fill;font-size:16px;font-weight:850;text-anchor:middle;stroke-linejoin:round}.review-participant-shape{fill:#dceeff;stroke:#4f91c8;stroke-width:2;vector-effect:non-scaling-stroke}.review-participant:nth-of-type(even) .review-participant-shape{fill:#e8f7f1;stroke:#4a9c7e}.review-participant-copy{display:grid;height:100%;place-content:center;padding:.25rem .5rem;text-align:center;overflow:hidden}.review-participant-copy b{font-size:1rem;line-height:1.15}.review-participant-copy span{display:block;margin-top:.15rem;color:#415e76;font-size:.72rem;line-height:1.2;overflow-wrap:anywhere}.semantic-relation{position:absolute;inline-size:1px;block-size:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.review-static-fallback{display:grid;gap:1rem}.review-fallback-finding{padding:1rem;border:1px solid rgba(109,159,205,.58);border-radius:1rem;background:#fff}.review-fallback-finding>h2{margin:0 0 .25rem;font-size:1.1rem}.review-fallback-finding>p{margin:0 0 .8rem;color:var(--muted);line-height:1.5}.review-fallback-view,.review-fallback-scenario{margin-top:.9rem;padding-top:.9rem;border-top:1px solid #d9e6f1}.review-fallback-view>h3,.review-fallback-scenario>h3{margin:0 0 .2rem;font-size:.98rem}.review-fallback-view>p,.review-fallback-scenario>p{margin:0 0 .65rem;color:var(--muted);font-size:.82rem}.review-fallback-scenario dl{display:grid;grid-template-columns:auto minmax(0,1fr);gap:.35rem .75rem;margin:.65rem 0 0}.review-fallback-scenario dt{font-weight:850}.review-fallback-scenario dd{margin:0;color:var(--muted)}.review-fallback-graph{overflow-x:auto;border:1px solid #d9e6f1;border-radius:.8rem}.review-fallback-graph .review-graph{transform-origin:0 0}
.review-enhanced .review-static-fallback{display:none}html:not(.review-enhanced) .review-layout{display:none}
.review-finding-tab:focus-visible{outline:3px solid #0877ff;outline-offset:2px}
@media(max-width:72rem){main{width:min(100vw - 1rem,72rem);padding-top:.75rem}.review-layout{grid-template-columns:1fr}.review-finding-nav{position:static;grid-template-columns:repeat(2,minmax(0,1fr));max-block-size:none}}
@media(max-width:48rem){.review-finding-nav,.review-scenario-grid{grid-template-columns:1fr}}
@media(max-width:40rem){.review-active-heading,.review-scenario-heading{padding:.65rem .7rem .8rem}.review-view-label,.review-scenario-label{font-size:.98rem}.review-scenario-grid{padding:.7rem}.review-canvas[data-diagram-mobile="summary"]>[data-diagram-stage]{min-inline-size:0!important}}
@media(prefers-reduced-motion:reduce){.review-finding-tab{transition:none}.review-finding-tab:hover{transform:none}}
@media print{body{background:#fff}.review-layout{display:none!important}.review-static-fallback{display:grid!important}.review-workspace{display:block}.review-fallback-finding{break-before:page;box-shadow:none}.review-fallback-finding:first-child{break-before:auto}.review-fallback-graph{overflow:visible}.review-fallback-graph .review-graph{inline-size:100%;min-inline-size:0;block-size:auto;min-block-size:0}.review-fallback-graph svg{block-size:auto}}
"""


CODE_REVIEW_RUNTIME = r"""
(() => {
  "use strict";
  const root = document.querySelector('[data-code-review-package="1"]');
  if (!root) return;
  document.documentElement.classList.add("review-enhanced");
  const artifact = root.closest("main") || document;
  const canvases = {
    current: root.querySelector('[data-diagram-id="code-review-current"]'),
    repair: root.querySelector('[data-diagram-id="code-review-repair"]')
  };
  const headings = {
    current: {
      type: root.querySelector("[data-review-current-title] [data-diagram-view-type]"),
      subject: root.querySelector("[data-review-current-title] [data-diagram-view-subject]"),
      summary: root.querySelector("[data-review-current-summary]")
    },
    repair: {
      type: root.querySelector("[data-review-repair-title] [data-diagram-view-type]"),
      subject: root.querySelector("[data-review-repair-title] [data-diagram-view-subject]"),
      summary: root.querySelector("[data-review-repair-summary]")
    }
  };
  const scenario = {
    title: root.querySelector("[data-review-scenario-title]"),
    trigger: root.querySelector("[data-review-scenario-trigger]"),
    process: root.querySelector("[data-review-scenario-process]"),
    impact: root.querySelector("[data-review-scenario-impact]")
  };
  const controls = artifact.querySelector('[data-diagram-controls="code-review-pair"]');
  const titleControls = controls?.closest("[data-artifact-shell-controls]");
  const comparison = root.querySelector("[data-review-comparison]");
  const findingTabs = Array.from(root.querySelectorAll("[data-review-finding-tab]"));
  let findingId = findingTabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.reviewFindingTab || "";
  let requestedZoom = controls?.querySelector(
    '[data-diagram-zoom-control][aria-pressed="true"]'
  )?.dataset.diagramZoomControl || "fit";
  let resizeFrame = 0;
  const definitions = () => Array.from(root.querySelectorAll("template[data-review-definition]"));
  const definitionFor = (id) => definitions().find((entry) => entry.dataset.reviewDefinition === id);

  const reflectZoom = (requested, applied, visible, overflow) => {
    if (!controls) return;
    controls.hidden = !visible;
    controls.dataset.diagramControlsVisible = String(visible);
    controls.dataset.diagramOverflow = String(overflow);
    if (titleControls) {
      titleControls.dataset.controlsState = visible ? "active" : "empty";
    }
    controls.querySelectorAll("[data-diagram-zoom-control]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.diagramZoomControl === requested && applied)
      );
    });
    const status = controls.querySelector("[data-diagram-zoom-status]");
    if (!status) return;
    const message = !visible
      ? controls.dataset.diagramStatusFits || "Fits at 100%"
      : applied
      ? (
        requested === "fit"
          ? controls.dataset.diagramStatusFit || "Fit width"
          : `${Number(requested) * 100}%`
      )
      : controls.dataset.diagramStatusScroll || "Scroll";
    status.textContent = message;
    if ("value" in status) status.value = message;
  };

  const applySharedZoom = () => {
    const viewport = globalThis.VibeDiagramViewport;
    if (!viewport) return false;
    const measurements = Object.values(canvases).map((canvas) => {
      const stage = canvas?.querySelector(":scope > [data-diagram-stage]");
      return {
        canvas,
        stage,
        overflow: Boolean(canvas && stage && stage.scrollWidth > canvas.clientWidth + 1)
      };
    });
    const controlsVisible = measurements.every((item) => item.canvas && item.stage);
    const overflow = measurements.some((item) => item.overflow);
    const effectiveZoom = requestedZoom;
    const results = measurements.map(({ canvas, stage }) => {
      const applied = Boolean(canvas && viewport.apply(canvas, effectiveZoom));
      const scale = Number.parseFloat(
        getComputedStyle(canvas).getPropertyValue("--diagram-scale") || "1"
      );
      const horizontalFit = Boolean(
        applied &&
        stage &&
        Number.isFinite(scale) &&
        stage.scrollWidth * scale <= canvas.clientWidth + 1
      );
      if (canvas) canvas.dataset.reviewHorizontalFit = String(horizontalFit);
      return applied;
    });
    const applied = results.length === 2 && results.every(Boolean);
    reflectZoom(effectiveZoom, applied, controlsVisible, overflow);
    return applied;
  };

  const render = () => {
    const definition = definitionFor(findingId);
    if (!definition) return;
    const scenarioDefinition = definition.content.querySelector(
      '[data-review-scenario-definition="1"]'
    );
    for (const viewId of ["current", "repair"]) {
      const view = definition.content.querySelector(`[data-review-view="${viewId}"]`);
      const source = view?.querySelector("[data-review-graph]");
      const currentStage = canvases[viewId]?.querySelector("[data-diagram-stage]");
      if (!view || !source || !currentStage) return;
      currentStage.replaceWith(source.cloneNode(true));
      if (headings[viewId].type) headings[viewId].type.textContent = view.dataset.reviewType || "";
      if (headings[viewId].subject) headings[viewId].subject.textContent = view.dataset.reviewTitle || "";
      if (headings[viewId].summary) {
        headings[viewId].summary.textContent = view.dataset.reviewSummary || "";
      }
    }
    if (!scenarioDefinition) return;
    for (const key of ["title", "trigger", "process", "impact"]) {
      if (scenario[key]) {
        const datasetKey = `reviewScenario${key[0].toUpperCase()}${key.slice(1)}`;
        scenario[key].textContent = scenarioDefinition.dataset[datasetKey] || "";
      }
    }
    findingTabs.forEach((tab) => {
      const selected = tab.dataset.reviewFindingTab === findingId;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && comparison) comparison.setAttribute("aria-labelledby", tab.id);
    });
    requestAnimationFrame(() => {
      applySharedZoom();
      globalThis.VibeDiagramQuality?.auditAll?.();
    });
  };
  const move = (tabs, current, key) => {
    let index = tabs.indexOf(current);
    if (key === "Home") index = 0;
    else if (key === "End") index = tabs.length - 1;
    else if (key === "ArrowRight" || key === "ArrowDown") index = (index + 1) % tabs.length;
    else if (key === "ArrowLeft" || key === "ArrowUp") index = (index - 1 + tabs.length) % tabs.length;
    else return false;
    tabs[index].click();
    tabs[index].focus({ preventScroll: true });
    return true;
  };
  findingTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      findingId = tab.dataset.reviewFindingTab || findingId;
      render();
    });
    tab.addEventListener("keydown", (event) => {
      if (move(findingTabs, tab, event.key)) event.preventDefault();
    });
  });
  controls?.addEventListener("click", (event) => {
    const target = event.target instanceof Element
      ? event.target.closest("[data-diagram-zoom-control]")
      : null;
    if (!target || !controls.contains(target)) return;
    requestedZoom = target.dataset.diagramZoomControl || "fit";
    applySharedZoom();
  });
  globalThis.addEventListener("resize", () => {
    if (resizeFrame) cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = 0;
      applySharedZoom();
    });
  }, { passive: true });
  render();
})();
"""


def _escape(value: Any) -> str:
    return html_lib.escape(str(value), quote=True)


def _canonical_template(family: str, template_id: str) -> Path:
    if IDENTITY_RE.fullmatch(family) is None or IDENTITY_RE.fullmatch(template_id) is None:
        raise ValueError("family and template must be lowercase hyphenated identifiers")
    path = TEMPLATE_ROOT / family / f"{template_id}.html"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unknown canonical template: {family}/{template_id}")
    if path.parent.parent != TEMPLATE_ROOT or path.parent.name != family:
        raise ValueError("canonical template path escaped the template root")
    return path


def _load_routing_contract() -> Dict[str, Any]:
    routing = json.loads(TEMPLATE_ROUTING_PATH.read_text(encoding="utf-8"))
    if set(routing) != {"schema_version", "code_review_routes", "families"}:
        raise ValueError("template routing contract has an invalid root schema")
    if type(routing["schema_version"]) is not int or routing["schema_version"] != 2:
        raise ValueError("template routing schema_version must be integer 2")
    routes = routing["code_review_routes"]
    if not isinstance(routes, dict) or set(routes) != set(CODE_REVIEW_TOPOLOGIES):
        raise ValueError("code-review routes must cover the exact supported review kinds")
    for kind, route in routes.items():
        if not isinstance(route, dict) or set(route) != {
            "family",
            "template",
            "primary_relation",
        }:
            raise ValueError(f"code-review route is invalid: {kind}")
        family = route["family"]
        template = route["template"]
        definition = routing["families"].get(family)
        if (
            not isinstance(family, str)
            or not isinstance(template, str)
            or not isinstance(route["primary_relation"], str)
            or not route["primary_relation"].strip()
            or not isinstance(definition, dict)
            or template not in definition.get("ready_templates", [])
        ):
            raise ValueError(f"code-review route target is not ready: {kind}")
    return routing


def _require_ready_template(family: str, template_id: str) -> None:
    if family in DEPRECATED_FAMILIES:
        raise ValueError(f"{family} is {DEPRECATED_FAMILIES[family]}")
    deprecation = DEPRECATED_TEMPLATES.get((family, template_id))
    if deprecation:
        raise ValueError(f"{family}/{template_id} is {deprecation}")
    routing = _load_routing_contract()
    definition = routing.get("families", {}).get(family)
    if not isinstance(definition, dict):
        raise ValueError(f"diagram family is not routed: {family}")
    ready = definition.get("ready_templates")
    default_template = definition.get("default_template")
    if (
        not isinstance(ready, list)
        or not isinstance(default_template, str)
        or template_id not in ready
    ):
        raise ValueError(
            f"template is blocked until its true-diagram migration is complete: "
            f"{family}/{template_id}; ready default: {default_template}"
        )


def _require_supported_standard(standard: str) -> None:
    normalized = standard.strip().lower()
    if normalized != NATIVE_STANDARD:
        raise ValueError(
            f'strict standard "{standard}" is not implemented by the canonical template catalog; '
            "refusing to substitute a Vibe Diagram native template"
        )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_review_view(
    value: Any,
    label: str,
    expected_nodes: int,
    expected_relations: int,
    expected_participants: int,
) -> Dict[str, Any]:
    expected_fields = {
        "title",
        "summary",
        "nodes",
        "relations",
    }
    if expected_participants:
        expected_fields.add("participants")
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValueError(f"{label} has an invalid field set")
    nodes = value["nodes"]
    relations = value["relations"]
    participants = value.get("participants", [])
    if not isinstance(nodes, list) or len(nodes) != expected_nodes:
        raise ValueError(f"{label}.nodes must contain exactly {expected_nodes} entries")
    if not isinstance(relations, list) or len(relations) != expected_relations:
        raise ValueError(
            f"{label}.relations must contain exactly {expected_relations} labels"
        )
    if not isinstance(participants, list) or len(participants) != expected_participants:
        raise ValueError(
            f"{label}.participants must contain exactly {expected_participants} entries"
        )
    normalized_nodes: List[Dict[str, str]] = []
    for index, node in enumerate(nodes, start=1):
        if not isinstance(node, dict) or set(node) != {"title", "detail"}:
            raise ValueError(f"{label}.nodes[{index}] has an invalid field set")
        normalized_nodes.append(
            {
                "title": _text(node["title"], f"{label}.nodes[{index}].title"),
                "detail": _text(node["detail"], f"{label}.nodes[{index}].detail"),
            }
        )
    normalized_participants: List[Dict[str, str]] = []
    for index, participant in enumerate(participants, start=1):
        if not isinstance(participant, dict) or set(participant) != {"title", "detail"}:
            raise ValueError(f"{label}.participants[{index}] has an invalid field set")
        normalized_participants.append(
            {
                "title": _text(
                    participant["title"],
                    f"{label}.participants[{index}].title",
                ),
                "detail": _text(
                    participant["detail"],
                    f"{label}.participants[{index}].detail",
                ),
            }
        )
    normalized_title = _text(value["title"], f"{label}.title")
    _review_title_parts(normalized_title)
    return {
        "title": normalized_title,
        "summary": _text(value["summary"], f"{label}.summary"),
        "participants": normalized_participants,
        "nodes": normalized_nodes,
        "relations": [
            _text(relation, f"{label}.relations[{index}]")
            for index, relation in enumerate(relations, start=1)
        ],
    }


def _validate_review_scenario(value: Any, label: str) -> Dict[str, str]:
    expected_fields = {"title", "trigger", "process", "impact"}
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValueError(f"{label} has an invalid field set")
    return {
        key: _text(value[key], f"{label}.{key}")
        for key in ("title", "trigger", "process", "impact")
    }


def _validate_review_spec(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "lang",
        "title",
        "summary",
        "guide",
        "findings",
    }:
        raise ValueError("review spec has an invalid root field set")
    guide = value["guide"]
    if not isinstance(guide, dict) or set(guide) != {
        "line_labels",
        "interaction",
        "observed_source",
        "checked_source",
        "unresolved_source",
        "current_tab",
        "repair_tab",
        "scenario_label",
        "scenario_trigger_label",
        "scenario_process_label",
        "scenario_impact_label",
        "finding_nav_label",
        "view_nav_label",
        "reading_guide_label",
        "line_types_label",
        "evidence_states_label",
        "observed_label",
        "checked_label",
        "unresolved_label",
        "interaction_label",
        "scale_controls_label",
        "zoom_controls_label",
        "auto_label",
        "fit_label",
        "fits_label",
        "scroll_label",
        "fallback_label",
    }:
        raise ValueError("review spec guide has an invalid field set")
    language_tag = _text(value["lang"], "lang")
    if LANGUAGE_TAG_RE.fullmatch(language_tag) is None:
        raise ValueError("review spec lang must be a valid BCP 47 language tag")
    page_title = _text(value["title"], "title")
    if "{{" not in page_title:
        title_parts = [part.strip() for part in page_title.split("｜")]
        if len(title_parts) != 2 or not all(title_parts):
            raise ValueError(
                "review spec title must use the “code review｜title description” format"
            )
    line_labels = guide["line_labels"]
    if not isinstance(line_labels, list) or len(line_labels) != 4:
        raise ValueError("review spec guide.line_labels must contain four entries")
    findings = value["findings"]
    if (
        not isinstance(findings, list)
        or not findings
        or len(findings) > CODE_REVIEW_FINDING_LIMIT
    ):
        raise ValueError(
            f"review spec findings must contain 1 to {CODE_REVIEW_FINDING_LIMIT} entries"
        )
    routing = _load_routing_contract()
    normalized_findings: List[Dict[str, Any]] = []
    seen_ids = set()
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict) or set(finding) != {
            "id",
            "severity",
            "title",
            "summary",
            "kind",
            "current",
            "scenario",
            "repair",
        }:
            raise ValueError(f"findings[{index}] has an invalid field set")
        finding_id = _text(finding["id"], f"findings[{index}].id")
        if IDENTITY_RE.fullmatch(finding_id) is None or finding_id in seen_ids:
            raise ValueError(f"findings[{index}].id must be a unique hyphenated identifier")
        seen_ids.add(finding_id)
        kind = _text(finding["kind"], f"findings[{index}].kind")
        if kind not in CODE_REVIEW_TOPOLOGIES or kind not in routing["code_review_routes"]:
            raise ValueError(
                f'findings[{index}].kind "{kind}" is unresolved; request an explicit '
                "primary-relation choice instead of using a fallback"
            )
        topology = CODE_REVIEW_TOPOLOGIES[kind]
        node_count = len(topology["nodes"])
        relation_count = len(topology["edges"])
        participant_count = len(topology.get("participants", ()))
        normalized_findings.append(
            {
                "id": finding_id,
                "severity": _text(finding["severity"], f"findings[{index}].severity"),
                "title": _text(finding["title"], f"findings[{index}].title"),
                "summary": _text(finding["summary"], f"findings[{index}].summary"),
                "kind": kind,
                "route": dict(routing["code_review_routes"][kind]),
                "current": _validate_review_view(
                    finding["current"],
                    f"findings[{index}].current",
                    node_count,
                    relation_count,
                    participant_count,
                ),
                "scenario": _validate_review_scenario(
                    finding["scenario"],
                    f"findings[{index}].scenario",
                ),
                "repair": _validate_review_view(
                    finding["repair"],
                    f"findings[{index}].repair",
                    node_count,
                    relation_count,
                    participant_count,
                ),
            }
        )
    return {
        "lang": language_tag,
        "title": page_title,
        "summary": _text(value["summary"], "summary"),
        "guide": {
            "line_labels": [
                _text(label, f"guide.line_labels[{index}]")
                for index, label in enumerate(line_labels, start=1)
            ],
            **{
                key: _text(guide[key], f"guide.{key}")
                for key in (
                    "interaction",
                    "observed_source",
                    "checked_source",
                    "unresolved_source",
                    "current_tab",
                    "repair_tab",
                    "scenario_label",
                    "scenario_trigger_label",
                    "scenario_process_label",
                    "scenario_impact_label",
                    "finding_nav_label",
                    "view_nav_label",
                    "reading_guide_label",
                    "line_types_label",
                    "evidence_states_label",
                    "observed_label",
                    "checked_label",
                    "unresolved_label",
                    "interaction_label",
                    "scale_controls_label",
                    "zoom_controls_label",
                    "auto_label",
                    "fit_label",
                    "fits_label",
                    "scroll_label",
                    "fallback_label",
                )
            },
        },
        "findings": normalized_findings,
    }


def _topology_decor(kind: str) -> str:
    if kind == "time-concurrency":
        return (
            '<g class="review-lifelines" aria-hidden="true" opacity=".72">'
            '<path d="M110 85V808M360 85V808M610 85V808M860 85V808" '
            'stroke="#b8cde1" stroke-width="2" stroke-dasharray="8 8"></path></g>'
        )
    if kind == "path-contract-drift":
        return (
            '<g aria-hidden="true"><rect x="250" y="45" width="490" height="175" rx="18" '
            'fill="#eef6ff" stroke="#9fc1df"></rect><rect x="250" y="400" width="490" '
            'height="175" rx="18" fill="#fff4f4" stroke="#dfaaaa"></rect></g>'
        )
    if kind == "architecture-boundary":
        return (
            '<g aria-hidden="true"><rect x="15" y="30" width="930" height="580" rx="24" '
            'fill="none" stroke="#9fc1df" stroke-width="2" stroke-dasharray="10 8"></rect></g>'
        )
    return ""


def _review_title_parts(value: str) -> Tuple[str, str]:
    parts = [part.strip() for part in value.split("｜", 1)]
    if len(parts) != 2 or not all(parts):
        raise ValueError("review diagram titles must use the diagram type｜title format")
    return parts[0], parts[1]


def _render_review_graph(
    *,
    finding_index: int,
    view_index: int,
    kind: str,
    view: Mapping[str, Any],
    instance: str,
    stage_attribute: str,
) -> str:
    topology = CODE_REVIEW_TOPOLOGIES[kind]
    base = (finding_index - 1) * 40 + view_index * 20
    marker_id = f"review-arrow-{finding_index:02d}-{view_index}-{instance}"
    participant_markup: List[str] = []
    for offset, ((x, y, width, height, role), participant) in enumerate(
        zip(topology.get("participants", ()), view.get("participants", [])),
        start=1,
    ):
        participant_id = f"layout-participant-{base + offset:03d}"
        slot_id = f"layout-slot-{base + 10 + offset:03d}"
        participant_markup.append(
            f'<g class="review-participant" data-sequence-participant="1" '
            f'data-participant-id="{participant_id}" '
            f'data-participant-role="{_escape(role)}" '
            f'data-participant-x="{x}" data-participant-y="{y}" '
            f'data-participant-width="{width}" data-participant-height="{height}">'
            f'<rect class="review-participant-shape" x="{x}" y="{y}" width="{width}" '
            f'height="{height}" rx="13"></rect>'
            f'<foreignObject x="{x + 5}" y="{y + 5}" width="{width - 10}" '
            f'height="{height - 10}"><div class="review-participant-copy">'
            f'<b data-slot="{slot_id}">{_escape(participant["title"])}</b>'
            f'<span>{_escape(participant["detail"])}</span></div></foreignObject></g>'
        )
    node_markup: List[str] = []
    for offset, ((x, y, width, height, theme), node) in enumerate(
        zip(topology["nodes"], view["nodes"]),
        start=1,
    ):
        node_id = f"layout-node-{base + offset:03d}"
        slot_id = f"layout-slot-{base + offset:03d}"
        node_markup.append(
            f'<g class="review-node" data-node-theme="{_escape(theme)}" '
            f'data-diagram-node-id="{node_id}" data-semantic-role="{_escape(theme)}" '
            f'data-node-primary-label="{_escape(node["title"])}">'
            f'<rect class="review-node-shape" x="{x}" y="{y}" width="{width}" '
            f'height="{height}" rx="14"></rect>'
            f'<foreignObject x="{x + 6}" y="{y + 6}" width="{width - 12}" '
            f'height="{height - 12}"><div class="review-node-copy">'
            f'<b data-slot="{slot_id}">{_escape(node["title"])}</b>'
            f'<span>{_escape(node["detail"])}</span></div></foreignObject></g>'
        )
    route_markup: List[str] = []
    semantic_markup: List[str] = []
    for offset, (edge, label) in enumerate(zip(topology["edges"], view["relations"]), start=1):
        source, target, path_data, label_x, label_y, relation_kind = edge
        relation_id = f"layout-relation-{base + offset:03d}"
        source_id = f"layout-node-{base + source + 1:03d}"
        target_id = f"layout-node-{base + target + 1:03d}"
        route_markup.append(
            f'<path class="review-route" d="{path_data}" marker-end="url(#{marker_id})" '
            f'data-diagram-visible-relation-id="{relation_id}" data-from="{source_id}" '
            f'data-to="{target_id}" data-relation-kind="{_escape(relation_kind)}"></path>'
            f'<text class="review-route-label" x="{label_x}" y="{label_y}" '
            f'data-route-label-for="{relation_id}">{_escape(label)}</text>'
        )
        semantic_markup.append(
            f'<span class="semantic-relation" data-diagram-relation-id="{relation_id}" '
            f'data-from="{source_id}" data-to="{target_id}" '
            f'data-relation-kind="{_escape(relation_kind)}" '
            f'data-semantic="{_escape(label)}">{_escape(label)}</span>'
        )
    stage_marker = stage_attribute if stage_attribute else "data-review-fallback-graph"
    return (
        f'<section {stage_marker} data-review-graph class="review-graph" '
        f'data-review-topology="{_escape(kind)}" aria-label="{_escape(view["title"])}">'
        f'<svg viewBox="{topology["view_box"]}" role="img" '
        f'aria-label="{_escape(view["title"])}"><defs><marker id="{marker_id}" '
        'viewBox="0 0 10 10" refX="9" refY="5" markerWidth="11" markerHeight="11" '
        'markerUnits="userSpaceOnUse" orient="auto"><path d="M1 1L9 5L1 9Z" '
        'fill="context-stroke"></path></marker></defs>'
        + _topology_decor(kind)
        + "".join(route_markup)
        + "".join(participant_markup)
        + "".join(node_markup)
        + "</svg>"
        + "".join(semantic_markup)
        + "</section>"
    )


def _render_review_definition(finding: Mapping[str, Any], index: int) -> str:
    route = finding["route"]
    views = []
    for view_index, view_id in enumerate(("current", "repair")):
        view = finding[view_id]
        title_type, visible_title = _review_title_parts(view["title"])
        graph = _render_review_graph(
            finding_index=index,
            view_index=view_index,
            kind=finding["kind"],
            view=view,
            instance="definition",
            stage_attribute="data-diagram-stage",
        )
        views.append(
            f'<section data-review-view="{view_id}" '
            f'data-review-type="{_escape(title_type)}" '
            f'data-review-title="{_escape(visible_title)}" '
            f'data-review-diagram-title="{_escape(view["title"])}" '
            f'data-review-summary="{_escape(view["summary"])}" '
            f'data-reuse-family="{_escape(route["family"])}" '
            f'data-reuse-template="{_escape(route["template"])}" '
            f'data-review-topology="{_escape(finding["kind"])}">{graph}</section>'
        )
        if view_id == "current":
            scenario = finding["scenario"]
            views.append(
                '<section data-review-scenario-definition="1" '
                f'data-review-scenario-title="{_escape(scenario["title"])}" '
                f'data-review-scenario-trigger="{_escape(scenario["trigger"])}" '
                f'data-review-scenario-process="{_escape(scenario["process"])}" '
                f'data-review-scenario-impact="{_escape(scenario["impact"])}"></section>'
            )
    return (
        f'<template data-review-definition="{_escape(finding["id"])}" '
        f'data-review-kind="{_escape(finding["kind"])}" '
        f'data-review-route-family="{_escape(route["family"])}" '
        f'data-review-route-template="{_escape(route["template"])}">'
        + "".join(views)
        + "</template>"
    )


def _render_review_fallback(
    finding: Mapping[str, Any],
    index: int,
    guide: Mapping[str, str],
) -> str:
    route = finding["route"]
    views = []
    for view_index, view_id in enumerate(("current", "repair")):
        view = finding[view_id]
        title_type, visible_title = _review_title_parts(view["title"])
        graph = _render_review_graph(
            finding_index=index,
            view_index=view_index,
            kind=finding["kind"],
            view=view,
            instance="fallback",
            stage_attribute="",
        )
        views.append(
            f'<section class="review-fallback-view" data-review-fallback-view="{view_id}" '
            f'data-reuse-family="{_escape(route["family"])}" '
            f'data-reuse-template="{_escape(route["template"])}" '
            f'data-review-topology="{_escape(finding["kind"])}">'
            f'<h3>{_escape(title_type)}｜{_escape(visible_title)}</h3><p>{_escape(view["summary"])}</p>'
            f'<div class="review-fallback-graph">{graph}</div></section>'
        )
        if view_id == "current":
            scenario = finding["scenario"]
            views.append(
                '<section class="review-fallback-scenario" '
                'data-review-fallback-scenario="1">'
                f'<h3>{_escape(scenario["title"])}</h3>'
                '<dl>'
                f'<dt>{_escape(guide["scenario_trigger_label"])}</dt>'
                f'<dd>{_escape(scenario["trigger"])}</dd>'
                f'<dt>{_escape(guide["scenario_process_label"])}</dt>'
                f'<dd>{_escape(scenario["process"])}</dd>'
                f'<dt>{_escape(guide["scenario_impact_label"])}</dt>'
                f'<dd>{_escape(scenario["impact"])}</dd>'
                '</dl></section>'
            )
    return (
        f'<article class="review-fallback-finding" '
        f'data-review-fallback-finding="{_escape(finding["id"])}">'
        f'<h2>{_escape(finding["title"])}</h2><p>{_escape(finding["summary"])}</p>'
        + "".join(views)
        + "</article>"
    )


def _kernel(path: str) -> str:
    return (SKILL_ROOT / "assets" / "contracts" / path).read_text(encoding="utf-8").rstrip()


def _render_code_review_package(spec: Mapping[str, Any]) -> str:
    normalized = _validate_review_spec(spec)
    guide = normalized["guide"]
    findings = normalized["findings"]
    first = findings[0]
    first_current = first["current"]
    first_scenario = first["scenario"]
    first_repair = first["repair"]
    nav = "".join(
        f'<button type="button" class="review-finding-tab" role="tab" '
        f'id="review-{_escape(finding["id"])}-tab" '
        f'data-review-finding-tab="{_escape(finding["id"])}" '
        f'aria-controls="code-review-comparison" '
        f'aria-selected="{"true" if index == 1 else "false"}" '
        f'tabindex="{"0" if index == 1 else "-1"}">'
        f'<span class="review-severity">{_escape(finding["severity"])}</span>'
        f'<span class="review-finding-copy">{_escape(finding["title"])}</span></button>'
        for index, finding in enumerate(findings, start=1)
    )
    definitions = "".join(
        _render_review_definition(finding, index)
        for index, finding in enumerate(findings, start=1)
    )
    fallbacks = "".join(
        _render_review_fallback(finding, index, guide)
        for index, finding in enumerate(findings, start=1)
    )
    current_graph = _render_review_graph(
        finding_index=1,
        view_index=0,
        kind=first["kind"],
        view=first_current,
        instance="active-current",
        stage_attribute="data-diagram-stage",
    )
    repair_graph = _render_review_graph(
        finding_index=1,
        view_index=1,
        kind=first["kind"],
        view=first_repair,
        instance="active-repair",
        stage_attribute="data-diagram-stage",
    )
    observed_for = " ".join(
        f"layout-node-{(index - 1) * 40 + 1:03d}"
        for index in range(1, len(findings) + 1)
    )

    def local_guide(canvas_id: str, suffix: str) -> str:
        return f"""<section data-slot="evidence-and-notes" data-evidence-ledger="1" data-diagram-reading-guide="1" data-reading-guide-for="{canvas_id}" aria-label="__READING_GUIDE_LABEL__">
      <div data-reading-guide-groups>
        <div data-reading-guide-group="relations"><span data-reading-guide-group-title>__LINE_TYPES_LABEL__</span><span data-reading-guide-item data-line-kind="line-01"><i data-line-swatch aria-hidden="true"></i><b>__LINE_1__</b></span><span data-reading-guide-item data-line-kind="line-02"><i data-line-swatch aria-hidden="true"></i><b>__LINE_2__</b></span><span data-reading-guide-item data-line-kind="line-03"><i data-line-swatch aria-hidden="true"></i><b>__LINE_3__</b></span><span data-reading-guide-item data-line-kind="line-04"><i data-line-swatch aria-hidden="true"></i><b>__LINE_4__</b></span></div>
        <div data-reading-guide-group="evidence"><span data-reading-guide-group-title>__EVIDENCE_STATES_LABEL__</span><article data-evidence-id="evidence-observed-{suffix}" data-evidence-status="observed" data-evidence-for="__OBSERVED_FOR__" data-evidence-source-kind="file" data-evidence-source="__OBSERVED_SOURCE__"><b>__OBSERVED_LABEL__</b></article><article data-evidence-id="evidence-check-{suffix}" data-evidence-status="observed" data-evidence-for="__OBSERVED_FOR__" data-evidence-source-kind="test" data-evidence-source="__CHECKED_SOURCE__"><b>__CHECKED_LABEL__</b></article><article data-evidence-id="evidence-unresolved-{suffix}" data-evidence-status="unresolved" data-evidence-for="__OBSERVED_FOR__" data-evidence-source-kind="runtime" data-evidence-source="__UNRESOLVED_SOURCE__"><b>__UNRESOLVED_LABEL__</b></article></div>
      </div>
    </section>"""

    current_guide = local_guide("code-review-current", "current")
    repair_guide = local_guide("code-review-repair", "repair")
    shell_css = _kernel("artifact-shell/v1.css")
    shell_js = _kernel("artifact-shell/v1.js")
    adaptive_css = _kernel("adaptive-viewport/v1.css")
    adaptive_js = _kernel("adaptive-viewport/v1.js")
    semantic_css = _kernel("semantic-relations/v1.css")
    document = """<!doctype html>
<html lang="__LANG__">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__PAGE_TITLE__</title>
  <style>__BASE_CSS__</style>
  <style data-artifact-shell-kernel="1">
__SHELL_CSS__
</style>
  <style data-adaptive-viewport-kernel="1">
__ADAPTIVE_CSS__
</style>
  <style data-semantic-relations-kernel="1">
__SEMANTIC_CSS__
</style>
</head>
<body>
<main data-diagram-type="code-review" data-template-family="code-review" data-template-id="code-review-package" data-template-layout="code-review-package" data-template-contract-version="2">
  <header data-diagram-title-region data-artifact-shell-title="1">
    <div data-diagram-title-copy><h1 data-slot="title">__TITLE__</h1><p class="summary" data-slot="summary">__SUMMARY__</p></div>
    <div data-artifact-shell-controls aria-label="__SCALE_CONTROLS_LABEL__"><div data-diagram-controls="code-review-pair" aria-label="__ZOOM_CONTROLS_LABEL__" data-diagram-status-fit="__FIT_LABEL__" data-diagram-status-fits="__FITS_LABEL__" data-diagram-status-scroll="__SCROLL_LABEL__"><button type="button" data-diagram-zoom-control="0.75" aria-pressed="false">75%</button><button type="button" data-diagram-zoom-control="0.9" aria-pressed="false">90%</button><button type="button" data-diagram-zoom-control="1" aria-pressed="false">100%</button><button type="button" data-diagram-zoom-control="fit" aria-pressed="true">__AUTO_LABEL__</button><output data-diagram-zoom-status aria-live="polite">__FIT_LABEL__</output></div></div>
  </header>
  <section class="review-workspace template-layout" data-code-review-package="1" data-diagram-composition-root="code-review-package">
    <div class="review-layout">
      <nav class="review-finding-nav" role="tablist" aria-label="__FINDING_NAV_LABEL__">__FINDING_NAV__</nav>
      <section id="code-review-comparison" class="review-comparison" data-review-comparison role="tabpanel" tabindex="0" aria-label="__VIEW_NAV_LABEL__" aria-labelledby="review-__FIRST_FINDING_ID__-tab" data-diagram-control-scope="primary" data-sequence-id="code-review-pair">
        <article class="review-active" data-review-active-view="current">
          <header class="review-active-heading"><span class="review-view-label">__CURRENT_TAB__</span><h2 data-review-current-title data-diagram-view-title="1"><span data-diagram-view-type>__CURRENT_TYPE__</span><span data-diagram-view-separator aria-hidden="true"></span><span data-diagram-view-subject>__CURRENT_TITLE__</span></h2><p data-review-current-summary>__CURRENT_SUMMARY__</p></header>
          <div class="review-canvas" data-diagram-canvas data-diagram-grid-surface="1" data-diagram-contract="1" data-diagram-id="code-review-current" data-diagram-control-scope="embedded" data-diagram-profile="graph" data-diagram-width="auto" data-diagram-height="flow" data-diagram-mobile="summary" data-diagram-controls-mode="persistent">__CURRENT_GUIDE____CURRENT_GRAPH__</div>
        </article>
        <section class="review-scenario" data-review-scenario aria-labelledby="code-review-scenario-title">
          <header class="review-scenario-heading"><span class="review-scenario-label">__SCENARIO_LABEL__</span><h2 id="code-review-scenario-title" data-review-scenario-title>__SCENARIO_TITLE__</h2></header>
          <div class="review-scenario-grid">
            <article class="review-scenario-item"><h3>__SCENARIO_TRIGGER_LABEL__</h3><p data-review-scenario-trigger>__SCENARIO_TRIGGER__</p></article>
            <article class="review-scenario-item"><h3>__SCENARIO_PROCESS_LABEL__</h3><p data-review-scenario-process>__SCENARIO_PROCESS__</p></article>
            <article class="review-scenario-item"><h3>__SCENARIO_IMPACT_LABEL__</h3><p data-review-scenario-impact>__SCENARIO_IMPACT__</p></article>
          </div>
        </section>
        <article class="review-active" data-review-active-view="repair">
          <header class="review-active-heading"><span class="review-view-label">__REPAIR_TAB__</span><h2 data-review-repair-title data-diagram-view-title="1"><span data-diagram-view-type>__REPAIR_TYPE__</span><span data-diagram-view-separator aria-hidden="true"></span><span data-diagram-view-subject>__REPAIR_TITLE__</span></h2><p data-review-repair-summary>__REPAIR_SUMMARY__</p></header>
          <div class="review-canvas" data-diagram-canvas data-diagram-grid-surface="1" data-diagram-contract="1" data-diagram-id="code-review-repair" data-diagram-control-scope="embedded" data-diagram-profile="graph" data-diagram-width="auto" data-diagram-height="flow" data-diagram-mobile="summary" data-diagram-controls-mode="persistent">__REPAIR_GUIDE____REPAIR_GRAPH__</div>
        </article>
      </section>
    </div>
    <section data-review-definitions hidden>__DEFINITIONS__</section>
    <section class="review-static-fallback" data-review-static-fallback aria-label="__FALLBACK_LABEL__">__FALLBACKS__</section>
  </section>
</main>
<script data-adaptive-viewport-kernel="1">
__ADAPTIVE_JS__
</script>
<script data-code-review-kernel="1">
__REVIEW_RUNTIME__
</script>
<script data-artifact-shell-preview-kernel="1">
__SHELL_JS__
</script>
</body>
</html>
"""
    document = document.replace("__CURRENT_GUIDE__", current_guide)
    document = document.replace("__REPAIR_GUIDE__", repair_guide)
    replacements = {
        "__LANG__": _escape(normalized["lang"]),
        "__PAGE_TITLE__": _escape(normalized["title"]),
        "__BASE_CSS__": CODE_REVIEW_BASE_CSS.strip(),
        "__SHELL_CSS__": shell_css,
        "__ADAPTIVE_CSS__": adaptive_css,
        "__SEMANTIC_CSS__": semantic_css,
        "__TITLE__": _escape(normalized["title"]),
        "__SUMMARY__": _escape(normalized["summary"]),
        "__FINDING_NAV_LABEL__": _escape(guide["finding_nav_label"]),
        "__FINDING_NAV__": nav,
        "__FIRST_FINDING_ID__": _escape(first["id"]),
        "__READING_GUIDE_LABEL__": _escape(guide["reading_guide_label"]),
        "__LINE_TYPES_LABEL__": _escape(guide["line_types_label"]),
        "__EVIDENCE_STATES_LABEL__": _escape(guide["evidence_states_label"]),
        "__LINE_1__": _escape(guide["line_labels"][0]),
        "__LINE_2__": _escape(guide["line_labels"][1]),
        "__LINE_3__": _escape(guide["line_labels"][2]),
        "__LINE_4__": _escape(guide["line_labels"][3]),
        "__OBSERVED_FOR__": observed_for,
        "__OBSERVED_SOURCE__": _escape(guide["observed_source"]),
        "__CHECKED_SOURCE__": _escape(guide["checked_source"]),
        "__UNRESOLVED_SOURCE__": _escape(guide["unresolved_source"]),
        "__OBSERVED_LABEL__": _escape(guide["observed_label"]),
        "__CHECKED_LABEL__": _escape(guide["checked_label"]),
        "__UNRESOLVED_LABEL__": _escape(guide["unresolved_label"]),
        "__INTERACTION_LABEL__": _escape(guide["interaction_label"]),
        "__INTERACTION__": _escape(guide["interaction"]),
        "__SCALE_CONTROLS_LABEL__": _escape(guide["scale_controls_label"]),
        "__ZOOM_CONTROLS_LABEL__": _escape(guide["zoom_controls_label"]),
        "__AUTO_LABEL__": _escape(guide["auto_label"]),
        "__FIT_LABEL__": _escape(guide["fit_label"]),
        "__FITS_LABEL__": _escape(guide["fits_label"]),
        "__SCROLL_LABEL__": _escape(guide["scroll_label"]),
        "__VIEW_NAV_LABEL__": _escape(guide["view_nav_label"]),
        "__CURRENT_TAB__": _escape(guide["current_tab"]),
        "__REPAIR_TAB__": _escape(guide["repair_tab"]),
        "__SCENARIO_LABEL__": _escape(guide["scenario_label"]),
        "__SCENARIO_TRIGGER_LABEL__": _escape(guide["scenario_trigger_label"]),
        "__SCENARIO_PROCESS_LABEL__": _escape(guide["scenario_process_label"]),
        "__SCENARIO_IMPACT_LABEL__": _escape(guide["scenario_impact_label"]),
        "__CURRENT_TYPE__": _escape(_review_title_parts(first_current["title"])[0]),
        "__CURRENT_TITLE__": _escape(_review_title_parts(first_current["title"])[1]),
        "__CURRENT_SUMMARY__": _escape(first_current["summary"]),
        "__CURRENT_GRAPH__": current_graph,
        "__SCENARIO_TITLE__": _escape(first_scenario["title"]),
        "__SCENARIO_TRIGGER__": _escape(first_scenario["trigger"]),
        "__SCENARIO_PROCESS__": _escape(first_scenario["process"]),
        "__SCENARIO_IMPACT__": _escape(first_scenario["impact"]),
        "__REPAIR_TYPE__": _escape(_review_title_parts(first_repair["title"])[0]),
        "__REPAIR_TITLE__": _escape(_review_title_parts(first_repair["title"])[1]),
        "__REPAIR_SUMMARY__": _escape(first_repair["summary"]),
        "__REPAIR_GRAPH__": repair_graph,
        "__DEFINITIONS__": definitions,
        "__FALLBACK_LABEL__": _escape(guide["fallback_label"]),
        "__FALLBACKS__": fallbacks,
        "__REVIEW_RUNTIME__": CODE_REVIEW_RUNTIME.strip(),
        "__ADAPTIVE_JS__": adaptive_js,
        "__SHELL_JS__": shell_js,
    }
    for token, replacement in replacements.items():
        document = document.replace(token, replacement)
    unresolved = re.findall(r"__[A-Z0-9_]+__", document)
    if unresolved:
        raise ValueError("code-review renderer left unresolved internal tokens")
    return document


def _draft_review_spec(kinds: Sequence[str]) -> Dict[str, Any]:
    routing = _load_routing_contract()
    findings: List[Dict[str, Any]] = []
    for index, kind in enumerate(kinds, start=1):
        if kind not in routing["code_review_routes"]:
            raise ValueError(
                f'unknown review kind "{kind}"; request an explicit primary-relation choice'
            )
        topology = CODE_REVIEW_TOPOLOGIES[kind]
        node_count = len(topology["nodes"])
        relation_count = len(topology["edges"])
        participant_count = len(topology.get("participants", ()))

        def view(diagram_type: str) -> Dict[str, Any]:
            result: Dict[str, Any] = {
                "title": f"{diagram_type}｜View {index:02d}",
                "summary": routing["code_review_routes"][kind]["primary_relation"],
                "nodes": [
                    {"title": f"Node {node_index}", "detail": "Replace with reviewed evidence"}
                    for node_index in range(1, node_count + 1)
                ],
                "relations": [
                    f"Relation {relation_index}"
                    for relation_index in range(1, relation_count + 1)
                ],
            }
            if participant_count:
                result["participants"] = [
                    {
                        "title": f"Participant {participant_index}",
                        "detail": "Replace with an independent sequence responsibility",
                    }
                    for participant_index in range(1, participant_count + 1)
                ]
            return result

        findings.append(
            {
                "id": f"finding-{index:02d}",
                "severity": "P2",
                "title": f"Review finding {index:02d}",
                "summary": routing["code_review_routes"][kind]["primary_relation"],
                "kind": kind,
                "current": view("Current-state diagram"),
                "scenario": {
                    "title": f"Real failure scenario {index:02d}",
                    "trigger": "Replace with the evidence-backed trigger condition.",
                    "process": "Replace with the real execution or state sequence.",
                    "impact": "Replace with the concrete user, data, or operational impact.",
                },
                "repair": view("Repair diagram"),
            }
        )
    return {
        "lang": "en",
        "title": "Code review｜Findings",
        "summary": "Replace the neutral scaffold text with repository evidence before delivery.",
        "guide": {
            "line_labels": ["Current path", "Expected result", "Risk path", "Repair path"],
            "interaction": "Choose a finding in the left rail, then read the current diagram, factual scenario, and repair diagram in order.",
            "observed_source": "Replace with reviewed source files and lines.",
            "checked_source": "Replace with completed static or runtime checks.",
            "unresolved_source": "Replace with remaining runtime verification.",
            "current_tab": "Current state and risk",
            "repair_tab": "Proposed repair",
            "scenario_label": "Real problem scenario",
            "scenario_trigger_label": "Trigger",
            "scenario_process_label": "What happens",
            "scenario_impact_label": "Concrete impact",
            "finding_nav_label": "Code review findings",
            "view_nav_label": "Review finding views",
            "reading_guide_label": "Diagram reading guide",
            "line_types_label": "Line types",
            "evidence_states_label": "Evidence states",
            "observed_label": "Observed implementation",
            "checked_label": "Completed check",
            "unresolved_label": "Not yet verified",
            "interaction_label": "Interaction",
            "scale_controls_label": "Diagram scale controls",
            "zoom_controls_label": "Diagram zoom controls",
            "auto_label": "Auto",
            "fit_label": "Fit width",
            "fits_label": "Fits at 100%",
            "scroll_label": "Scroll",
            "fallback_label": "Expanded code review findings",
        },
        "findings": findings,
    }


def _canonical_review_spec() -> Dict[str, Any]:
    counter = 1
    attribute_counter = 1

    def text() -> str:
        nonlocal counter
        value = f"{{{{canvas-text-{counter:03d}}}}}"
        counter += 1
        return value

    def attribute() -> str:
        nonlocal attribute_counter
        value = f"{{{{canvas-attribute-{attribute_counter:03d}}}}}"
        attribute_counter += 1
        return value

    kind = "control-branch"
    topology = CODE_REVIEW_TOPOLOGIES[kind]

    def view() -> Dict[str, Any]:
        return {
            "title": f"{text()}｜{text()}",
            "summary": text(),
            "nodes": [
                {"title": text(), "detail": text()} for _node in topology["nodes"]
            ],
            "relations": [text() for _edge in topology["edges"]],
        }

    return {
        "lang": "en",
        "title": "{{title}}",
        "summary": "{{summary}}",
        "guide": {
            "line_labels": [
                "{{reading-guide-line-01}}",
                "{{reading-guide-line-02}}",
                "{{reading-guide-line-03}}",
                "{{reading-guide-line-04}}",
            ],
            "interaction": "{{interaction-hint}}",
            "observed_source": "{{evidence-observed-source}}",
            "checked_source": "{{evidence-check-source}}",
            "unresolved_source": "{{evidence-unresolved-source}}",
            "current_tab": text(),
            "repair_tab": text(),
            "scenario_label": text(),
            "scenario_trigger_label": text(),
            "scenario_process_label": text(),
            "scenario_impact_label": text(),
            "finding_nav_label": attribute(),
            "view_nav_label": attribute(),
            "reading_guide_label": text(),
            "line_types_label": text(),
            "evidence_states_label": text(),
            "observed_label": text(),
            "checked_label": text(),
            "unresolved_label": text(),
            "interaction_label": text(),
            "scale_controls_label": attribute(),
            "zoom_controls_label": attribute(),
            "auto_label": text(),
            "fit_label": text(),
            "fits_label": text(),
            "scroll_label": text(),
            "fallback_label": attribute(),
        },
        "findings": [
            {
                "id": "finding-01",
                "severity": text(),
                "title": text(),
                "summary": text(),
                "kind": kind,
                "current": view(),
                "scenario": {
                    "title": text(),
                    "trigger": text(),
                    "process": text(),
                    "impact": text(),
                },
                "repair": view(),
            }
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create one canonical Vibe Diagram artifact.")
    parser.add_argument("--type", required=True, dest="family", help="diagram family")
    parser.add_argument("--template", required=True, dest="template_id", help="template id")
    parser.add_argument(
        "--standard",
        default=NATIVE_STANDARD,
        help="authoring standard; only native is currently implemented",
    )
    parser.add_argument(
        "--review-kind",
        action="append",
        default=[],
        help="repeatable code-review primary relation kind",
    )
    parser.add_argument(
        "--review-spec",
        type=Path,
        help="JSON code-review package specification",
    )
    parser.add_argument("--output", required=True, type=Path, help="new HTML artifact path")
    args = parser.parse_args(argv)
    try:
        _require_supported_standard(args.standard)
        _require_ready_template(args.family, args.template_id)
        output = args.output.expanduser()
        if output.exists() or output.is_symlink():
            raise ValueError(f"refusing to overwrite existing output: {output}")
        if output.suffix.lower() != ".html":
            raise ValueError("output must use the .html suffix")
        if not output.parent.is_dir():
            raise ValueError(f"output parent does not exist: {output.parent}")
        if args.family == CODE_REVIEW_FAMILY:
            if args.template_id != CODE_REVIEW_TEMPLATE:
                raise ValueError("code-review requires the code-review-package template")
            if args.review_spec and args.review_kind:
                raise ValueError("--review-spec and --review-kind are mutually exclusive")
            if args.review_spec:
                spec = json.loads(args.review_spec.read_text(encoding="utf-8"))
            elif args.review_kind:
                spec = _draft_review_spec(args.review_kind)
            else:
                raise ValueError(
                    "code-review routing requires --review-spec or at least one "
                    "--review-kind; refusing a low-confidence default"
                )
            payload = _render_code_review_package(spec).encode("utf-8")
        else:
            if args.review_spec or args.review_kind:
                raise ValueError("review routing options are valid only for code-review")
            source = _canonical_template(args.family, args.template_id)
            payload = source.read_bytes()
        output.write_bytes(payload)
        print(
            json.dumps(
                {
                    "status": "created",
                    "family": args.family,
                    "template": args.template_id,
                    "standard": NATIVE_STANDARD,
                    "output": str(output.resolve()),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
