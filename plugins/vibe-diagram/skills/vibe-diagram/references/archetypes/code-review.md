# Archetype: Code Review Package

Use for one or more findings that need current behavior, a real failure scenario, and a repair explanation.

## Recognizable shape

- Findings remain individually navigable without hiding the active finding's three-part story.
- Each finding reads current behavior → trigger/process/impact scenario → repaired behavior.
- Choose the relation grammar per finding: branch, exception, concurrency, state, path drift, causality, or boundary.
- Current and repair views use a comparable grammar, while facts may require different geometry.
- Source locations and raw evidence remain mapped details.

## Avoid

- selecting a diagram by severity or programming language;
- replacing the real scenario with generic risk prose;
- forcing every finding into the same coordinates;
- nested vertical scrolling inside review canvases.

## Product-manager reading

Name each finding by the real user or business failure, not the code smell. Keep scenario, impact, repaired behavior, and acceptance visible; put source locations, symbols, and raw excerpts in mapped technical details.
