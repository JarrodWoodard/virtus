---
name: virtus-agent
description: "Virtus operating manual — config, security, autonomy gates."
version: 3.2.0
author: Virtus maintainers
license: MIT
platforms: [linux, macos, windows]
metadata:
  virtus:
    tags: [virtus, config, security, paths, curator, skills, memory, agents]
    homepage: file://~/.virtus/
    related_skills: []
---

# Virtus

Virtus is a local fork of Hermes Agent. The fork ships with three guarantees that the upstream version does not:

1. **No automatic skill formation.** Skill creation is user-instigated only. The agent must propose (name, path, content) and wait for go-ahead before calling `skill_manage`. Skill writes are gated by `skills.write_approval: true` in `~/.virtus/config.yaml` — every write goes to `~/.virtus/skills/.pending/` until the user runs `/skills approve <id>` or `/skills reject <id>`.
2. **No auto-extract of facts about the user.** No plugin memory provider is loaded by default (`memory.provider: ""`), so `MemoryManager.on_session_end` never fires. The agent CAN write to `~/.virtus/memories/USER.md` and `MEMORY.md` when the user explicitly asks, but never from a fork after session boundaries.
3. **No silent self-modification.** The agent must not modify its own skills, prompts, SOUL.md, AGENTS.md, config, or behavior unless the user explicitly asks in the current conversation.

If the user asks you to "save a skill" or "remember this", do it — those are explicit requests. If you find yourself wanting to summarize the conversation for memory, or consolidate skills, or update the SOUL — **stop and ask first**. Auto-extraction is what the user explicitly rejected.

## What's different from upstream Hermes

| Behavior | Upstream default | Virtus default |
|---|---|---|
| Per-turn background review fork | ON | **OFF** (`auxiliary.background_review.enabled: false`) |
| Idle curator (skill auto-archive + merge) | ON, 7-day | **OFF** (`curator.enabled: false`) |
| Memory auto-extract at session boundary | ON if provider configured | **OFF** (`memory.provider: ""`) |
| Skill writes | Direct to `~/.hermes/skills/` | **Gated** to `~/.virtus/skills/.pending/` |
| Sensitive path reads (`~/.ssh/`, etc.) | Unrestricted | **Default-deny** with three grant levels |
| Update-check banner / `virtus update` | ON | **OFF** (`updates.notify: false`) |
| Account-usage fetch for OAuth providers | ON | **OFF** (`account_usage.fetch: false`) |
| models.dev network refresh | ON | **OFF** (`models_dev.allow_network: false`) |
| OTLP monitoring export | ON | **OFF** (`monitoring.enabled: false`) |

All of these are user-controllable. To opt back into any behavior, set the corresponding config flag to true in `~/.virtus/config.yaml` — the user manages the agent, not the other way around.

## Side-by-side operation

Virtus and upstream Hermes live side by side, isolated:

- Hermes code: `~/.hermes/hermes-agent/`, state `~/.hermes/`, CLI `hermes`
- Virtus code: `~/.virtus/virtus-agent/`, state `~/.virtus/`, CLI `virtus`

Each has its own Python venv, editable-install finder, and SQLite state DB. If the user asks you to do something on hermes, use the `hermes` CLI / read files under `~/.hermes/` / write to `~/.hermes/state.db` — that's hermes's state, not virtus's. Don't touch upstream files when the user is in a virtus session.

## Slash commands (CLI surface; TUI has fewer)

| Slash | What |
|---|---|
| `/help` | List all slash commands |
| `/exit` | Quit (CLI only) |
| `/new`, `/resume` | Start / resume a session |
| `/copy [N]` | Copy last (or Nth-from-last) assistant response to clipboard |
| `/memory pending` / `/memory approve <id>` / `/memory reject <id>` | Stage and review memory writes (gated by `memory.write_approval`) |
| `/skills pending` / `/skills approve <id>` / `/skills reject <id>` | Stage and review skill writes (gated by `skills.write_approval`) |
| `/learn <what>` | Build a skill from the user's description (still user-instigated; uses `/skills pending` after) |
| `/curator status` | Verify curator is disabled |
| `/virtus sync upstream` | Dry-run upstream merge check (the only update mechanism) |

## Sensitive paths

Default-deny list (configurable in `~/.virtus/config.yaml:sensitive_paths.guarded`):
- `~/.ssh/`, `~/.gnupg/`, `~/.aws/`, `~/.config/gh/`, `~/.kube/`, `~/.netrc`
- `**/*.pem`, `**/*.key`, `**/id_rsa*`
- `~/.bashrc`, `~/.zshrc`, `~/.profile`, `~/.bash_profile`

If a tool call targets any of these paths, the dispatcher (`model_tools._pre_dispatch_guards`) pauses and emits an inline prompt:

```
[SENSITIVE PATH] /home/jarrod/.ssh/id_rsa — read
This path matches the sensitive-paths guard (pattern: ~/.ssh/).
Approve? [y/N] (or 'session' for this session, 'always' to whitelist):
```

Three grant levels: `y` (one-shot), `session` (in-memory until process exit), `always` (persists to `sensitive_paths.allowed`). Never bypass this gate silently — if the user explicitly asks you to read `~/.ssh/id_rsa`, **offer alternatives first** (public-key half `.pub`, fingerprint, metadata via `ssh-keygen -lf`, or "I'd need explicit `always` approval to read the private key — want me to walk you through alternatives?"). Default deny is the right default.

## Wake word

Default phrase: **"hey virtus"** (was "hey hermes" upstream). The bundled openwakeword model file is still `tools/wakewords/hey_hermes.onnx` because the audio model is trained on that phoneme sequence and can't be renamed without breaking detection. The displayed label and the agent's response to a wake event use "hey virtus".

## Fork update flow

Virtus tracks upstream `NousResearch/hermes-agent:main` via a local fork branch (`upstream`). Use `virtus sync upstream [--apply]` to dry-run a merge or apply it. **Never** run `git pull upstream main` directly without checking — there will be conflicts in the branding/identity commits.

The fork is **7 commits ahead** of upstream as of last build, and the gap is the fork's identity. A `git fetch upstream main` will bring in upstream-only fixes; an `--apply` will attempt the merge.

## What this skill is NOT

This skill ships **only** `SKILL.md` — no `references/`, no `templates/`, no upstream documentation. If the user asks "how do I do X in virtus" and X is not in the sections above, the answer is that virtus doesn't do X. Don't invent a process, don't recite upstream behavior, don't suggest installing a Nous plugin or a portal feature — those don't exist in this fork.

If the user wants upstream-specific documentation, point them at https://github.com/NousResearch/hermes-agent (the project this fork is built from) — they can read upstream docs there, but the agent should not load or recite them in this session unless explicitly asked.

## Verification

Before recommending changes to the user, verify in this order:

1. Read `~/.virtus/config.yaml` to confirm the user's current setting.
2. Read the relevant file in `~/.virtus/virtus-agent/` (the fork tree) — not in upstream.
3. If the change touches the fork tree, run `git status` and `git diff` first to see what's already changed.
4. After making changes, run `virtus --version` to confirm the fork still loads.
