#!/usr/bin/env bash
# virtus installer — one command, no sudo, nothing outside your home directory.
#
#   git clone https://github.com/JarrodWoodard/virtus ~/.virtus/virtus-agent
#   ~/.virtus/virtus-agent/install.sh
#
# or, once the repository is public:
#
#   curl -fsSL https://raw.githubusercontent.com/JarrodWoodard/virtus/main/install.sh | bash
#
# What it does, in order: find (or fetch) a Python 3.14, create the virtualenv inside the checkout,
# install the package into it, write a launcher that pins HERMES_HOME so this fork never shares state
# with an upstream install, and prove the result answers `--version`.
#
# Re-run it any time: an existing checkout is fast-forwarded, the venv is reused, the launcher is
# rewritten. Options:
#   --update        pull the checkout only, skip the dependency install
#   --dir PATH      install somewhere other than ~/.virtus/virtus-agent
#   --bin PATH      put the launcher somewhere other than ~/.local/bin
#   --ref REF       check out a branch or tag instead of the default branch
#   --dry-run       print the plan, change nothing
set -euo pipefail

REPO_URL="${VIRTUS_REPO_URL:-https://github.com/JarrodWoodard/virtus.git}"
INSTALL_DIR="${VIRTUS_INSTALL_DIR:-$HOME/.virtus/virtus-agent}"
BIN_DIR="${VIRTUS_BIN_DIR:-$HOME/.local/bin}"
STATE_DIR="$(dirname "$INSTALL_DIR")"          # ~/.virtus — the HERMES_HOME the launcher pins
REF=""
UPDATE_ONLY=0
DRY_RUN=0
PY_MIN="3.14"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf '\n  ERROR: %s\n\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --update) UPDATE_ONLY=1 ;;
    --dir) INSTALL_DIR="$2"; STATE_DIR="$(dirname "$2")"; shift ;;
    --bin) BIN_DIR="$2"; shift ;;
    --ref) REF="$2"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

run() { if [ "$DRY_RUN" = 1 ]; then printf '  would run: %s\n' "$*"; else "$@"; fi; }

bold "virtus installer"
info "checkout : $INSTALL_DIR"
info "launcher : $BIN_DIR/virtus"
info "state    : $STATE_DIR  (HERMES_HOME)"

# 1. git
command -v git >/dev/null 2>&1 || die "git is required. Install it first (pacman -S git)."

# 2. the checkout
if [ -d "$INSTALL_DIR/.git" ]; then
  info "existing checkout found — fast-forwarding"
  run git -C "$INSTALL_DIR" fetch --quiet --all --tags
  if [ -n "$REF" ]; then
    run git -C "$INSTALL_DIR" checkout --quiet "$REF"
  else
    run git -C "$INSTALL_DIR" pull --ff-only --quiet || warn "could not fast-forward (local changes?); continuing with what is there"
  fi
else
  info "cloning"
  run mkdir -p "$(dirname "$INSTALL_DIR")"
  if [ -n "$REF" ]; then
    run git clone --quiet --branch "$REF" "$REPO_URL" "$INSTALL_DIR"
  else
    run git clone --quiet "$REPO_URL" "$INSTALL_DIR"
  fi
fi
[ "$DRY_RUN" = 1 ] || [ -d "$INSTALL_DIR" ] || die "checkout missing after clone"

if [ "$UPDATE_ONLY" = 1 ]; then
  bold "updated (dependencies untouched)"
  exit 0
fi

# 3. a Python the pinned dependency set actually targets.
#    The dependency block is gated on python_version >= 3.14, so an older interpreter resolves an
#    almost-empty set and fails at first run. Find 3.14, or let uv fetch one.
PY=""
if command -v uv >/dev/null 2>&1; then
  info "uv found — using the interpreter it manages"
  run uv python install "$PY_MIN" >/dev/null 2>&1 || warn "uv could not fetch Python $PY_MIN; trying a system interpreter"
  PY="$(uv python find "$PY_MIN" 2>/dev/null || true)"
fi
if [ -z "$PY" ]; then
  for candidate in "python$PY_MIN" "python3"; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,14) else 1)" 2>/dev/null; then
        PY="$(command -v "$candidate")"
        break
      fi
    fi
  done
fi
[ -n "$PY" ] || die "Python $PY_MIN is required (the dependency pins are gated on it).
  Either install uv (curl -LsSf https://astral.sh/uv/install.sh | sh) and re-run this installer,
  or install Python $PY_MIN from your distro."

info "python   : $PY ($("$PY" -V 2>&1))"

# 4. venv + install
VENV="$INSTALL_DIR/venv"
if [ ! -x "$VENV/bin/python" ]; then
  info "creating virtualenv"
  if command -v uv >/dev/null 2>&1; then
    run uv venv --python "$PY" "$VENV"
  else
    run "$PY" -m venv "$VENV"
  fi
fi
info "installing virtus (this is the slow step, one to three minutes)"
if command -v uv >/dev/null 2>&1; then
  run uv pip install --quiet --python "$VENV/bin/python" -e "$INSTALL_DIR"
else
  run "$VENV/bin/python" -m pip install --quiet --upgrade pip
  run "$VENV/bin/python" -m pip install --quiet -e "$INSTALL_DIR"
fi

# 5. the launcher. HERMES_HOME is pinned so this fork's profiles, sessions and credentials live under
#    $STATE_DIR and never collide with an upstream install's ~/.hermes.
run mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/virtus"
if [ "$DRY_RUN" = 1 ]; then
  printf '  would write: %s\n' "$LAUNCHER"
else
  cat > "$LAUNCHER" <<LAUNCH
#!/usr/bin/env bash
# virtus launcher — written by install.sh. HERMES_HOME pins this fork's state root.
export HERMES_HOME="$STATE_DIR"
exec "$VENV/bin/python" "$INSTALL_DIR/virtus" "\$@"
LAUNCH
  chmod +x "$LAUNCHER"
fi

# 6. prove it runs
if [ "$DRY_RUN" = 1 ]; then
  bold "dry run complete — nothing was changed"
  exit 0
fi
# No pipe to head here: under `set -o pipefail` head's SIGPIPE makes a working launcher look broken.
if version="$("$LAUNCHER" --version 2>&1)"; then
  bold "installed"
  info "${version%%$'\n'*}"
else
  die "the launcher did not run. Try $VENV/bin/python $INSTALL_DIR/virtus --version and report the error."
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on PATH — add it to your shell rc, or run $LAUNCHER directly" ;;
esac

cat <<NEXT

  next:  virtus setup        # pick a provider and model
         virtus              # start a session
         virtus model        # change the model later
         virtus --help

  state lives in $STATE_DIR (config.yaml, profiles/, state.db)
  remove everything:  rm -rf $LAUNCHER \
                        $( [ "$INSTALL_DIR" = "$STATE_DIR" ] && echo "$INSTALL_DIR" || echo "$INSTALL_DIR $STATE_DIR" )
NEXT
