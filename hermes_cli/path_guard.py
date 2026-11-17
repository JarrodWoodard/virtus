"""Virtus sensitive-paths guard.

Wraps the file-tool dispatcher so that any read or write under a guarded path
(default-deny: ``~/.ssh/``, ``~/.gnupg/``, ``~/.aws/``, ``~/.config/gh/``,
``~/.kube/``, ``~/.netrc``, ``**/*.pem``, ``**/*.key``, ``**/id_rsa*``, the
user's shell rc files, and virtus's own secrets) pauses the run and asks for
explicit approval.

Three grant levels:
  - one-shot:    allow this single tool call
  - session:     allow for the rest of the process's lifetime (in-memory only)
  - always:      persist into ``sensitive_paths.allowed`` in config.yaml

The list is editable by the user via ``virtus config set sensitive-paths …``
helpers (see ``hermes_cli.config`` integration in setup-virtus.sh).

The guard does NOT block the tool dispatcher's existing approval flow. If a
sensitive-path tool call is denied, the tool dispatcher receives a
``PermissionError`` and surfaces it the same way it would any other tool
refusal. Approved paths return immediately to the dispatcher.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DEFAULT_GUARDED: tuple[str, ...] = (
    "~/.ssh/",
    "~/.gnupg/",
    "~/.aws/",
    "~/.config/gh/",
    "~/.kube/",
    "~/.netrc",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa*",
    "~/.bashrc",
    "~/.zshrc",
    "~/.profile",
    "~/.bash_profile",
    "~/.virtus/config.yaml",
    "~/.virtus/.env",
    "~/.virtus/auth.json",
    "~/.virtus/SOUL.md",
    "~/.virtus/AGENTS.md",
)


@dataclass
class GuardDecision:
    allowed: bool
    reason: str
    grant_level: str = ""  # "one-shot" | "session" | "always" | ""


@dataclass
class _SessionGrants:
    _paths: set[str] = field(default_factory=set)

    def grant(self, p: str) -> None:
        self._paths.add(p)

    def contains(self, p: str) -> bool:
        return p in self._paths


_SESSION = _SessionGrants()


def _expand(p: str) -> str:
    return os.path.expanduser(p)


def _matches_one(target: str, pattern: str) -> bool:
    """Match target against pattern. Supports ~/, ** globs, and literal paths."""
    pat = _expand(pattern)
    if pat.endswith("/") or "/" not in pat.replace("~", ""):
        # directory pattern → target must be inside it
        try:
            Path(target).resolve().relative_to(Path(pat).resolve())
            return True
        except (ValueError, OSError):
            return False
    return fnmatch.fnmatch(target, pat) or fnmatch.fnmatch(Path(target).name, pat)


def is_sensitive(path: str, guarded: Iterable[str]) -> str | None:
    """Return the matching guarded pattern if ``path`` is sensitive, else None."""
    if not path:
        return None
    target = os.path.abspath(_expand(path))
    for pat in guarded:
        if _matches_one(target, pat):
            return pat
    return None


def evaluate(
    path: str,
    operation: str,
    guarded: Iterable[str],
    allowed: Iterable[str],
    *,
    interactive: bool = True,
) -> GuardDecision:
    """Decide whether to allow ``operation`` on ``path``.

    ``interactive=True`` prompts on stdin when the path is sensitive and not
    pre-allowed. Set ``interactive=False`` (e.g. in non-TTY contexts, batch
    runs, or tests) to deny by default with a clear reason.
    """
    op = (operation or "access").lower()
    pattern = is_sensitive(path, guarded)
    if pattern is None:
        return GuardDecision(allowed=True, reason="path not in guard list")

    target = os.path.abspath(_expand(path))

    # already on the persisted allow list
    for ap in allowed:
        if _matches_one(target, ap):
            return GuardDecision(allowed=True, reason=f"allow-listed: {ap}", grant_level="always")

    # session-level grant
    if _SESSION.contains(target):
        return GuardDecision(allowed=True, reason="session-granted", grant_level="session")

    if not interactive:
        return GuardDecision(
            allowed=False,
            reason=f"[SENSITIVE PATH] {target} — {op} refused: matches guard pattern '{pattern}' (non-interactive)",
        )

    prompt = (
        f"[SENSITIVE PATH] {target} — {op}\n"
        f"This path matches the sensitive-paths guard (pattern: {pattern}).\n"
        f"Approve? [y/N] (or 'session' for this session, 'always' to whitelist): "
    )
    try:
        answer = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return GuardDecision(allowed=False, reason="no interactive response")

    if answer == "y" or answer == "yes":
        return GuardDecision(allowed=True, reason="one-shot approval", grant_level="one-shot")
    if answer == "session":
        _SESSION.grant(target)
        return GuardDecision(allowed=True, reason="session grant", grant_level="session")
    if answer == "always":
        # Persist via the caller; this module doesn't write config.yaml directly.
        return GuardDecision(allowed=True, reason="always grant (caller must persist)", grant_level="always")
    return GuardDecision(allowed=False, reason="user denied")


def load_guarded_from_config(config: dict) -> tuple[list[str], list[str]]:
    """Read ``sensitive_paths.{guarded,allowed}`` from a merged config dict."""
    sp = (config or {}).get("sensitive_paths") or {}
    guarded = list(sp.get("guarded") or DEFAULT_GUARDED)
    allowed = list(sp.get("allowed") or [])
    return guarded, allowed


def clear_session_grants() -> None:
    """Drop all session-level grants (used at process start and on /reset)."""
    _SESSION._paths.clear()
