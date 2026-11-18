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
#   -y, --yes       do not ask before installing dependencies
set -euo pipefail

ORIG_ARGS=("$@")   # kept whole: the hand-over below must re-run with the same options

REPO_URL="${VIRTUS_REPO_URL:-https://github.com/JarrodWoodard/virtus.git}"
INSTALL_DIR="${VIRTUS_INSTALL_DIR:-$HOME/.virtus/virtus-agent}"
BIN_DIR="${VIRTUS_BIN_DIR:-$HOME/.local/bin}"
STATE_DIR="$(dirname "$INSTALL_DIR")"          # ~/.virtus — the HERMES_HOME the launcher pins
REF=""
UPDATE_ONLY=0
DRY_RUN=0
ASSUME_YES=0
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
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

run() { if [ "$DRY_RUN" = 1 ]; then printf '  would run: %s\n' "$*"; else "$@"; fi; }

# Everything is logged. On a machine I cannot see, the log is the only way to know what failed, and a
# resolver error without its cause is what made the first reports useless.
LOG="$STATE_DIR/install.log"
if [ "$DRY_RUN" = 0 ]; then
  mkdir -p "$STATE_DIR"
  exec > >(tee -a "$LOG") 2>&1
  echo "=== virtus install $(date -Is) ===" >> "$LOG"
fi

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
  PULLED=0
  if [ -n "$REF" ]; then
    run git -C "$INSTALL_DIR" checkout --quiet "$REF"
  else
    if run git -C "$INSTALL_DIR" pull --ff-only --quiet; then
      PULLED=1
    else
      # A checkout from an earlier attempt (local edits, a detached HEAD, an old branch) would keep
      # running old logic and an old lock forever. The install directory is not a workspace: force it
      # to the remote and say so.
      _branch="$(git -C "$INSTALL_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
      [ "$_branch" = "HEAD" ] && _branch="main"
      warn "fast-forward failed — forcing the checkout to origin/$_branch (local edits there are discarded)"
      if run git -C "$INSTALL_DIR" fetch --quiet origin && \
         run git -C "$INSTALL_DIR" reset --hard --quiet "origin/$_branch"; then
        PULLED=1
      else
        warn "could not update the checkout at all; continuing with what is there"
      fi
    fi
  fi
  # A copy of this script that is older than the checkout will keep doing whatever the old version did,
  # no matter how often it is re-run. Hand over to the checkout's own installer instead.
  # Only hand over when the checkout actually advanced: handing over to a copy that is older than the
  # one running would move backwards.
  if [ "$DRY_RUN" = 0 ] && [ "${PULLED:-0}" = 1 ] && [ "${VIRTUS_INSTALL_REEXEC:-0}" = 0 ] && [ -f "$0" ] \
     && [ -f "$INSTALL_DIR/install.sh" ] && ! cmp -s "$0" "$INSTALL_DIR/install.sh"; then
    info "this copy of the installer is older than the checkout — handing over to $INSTALL_DIR/install.sh"
    VIRTUS_INSTALL_REEXEC=1 exec bash "$INSTALL_DIR/install.sh" "${ORIG_ARGS[@]}"
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

# 3. A Python 3.14. The system one is preferred: it already ships pip, so the install needs nothing
#    beyond git and Python. uv is used only to OBTAIN a 3.14 when the system does not have one.
PY=""
for candidate in python3.14 python3; do
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,14) else 1)" 2>/dev/null; then
    PY="$(command -v "$candidate")"
    break
  fi
done
if [ -z "$PY" ] && command -v uv >/dev/null 2>&1; then
  info "no system Python $PY_MIN — uv will provide one"
  uv python install "$PY_MIN" >/dev/null 2>&1 || warn "uv could not fetch Python $PY_MIN"
  PY="$(uv python find "$PY_MIN" 2>/dev/null || true)"
fi
info "python   : ${PY:-none} $([ -n "$PY" ] && "$PY" -V 2>&1)"
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 14) else 1)' 2>/dev/null; then
  die "found $("$PY" -V 2>&1) at $PY, but Python 3.14 is required.
  Install uv (curl -LsSf https://astral.sh/uv/install.sh | sh) and re-run, or install Python 3.14.
  uv version: $(command -v uv >/dev/null 2>&1 && uv --version || echo 'not installed')"
fi

# 4. venv + install
VENV="$INSTALL_DIR/venv"
if [ ! -x "$VENV/bin/python" ]; then
  info "creating virtualenv"
  if ! run "$PY" -m venv "$VENV"; then
    warn "python -m venv failed (missing ensurepip?) — falling back to uv venv"
    run uv venv --python "$PY" "$VENV"
  fi
fi
if [ "$DRY_RUN" = 0 ] && [ "$ASSUME_YES" = 0 ] && [ -t 0 ]; then
  printf '  Install the project dependencies into %s now? [Y/n] ' "$VENV"
  read -r _answer || _answer=""
  case "$_answer" in
    n|N|no|NO) die "stopped before installing dependencies. Re-run with -y to skip this question." ;;
  esac
fi

info "installing virtus (this is the slow step, one to three minutes)"
install_failed=0

# No resolver runs here. requirements.lock.txt is exported from uv.lock, every pin is exact, and
# `pip install --no-deps` takes it literally: there is nothing to solve, so "No solution found when
# resolving dependencies" cannot happen. That message cost three rounds on two machines; the fix is to
# stop asking a resolver to re-derive a set that is already pinned.
ensure_pip() {
  "$VENV/bin/python" -m pip --version >/dev/null 2>&1 && return 0
  "$VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 && return 0
  command -v uv >/dev/null 2>&1 && uv pip install --quiet pip --python "$VENV/bin/python" >/dev/null 2>&1
}

LOCK="$INSTALL_DIR/requirements.lock.txt"
if [ ! -f "$LOCK" ] && [ "$DRY_RUN" = 0 ]; then
  warn "the checkout has no requirements.lock.txt — forcing it to origin/main to obtain one"
  _b="$(git -C "$INSTALL_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
  [ "$_b" = "HEAD" ] && _b="main"
  git -C "$INSTALL_DIR" fetch --quiet origin 2>/dev/null && git -C "$INSTALL_DIR" reset --hard --quiet "origin/$_b" 2>/dev/null || true
fi

if [ -f "$LOCK" ]; then
  info "installing from requirements.lock.txt ($(grep -c '==' "$LOCK" 2>/dev/null || echo '?') pinned packages, no resolver)"
  if ensure_pip; then
    ( cd "$INSTALL_DIR" && "$VENV/bin/python" -m pip install --no-deps --quiet --disable-pip-version-check -r requirements.lock.txt ) || install_failed=1
  else
    warn "could not bootstrap pip into the venv"
    install_failed=1
  fi
else
  # Deliberately no fallback that resolves dependencies. This project cannot be resolved from the
  # manifest (browser-harness pins pillow==12.3.0, the project requires Pillow 13), so a resolving
  # install fails 100% of the time with "No solution found when resolving dependencies". Failing here
  # with the reason beats failing there with a message that hides it.
  warn "no requirements.lock.txt in $INSTALL_DIR after forcing the checkout to origin/$_b"
  warn "the checkout is not a usable copy of the repository"
  die "cannot install without the exported lock. Remove the checkout and clone again: rm -rf $INSTALL_DIR"
fi

if [ "$install_failed" = 0 ] && [ "$DRY_RUN" = 0 ]; then
  if ! "$VENV/bin/python" -m pip show virtus-agent >/dev/null 2>&1; then
    warn "the project itself did not install"
    install_failed=1
  fi
fi

if [ "$install_failed" = 1 ] && [ "$DRY_RUN" = 0 ]; then
  warn "install failed; the last 15 lines of the log:"
  tail -15 "$LOG" 2>/dev/null | sed 's/^/    /' >&2 || true
fi

if [ "$install_failed" = 1 ] && [ "$DRY_RUN" = 0 ]; then
  warn "environment: $("$VENV/bin/python" -V 2>&1) · $(uv --version 2>/dev/null || echo 'uv none') · $(uname -sm)"
  warn "lock: $([ -f "$INSTALL_DIR/uv.lock" ] && echo present || echo absent)"
  warn "log:  $LOG"
  die "dependency installation failed — the last lines above and $LOG name the cause"
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
