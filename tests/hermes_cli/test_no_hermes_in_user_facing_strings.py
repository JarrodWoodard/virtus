"""CI guard: prevent 'Hermes Agent' / 'Nous Research' / 'hermes-agent' /
'Nous Portal' / 'Messenger of the Digital Gods' from appearing in
USER-VISIBLE strings (print/console.log/banner/title/help/welcome/
description/error_msg) in the runtime surface.

Skip: comments, docstrings on non-user-facing modules, internal Python
identifiers (HermesCLI class name, importlib.metadata keys, HTTP
User-Agent headers, package version lookups), upstream docs URLs.

The fork rebrand is in commit history; this test is the regression net.
If any future commit adds one of these strings to a USER-VISIBLE
literal in the runtime surface, this test fails.
"""
import re
from pathlib import Path

import pytest

ROOT = Path("/home/jarrod/.virtus/virtus-agent")

# Strings that must NOT appear in user-facing strings
FORBIDDEN = [
    (re.compile(r"\bHermes Agent\b"), "Hermes Agent"),
    (re.compile(r"\bNous Research\b"), "Nous Research"),
    (re.compile(r"\bMessenger of the Digital Gods\b"), "messenger tagline"),
    (re.compile(r"\bNous Portal\b"), "Nous Portal"),
]

# Files / dirs that aren't user-visible
SKIP = {
    "tests/", "website/", "docker/", "docs/", "evals/",
    # Pure internal modules — these don't print to users
    "hermes_cli/auth_nous.py",
    "hermes_cli/nous_account.py",
    "hermes_cli/anon_auth.py",
    "hermes_cli/anon_sign_in.py",
    "hermes_cli/anon_sign_in_cli.py",
    "hermes_cli/nous_subscription.py",
    "hermes_cli/nous_auth_keepalive.py",
    "hermes_cli/portal_cli.py",
    "hermes_cli/uninstall.py",
    "hermes_cli/console_engine.py",
    "hermes_cli/auth_commands.py",  # Nous OAuth rehydration paths
    "hermes_constants.py",  # env-var fallback resolution
    "agent/relay_runtime.py",  # NeMo Relay plugin internals
    # Docs / README / AGENTS / SECURITY (developer docs reference upstream)
    "CONTRIBUTING.md", "CONTRIBUTING.es.md",
    "README.md", "README.es.md", "README.ur-pk.md", "README.zh-CN.md",
    "AGENTS.md", "COMPAT_MANIFEST.md", "SECURITY.md", "SECURITY.es.md",
    "PULL_REQUEST_TEMPLATE",
}

# Heuristic: a line is user-facing if it contains one of these token patterns.
# Use anchored alternation so the regex doesn't match empty strings.
USER_FACING_TOKENS = re.compile(
    r"""(?x)
        (?:
            print\s*\(|                  # python print()
            console\.log|                # node console.log
            return\s*['\"]|               # returned string literal
            \bprint_error\(|
            \bprint_warning\(|
            \bprint_info\(|
            \bprint_header\(|
            \bcprint\(|
            \b_say\(|
            \b_cprint\(|
            \b_info\(|
            \b_diag\(|
            \.error\(\)|
            \bprint_error_message\(|
            \bdescription\s*=\s*['\"]|
            \bhelp\s*=\s*['\"]|
            \btitle\s*=\s*['\"]|
            \bprog\s*=\s*['\"]|
            \bHERMES_AGENT_LOGO\s*=|
            \bSERVICE_DESCRIPTION\s*=|
            \bTASK_DESCRIPTION\s*=|
            \binfo\s*\(|\binfo_\(|\bHEADER\s*=\s*['\"]|
            \bsub_marker\s*=|             # tools_config_providers.py
            _STATUS\s*\._row\(
        )
    """
)


def _is_skipped(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel.startswith(d) or rel == d for d in SKIP)


def _is_user_facing_line(line: str) -> bool:
    return bool(USER_FACING_TOKENS.search(line))


def _scan(path: Path) -> list:
    try:
        text = path.read_text(errors="ignore")
    except (OSError, UnicodeDecodeError):
        return []
    hits = []
    for line_no, line in enumerate(text.split("\n"), 1):
        if not _is_user_facing_line(line):
            continue
        for pattern, name in FORBIDDEN:
            for m in pattern.finditer(line):
                hits.append((line_no, name, line.strip()[:200]))
    return hits


SCAN_DIRS = ["hermes_cli", "cli.py", "agent", "gateway"]


def test_no_hermes_or_nous_in_user_facing_strings():
    """No user-facing string in hermes_cli/, cli.py, agent/, gateway/
    may contain 'Hermes Agent', 'Nous Research', 'Nous Portal', or
    'Messenger of the Digital Gods' — these were removed in the
    virtus fork rebrand."""
    all_hits = []
    for entry in SCAN_DIRS:
        scan_path = ROOT / entry
        if scan_path.is_file():
            files = [scan_path]
        elif scan_path.is_dir():
            files = [p for p in scan_path.rglob("*") if p.is_file() and p.suffix in {".py", ".ts", ".tsx"}]
        else:
            continue
        for p in files:
            if _is_skipped(p):
                continue
            hits = _scan(p)
            for h in hits:
                rel = p.relative_to(ROOT)
                all_hits.append((str(rel), *h))
    if all_hits:
        msg = "\n".join(
            f"  {rel}:{ln}: {name}: {snippet}"
            for rel, ln, name, snippet in all_hits[:30]
        )
        if len(all_hits) > 30:
            msg += f"\n  ...and {len(all_hits)-30} more"
        pytest.fail(f"Forbidden user-facing strings found:\n{msg}")
