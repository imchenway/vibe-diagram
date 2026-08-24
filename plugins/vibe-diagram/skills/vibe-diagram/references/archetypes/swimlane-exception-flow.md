# Archetype: Swimlane and Exception Flow

Use when ownership, handoffs, two implementation paths, compensation, or failure recovery are central.

## Recognizable shape

- Each lane represents a real actor, system, responsibility, or implementation path.
- The main reading direction stays consistent across lanes.
- Cross-lane arrows make handoffs visible; missing handoffs are shown at the exact break.
- Exception and compensation paths use a separate visual channel and rejoin or terminate explicitly.
- Shared inputs and outputs may span lanes when they are genuinely shared.

## Avoid

- lanes that merely group unrelated cards;
- duplicating the same actor to make routing easier;
- a relationship ledger standing in for arrows;
- forcing three lanes because an example happened to use three.

## Product-manager reading

Name lanes by business role or responsibility, show every real handoff, and make rejection, compensation, recovery, and final outcome directly visible. Exact services may appear as secondary lane labels when they help implementation traceability.
