---
name: browser-driving
description: "The only browser virtus has: Rotunda, headless, background, never steals focus."
version: 1.0.0
platforms: [linux]
metadata:
  rotunda:
    profile: prof_8ac20ec9fa70
    mode: headless
    daemon: "127.0.0.1:51240-51271"
---

# Browser driving — Rotunda only

Virtus has exactly one browser: **Rotunda**, a patched Firefox driven over a loopback daemon by the
`rotunda agent` CLI. The built-in `browser_*` stack, the `browser-cdp` toolset and `computer_use`
are DISABLED in `~/.virtus/config.yaml` (`agent.disabled_toolsets`). There is no Chromium, no
Playwright, no Browser Use CLI, and no cloud browser. If a task says "open the site", it goes
through Rotunda.

## Non-negotiable rules

1. **Never steal focus.** The profile is `--headless`, so no window exists and nothing can pop to
   the front. Do not create a headed profile to "see what happens": a headed context RAISES its
   window (measured 2026-11-16 — `new-context` on a headed profile changed the active window).
   Only a headed profile when the owner explicitly asks for one, and then expect the window.
2. **Never raise, focus or activate anything.** No `windowactivate`, no `windowraise`, no
   `focus_app`, no pointer movement. Rotunda's ref actions are semantic and work in the background.
3. **One daemon, take turns.** There is a single agent daemon per machine, bound to one profile at a
   time. Starting virtus's context replaces whichever profile held it. That is shared with the job
   agent (`prof_a9c84ba06837`); when a run is finished, hand the daemon back:
   `rotunda agent new-context prof_a9c84ba06837`.
4. **Refs come only from `describe`.** A ref looks like `page_8cdb2471b5` / `[sc6wfz5r]`
   (pass without brackets). A DOM id is not a ref. After a navigation or reload, re-describe.
5. **Scroll before you act.** `scroll <page> <ref> down` immediately before `fill`/`click`, or the
   actionability check times out on long forms.
6. **Read back every fill.** `info <ref>` then compare `value:` / `selectedIndex:` / `checked=`.
   "page: stayed the same" is NOT proof that a field took the value.
7. **Radios cannot be unchecked.** Have the answer before clicking one.
8. **Never close the last page.** One window, one page that navigates between sites.

## Command set

```bash
rotunda agent pages                      # page ids, urls, titles
rotunda agent describe <page>            # element tree with refs
rotunda agent navigate <page> <url>
rotunda agent extract <page> --format text|html|markdown|links|forms
rotunda agent fill <ref> "text"
rotunda agent click <ref>
rotunda agent select <ref> "<value>"     # --by label for the visible text
rotunda agent check <ref>
rotunda agent press <ref> <key>
rotunda agent scroll <page> <ref> down
rotunda agent info <ref>
rotunda agent screenshot <page> [path]
rotunda agent stop <profile>             # stop the daemon for a profile
```

Health check, read-only: `rotunda agent pages` plus `pgrep -x rotunda-bin | wc -l`. A daemon that
answers with valid refs while that count is 0 is a zombie: `pkill -x rotunda-bin`, remove
`~/.rotunda/agent/daemon.json` and `agent/sessions/*.json`, then `new-context`.

## Profiles

    prof_8ac20ec9fa70   virtus, headless — THIS one
    prof_a9c84ba06837   jobhunt (the job agent's browser, carries its logins)
    prof_3c9152548d6a   an earlier headed virtus profile, retired (it raised a window)

## Why headless, stated plainly

The owner's ruling: the browser must not come to the foreground or interfere with work. Headless is
the only mode that guarantees it — measured: a headless context + navigation + extraction left the
active window unchanged, while a headed context took focus on `new-context`. Fingerprint-sensitive
sites that reject headless are the one case where a headed run is justified, and only when the owner
asks for it.
