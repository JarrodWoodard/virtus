"""Regression tests for #83220: oversized approvals.timeout must never
overflow platform wait primitives (macOS time_t OverflowError).

The clamp lives at the single config-read site (_get_approval_timeout), so
every consumer — CLI prompt thread.join, gateway poll deadline, human-wait
ceiling, and the tool_executor authorization gate — is covered at once.
"""

from __future__ import annotations

import threading

from unittest.mock import patch

from agent.deadline import MAX_SAFE_TIMEOUT_S


def _with_configured_timeout(value):
    return patch(
        "tools.approval_context._get_approval_config",
        return_value={"timeout": value},
    )


class TestApprovalTimeoutOverflowClamp:
    def test_normal_value_passes_through(self):
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(300):
            assert _get_approval_timeout() == 300

    def test_oversized_value_clamped(self):
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(10**18):
            assert _get_approval_timeout() == int(MAX_SAFE_TIMEOUT_S)

    def test_invalid_value_falls_back_to_default(self):
        from tools.approval_context import _get_approval_timeout

        # virtus: SPEC #3a — fallback is the platform-safe ceiling (~1 year),
        #   not the upstream 300s. See config_defaults.py approvals.timeout.
        with _with_configured_timeout("soon"):
            assert _get_approval_timeout() == 31_536_000

    def test_oversized_float_value_clamped(self):
        # YAML `1e18` arrives as a float, not an int — different int() path
        # than the string/int forms; the clamp must cover it too.
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(1e18):
            assert _get_approval_timeout() == int(MAX_SAFE_TIMEOUT_S)



    def test_clamped_value_safe_for_lock_acquire(self):
        # The exact primitive that crashed in #83220: Lock.acquire on macOS
        # converts the relative timeout to an absolute time_t timestamp.
        from tools.approval_context import _get_approval_timeout

        with _with_configured_timeout(10**18):
            timeout = _get_approval_timeout()
        lock = threading.Lock()
        assert lock.acquire(timeout=timeout)  # would raise OverflowError unclamped
        lock.release()


    def test_human_wait_ceiling_inherits_clamp(self):
        from tools.approval_human_wait import human_wait_ceiling

        with _with_configured_timeout(10**18):
            ceiling = human_wait_ceiling()
        # The margin must not push the clamped timeout back past the safe cap.
        assert int(MAX_SAFE_TIMEOUT_S) <= ceiling <= MAX_SAFE_TIMEOUT_S
        lock = threading.Lock()
        assert lock.acquire(timeout=ceiling)
        lock.release()

    def test_authorization_gate_timeout_safe_and_extends_with_config(self):
        # The gate bound must (a) be platform-safe with an oversized config
        # and (b) honor a configured approval timeout smaller than the
        # platform ceiling. virtus SPEC #3c — the gate fallback constant is
        # itself the platform-safe ceiling, so a configured timeout smaller
        # than that is what makes the gate shorter than its fallback.
        from agent.tool_executor import (
            _AUTHORIZATION_GATE_LOCK_TIMEOUT_S,
            _authorization_gate_lock_timeout,
        )
        from agent.deadline import MAX_SAFE_TIMEOUT_S
        from tools.approval_human_wait import HUMAN_WAIT_MARGIN_S

        # (a) Oversized config → clamped to MAX_SAFE_TIMEOUT_S, still safe to
        # pass to threading.Lock.acquire (regression for #83220). The gate adds
        # HUMAN_WAIT_MARGIN_S (60s) on top of the human-wait ceiling.
        with _with_configured_timeout(10**18):
            bound = _authorization_gate_lock_timeout()
        lock = threading.Lock()
        assert lock.acquire(timeout=bound)
        lock.release()
        assert bound == float(MAX_SAFE_TIMEOUT_S) + HUMAN_WAIT_MARGIN_S

        # (b) A legitimately small configured timeout shortens the gate below
        # the fallback. Upstream invariant was "gate floor < bound when
        # configured"; virtus invariant is the dual: "gate bound == fallback
        # when configured ≥ fallback, == configured when below fallback".
        with _with_configured_timeout(3600):
            bound = _authorization_gate_lock_timeout()
        assert bound < _AUTHORIZATION_GATE_LOCK_TIMEOUT_S
        assert bound == 3600 + 60.0  # approvals.timeout + HUMAN_WAIT_MARGIN_S
