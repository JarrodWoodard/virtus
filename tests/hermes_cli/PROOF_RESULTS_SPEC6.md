# PROOF RESULTS — SPEC #6, shared headed browser (2026-10-09)

Live receipts for the SPEC #6 implementation. Every row was produced on the
real stack: the tmux-managed headed Chrome (`agent-chrome`, up since 2026-10-07),
loopback CDP :9222, virtus runtime (`HERMES_HOME=/home/jarrod/.virtus`).

## 1. Schema swap — built-in stack default (fork default change)

`tools/browser_use_cli.py::is_browser_use_cli_mode` with `browser.backend`
unset now keeps the built-in tools even though the Browser Use CLI is
discoverable (uvx on PATH). Probed through `model_tools.get_tool_definitions`
with the real virtus config:

| Check | Result |
|---|---|
| `browser-use mode` | `False` |
| `browser_exec` in schema | **absent** |
| browser tools in schema | `browser_navigate, browser_snapshot, browser_click, browser_type, browser_scroll, browser_back, browser_press, browser_get_images, browser_vision, browser_console, browser_cdp, browser_dialog` + 5 `browser_vault_*` |
| total tools | 34 (with `web`/`x_search` toolsets disabled per posture) |

Unit contract: `tests/tools/test_browser_backend_default.py` — 5 tests, real
config files + a real executable named `browser-use` on PATH (no mocks):
discoverable CLI does NOT enable the mode; explicit `browser.backend:
browser-use` does; `off`/unset keep the built-in tools; no downgrade nag.

## 2. agent-chrome-run v3 — raw CDP, stdlib only

Playwright dependency and the hardwired hermes-venv shebang removed; minimal
RFC 6455 client + CDP multiplexer in stdlib. Against the live shared Chrome:

| Run | Result |
|---|---|
| `--url https://example.com --screenshot /tmp/acr_smoke.png` | exit 0, `SCREENSHOT: /tmp/acr_smoke.png` (58,132-byte PNG), tab auto-closed |
| transport | raw WebSocket, no Origin header — works against the loopback-only CDP port (no `--remote-allow-origins` needed) |

## 3. Handoff E2E — login wall (the full control-state contract)

Local page served on `127.0.0.1:18927` with a visible `input[type=password]`
(login-wall trigger). Run with `--handoff --handoff-timeout 10`:

```
🚨 NEED YOU: http://127.0.0.1:18927/ — login-wall:password-field
[notify] handoff: waiting up to 10s for you to clear it
HANDOFF TIMEOUT: still blocked (login-wall:password-field) at http://127.0.0.1:18927/
    after 10s — tab left open, task marked failed
SCREENSHOT: /tmp/lw_handoff3.png
EXIT=3
```

Visual verification of `/tmp/lw_handoff3.png`: red banner
`AGENT BLOCKED — needs you: login-wall:password-field` rendered at the top of
the login page; tab left open for the user.

First run of this E2E exposed exactly the eval bug the skill now warns about:
two detector expressions were bare `() => {...}` — `Runtime.evaluate` returns
the uncalled function (→ `None`), so detection silently passed. Fixed to
`(() => {...})()`; the same bug class is recorded in the skill's eval
discipline and pitfalls.

Note: an initial run on port 8765 captured an unrelated app already bound to
that port (my test server had silently failed to bind) — the E2E above is the
re-run on a verified-free port with a readiness check. Lesson is operational,
not a code defect.

## 4. Isolated-world isolation

Against the shared Chrome, page world vs `Page.createIsolatedWorld`
(`worldName: "agent-world"`) evaluated in the same frame:

| World | `window.__page_secret` | `document.title` |
|---|---|---|
| page (set by page-world eval) | `page-world-value` | `Acme Portal — Sign in` |
| isolated agent world | `undefined` (not visible) | `Acme Portal — Sign in` (DOM visible) |

The agent can read the DOM without colliding with page JS state. (Also
receipt for the pitfall: `Page.createIsolatedWorld` without `sessionId` fails
with `wasn't found` — every page call carries the target's sessionId.)

## 5. Launch hardening

`agent-chrome-launch` now passes `--remote-debugging-address=127.0.0.1` and no
longer passes `--remote-allow-origins='*'` (both launch paths). Verified by
inspection; the live session predates the change and will pick the flags up on
next start.

## Known boundaries (honest scope)

- The `HANDOFF → cleared` path is exercised by code symmetry and the v2
  live-site table (nowsecure.nl); the automated E2E covers the timeout path.
- Built-in `browser_navigate` refuses loopback/LAN URLs by design (private-
  address guard) — local pages go through `agent-chrome-run`.
- The gateway/long-running sessions pick all of this up on restart.
- PRE-EXISTING failure (not from this batch; verified to fail without these
  changes): `tests/tools/test_browser_real_profile.py::
  TestReviewRound3::test_relaunch_path_does_snapshot` — real-profile binary
  discovery assumes a Google Chrome ("chrome" channel) install; this host has
  only Chromium. 308/309 of the affected battery green otherwise.
