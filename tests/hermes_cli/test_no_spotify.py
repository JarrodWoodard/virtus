"""Guard: Spotify is banned from Virtus.

The owner's ruling, 2026-11-15: "I want nothing to do with spotify, ban it."

Upstream keeps a Spotify integration in the plugin catalog and keeps a migration prompt
that walks users from `virtus auth spotify` to the third-party plugin's own login command.
Both are removed in this fork. A future upstream merge will re-introduce them, so this
test is the net: it fails if the integration returns in any runtime surface.

What it looks for (functional markers, not prose):
  - a module or import named auth_spotify / spotify_*
  - a provider or plugin registration for spotify
  - a plugin-catalog entry for spotify
  - the left-core migration predicate `spotify_in_use`
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

RUNTIME_DIRS = ("agent", "hermes_cli", "tools", "plugins", "cron", "gateway", "scripts")
FORBIDDEN = [
    (re.compile(r"\bauth_spotify\b"), "auth module / import"),
    (re.compile(r"\bspotify_in_use\b"), "left-core migration predicate"),
    (re.compile(r"^\s*(from|import)\s+spotify\b", re.M), "direct import"),
    (re.compile(r"plugin-catalog/spotify"), "catalog entry reference"),
]
CATALOG = ROOT / "plugin-catalog"


def _runtime_files():
    for d in RUNTIME_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".yaml", ".yml", ".json"}:
                if "/tests/" in str(p):
                    continue
                yield p


def test_no_spotify_integration_in_runtime_surfaces():
    hits = []
    for path in _runtime_files():
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        if "spotify" not in text.lower():
            continue
        for pattern, label in FORBIDDEN:
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)}: {label}")
    assert not hits, "Spotify is banned in Virtus; these surfaces re-introduce it:\n  " + "\n  ".join(hits)


def test_no_spotify_plugin_catalog_entry():
    if not CATALOG.is_dir():
        pytest.skip("no plugin catalog in this tree")
    offenders = [p.name for p in CATALOG.iterdir() if "spotify" in p.name.lower()]
    assert not offenders, f"Spotify catalog entries must not exist: {offenders}"
