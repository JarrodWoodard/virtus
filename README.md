# virtus — the Dextral agent

A local-first agent for the terminal. It runs one agent per session, in a TUI you can attach to,
watch, interrupt and take over, with every conversation stored locally and nothing phoning home.

virtus is a fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT). The fork keeps
the engine and removes the parts that pointed somewhere else: no portal, no account, no plugin
marketplace, no shared-metrics reporting, and no borrowed logins from other tools.

## What it is

- **Local first.** Models can be local (llama.cpp on your own box, LM Studio, Ollama) or any
  OpenAI-compatible endpoint you configure. Credentials live in the profile's `.env`, never in git.
- **One session, one record.** Every conversation is a row in `state.db`, resumable by id from the CLI,
  the TUI or a script.
- **An agent you can watch.** The TUI streams reasoning and tool calls as they happen; `ctrl-c`
  interrupts the turn, and the same PTY takes your typing the moment you want it.
- **Boring about trust.** No telemetry, no update pings, no catalog fetching. Provider and model
  choices are declarative in `config.yaml`.

## Install

One command. No sudo, nothing written outside your home directory:

```bash
git clone https://github.com/JarrodWoodard/virtus ~/.virtus/virtus-agent
~/.virtus/virtus-agent/install.sh
```

The installer finds a Python 3.14 (through `uv` when it is present, a system 3.14 otherwise), creates
the virtualenv inside the checkout, installs the package, writes `~/.local/bin/virtus` with
`HERMES_HOME` pinned to `~/.virtus`, and proves the launcher answers `--version`. Re-run it to update;
`--update`, `--dir`, `--bin`, `--ref` and `--dry-run` are documented at the top of the script.

Python 3.14 is required, not 3.11: 46 dependency pins are gated on it, so an older interpreter resolves
an almost-empty dependency set and fails at first run.

`virtus setup` then picks a provider and model. Provider keys live in `~/.virtus/.env`; a named profile
reads only its own `~/.virtus/profiles/<name>/.env`.

`HERMES_HOME` selects the state root. The launcher in this repository's docs pins it to `~/.virtus`, so
the fork and an upstream install can live side by side without sharing profiles.

## Providers

`virtus model` offers whichever providers you have credentials for, plus local options. A saved custom
provider is a block in `config.yaml`:

```yaml
providers:
  qwen-local:
    api: http://127.0.0.1:8080/v1
    api_key: not-needed
    models: {Qwen3.8-27B: {}}
    reasoning_efforts: [low, medium, xhigh]   # declare it; the clamp then keeps requests valid
```

That last line matters for servers on another host: without it, a session-pinned reasoning level is
passed through unchanged and a strict chat template answers HTTP 500 instead of a completion.

## What this fork changes

| area | change |
|---|---|
| network egress | the plugin catalog is never fetched and nothing auto-installs |
| accounts | portal, account and usage checks are gone; no external login is borrowed |
| prompting | the built-in "act, don't ask" text can be exempted per profile, and a profile can opt into answering questions instead of treating them as tasks |
| brand | Dextral palette and mark, in the TUI, the banner and the exported HTML |
| distribution | ships as source; there is no store build and no self-update channel |

## Layout note

The internal module layout is inherited from upstream and keeps its names (`hermes_cli/`,
`hermes_constants.py`, `HERMES_*` environment variables). Renaming them would break every future
upstream merge for no reader's benefit. Everything a user reads or types is `virtus`.

## Licence

MIT. See `LICENSE` and `NOTICE`. The original copyright notice from Nous Research is preserved; this
fork adds its own.

Upstream's own README is kept for reference at `docs/UPSTREAM-README.md`.
