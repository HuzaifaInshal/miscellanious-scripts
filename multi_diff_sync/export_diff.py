#!/usr/bin/env python3
"""
export_diff.py - Multi-folder Git Diff Exporter

Exports git diffs between two commits for specified root folders (defaulting to FE and BE).
Designed for monorepo / multi-root setups where folders like FE, BE, and file-handler
live at the same directory level.

Spits out separate diff files for each folder (e.g. files_FE.txt and FE/files.txt,
files_BE.txt and BE/files.txt) with paths relative to each folder's root.
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


def find_git_root(start_dir: Path) -> Path:
    """Locates the git root directory containing start_dir."""
    try:
        out = run_git_command(["git", "rev-parse", "--show-toplevel"], cwd=start_dir)
        return Path(out.strip()).resolve()
    except Exception as e:
        print(f"Error: Not inside a valid git repository: {e}", file=sys.stderr)
        sys.exit(1)


def resolve_folder_path(folder_name: str, current_dir: Path, git_root: Path) -> Path:
    """
    Finds where folder_name lives:
    1. Sibling to current_dir (e.g. current_dir is file-handler -> ../folder_name)
    2. Inside current_dir (current_dir / folder_name)
    3. Directly under git_root (git_root / folder_name)
    """
    candidates = [
        (current_dir.parent / folder_name).resolve(),
        (current_dir / folder_name).resolve(),
        (git_root / folder_name).resolve(),
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    # Return path relative to git_root even if not created yet
    return (git_root / folder_name).resolve()


def export_multi_diff(
    commit_base: str,
    commit_target: str,
    folders: list[str],
    current_dir: Path | None = None,
) -> dict[str, list[str]]:
    """
    Exports git diff for each specified folder between commit_base and commit_target.
    Generates files_<folder>.txt and <folder>/files.txt for each.
    """
    if current_dir is None:
        current_dir = Path.cwd().resolve()
    else:
        current_dir = current_dir.resolve()

    git_root = find_git_root(current_dir)

    # Verify both commit hashes/references exist
    for commit, label in [(commit_base, "Base commit"), (commit_target, "Target commit")]:
        try:
            run_git_command(["git", "rev-parse", "--verify", commit], cwd=git_root)
        except Exception as e:
            print(f"Error: {label} '{commit}' was not found in git repository: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Repository root: {git_root}")
    print(f"Comparing '{commit_base}' -> '{commit_target}' across folders: {', '.join(folders)}\n")

    generated_files: dict[str, list[str]] = {}

    for folder in folders:
        folder_path = resolve_folder_path(folder, current_dir, git_root)
        try:
            rel_to_git_root = folder_path.relative_to(git_root).as_posix()
        except ValueError:
            print(f"Warning: Folder '{folder}' ({folder_path}) is outside git repo root. Skipping.", file=sys.stderr)
            continue

        print(f"=== Processing [{folder}] (path: {rel_to_git_root}) ===")

        # Check changed files inside this folder
        try:
            status_cmd = [
                "git",
                "diff",
                "--name-status",
                commit_base,
                commit_target,
                "--",
                rel_to_git_root,
            ]
            status_out = run_git_command(status_cmd, cwd=git_root).strip()
            if status_out:
                for line in status_out.splitlines():
                    parts = line.split("\t", 1)
                    status = parts[0]
                    filepath = parts[1] if len(parts) > 1 else ""
                    # Strip the folder prefix for clean display
                    if filepath.startswith(rel_to_git_root + "/"):
                        filepath = filepath[len(rel_to_git_root) + 1:]
                    status_desc = {
                        "A": "Created ",
                        "M": "Modified",
                        "D": "Deleted ",
                        "R": "Renamed ",
                    }.get(status[0], status)
                    print(f"  [{status_desc}] {filepath}")
            else:
                print("  No changes detected in this folder between the two commits.")
        except Exception as e:
            print(f"  Warning: Could not fetch status: {e}", file=sys.stderr)

        # Generate diff relative to this folder's root
        diff_cmd = [
            "git",
            "diff",
            "--binary",
            "--full-index",
            f"--relative={rel_to_git_root}",
            commit_base,
            commit_target,
        ]
        diff_output = run_git_command(diff_cmd, cwd=git_root)

        # Output targets:
        # 1. files_<folder>.txt in current directory
        # 2. <folder>/files.txt in current directory (or inside folder directory)
        out1 = current_dir / f"files_{folder}.txt"
        out2 = current_dir / folder / "files.txt"

        out1.parent.mkdir(parents=True, exist_ok=True)
        with open(out1, "w", encoding="utf-8", errors="replace") as f:
            f.write(diff_output)

        out2.parent.mkdir(parents=True, exist_ok=True)
        with open(out2, "w", encoding="utf-8", errors="replace") as f:
            f.write(diff_output)

        generated_files[folder] = [str(out1), str(out2)]
        print(f"  -> Generated: {out1.name} and {folder}/files.txt ({len(diff_output)} bytes)\n")

    print("Diff generation complete!")
    return generated_files


def main():
    parser = argparse.ArgumentParser(
        description="File A (Multi-folder): Export separate diffs for FE and BE between 2 commits."
    )
    parser.add_argument(
        "commit1",
        nargs="?",
        help="Base / older commit hash or reference (e.g. HEAD~1, main, hash)",
    )
    parser.add_argument(
        "commit2",
        nargs="?",
        help="Target / newer commit hash or reference (e.g. HEAD, feature-branch)",
    )
    parser.add_argument(
        "folders",
        nargs="*",
        default=["FE", "BE"],
        help="Root folders to generate diffs for (default: FE BE)",
    )

    args = parser.parse_args()

    commit1 = args.commit1
    commit2 = args.commit2
    folders = args.folders if args.folders else ["FE", "BE"]

    # Interactive prompts if commit hashes are not provided via CLI
    if not commit1:
        commit1 = input("Enter base / older commit hash (e.g. HEAD~1 or commit hash): ").strip()
    if not commit2:
        commit2 = input("Enter target / newer commit hash (e.g. HEAD or commit hash): ").strip()

    if not commit1 or not commit2:
        print("Error: Both commit hashes must be provided.", file=sys.stderr)
        sys.exit(1)

    export_multi_diff(
        commit_base=commit1,
        commit_target=commit2,
        folders=folders,
    )


if __name__ == "__main__":
    main()
