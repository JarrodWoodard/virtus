"""Tests for per-model reasoning_effort override in cron scheduler."""

import pytest


class TestCronPerModelReasoningConfig:
    """Test cron scheduler respects per-model reasoning overrides.

    Rather than spinning up a full CronScheduler (heavy), we verify the
    resolution logic by testing the helper directly against a config dict
    shaped the same way the scheduler reads it.
    """

    def test_per_model_override_resolves_for_cron_model(self):
        """The spelling-tolerant helper resolves the cron config's model."""
        from hermes_constants import resolve_per_model_reasoning_effort

        # Simulate cron scheduler config shape
        _cfg = {
            "model": {"default": "anthropic/claude-opus-4.5"},
            "agent": {
                "reasoning_effort": "medium",
                "reasoning_overrides": {
                    "anthropic/claude-opus-4.5": "xhigh",
                },
            },
        }
        _model_cfg = _cfg.get("model", {})
        _model = str(_model_cfg.get("default", "") or "").strip()
        _overrides = (_cfg.get("agent", {}) or {}).get("reasoning_overrides", {}) or {}

        result = resolve_per_model_reasoning_effort(_model, _overrides)
        assert result is not None
        assert result["effort"] == "xhigh"

    def test_cron_falls_back_to_global_when_no_override(self):
        """When no per-model override matches, global effort is used."""
        from hermes_constants import parse_reasoning_effort, resolve_per_model_reasoning_effort

        _cfg = {
            "model": {"default": "gpt-5"},
            "agent": {
                "reasoning_effort": "low",
                "reasoning_overrides": {
                    "anthropic/claude-opus-4.5": "xhigh",
                },
            },
        }
        _model = _cfg["model"]["default"]
        _overrides = _cfg["agent"]["reasoning_overrides"]

        per_model = resolve_per_model_reasoning_effort(_model, _overrides)
        assert per_model is None  # no match

        # Scheduler falls back to global
        effort = _cfg["agent"]["reasoning_effort"]
        result = parse_reasoning_effort(effort)
        assert result is not None
        assert result["effort"] == "low"


    def test_global_fallback_with_yaml_false(self):
        """YAML boolean False must reach parse_reasoning_effort uncoerced.

        Regression: str(... or "").strip() turned False into "", silently
        re-enabling thinking. The raw value must pass through so
        parse_reasoning_effort(False) returns {'enabled': False}.
        """
        from hermes_constants import parse_reasoning_effort, resolve_per_model_reasoning_effort

        _cfg = {
            "model": {"default": "gpt-5"},
            "agent": {
                "reasoning_effort": False,  # YAML boolean, not string
                "reasoning_overrides": {"claude-opus-4.5": "xhigh"},
            },
        }
        _model = _cfg["model"]["default"]
        _overrides = _cfg["agent"]["reasoning_overrides"]

        per_model = resolve_per_model_reasoning_effort(_model, _overrides)
        assert per_model is None  # no match

        # Scheduler global fallback — raw value, no coercion
        result = parse_reasoning_effort(
            _cfg.get("agent", {}).get("reasoning_effort", "")
        )
        assert result is not None
        assert result.get("enabled") is False

    def test_minimax_m3_1_exact_case_override_wins_over_global_low(self):
        """The live ~/.virtus/config.yaml shape: global ``low``, M3.1 pinned to ``max``.

        Virtus always sends a concrete effort, so without the per-model override the
        model's own ``max`` default never applies. The override key is CASE-SENSITIVE —
        ``resolve_per_model_reasoning_effort`` matches canonical variants without
        casefolding, so a lowercase key silently resolves to None.
        """
        from hermes_constants import resolve_per_model_reasoning_effort

        _cfg = {
            "model": {"default": "MiniMax-M3.1-Flash-Preview"},
            "agent": {
                "reasoning_effort": "low",
                "reasoning_overrides": {"MiniMax-M3.1-Flash-Preview": "max"},
            },
        }
        _model = _cfg["model"]["default"]
        _overrides = _cfg["agent"]["reasoning_overrides"]

        result = resolve_per_model_reasoning_effort(_model, _overrides)
        assert result is not None
        assert result["enabled"] is True
        assert result["effort"] == "max"

        # The failure mode the exact-case key exists to prevent: same config, key lowercased.
        assert resolve_per_model_reasoning_effort(_model, {"minimax-m3.1-flash-preview": "max"}) is None
