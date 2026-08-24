# Archetype: Async, Retry, and Timeout Sequence

Use when queues, callbacks, leases, concurrency, retry limits, or timeout boundaries matter.

## Recognizable shape

- Keep each producer, broker/store, worker, callback target, and observer as a real participant when evidence distinguishes them.
- Async sends, returns, errors, and timeout boundaries have different line treatment.
- Retry or loop fragments show their guard or limit.
- Concurrent alternatives and late arrivals are shown at the point they diverge.
- The final state or observable outcome remains connected to the interaction.

## Avoid

- hiding the broker or durable store inside a generic service;
- drawing retries as an unlabeled backward arrow;
- inventing timing values or delivery guarantees;
- shrinking participant text to fit one viewport.

## Product-manager reading

Lead with the user or business action, the observable result, and how timeout, retry, duplicate delivery, or late arrival changes that result. Use business roles as participant labels first; keep queue, worker, lease, and callback identifiers as secondary technical evidence.
