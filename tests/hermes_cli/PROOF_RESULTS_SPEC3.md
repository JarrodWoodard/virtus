# SPEC #3 — Live TUI Proof Results

**Date:** 2026-09-15
**Branch:** `fork/spec-3-defaults` (uncommitted)
**Driver:** `/tmp/prove_virtus_spec3.py`
**Captured panes:** `/tmp/tui_proof_spec3/`

## Goal

Verify the SPEC #3 fork defaults are **live in a real `virtus --tui` session**
before committing the branch as Stable State 2. Each task spawns a fresh TUI,
asks the agent a specific question about a config default, and asserts the
agent's response matches the new fork value (not the upstream default).

## Tasks (final run, exit 0, all PASS)

| # | Question | Expected (must-match) | Verdict |
|---|---|---|---|
| T1 | Default `approvals.timeout` seconds value | `31_536_000` (or "year"/"365 days") | **PASS** |
| T2 | Fork default `goals.max_turns` integer | `1000` | **PASS** |
| T3 | Fork default `agent.local_stream_stale_timeout` seconds | `31_536_000` (or "year"/"365 days") | **PASS** |
| T4 | Fork default `DEFAULT_MAX_ITERATIONS` for subagents | `1000` | **PASS** |

## Ground truth

| Check | Before | After | Delta |
|---|---|---|---|
| `~/.virtus/skills/` entries | 5 | 5 | 0 |
| `~/.virtus/skills/.pending/` entries | 0 | 0 | 0 |
| `~/.virtus/memories/` entries | 4 | 4 | 0 |

The proof run wrote **no new skill, no pending skill, no memory file**.
The fork's auto-extract / write-approval gates are intact.

## Per-task agent responses (excerpted, final run)

### T1 — `approvals.timeout`
> The source confirms the fork default exactly. Three independent corroborations:
> hermes_cli/config_defaults.py — `"approvals": { ... "timeout": 31_536_000, ... }` at line 1567
> tools/approval_context.py — `_get_approval_timeout` reads default `31_536_000`
> agent.deadline.MAX_SAFE_TIMEOUT_S — the clamp ceiling (31_536_000)
> This is a Virtus fork delta under SPEC #3a, raised from the upstream 300s default
> so the user is never auto-denyed because the agent got impatient.

### T2 — `goals.max_turns`
> Direct hit in config_defaults.py:1297-1305. The fork's `DEFAULT_CONFIG["goals"]["max_turns"]`
> is the literal integer **1000**, annotated `virtus: SPEC #3b — default raised from 20 to 1000`
> — matching the SPEC's rule.

### T3 — `local_stream_stale_timeout`
> Verified in source at `config_defaults.py:239` — the literal value `31_536_000`. Fork
> delta under SPEC #3c, raised from the upstream 900s default so a stalled local stream
> is treated as a stalled user wait (matches approvals.timeout).

### T4 — `DEFAULT_MAX_ITERATIONS`
> Direct hit at `tools/delegate_tool.py:69` — the actual constant is `DEFAULT_MAX_ITERATIONS = 1000`.
> Fork delta under SPEC #3b's theme: fork raises the upstream cap (250) so persistent delegation
> loops don't stop early by default.

## Driver notes (pacing pitfalls hit during this run)

1. **Wrong idle marker.** Sep 14's driver polled for the substring `idle`; this
   fork's TUI uses `─ ready`. Driver patched to wait for `─ ready`.
2. **Wrong response-start marker.** The old `─ starting agent…` substring isn't
   emitted by this TUI; responses begin after ` ┊ ` (a vertical box-drawing
   char). Driver patched.
3. **Over-aggressive must-not regexes.** First-pass assertions included
   `\bdefault.*\b20\b` and `\b900\b` — those fire when the agent correctly
   explains "raised from the upstream default of 20" or "raised from upstream
   900". Tightened to anchor-only (`^\s*20\s*$`) so they only catch the
   upstream value appearing as a *standalone* answer. The skill reference
   warned about this: "Always read the captured agent text when a task fails —
   if the agent's response is correct, the assertion was the bug, not the
   agent." Confirmed: agent behavior was right in the first run; the assertion
   was wrong.
4. **Per-task fresh TUI.** SPEC #3 changed config defaults — system-prompt
   caching means a single TUI session would not re-read config. Driver
   re-spawns TUI before each task.

## Verdict

**ALL 4 TASKS PASS, DISK DELTA ZERO.** The fork defaults are live and the
agent reads them correctly from the source. Safe to commit this branch as
Stable State 2.
