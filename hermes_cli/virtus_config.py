"""Virtus-only feature switches read from `~/.virtus/config.yaml`.

The upstream DEFAULT_CONFIG dict in `hermes_cli/config_defaults.py` is the
canonical schema; these helpers consume the merged-config dict for the
few block-names added by the fork. Pure functions; no upstream surface
modification.
"""

from __future__ import annotations

from typing import Any


def _safe_get(cfg: dict, *keys: str, default: Any = None) -> Any:
    cur: Any = cfg
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _merged(config: dict | None) -> dict:
    """The config these helpers read.

    Every call site passes no argument, so reading only the passed dict made each
    helper return its fallback unconditionally: the switches read as "off" no
    matter what config.yaml said, which also made the documented opt-in
    (`virtus config set <key> true`) impossible. Load the merged config instead.
    """
    if config is not None:
        return config
    try:
        from hermes_cli.config import load_config

        return load_config() or {}
    except Exception:  # pragma: no cover - a broken config must not break the agent loop
        return {}


def _virtus_from_defaults_or(config: dict, *path: str, fallback: Any) -> Any:
    if config is None:
        return fallback
    val = _safe_get(config, *path)
    if val is None:
        return fallback
    return val


def updates_enabled(config: dict | None = None) -> bool:
    """`updates.notify` — banner / daemon / pre-fetch of upstream version."""
    return bool(_virtus_from_defaults_or(
        _merged(config), "updates", "notify", fallback=False,
    ))


def maintenance_enabled(config: dict | None = None) -> bool:
    """`updates.auto_maintenance` — cron-driven DB compaction etc."""
    return bool(_virtus_from_defaults_or(
        _merged(config), "updates", "auto_maintenance", fallback=False,
    ))


def account_usage_enabled(config: dict | None = None) -> bool:
    """`account_usage.fetch` — per-OAuth-credential balance / quota reads."""
    return bool(_virtus_from_defaults_or(
        _merged(config), "account_usage", "fetch", fallback=False,
    ))


def models_dev_network_allowed(config: dict | None = None) -> bool:
    """`models_dev.allow_network` — default OFF so the catalog is read from
    the on-disk cache. Opt in for one boot with the usual config set."""
    return bool(_virtus_from_defaults_or(
        _merged(config), "models_dev", "allow_network", fallback=False,
    ))


def plugin_catalog_network_allowed(config: dict | None = None) -> bool:
    """`plugins.catalog_allow_network` — the live plugin-catalog fetch.

    Upstream refreshes a 2,378-entry third-party plugin catalog from
    hermes-agent.nousresearch.com every six hours. Virtus does not fetch it unless the owner opts
    in: the in-tree catalog still works for an explicit install, and nothing is downloaded,
    parsed or offered from a remote manifest by default.
    """
    return bool(_virtus_from_defaults_or(
        _merged(config), "plugins", "catalog_allow_network", fallback=False,
    ))


def monitoring_enabled(config: dict | None = None) -> bool:
    """OTLP / observability export. Off by default — the entire upstream
    `monitoring` block is treated as inactive unless this returns True AND
    the user has set an endpoint."""
    return bool(_virtus_from_defaults_or(
        _merged(config), "monitoring", "enabled", fallback=False,
    ))


# Back-compat alias for the early-return guard in `banner.py`.
def _virtus_updates_enabled(config: dict | None = None) -> bool:  # noqa: D401
    return updates_enabled(config)


def curator_enabled(config: dict | None = None) -> bool:
    """Virtus flips the upstream default ``curator.enabled`` (True) to False.
    Opt in with `virtus config set curator.enabled true` AND restart.

    The fallback is False because the upstream ``DEFAULT_CONFIG`` still has
    ``curator.enabled: True``; this helper is the fork's opt-in gate, so it
    requires an explicit True from the merged config to run.
    """
    # Owner ruling: OFF everywhere, and a config line cannot switch it on. The old gate read the
    # MERGED config, so on any box whose file had no `curator:` key the upstream default (True) won —
    # and a process that resolved HERMES_HOME to ~/.hermes instead of ~/.virtus found that default and
    # ran the curator anyway. The environment is now the only way to ask for it:
    #   VIRTUS_CURATOR=1 virtus
    import os as _os
    if _os.environ.get("VIRTUS_CURATOR", "").strip() not in ("1", "true", "yes", "on"):
        return False
    val = _virtus_from_defaults_or(_merged(config), "curator", "enabled", fallback=False)
    return val is True


def _virtus_curator_enabled(config: dict | None = None) -> bool:
    return curator_enabled(config)


# Reference imports for callers that want them under one name.
__all__ = [
    "updates_enabled",
    "maintenance_enabled",
    "account_usage_enabled",
    "models_dev_network_allowed",
    "monitoring_enabled",
    "plugin_catalog_network_allowed",
    "curator_enabled",
    "_virtus_updates_enabled",
    "_virtus_curator_enabled",
]
