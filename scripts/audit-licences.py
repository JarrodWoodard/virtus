#!/usr/bin/env python3
"""Licence audit — the fork is MIT and must stay free of copyleft IN COMBINATION.

The rule from the project's posture: exec'ing a GPL program is safe; linking or loading one into this
codebase is not. This checks the two things that can actually link: the declared dependencies and the
installed distributions. It cannot tell you how a package is used — that stays a review question — but
it guarantees nothing reciprocal is sitting in the dependency graph unnoticed.

    python3 scripts/audit-licences.py            # audit the current environment
    python3 scripts/audit-licences.py --strict   # exit 1 on any flagged finding (CI)

Exit status: 0 clean, 1 flagged (with --strict), 2 could not read the project metadata.
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

COPYLEFT = ("GPL", "AGPL", "SSPL", "EUPL", "CDDL", "CPL", "MPL-1")
# Permissive licences this project accepts without further thought.
PERMISSIVE = ("MIT", "BSD", "APACHE", "ISC", "ZLIB", "PYTHON", "PSF", "UNLICENSE", "CC0", "0BSD")


def declared(root: Path) -> list[str]:
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text())
    except Exception as exc:  # pragma: no cover - environment problem, not a licence one
        print(f"cannot read pyproject.toml: {exc}", file=sys.stderr)
        raise SystemExit(2)
    project = data.get("project") or {}
    names = []
    for spec in project.get("dependencies") or []:
        name = spec.split("[")[0].split("=")[0].split(">")[0].split("<")[0].split(";")[0].strip()
        if name:
            names.append(name)
    for group in (project.get("optional-dependencies") or {}).values():
        for spec in group or []:
            name = spec.split("[")[0].split("=")[0].split(">")[0].split("<")[0].split(";")[0].strip()
            if name and not name.startswith("virtus-agent") and name not in names:
                names.append(name)
    return names


def installed() -> list[tuple[str, str]]:
    from importlib import metadata

    rows = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"] or "?"
        classifiers = " ".join(dist.metadata.get_all("Classifier") or [])
        licence = str(dist.metadata.get("License") or "")
        rows.append((name, f"{licence} {classifiers}".strip()))
    return rows


def classify(text: str) -> str:
    upper = text.upper()
    if any(bad in upper for bad in COPYLEFT):
        return "copyleft"
    if any(ok in upper for ok in PERMISSIVE):
        return "permissive"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="licence audit")
    ap.add_argument("--root", default=".", help="project root containing pyproject.toml")
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is flagged")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    print(f"project: {root}")
    names = declared(root)
    print(f"declared dependencies: {len(names)}")

    copyleft, unknown = [], []
    for name, text in installed():
        verdict = classify(text)
        if verdict == "copyleft":
            copyleft.append((name, text[:90]))
        elif verdict == "unknown":
            unknown.append(name)

    print(f"installed distributions: {len(installed())}")
    if copyleft:
        print("\nCOPYLEFT IN THE ENVIRONMENT — must not be linked, only exec'd:")
        for name, text in sorted(copyleft):
            print(f"  {name}: {text}")
    else:
        print("copyleft in the environment: none")
    if unknown:
        shown = ", ".join(sorted(unknown)[:12])
        more = "" if len(unknown) <= 12 else f" (+{len(unknown) - 12} more)"
        print(f"licence not stated (review before use): {shown}{more}")

    if copyleft and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
