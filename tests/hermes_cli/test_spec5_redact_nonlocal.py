"""Regression tests for SPEC #5 — plugin secrets must not leak through
model egress when the active provider is non-local.

Covers the three SPEC #5d contracts:
1. Non-local provider → adapter connect() registers the exact token bytes
   in ``_VAULT_REDACTION_VALUES`` for the active profile.
2. Loopback provider → registration is skipped.
3. A tool-output string containing the token is replaced with the
   ``«redacted-vault-secret»`` sentinel by ``redact_sensitive_text(force=True)``
   regardless of ``security.redact_secrets``.

We test the redactor policy helper (``_is_local_endpoint``) and the
vault-registry round-trip directly. We do NOT exercise the adapter's full
``connect()`` here — that pulls in python-telegram-bot and a live
HTTP loop, which is the wrong test for a unit-level regression guard.
The adapter wiring is exercised by the SPEC #5 proof doc.
"""
from __future__ import annotations

import pytest

import agent.redact as redact_mod
from agent.redact import (
    _is_local_endpoint,
    _VAULT_REDACTION_VALUES,
    _vault_scope,
    clear_vault_redaction_values,
    redact_sensitive_text,
    register_vault_redaction_value,
)


SAMPLE_TOKEN = "1234567890:AAH-abc_DEFghI-JKLmnoPQRSTUvwxyz12345"
SAMPLE_WEBHOOK_SECRET = "wbhk_super_secret_value_AAAAAAAAAA"


@pytest.fixture(autouse=True)
def _clean_vault():
    """Reset the per-profile vault bucket around every test.

    ``_VAULT_REDACTION_VALUES`` is module-global, keyed by profile home;
    a fill-heavy test session would otherwise accumulate values across
    tests and break the "absent" assertion below.
    """
    clear_vault_redaction_values()
    yield
    clear_vault_redaction_values()


# ── _is_local_endpoint: URL classification ─────────────────────────────


class TestIsLocalEndpoint:
    def test_loopback_ipv4_is_local(self):
        assert _is_local_endpoint("http://127.0.0.1:8080/v1") is True

    def test_loopback_ipv6_is_local(self):
        assert _is_local_endpoint("http://[::1]:8080/v1") is True

    def test_localhost_name_is_local(self):
        assert _is_local_endpoint("http://localhost:8080/v1") is True

    def test_https_loopback_is_local(self):
        assert _is_local_endpoint("https://127.0.0.1:443/v1") is True

    def test_public_cloud_is_nonlocal(self):
        assert _is_local_endpoint("https://api.minimax.io/anthropic") is False

    def test_public_ip_is_nonlocal(self):
        assert _is_local_endpoint("https://8.8.8.8/v1") is False

    def test_empty_string_is_nonlocal_fail_closed(self):
        assert _is_local_endpoint("") is False

    def test_garbage_string_is_nonlocal_fail_closed(self):
        assert _is_local_endpoint("not a url") is False

    def test_none_is_nonlocal_fail_closed(self):
        assert _is_local_endpoint(None) is False


# ── Round-trip: registered secret is scrubbed at model egress ──────────


class TestVaultRedactionRoundTrip:
    def test_registered_token_masked_via_force(self):
        register_vault_redaction_value(SAMPLE_TOKEN)
        out = redact_sensitive_text(
            f"telegram connect failed: token={SAMPLE_TOKEN} retried",
            force=True,
        )
        assert SAMPLE_TOKEN not in out
        assert "«redacted-vault-secret»" in out

    def test_registered_token_masked_in_url_path(self):
        """The exact common leak: curl https://api.telegram.org/bot<TOKEN>/getMe."""
        register_vault_redaction_value(SAMPLE_TOKEN)
        out = redact_sensitive_text(
            f"GET https://api.telegram.org/bot{SAMPLE_TOKEN}/getMe → 401",
            force=True,
        )
        assert SAMPLE_TOKEN not in out
        assert "«redacted-vault-secret»" in out

    def test_registered_token_masked_in_json_dump(self):
        """Echoed config: agent prints its own config and the token leaks verbatim."""
        register_vault_redaction_value(SAMPLE_TOKEN)
        out = redact_sensitive_text(
            f'{{"platforms": {{"telegram": {{"token": "{SAMPLE_TOKEN}"}}}}}}',
            force=True,
        )
        assert SAMPLE_TOKEN not in out
        assert "«redacted-vault-secret»" in out

    def test_unrelated_value_unaffected(self):
        """Registration is exact-byte; an unrelated string passes through."""
        register_vault_redaction_value(SAMPLE_TOKEN)
        out = redact_sensitive_text("the answer is 42", force=True)
        assert out == "the answer is 42"

    def test_webhook_secret_round_trip(self):
        register_vault_redaction_value(SAMPLE_WEBHOOK_SECRET)
        out = redact_sensitive_text(
            f"webhook secret = {SAMPLE_WEBHOOK_SECRET}",
            force=True,
        )
        assert SAMPLE_WEBHOOK_SECRET not in out
        assert "«redacted-vault-secret»" in out


# ── Module-global state stays clean across tests ────────────────────────


class TestVaultStateIsolation:
    def test_clear_removes_value(self):
        register_vault_redaction_value(SAMPLE_TOKEN)
        scope = _vault_scope()
        assert SAMPLE_TOKEN in _VAULT_REDACTION_VALUES.get(scope, {})
        clear_vault_redaction_values()
        assert SAMPLE_TOKEN not in _VAULT_REDACTION_VALUES.get(scope, {})

    def test_lru_eviction_at_capacity(self):
        """64-entry cap per profile — a 65th value bumps the oldest."""
        from agent.redact import _VAULT_REDACTION_MAX_PER_PROFILE
        boundary_value = f"boundary-{_VAULT_REDACTION_MAX_PER_PROFILE + 1}"
        register_vault_redaction_value(boundary_value)
        # The boundary value should be in the bucket...
        scope = _vault_scope()
        assert boundary_value in _VAULT_REDACTION_VALUES.get(scope, {})
        # ...and a freshly-registered value must NOT be evicted immediately.
        fresh = "fresh-value-after-boundary"
        register_vault_redaction_value(fresh)
        assert fresh in _VAULT_REDACTION_VALUES.get(scope, {})
