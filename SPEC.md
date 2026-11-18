# Virtus Fork — Ordered Specification

Source of truth for what we're changing in this fork, in priority order.
Lower-numbered items are foundational — every later item must not regress them.

**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` deferred/superseded

**Stable-state tag convention:** each completed item (or coherent batch) gets a git
commit note marking the fork "stable at vN". Stable states are rollback points.

**Re-mergeability:** every change must remain surgically mergeable against
`remotes/upstream/main`. Integration uses `virtus sync upstream [--apply]`,
never a raw `git pull upstream main`.

---

## #1 — Selective upstream Hermes integration  *(standard, maintained)*

**Standard.** The fork stays mergeable with `remotes/upstream/main`. The
user selects what lands; nothing auto-merges.

**Rules.**

- Integration command is `virtus sync upstream [--apply]`, never a raw
  `git pull upstream main`.
- Each accepted sync batch lands on a branch named
  `sync/upstream-YYYYMMDD`, gets tested via `scripts/run_tests.sh`, and is
  followed by a stable-state commit note summarizing what landed and what
  was skipped.
- Identity files (branding, the three guarantees in #2, wake word,
  sensitive-paths, curator, memory provider defaults) are treated as
  identity-risk on any upstream diff that touches them — surfaced for
  explicit review, never silently taken.
- Each sync produces a commit note describing the batch.

**How it should look when working.** A sync run prints: commits ahead,
classification of each (`identity-risk` / `core-bugfix` / `feature` /
`deps` / `docs-only`), and waits for the user to pick. `--apply` cherry-
picks the chosen ones onto a branch and reports test results. No auto-
merge to `main`.

**Status.** Largely in place from prior fork work; verify on every sync
and re-affirm in the stable-state commit note.

---

## #2 — No silent learning, no user-fact extraction, no phone-home  *(standard, maintained)*

**Standard.** The agent does not silently learn about the user, write
skills by itself, or report usage/telemetry anywhere. Everything that
touches the user's behavior, data, or external systems is explicit and
user-instigated.

### 2a. No automatic skill formation

**Rules.**

- `~/.virtus/config.yaml` carries `skills.write_approval: true` and
  `curator.enabled: false`.
- Skill writes never land directly in `~/.virtus/skills/`; pending writes
  go to `~/.virtus/skills/.pending/` until the user runs
  `/skills approve <id>` or `/skills reject <id>`.
- The agent proposes (name + path + one-paragraph intent) before calling
  `skill_manage` and waits for go-ahead.
- The bundled `virtus-agent` SKILL.md encodes the rule (current v3.2.0
  matches; reverify on any touch).

### 2b. No auto-extraction of facts about the user

**Rules.**

- `memory.provider: ""` in `~/.virtus/config.yaml` — no plugin memory
  provider loaded.
- `MemoryManager.on_session_end` (and any equivalent hook in this fork)
  does not fire.
- Writes to `~/.virtus/memories/USER.md` and `MEMORY.md` only happen on
  explicit user request in the current conversation.
- Cross-session "remember this" still works when asked; only the
  auto-extraction path is dead.

### 2c. No phone-home telemetry / outbound usage reporting

**Rules.**

- `updates.notify: false`, `account_usage.fetch: false`,
  `monitoring.enabled: false`, `models_dev.allow_network: false`.
- No analytics, third-party identifier tagging, or attribution tags
  shipped by default. Anything of that shape is gated behind a labeled
  config flag and a setup prompt.
- OTLP / OpenTelemetry exporters off by default.
- Crash reports: if any exist, must be local-only (write to
  `~/.virtus/logs/`, never POST).
- A regression guard (e.g. `tests/hermes_cli/test_no_phone_home.py`) fails
  CI if any non-gated code path opens a network connection to a vendor
  analytics endpoint, sets a tracking header, or POSTs usage data.

### 2d. How "still satisfied" should be verifiable

- `virtus --version` prints a one-line "telemetry: off" assertion.
- A cold-start network audit (`strace -e trace=network -f virtus ...` or
  equivalent socket audit) shows zero outbound connections other than the
  configured model provider.
- The regression guard from 2c runs in CI alongside the existing branding
  guard (`tests/hermes_cli/test_no_hermes_in_user_facing_strings.py`).

**Status.** Largely in place from prior fork work (the three guarantees
the `virtus-agent` skill ships with). Each sync and each fork change
must re-verify these rules; the stable-state commit note records the
verification result.

---

## #3 — Adjust Hermes defaults: very long (effectively unbounded) waits and limits  *(standard, maintained)*

**Standard.** The fork's defaults raise the ceiling on user-facing waits
and per-loop turn budgets so the agent does not give up early on work
the user wanted to continue. Every knob remains user-overridable in
`~/.virtus/config.yaml`.

### 3a. No effective timeout on user-approval prompts

**Rule.** Default `approvals.timeout` is raised from the upstream 300 s
to the platform-safe ceiling (`agent.deadline.MAX_SAFE_TIMEOUT_S`, ≈1
year). The user is never auto-denyed because the agent got impatient.

- [ ] Fork-side default in the config schema / first-run prompt is the
      safe ceiling, not 300.
- [ ] The clamp logic in `tools/approval_context.py::_get_approval_timeout`
      continues to enforce the platform-safe ceiling (macOS `time_t`
      overflow guard — `#83220`).
- [ ] The `_AUTHORIZATION_GATE_LOCK_TIMEOUT_S` fallback is raised to
      match (or, better, derived from `human_wait_ceiling()` so the two
      cannot drift — already the design intent per
      `agent/tool_executor.py:123`).
- [ ] User's existing config (no `approvals.timeout` key) inherits the
      new fork default; user's explicit override is preserved verbatim.

### 3b. /goal default turn budget: 20 → 1000

**Rule.** `goals.max_turns` fork default is 1000, not 20. Persistent
cross-turn goals (Ralph-style loops) should not stop early by default.

- [ ] Fork-side default in the config schema is 1000.
- [ ] The legacy `agent.max_turns` config key — which the gateway
      bridges into the same budget via `_bridge_max_turns_to_env` —
      gets a fork default of 1000 as well, so legacy configs without
      an explicit `goals:` block still get the higher budget.
- [ ] The string spellings `"none"` / `"unlimited"` continue to mean
      unbounded (already preserved by the bridge).
- [ ] User's existing override (`agent.max_turns: 90` in
      `~/.virtus/config.yaml`) is left alone unless they say otherwise.

### 3c. Other surfaced timeouts / caps — adjusted to match

| Knob | Upstream | Fork default | Why |
|---|---|---|---|
| `_DEFAULT_CONCURRENT_TOOL_TIMEOUT_S` (parallel tool batch) | 420 s | same as `approvals.timeout` ceiling | A long approval prompt is a long batch — clamp them together |
| `_DEFAULT_IMAGE_PARALLEL_REQUESTS` | 4 | 4 (no change) | Rate-limit safety, not a wait |
| `local_stream_stale_timeout` (local provider) | 900 s | same as `approvals.timeout` ceiling | A stalled local stream is a stalled user wait |
| `_AUTHORIZATION_GATE_LOCK_TIMEOUT_S` fallback | 360 s | derived from `human_wait_ceiling()` | Already the design intent (#79719) |
| `MATRIX_APPROVAL_TIMEOUT_SECONDS` | 300 s | same as `approvals.timeout` ceiling | Same approval-prompt reasoning |
| `delegation.max_iterations` (subagents) | 500 | 1000 | Matches the raised `/goal` budget |
| `terminal.timeout` | varies | inherits from upstream; user's `180` in config left alone | Per-command deadline; user can dial it |

**Out of scope for #3.**

- Provider API request timeouts (anthropic / openai client kwargs).
  Those gate real network calls to third parties, not user waits;
  changing them trades latency for cost, not "patience".
- Compression / context-window thresholds.
- Model-tool schema / toolset defaults.

**Status.** Defaults to set in the fork schema; user-side `config.yaml`
remains the override surface. Re-verify on every sync.

---

## #4 — Local LLM endpoints (no fork changes; documented standard)

**Standard.** Virtus supports local LLM endpoints through the existing
`custom` provider + `base_url` pattern. This is **already in place** — no
fork code change is required, and the four profiles on `10.0.0.161` already
use this pattern against their local Qwen3.8 dispatcher.

### 4a. The pattern

```yaml
model:
  provider: custom
  base_url: http://localhost:8080/v1   # any OpenAI-compat endpoint
  api_key: dummy                        # non-empty; local servers usually ignore it
  default: my-model-name                # exact id from GET <base_url>/models
  # timeout: 1800                        # raise for slow first-token-on-load
```

The `custom` provider:

- POSTs to `<base_url>/chat/completions` (streaming + non-streaming)
- Reads model names from `<base_url>/models`
- Sets `Authorization: Bearer <api_key>` by default; most local servers ignore it

### 4b. What virtus does NOT do

By design — these are separate concerns, not fork features:

- **Does not start, stop, or monitor the local LLM server.** Use systemd,
  docker compose, or a separate dispatcher (e.g. the user's own
  `~/Projects/llm-dispatcher/` repo).
- **Does not implement auth / rate limiting on the local server.** The
  server is responsible; virtus just speaks OpenAI-compat.
- **Does not bundle a dispatcher process.** The dispatcher is a homelab
  service the user deploys independently; virtus points at it via
  `base_url`.

### 4c. Documentation surface

- [ ] Skill `~/.virtus/skills/virtus-local-llm/SKILL.md` teaches the agent
      the recipe (already shipped 2026-09-15, version 1.0.0).
- [ ] `config_defaults.py` inline comment near the `custom` provider example
      mentions local-LLM endpoints (so users discover the pattern without
      reading the skill).
- [ ] No CLI subcommand, no plugin, no in-tree dispatcher code. Adding any
      of those would couple the fork to a specific LLM server, which
      violates "narrow core, wide edges."

### 4d. Regression guard

A test (`tests/hermes_cli/test_custom_provider_local_url.py` or similar)
that confirms the `custom` provider still:

- Resolves a model name via `GET <base_url>/models`
- POSTs to `<base_url>/chat/completions`
- Streams SSE chunks correctly
- Sets `Authorization: Bearer <api_key>` from config

The guard fails if upstream changes the `custom` provider path in a way
that breaks local-LLM users.

**Status.** Standard is in place. Skill shipped. Guard test is the only
outstanding fork work — and it's a regression guard, not a feature.

---

## #5 — Plugin secrets must not leak through model egress  *(standard, maintained)*

**Standard.** Plugin credentials registered with the platform gateway
(Telegram bot token, webhook secret, future OAuth tokens, etc.) are
scrubbed at the model-egress boundary when the active provider is
non-local. Local endpoints (loopback, and any URL in
`virtus.trusted_local_cidrs`) are trusted to see the raw values for
debugging.

### 5a. Layered defense

**Rules.**

- The existing `agent.redact.register_vault_redaction_value` is the
  model-egress scrubber. Exact-byte match, runs with `force=True`
  regardless of `security.redact_secrets`, survives token rotations and
  non-regex-shaped wrappers. Per-profile scope, bounded LRU at 64
  values.
- The existing `agent.file_safety.get_read_block_error` already denies
  `.env`, `auth.json`, `vault/`, `mcp-tokens/`, `browser-profile/`
  reads through `tools/file_tools.py`. This is the file-read layer.
- Both layers must be wired for a credential to be considered safe.
- The file-read layer is upstream-maintained; the fork only owns the
  vault-registry wiring (which plugins opt into).

### 5b. Local vs. non-local provider trust

**Rules.**

- A provider is "local" if `model.base_url` is loopback (`127.0.0.1`,
  `::1`) or matches a CIDR in `virtus.trusted_local_cidrs` (default:
  loopback only — no LAN trust).
- For local providers, plugin credentials may be visible to the LLM
  (used for legitimate debugging of the bot's own behavior).
- For non-local providers, plugin credentials are registered with the
  vault redactor on adapter `connect()`, and the registration is held
  until adapter `disconnect()`.
- Registration is opt-in per plugin via a one-line call in
  `connect()` — opt-out is the wrong default (a forgotten opt-in is a
  silent leak).

### 5c. Plugins that ship secret registration in this fork

- [ ] `plugins/platforms/telegram/adapter.py` registers
      `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` (when set) on
      `connect()`, after token-lock acquire.
- [ ] Future platform adapters (Discord, Signal, Matrix, …) follow the
      same pattern: register every secret the adapter holds, after
      every lock acquire, in `connect()`.

### 5d. Regression guard

A test (`tests/hermes_cli/test_spec5_redact_nonlocal.py` or similar)
that:

- Mocks a non-local provider (`base_url: https://api.example.com`),
  instantiates the Telegram adapter, calls `connect()`, asserts the
  exact token bytes are present in `_VAULT_REDACTION_VALUES` for the
  active profile.
- Reverses the provider to loopback, asserts registration is skipped.
- Round-trips a tool-output string containing the token through
  `redact_sensitive_text(force=True)` and asserts the token is replaced
  with `«redacted-vault-secret»`.

**Status.** v1 covers Telegram. Generalization to "every plugin
credential" is the long-term shape; per-plugin opt-in keeps the v1
diff minimal.

### 5e. Out of scope (recorded for future specs)

- Prompt-level redaction (stripping secret-bearing values from the
  outbound system prompt before it reaches the provider) — different
  mechanism, different PR.
- Transport-level encryption / mTLS between virtus and the local LLM
  endpoint — local endpoints are LAN-trusted by current posture.
- Removing the existing `_TELEGRAM_RE` regex from `agent/redact.py` —
  it remains as a defense-in-depth for plugins that don't opt in.

---

## #6 — Rotunda is the only browser, and it never steals focus  *(standard, maintained)*

**Standard.** Virtus has exactly one browsing surface: **Rotunda**, a patched Firefox driven over a
loopback daemon by the `rotunda agent` CLI. It runs **headless** by default so the browser cannot
come to the foreground or interfere with the owner's work. No Chromium, no Playwright, no Browser
Use CLI, no cloud browser, no `browser_*` toolset.

**Rules.**

- `agent.disabled_toolsets` in `~/.virtus/config.yaml` carries `browser`, `browser-cdp` and
  `computer_use`. Verified: the resolved CLI toolset list contains none of them.
- The skill is `skills/web/browser-driving` (repo) and `~/.virtus/skills/web/browser-driving`
  (live). It carries the hard-won rules: refs come only from `describe`, scroll before acting, read
  every fill back, radios cannot be unchecked, never close the last page.
- The profile is `prof_8ac20ec9fa70` (`virtus`, `--headless`). A headed profile is allowed ONLY
  when the owner asks for one, and it is expected to take focus: measured 2026-11-16, `new-context`
  on a headed profile changed the active window; the headless profile did not, through a navigation
  and an extraction.
- One daemon per machine. Starting virtus's context replaces whichever profile held it, so a virtus
  browsing run hands the daemon back with `rotunda agent new-context prof_a9c84ba06837` (the job
  agent's profile).
- Never `windowactivate`, `windowraise`, `focus_app`, or move the pointer. Ref actions are semantic
  and work in the background.
- Secrets (cookies, tokens, codes) never enter prompts, logs, or model context.

**Regressions to guard.**

- A future upstream merge re-enables the built-in browser toolsets → the disabled list and the
  resolved-toolset check catch it.
- A headed profile appearing as the default → the focus measurement in this section is the test.
