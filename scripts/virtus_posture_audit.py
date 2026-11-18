#!/usr/bin/env python3
"""Virtus posture audit.

One line per posture intent: is the owner's setting in force, and what enforces it?
Run before and after an upstream merge — the merge is when a gate gets dropped,
renamed, or bypassed by a new call path on the far side of it.

    python scripts/virtus_posture_audit.py
    python scripts/virtus_posture_audit.py --json
    python scripts/virtus_posture_audit.py --strict   # exit 1 when an intent leaks

Classifications per intent:
    ok         value matches the intent
    WRONG      value on disk contradicts the intent
    LEAK       a code path does the thing while the setting says not to
    dead       nothing reads the key and nothing else guarantees the behaviour
    default    nothing reads the key, but the behaviour is off by upstream default
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN_ROOTS = ("agent", "hermes_cli", "tools", "gateway", "cli.py", "run_agent.py")

# label, config path, required value, consumer
#   consumer "guard:<helper>" = a fork helper must have a live call site
#   consumer "reader"         = upstream/fork code reads the key itself
#   consumer "none"           = nothing reads it
INTENTS = [
    ("update checks silenced",       ("updates", "notify"),               False,       "guard:updates_enabled"),
    ("account usage fetch off",      ("account_usage", "fetch"),          False,       "guard:account_usage_enabled"),
    ("models.dev network off",       ("models_dev", "allow_network"),     False,       "guard:models_dev_network_allowed"),
    ("curator off",                  ("curator", "enabled"),              False,       "reader"),
    ("web keyless fallback off",     ("web", "keyless_fallback"),         False,       "reader"),
    ("connector discovery off",      ("tools", "connectors", "enabled"),  False,       "reader"),
    ("remote model catalog off",     ("model_catalog", "enabled"),        False,       "reader"),
    ("skills write approval on",     ("skills", "write_approval"),        True,        "reader"),
    ("plugin update checks off",     ("plugins", "auto_update_check_hours"), 0,        "reader"),
    ("external logins not adopted",  ("auth", "adopt_external_logins"),   False,       "reader"),
    ("title model upgrade off",      ("auxiliary", "title_generation", "model_upgrade_enabled"), False, "reader"),
    ("language servers off",         ("lsp", "enabled"),                False,       "reader"),
    # updates.auto_maintenance and monitoring.enabled were DELETED from config.yaml on
    # 2026-11-16: nothing read them, so they were decor, not controls.
    ("lazy installs off",            ("security", "allow_lazy_installs"),  False,       "reader"),
    ("plugin catalog network off",   ("plugins", "catalog_allow_network"), False,       "guard:plugin_catalog_network_allowed"),
    ("memory provider empty",        ("memory", "provider"),              "",          "reader"),
    ("approvals timeout at ceiling", ("approvals", "timeout"),            31_536_000,  "reader"),
    # browser.backend was retired upstream in the 2026-11 merge. The browser posture is
    # being replaced by the Rotunda item (item 9 in the queue), not by a config key.
]


def _dig(cfg, path, default=None):
    cur = cfg
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _matches(have, want) -> bool:
    if isinstance(want, tuple):
        return have in want
    return have == want


def _guard_call_sites(helper: str) -> list:
    """Files that consult *helper*, excluding its own module and the tests."""
    hits = []
    for root in SCAN_ROOTS:
        target = REPO / root
        files = [target] if target.is_file() else [p for p in target.rglob("*.py")]
        for path in files:
            if "tests/" in str(path) or path.name == "virtus_config.py":
                continue
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            if re.search(rf"\b{re.escape(helper)}\b", text):
                hits.append(str(path.relative_to(REPO)))
    return sorted(hits)


def audit() -> list:
    from hermes_cli.config import load_config
    cfg = load_config()
    rows = []
    for label, path, want, consumer in INTENTS:
        have = _dig(cfg, path, default="<absent>")
        sites: list = []
        if consumer.startswith("guard:"):
            sites = _guard_call_sites(consumer.split(":", 1)[1])
        value_ok = _matches(have, want)
        if not value_ok:
            verdict, why = "WRONG", f"expected {want!r}"
        elif consumer.startswith("guard:") and not sites:
            verdict, why = "LEAK", "setting is not consulted anywhere"
        elif consumer.startswith("guard:"):
            verdict, why = "ok", ""
        elif consumer == "reader":
            verdict, why = "ok", ""
        else:
            verdict, why = "dead", "no reader; behaviour not guaranteed by config"
        if verdict == "ok":
            why = (", ".join(sites) if sites else "read by its consumer")
        rows.append({
            "intent": label,
            "key": ".".join(path),
            "want": want,
            "have": have,
            "verdict": verdict,
            "enforced_by": why,
            "consumer": consumer,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtus posture audit")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on LEAK or WRONG")
    args = ap.parse_args()

    os.environ.setdefault("HERMES_HOME", os.path.expanduser("~/.virtus"))
    sys.path.insert(0, str(REPO))
    try:
        rows = audit()
    except Exception as exc:  # noqa: BLE001 - report, never traceback
        print(f"audit error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        w = max(len(r["intent"]) for r in rows)
        print(f"{'intent'.ljust(w)}  verdict  {'value':<11}  enforced by")
        print(f"{'-' * w}  -------  {'-' * 11}  {'-' * 34}")
        for r in rows:
            print(f"{r['intent'].ljust(w)}  {r['verdict']:<7}  {str(r['have'])[:11]:<11}  {r['enforced_by']}")
        bad = [r for r in rows if r["verdict"] in ("WRONG", "LEAK")]
        dead = [r for r in rows if r["verdict"] == "dead"]
        print()
        print(f"{len(rows) - len(bad) - len(dead)}/{len(rows)} in force and enforced"
              f" · {len(dead)} dead · {len(bad)} broken")
        for r in bad:
            print(f"  ! {r['intent']} ({r['key']}): {r['verdict']} — {r['enforced_by']}")
        for r in dead:
            print(f"  ~ {r['intent']} ({r['key']}): dead — {r['enforced_by']}")

    if args.strict and any(r["verdict"] in ("WRONG", "LEAK") for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
