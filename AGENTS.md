# Vibe Diagram Agent Contract

## Canonical boundary

- Edit reusable skill behavior only in `skills/vibe-diagram/`, the canonical core.
- Treat `build/` as generated output. Only the repository builder may create or replace it.
- Read `CONTEXT.md` before every change.

## Development rules

- Use test-driven development for every behavior change: observe a relevant test fail, make the smallest implementation pass, then refactor while green.
- Do not access the network or add third-party runtime or test dependencies.
- Do not perform Git, GitHub, marketplace, or client installation/execution actions without explicit authorization in the current user turn.

## Evidence boundary

- `package-static-valid` means only that the builder's production preflight passed.
- `static-valid` additionally requires the complete unit-test suite, deterministic build report, and a second complete unit-test run; its evidence stays in command or CI output rather than tracked documentation.
- Neither static state is `runtime-verified`; only real client installation, discovery, invocation, output, delivery, upgrade, and uninstall evidence can establish runtime verification.
