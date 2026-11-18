"""Guard: the skill curator must stay off by default.

It writes and patches skills on its own at TUI startup and after sessions. Turning it off in one
machine's config.yaml is not enough — a fresh install reads the shipped default, which is how it came
back on a new box. This test fails if either default flips back to ON.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_shipped_default_is_off():
    text = (ROOT / "hermes_cli/config_defaults.py").read_text()
    block = re.search(r'"curator":\s*\{(.*?)\n    \}', text, re.S)
    assert block, "curator block not found in config_defaults.py"
    enabled = re.search(r'"enabled":\s*(\w+)', block.group(1))
    assert enabled, "curator.enabled not found"
    assert enabled.group(1) == "False", (
        "curator.enabled must default to False: it writes skills without being asked"
    )


def test_runtime_fallback_is_off():
    text = (ROOT / "agent/curator.py").read_text()
    assert 'get("enabled", False)' in text, (
        "agent.curator.is_enabled() must default to False when the config has no key"
    )


def test_config_cannot_switch_it_on():
    """A stray `curator.enabled: true` must not be enough: only the environment can ask for it."""
    import os
    import tempfile
    from pathlib import Path

    home = Path(tempfile.mkdtemp())
    (home / ".virtus").mkdir()
    (home / ".virtus" / "config.yaml").write_text("curator:\n  enabled: true\n")
    saved = {k: os.environ.get(k) for k in ("HERMES_HOME", "VIRTUS_CURATOR")}
    try:
        os.environ["HERMES_HOME"] = str(home / ".virtus")
        os.environ.pop("VIRTUS_CURATOR", None)
        from agent.curator import is_enabled as check
        assert check() is False, "config alone must not enable the curator"
        os.environ["VIRTUS_CURATOR"] = "1"
        assert check() is True, "VIRTUS_CURATOR=1 is the documented opt-in"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_run_gate_requires_the_environment():
    """The gate the startup pass actually calls must be closed without VIRTUS_CURATOR=1."""
    import os
    from hermes_cli.virtus_config import curator_enabled

    saved = os.environ.pop("VIRTUS_CURATOR", None)
    try:
        # A merged config carrying upstream's default (True) must still not open the gate.
        assert curator_enabled({"curator": {"enabled": True}}) is False
        os.environ["VIRTUS_CURATOR"] = "1"
        assert curator_enabled({"curator": {"enabled": True}}) is True
        assert curator_enabled({"curator": {"enabled": False}}) is False
    finally:
        os.environ.pop("VIRTUS_CURATOR", None)
        if saved is not None:
            os.environ["VIRTUS_CURATOR"] = saved
