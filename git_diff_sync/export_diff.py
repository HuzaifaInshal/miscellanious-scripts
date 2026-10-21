#!/usr/bin/env python3
"""
export_diff.py - File A

Takes 2 commit hashes inside a git repository, generates the full git diff
(covering file creation, modification, deletion, renames, and binary files),
and writes the output to files.txt.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_git_command(cmd: list[str], cwd: str | Path = ".") -> str:
    """Runs a git command and returns the stdout text, or raises an error."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"Git command failed with exit code {result.returncode}"
        raise RuntimeError(error_msg)
    return result.stdout


def export_diff(
    commit_base: str,
    commit_target: str,
    output_file: str = "files.txt",
    repo_dir: str = ".",
) -> str:
    """
    Generates git diff between commit_base and commit_target and saves to output_file.
    Includes full changes: creation, modification, deletion, and binary diffs.
    """
    repo_path = Path(repo_dir).resolve()
    output_path = Path(output_file).resolve()

    # Verify repo directory is a git repo
    try:
        run_git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    except Exception as e:
        print(f"Error: '{repo_path}' is not a valid git repository: {e}", file=sys.stderr)
        sys.exit(1)

    # Verify both commit hashes/references exist
    for commit, label in [(commit_base, "Base commit"), (commit_target, "Target commit")]:
        try:
            run_git_command(["git", "rev-parse", "--verify", commit], cwd=repo_path)
        except Exception as e:
            print(f"Error: {label} '{commit}' was not found: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Generating diff between '{commit_base}' and '{commit_target}'...")

    # Fetch git status summary of changed files (added, modified, deleted)
    try:
        status_output = run_git_command(
            ["git", "diff", "--name-status", commit_base, commit_target],
            cwd=repo_path,
        )
        if status_output.strip():
            print("\nChanges detected:")
            for line in status_output.strip().splitlines():
                parts = line.split("\t", 1)
                status = parts[0]
                filepath = parts[1] if len(parts) > 1 else ""
                status_desc = {
                    "A": "Created ",
                    "M": "Modified",
                    "D": "Deleted ",
                    "R": "Renamed ",
                }.get(status[0], status)
                print(f"  [{status_desc}] {filepath}")
        else:
            print("\nNotice: No changes detected between these two commits.")
    except Exception as e:
        print(f"Warning: Could not fetch changed files list: {e}", file=sys.stderr)

    # Generate full binary diff
    diff_cmd = [
        "git",
        "diff",
        "--binary",
        "--full-index",
        commit_base,
        commit_target,
    ]
    diff_output = run_git_command(diff_cmd, cwd=repo_path)

    # Save to output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(diff_output)

    print(f"\nSuccessfully generated diff in '{output_path}' ({len(diff_output)} bytes).")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="File A: Export git diff between two commits into files.txt"
    )
    parser.add_argument(
        "commit1",
        nargs="?",
        help="Base / older commit hash or reference (e.g. HEAD~1, main, 42f395b)",
    )
    parser.add_argument(
        "commit2",
        nargs="?",
        help="Target / newer commit hash or reference (e.g. HEAD, feature-branch)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="files.txt",
        help="Output diff filename (default: files.txt)",
    )
    parser.add_argument(
        "-r",
        "--repo",
        default=".",
        help="Path to git repository root (default: current directory)",
    )

    args = parser.parse_args()

    commit1 = args.commit1
    commit2 = args.commit2

    # If commits not supplied as arguments, prompt interactively
    if not commit1:
        commit1 = input("Enter base / older commit hash (e.g. HEAD~1 or hash): ").strip()
    if not commit2:
        commit2 = input("Enter target / newer commit hash (e.g. HEAD or hash): ").strip()

    if not commit1 or not commit2:
        print("Error: Both commit hashes must be provided.", file=sys.stderr)
        sys.exit(1)

    export_diff(
        commit_base=commit1,
        commit_target=commit2,
        output_file=args.output,
        repo_dir=args.repo,
    )


if __name__ == "__main__":
    main()
