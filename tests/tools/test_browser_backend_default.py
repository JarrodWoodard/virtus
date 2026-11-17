"""Fork contract: the Browser Use CLI never becomes the browser stack implicitly.

``tools.browser_use_cli.is_browser_use_cli_mode()`` is the gate that swaps
``browser_exec`` in for the built-in ``browser_*`` tools. The Browser Use CLI is
a third-party dependency (fork posture: third-party backends are explicit opt-in
only, same as third-party TTS), so the gate must open ONLY on explicit
``browser.backend: browser-use`` — not on the CLI being installed or runnable.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".virtus"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def _write_browser_config(home: Path, backend) -> None:
    if backend is None:
        text = "model:\n  default: test-model\n"
    else:
        text = f"browser:\n  backend: {backend}\n"
    (home / "config.yaml").write_text(text)


def _fake_cli_on_path(tmp_path, monkeypatch) -> Path:
    """A real, discoverable ``browser-use`` executable on PATH (no mocks)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    cli = bindir / "browser-use"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")
    return cli


def test_discoverable_cli_does_not_enable_browser_use(hermes_home, tmp_path, monkeypatch):
    """The core contract: an installed/runnable CLI must not replace the local stack."""
    _write_browser_config(hermes_home, None)
    _fake_cli_on_path(tmp_path, monkeypatch)
    from tools.browser_use_cli import is_browser_use_cli_mode
    assert is_browser_use_cli_mode() is False


def test_explicit_backend_enables_browser_use(hermes_home):
    _write_browser_config(hermes_home, "browser-use")
    from tools.browser_use_cli import is_browser_use_cli_mode
    assert is_browser_use_cli_mode() is True


def test_off_backend_keeps_builtin_tools(hermes_home):
    """YAML 1.1 parses unquoted ``off`` as False — that must mean disabled, not unset."""
    _write_browser_config(hermes_home, "off")
    from tools.browser_use_cli import get_browser_backend, is_browser_use_cli_mode
    assert get_browser_backend() == "off"
    assert is_browser_use_cli_mode() is False


def test_unset_backend_keeps_builtin_tools(hermes_home):
    _write_browser_config(hermes_home, None)
    from tools.browser_use_cli import get_browser_backend, is_browser_use_cli_mode
    assert get_browser_backend() == ""
    assert is_browser_use_cli_mode() is False


def test_no_downgrade_notice(hermes_home):
    """Built-in is the default, so there is nothing to 'downgrade' and nothing to nag about."""
    _write_browser_config(hermes_home, None)
    from tools.browser_use_cli import default_downgrade_notice
    assert default_downgrade_notice() is None
