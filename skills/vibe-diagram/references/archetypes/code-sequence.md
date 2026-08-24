# Archetype: Code Sequence

Use for ordered calls, returns, synchronous work, transactions, and participant interaction.

## Recognizable shape

- Distinct participants have visible headers and independent lifelines.
- Time progresses from top to bottom.
- Messages connect the actual sender and receiver lifelines.
- Calls, returns, self-calls, activation, and exceptions use distinguishable visual forms.
- Phase or alternative fragments span only the participants they concern.

## Avoid

- floating message cards without lifelines;
- merging semantically different participants to reduce width;
- an ordinary flowchart relabeled as a sequence;
- message captions covering their arrows.

Wide sequences may use local horizontal scrolling at the 75% readability floor.

## Product-manager reading

Start from the user or business action and end at the visible result. Participant headers use business responsibility first and exact service names second; calls and errors explain their business meaning without losing the real sender, receiver, order, or exception.
