"""``virtus sync upstream`` — manual upstream-merge CLI subcommand.

Dry-run by default. Fetches the configured upstream ref, diffs
``upstream/<ref>`` against the fork's current branch, prints a one-paragraph
summary, and exits. With ``--apply``, runs ``git fetch`` + ``git merge`` and
prints the same summary plus the merge result. With ``--abort``, runs
``git merge --abort`` to roll back an in-progress merge.

Never auto-runs. Never called by the agent. Invoked only from the CLI.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_UPSTREAM_REMOTE = "upstream"
DEFAULT_UPSTREAM_REF = "main"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ("git",) + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def _resolve_repo(start: Path) -> Path:
    """Walk up to find the git work-tree root."""
    cur = start.resolve()
    for parent in (cur, *cur.parents):
        if (parent / ".git").exists():
            return parent
    raise RuntimeError(f"not inside a git work-tree: {start}")


def _has_merge_in_progress(repo: Path) -> bool:
    return (repo / ".git" / "MERGE_HEAD").exists()


def status(repo: Path, remote: str, ref: str) -> str:
    """Print a one-paragraph 'X ahead, Y behind, conflicts?' summary."""
    try:
        _git(repo, "rev-parse", "--verify", f"{remote}/{ref}", check=True)
    except subprocess.CalledProcessError:
        return f"[virtus sync] no upstream ref {remote}/{ref} — run `git remote add {remote} <url>` first"

    rev = _git(repo, "rev-list", "--left-right", "--count", f"HEAD...{remote}/{ref}").stdout.strip()
    if not rev:
        return f"[virtus sync] unable to compute ahead/behind for {remote}/{ref}"

    left, right = rev.split()
    ahead, behind = int(left), int(right)

    try:
        base = _git(repo, "merge-base", "HEAD", f"{remote}/{ref}").stdout.strip()
    except subprocess.CalledProcessError:
        base = ""

    conflict_hint = ""
    if ahead and behind and base:
        # count files that would differ on a merge (rough)
        merge_tree = _git(repo, "diff", "--name-only", "HEAD...MERGE_BASE", check=False).stdout.strip()
        base_tree = _git(repo, "diff", "--name-only", f"{remote}/{ref}...MERGE_BASE", check=False).stdout.strip()
        merge_files = set(merge_tree.splitlines())
        base_files = set(base_tree.splitlines())
        conflict_files = merge_files & base_files
        if conflict_files:
            conflict_hint = f" potential conflicts in: {', '.join(sorted(conflict_files))[:200]}"

    return (
        f"[virtus sync] {ahead} ahead, {behind} behind {remote}/{ref}.{conflict_hint} "
        f"Use `--apply` to merge or `--abort` to cancel an in-progress merge."
    )


def apply(repo: Path, remote: str, ref: str) -> int:
    if _has_merge_in_progress(repo):
        print("[virtus sync] merge already in progress — run `--abort` first or resolve manually", file=sys.stderr)
        return 1

    print(f"[virtus sync] fetching {remote} {ref}…")
    try:
        _git(repo, "fetch", remote, ref)
    except subprocess.CalledProcessError as e:
        print(f"[virtus sync] fetch failed: {e.stderr.strip()}", file=sys.stderr)
        return 2

    print(f"[virtus sync] merging {remote}/{ref} into current branch…")
    merge = subprocess.run(
        ("git", "merge", f"{remote}/{ref}", "--no-ff",
         "-m", f"virtus sync: merge {remote}/{ref}"),
        cwd=str(repo),
    )
    rc = merge.returncode
    if rc != 0:
        print(f"[virtus sync] merge returned {rc}; resolve manually or run `virtus sync upstream --abort`",
              file=sys.stderr)
        return rc
    print(status(repo, remote, ref))
    return 0


def abort(repo: Path) -> int:
    if not _has_merge_in_progress(repo):
        print("[virtus sync] no merge in progress", file=sys.stderr)
        return 0
    try:
        _git(repo, "merge", "--abort")
        print("[virtus sync] merge aborted")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[virtus sync] abort failed: {e.stderr.strip()}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="virtus sync upstream",
        description="Sync the virtus fork with the upstream hermes-agent repository.",
    )
    parser.add_argument("--apply", action="store_true",
                        help="fetch + merge (default is dry-run, prints status only)")
    parser.add_argument("--abort", action="store_true",
                        help="abort an in-progress merge")
    parser.add_argument("--remote", default=DEFAULT_UPSTREAM_REMOTE,
                        help=f"upstream remote name (default: {DEFAULT_UPSTREAM_REMOTE})")
    parser.add_argument("--ref", default=DEFAULT_UPSTREAM_REF,
                        help=f"upstream ref to track (default: {DEFAULT_UPSTREAM_REF})")
    parser.add_argument("--repo", default=None,
                        help="path to the virtus-agent checkout (default: auto-detect from cwd)")

    args = parser.parse_args(argv)

    repo_path = Path(args.repo) if args.repo else _resolve_repo(Path.cwd())
    if not (repo_path / ".git").exists():
        print(f"[virtus sync] not a git repo: {repo_path}", file=sys.stderr)
        return 1

    if args.abort:
        return abort(repo_path)

    if args.apply:
        return apply(repo_path, args.remote, args.ref)

    print(status(repo_path, args.remote, args.ref))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
