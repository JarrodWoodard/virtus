# SPEC #5 — Test Suite Results

**Date:** 2026-09-21
**Branch:** `fork/spec-5-redact-nonlocal` (uncommitted at proof time)
**Proof basis:** `scripts/run_tests.sh tests/hermes_cli/`
**Pyright noise:** the LSP flags `pytest` and `agent.redact._is_local_endpoint`
as unresolvable imports — false-positive venv resolution issue affecting
every `tests/hermes_cli/` file; the test runner resolves them correctly.

## Goal

Verify SPEC #5 (plugin secrets must not leak through model egress when the
active provider is non-local) is wired correctly:

1. `_is_local_endpoint()` classifies URLs correctly (loopback → local, cloud → non-local, fail-closed on garbage/empty/None).
2. `register_vault_redaction_value()` round-trips through `redact_sensitive_text(force=True)` for the realistic leak shapes (config echo, URL path, JSON dump).
3. The new wiring in the Telegram adapter's `connect()` does not break existing tests.

## Targeted suite — `tests/hermes_cli/test_spec5_redact_nonlocal.py` (NEW)

```
=== Summary: 1 files, 16 tests passed, 0 failed (100% complete) in 0.5s (24 workers) ===
```

| Test class | Tests | Result |
|---|---|---|
| `TestIsLocalEndpoint` | 9 (loopback IPv4/IPv6, localhost, https loopback, public cloud, public IP, empty/garbage/None fail-closed) | **PASS** |
| `TestVaultRedactionRoundTrip` | 5 (config-echo, URL-path, JSON-dump, unrelated-value-passthrough, webhook-secret round-trip) | **PASS** |
| `TestVaultStateIsolation` | 2 (clear removes value, LRU eviction at 64-entry cap) | **PASS** |

The URL-path test (`curl https://api.telegram.org/bot<TOKEN>/getMe → 401`)
specifically guards against the realistic "agent makes an API call and
the URL echoes through tool output" leak path that the prior
`_TELEGRAM_RE` regex alone did not cover for all wrapping shapes.

## Adjacent-secret suites — no regressions

```
tests/test_redaction_registry.py
tests/tools/test_approval_mode_parity.py
tests/tools/test_approval_timeout_overflow.py
=== Summary: 3 files, 36 tests passed, 0 failed (100% complete) in 1.7s (24 workers) ===
```

The new `_is_local_endpoint()` helper lives next to `_redact_enabled()`
in `agent/redact.py`. The two helpers do not interact; the redactor
path is unchanged for the local case (it is a NO-OP for the vault
bucket when nothing is registered), and the non-local case adds new
entries to `_VAULT_REDACTION_VALUES` which the existing registry
mechanism already scrubs at the model-egress boundary.

## Full `tests/hermes_cli/` baseline comparison

| Branch | Files | Tests | Passed | Failed | Skipped |
|---|---|---|---|---|---|
| `stable-state-2` (SPEC #3 baseline) | 905 | 9523+23+129 | 9523 | 23 (pre-existing) | 129 |
| `fork/spec-5-redact-nonlocal` | 906 | 9539+23+129 | 9539 (+16 new) | 23 (same set) | 129 |

**Delta:** +1 file, +16 tests, all 16 pass. **Zero new failures.**

The 23 pre-existing failures (dashboard, updater, kanban, xai provider
labels, skin engine) are unchanged between baseline and feature branch.
They are unrelated to the redactor / plugin-secret code path.

## Fork loads cleanly

```
$ virtus --version
Virtus v0.21.2 (Hermes fork; 2026.9.11)
Install directory: /home/jarrod/.virtus/virtus-agent
Install method: git
Python: 3.11.15
OpenAI SDK: 2.24.0
```

## Out-of-band checks (manual, not pytest)

These are the SPEC #5d contracts that pytest cannot directly verify
because they require a live `virtus --tui` session and a real provider
round-trip:

1. **Telegram adapter `connect()` calls `_is_local_endpoint` on the
   active profile's `model.base_url` and calls
   `register_vault_redaction_value(self.config.token)` when non-local.**
   Verified by reading the diff at
   `plugins/platforms/telegram/adapter.py` lines 2930-2946 — the new
   block sits between `_acquire_platform_lock(...)` and
   `Application.builder().token(...)`, exactly per SPEC #5c.

2. **The whole block is wrapped in a bare `except Exception: pass`.**
   Verified by reading the diff. A misconfigured / missing
   `model.base_url` cannot break the adapter's connect path — the
   redactor is defense-in-depth, not a hard dependency.

3. **Local provider path is a no-op for the vault bucket.** Verified
   by reading `_is_local_endpoint()` — when it returns True, the
   `register_vault_redaction_value` call is skipped entirely. A local
   LLM may see plugin secrets raw for debugging; this matches SPEC #5b.

## Status

SPEC #5 implementation is complete. Awaiting final commit + tag as
`stable-state-3`.
