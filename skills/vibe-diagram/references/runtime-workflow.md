# Vibe Diagram Runtime Workflow

## Production boundary

The model authors the final self-contained HTML, CSS, and SVG. There is no semantic-spec compiler, production template, fixed node inventory, generic graph renderer, or coordinate allocator. Archetypes are references only.

The production path is:

1. inspect the current request and its real evidence;
2. form a private Diagram Brief around the product questions, business impact, decision, acceptance meaning, and evidence states;
3. map important technical identifiers to business-first labels, then select the relationship grammar and one primary view;
4. read at most two relevant archetypes;
5. initialize a blank artifact shell;
6. directly author the product-manager-first primary layer, supporting technical views, and evidence details as needed;
7. embed ArtifactManifest v1 and semantic markers;
8. lint, inspect in a browser, perform a product reading review, repair outcome defects, and deliver.

Mermaid, prose, a copied archetype, a pre-authored JSON graph, an engineering artifact with a decorative summary, or an unverified HTML draft is not invocation-complete.

## Diagram Brief

Before writing the artifact, privately identify:

- what a product manager must understand or decide;
- the concise conclusion, change, or problem and its business impact;
- questions that must be answerable without opening technical details;
- facts, differences, decisions, exceptions, outcomes, and acceptance meaning;
- evidence status for every material claim;
- the business meaning of every important code, API, field, table, infrastructure, error, or log identifier;
- the primary relationship and suitable diagram family;
- facts that belong on the product primary layer, technical supporting views, or mapped evidence details;
- unresolved items and their verification paths;
- whether multiple views are genuinely needed.

The product manager is always the primary reader. Other readers may require supporting depth but cannot replace the product-readable entry. The brief is reasoning, not a rendering contract. Do not turn it into a node list that another program draws. When evidence is incomplete, show known facts, unresolved items, and a verification path; never promote a hypothesis to a confirmed cause.

## Initialize and author

Create a blank artifact:

```sh
python3 <skill-root>/scripts/vibe_diagram_scaffold.py \
  --output <artifact.html> \
  --title '<localized title>' \
  --lang <language-tag>
```

The command refuses an existing output and emits only the global shell. Edit the artifact directly. Replace the empty manifest arrays and author one or more real diagram views under `main[data-vd-content]`.

Author in reading order: first make the visible summary and primary view understandable without source-code knowledge, then add only the technical views and details needed to preserve precision. Do not draw a complete engineering document first and add one vague sentence above it. A technical request may have a detailed sequence, architecture, state, or data view, but its business result and impact remain visible at the entry.

Use arbitrary semantic HTML and SVG appropriate to the current relationship. The shell does not impose tags, classes, node counts, ranks, lanes, or coordinates. Prefer explicit SVG paths for directional graph relations so endpoint and collision checks can inspect real geometry.

Do not use retired `--spec`, `--template`, `--review-kind`, or `--review-spec` inputs. Do not recreate `DiagramDocumentSpec` under another name.

## Artifact contract

Read [artifact authoring](artifact-authoring.md) completely. Every finished artifact must include:

- one `script#vibe-diagram-manifest[type="application/json"]` using ArtifactManifest v1;
- `product-manager` in the Manifest audience, with any other readers added only as secondary audiences;
- one visible, product-readable `data-vd-summary`;
- one or more elements with `data-vd-view`, `data-vd-family`, and `data-vd-view-role`;
- stable unique ids on every manifest target and relation endpoint;
- semantic nodes with `data-vd-node`, groups with `data-vd-group`, and directed relations with `data-vd-edge`, `data-from`, and `data-to` where the family uses a graph;
- `data-vd-critical` on the visible elements that answer critical questions;
- authored details mapped through `data-vd-detail-for` when raw evidence is disclosed progressively;
- business-first primary labels and exact implementation identities as secondary labels or details;
- a visible family-correct title in `diagram type｜business subject` form for each graph.

ArtifactManifest records questions, critical facts, views, and evidence coverage. It must not enumerate every node, store coordinates, or prescribe DOM. Do not delete technical evidence to simplify the primary layer.

## Family selection

Route by the relationship the reader must understand, not by filenames, severity, or the existence of a familiar example. Use multiple views only when different relationships cannot remain readable in one topology.

- Every family begins with a product-readable entry and business result.
- Technical design adds only the flow, sequence, state, data, architecture, comparison, or prototype views required by the question.
- Code review preserves a visible current behavior → real scenario → repair reading order for each finding; it need not force identical coordinates when the facts differ.
- Comparison uses a real matrix with conditions as rows and candidates as columns. Never invent weights or scores.
- Page prototype uses real HTML controls and responsive states, not device frames or workflow cards.
- Route decisions, delivery acceptance, release rollback, and feature iteration are topics, not standalone visual grammars. Express them with the appropriate flow, matrix, state, debugging, or technical-design view.

If the user explicitly requests an external standard and no strict standard reference is present under `references/standards/`, stop and explain that strict generation is unavailable. Never relabel native output as standard-conformant.

## Validate and repair

Run:

```sh
python3 <skill-root>/scripts/vibe_diagram_lint.py <artifact.html>
```

Use `--type <family>` only when the request declares one expected primary family. Candidate tabs require the user's explicit exploration request and `--allow-candidates`.

Open the artifact in a real browser at `1440×900`, `1280×800`, and `390×844` after fonts are ready. Run `VibeDiagramQuality.auditAll()` and require `status: "passed"`. Exercise zoom, details, Esc, focus return, and narrow-screen horizontal overflow when present.

With every technical detail closed, perform a product reading review. Answer each critical Manifest question using only the summary and primary view. Confirm that the business conclusion, impact, applicable rules or branches, decision, acceptance meaning, and unresolved state are understandable without relying on exact implementation identifiers. Then confirm that every exact source or log remains reachable from its mapped fact. Only then report `product-reading-reviewed`.

If validation fails, repair the authored composition. Do not change the checker to accept a bad picture, shrink below the 75% readable floor, hide critical facts, or delete relations. Split mapped views when one canvas cannot remain clear. Perform at most three repair passes; after the third failure, do not claim the failed evidence layer and report the exact unresolved issue.

## Delivery

Deliver the single HTML artifact with a clickable absolute path. State unresolved evidence honestly. Report these evidence levels separately:

- `artifact-static-valid`: manifest, self-containment, semantic binding, and family grammar passed;
- `product-reading-reviewed`: a named real-demand artifact answered its critical product questions without opening technical details while preserving exact mapped evidence;
- `browser-layout-verified`: the declared browser viewports and interactions passed;
- `client-runtime-verified`: installation, discovery, invocation, output, delivery, upgrade, and uninstall passed in a named real client.

No evidence layer implies another.
