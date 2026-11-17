"""Virtus posture switches must read config.yaml, and must actually gate.

Regression cover for two defects found 2026-11-15 while preparing the upstream merge:

1. Every helper in hermes_cli/virtus_config.py took `config: dict | None = None` and
   read `config or {}`, so a call with no argument returned the fallback. All six
   switches therefore read "off" regardless of config.yaml, which also made the
   documented opt-in (`virtus config set <key> true`) impossible.
2. models.dev network access is supposed to follow `models_dev.allow_network`.
   The test proves fetch_models_dev makes no request when the key is false.
"""

from __future__ import annotations

import textwrap

import pytest


def _write_config(home, body: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(textwrap.dedent(body))


def test_posture_helpers_read_config_yaml(tmp_path, monkeypatch):
    home = tmp_path / ".virtus"
    _write_config(home, """
        models_dev:
          allow_network: true
        curator:
          enabled: true
        updates:
          notify: true
        account_usage:
          fetch: true
        monitoring:
          enabled: true
        """)
    monkeypatch.setenv("HERMES_HOME", str(home))

    from hermes_cli import virtus_config as vc

    assert vc.models_dev_network_allowed() is True
    assert vc.curator_enabled() is True
    assert vc.updates_enabled() is True
    assert vc.account_usage_enabled() is True
    assert vc.monitoring_enabled() is True

    _write_config(home, """
        models_dev:
          allow_network: false
        curator:
          enabled: false
        updates:
          notify: false
        account_usage:
          fetch: false
        monitoring:
          enabled: false
        """)
    assert vc.models_dev_network_allowed() is False
    assert vc.curator_enabled() is False
    assert vc.updates_enabled() is False
    assert vc.account_usage_enabled() is False
    assert vc.monitoring_enabled() is False


def test_models_dev_never_dials_out_when_network_is_off(tmp_path, monkeypatch):
    home = tmp_path / ".virtus"
    _write_config(home, """
        models_dev:
          allow_network: false
        """)
    monkeypatch.setenv("HERMES_HOME", str(home))

    from agent import models_dev

    calls = []

    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        calls.append(args)
        raise AssertionError("models.dev made a network call with allow_network false")

    monkeypatch.setattr(models_dev.requests, "get", _boom)
    monkeypatch.setattr(models_dev, "_models_dev_cache", None, raising=False)
    monkeypatch.setattr(models_dev, "_models_dev_cache_time", 0.0, raising=False)

    result = models_dev.fetch_models_dev(force_refresh=True)

    assert calls == [], "the gate let a request through"
    assert result in (None, {})  # no disk cache in a fresh HERMES_HOME
