---
name: vibe-diagram
description: Use when an agent should create and deliver a self-contained HTML visual artifact for architecture, workflows, sequences, state and data models, debugging evidence, or code review, including explicit or contextual requests such as “画图”, “画个图”, “画图给我看”, “架构图”, “UML”, “流程图”, and “时序图”; Mermaid alone never satisfies the request.
---

# Vibe Diagram

## 0.1.12 drawing principles

Vibe Diagram exists to explain subjects through real diagram geometry. Generation must first select the correct family, establish its primary visual grammar, size nodes for their actual copy, and then draw readable relationships. Scripts efficiently detect regressions; they do not replace drawing judgment, and reducing font size must never turn a failed composition into a pass.

- When the user does not name an external standard, use the native Vibe Diagram family grammar.
- When the user explicitly requests UML, BPMN, C4, ArchiMate, or another standard, follow that standard strictly. If strict support is unavailable, fail closed instead of silently degrading to a native template.
- Delivery-acceptance diagrams and release-rollback diagrams are no longer public recommended families. Model ordered acceptance or release work as business flow, fail closed for unsupported itemized requirement-evidence comparisons, and use a state machine only when the user explicitly requests state semantics.
- Keep old explicit entry names for one release cycle as migration notices only; they must not become defaults again.
- Write every graph-level title as `diagram type｜title`, localized to the artifact language. In a standalone artifact, the page `h1` is also its only graph-level title and must use this structure directly. In a multi-diagram package, the page title may remain independent while every subgraph title uses the structure. Do not apply it to table captions or detail headings.
- Keep the percentage zoom component persistently visible in the shared title shell whenever its canvas is measurable, to the right of the title on wide screens and below the title copy on narrow screens. A canvas-local reading guide, when required by its family or template contract, stays visibly inside the owning diagram surface at its top-left on the same continuous 24-pixel grid as the diagram body, with no ungridded separator strip; its wording and swatches must be authored from that diagram's real relation categories and computed visual tokens. The shared shell validates ownership, grid-surface placement, relation binding, and structure without prescribing domain-specific guide groups. A code-review package specifically requires relation-type and evidence-state groups, and uses one shared persistent canonical control group for its current and repair diagrams; the factual scenario between them is never scaled.
- Sequence participants and message captions use semantic accent fills. Do not restore white participant or caption cards.

## Update gate

On every invocation, resolve this skill directory and run `python3 <skill-root>/scripts/update_skill.py --check-and-update --json` before doing the requested work.

- For `current`, `updated`, or `managed`, continue normally.
- For `offline` or `failed`, continue with the installed version and mention the update status briefly without blocking the requested artifact.
- Never replace the installed tree directly or bypass the updater's integrity check, lock, or transactional activation.
- For an explicit manual update request, run the same script with `--force-check --json` and report the exact result.

## Runtime workflow

After the update gate finishes, read [the runtime workflow](references/runtime-workflow.md) completely from the current skill directory, then follow it for the request. Resolve this path after a successful update so the current invocation uses the newly installed workflow.

## Reference index

- [Runtime workflow](references/runtime-workflow.md)
- [Adaptive readability and semantic relations](references/adaptive-readability.md)
- [Business architecture](references/business-architecture.md)
- [Business flow](references/business-flow.md)
- [Code review](references/code-review.md)
- [Code sequence](references/code-sequence.md)
- [Delivery acceptance compatibility migration](references/delivery-acceptance.md)
- [Fault debugging](references/fault-debugging.md)
- [State and data model](references/state-data-model.md)
- [System architecture](references/system-architecture.md)
