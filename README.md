# virtus

A fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT licence; see `LICENSE`
and `NOTICE`.

## Install

Python 3.14 and git are required. `uv` provides Python 3.14, so the only thing you install from your
package manager is git (and uv if your distro packages it). No sudo is needed for the installer
itself; it writes only inside `$HOME`.

### Any Linux or macOS — one command

```bash
curl -fsSL https://raw.githubusercontent.com/JarrodWoodard/virtus/main/install.sh | bash
```

### Arch Linux / Omarchy

```bash
sudo pacman -S --needed git uv
git clone https://github.com/JarrodWoodard/virtus ~/.virtus/virtus-agent
~/.virtus/virtus-agent/install.sh
```

### Debian / Ubuntu

```bash
sudo apt update && sudo apt install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
git clone https://github.com/JarrodWoodard/virtus ~/.virtus/virtus-agent
~/.virtus/virtus-agent/install.sh
```

### Fedora

```bash
sudo dnf install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
git clone https://github.com/JarrodWoodard/virtus ~/.virtus/virtus-agent
~/.virtus/virtus-agent/install.sh
```

### macOS

```bash
brew install git uv
git clone https://github.com/JarrodWoodard/virtus ~/.virtus/virtus-agent
~/.virtus/virtus-agent/install.sh
```

Windows is not covered by these instructions.

### Installer options

```bash
~/.virtus/virtus-agent/install.sh -y             # do not ask before installing dependencies
~/.virtus/virtus-agent/install.sh --update       # pull the checkout only
~/.virtus/virtus-agent/install.sh --dry-run      # print the plan, change nothing
~/.virtus/virtus-agent/install.sh --dir PATH --bin PATH --ref REF
```

Re-running it is safe: an existing checkout is fast-forwarded, the virtualenv is reused, and the
launcher is rewritten. It asks before installing dependencies unless `-y` is given. If the copy of the
script you run is older than the checkout, it hands over to the checkout's copy.

## Run

```bash
virtus            # start a session
virtus setup      # choose a provider and model
virtus model      # change the model
virtus --help
```

## Files

```
~/.virtus/config.yaml                    settings
~/.virtus/profiles/<name>/config.yaml    per-profile settings
~/.virtus/.env                           API keys
~/.virtus/profiles/<name>/.env           API keys for one profile
~/.virtus/state.db                       sessions
~/.local/bin/virtus                      launcher
~/.virtus/install.log                    log of the last install or update
```

## Providers

```yaml
providers:
  qwen-local:
    api: http://127.0.0.1:8080/v1
    api_key: not-needed
    models: {Qwen3.8-27B: {}}
    reasoning_efforts: [low, medium, xhigh]
```

`reasoning_efforts`: the levels the server accepts. `model_catalog.visible_providers` restricts the
`virtus model` list; empty lists every provider.

## Licence

MIT. `LICENSE`, `NOTICE`. Upstream README: `docs/UPSTREAM-README.md`.
