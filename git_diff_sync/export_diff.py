#!/usr/bin/env python3
"""
export_diff.py - Git Diff Exporter (Two-Operation Engine: CREATE & DELETE)

Compares two commits in a git repository and packages the full changes into files.txt.
Designed specifically for syncing across DIFFERENT REPOSITORIES that share directory
structures, without relying on matching git histories, object indexes, or git apply.

Only 2 operations:
1. CREATE: If a file is Added or Modified, exports its ENTIRE whole content so the
   target repository can blatantly overwrite/create it.
2. DELETE: If a file is Deleted, records a deletion instruction so the target repository
   can delete it.

Includes ignore_dirs and ignore_files filters (matching file_packer).
"""

import argparse
import base64
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    'node_modules',
    'reports',
    'dist',
    '.git',
    '__pycache__',
    '.venv',
    'venv',
    'build',
    '.vscode',
    'public',
    '.next',
}

DEFAULT_IGNORE_FILES = {
    'package-lock.json',
    'test.py',
    'files.txt',
    'files_FE.txt',
    'files_BE.txt',
    'final.txt',
    '.DS_Store',
}


def run_git_command(cmd: list[str], cwd: str | Path = ".") -> subprocess.CompletedProcess:
    """Runs a git command and returns CompletedProcess, or raises RuntimeError."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(err or f"Git command failed with exit code {result.returncode}")
    return result


def is_ignored(rel_path: str, ignore_dirs: set[str], ignore_files: set[str]) -> bool:
    """Checks if rel_path matches any ignored directory or ignored filename."""
    path = Path(rel_path)
    for part in path.parts[:-1]:
        if part in ignore_dirs:
            return True
    if len(path.parts) == 1 and path.name in ignore_dirs:
        return True
    if path.name in ignore_files:
        return True
    return False


def is_binary_bytes(data: bytes) -> bool:
    """Heuristic check if byte data is binary (e.g. contains null byte in initial chunk)."""
    return b"\x00" in data[:8000]


def get_file_content_at_commit(
    commit: str,
    git_rel_path: str,
    repo_root: Path,
) -> tuple[str, bool]:
    """
    Retrieves the entire content of git_rel_path at the specified commit.
    Returns (content_string, is_binary).
    If binary, content_string is base64 encoded.
    """
    res = run_git_command(["git", "show", f"{commit}:{git_rel_path}"], cwd=repo_root)
    raw_bytes = res.stdout

    if is_binary_bytes(raw_bytes):
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        return b64_str, True

    try:
        text = raw_bytes.decode("utf-8")
        return text, False
    except UnicodeDecodeError:
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        return b64_str, True


def export_diff(
    commit_base: str,
    commit_target: str,
    output_file: str = "files.txt",
    repo_dir: str = ".",
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
) -> str:
    """
    Exports changes between commit_base and commit_target into output_file
    using only CREATE and DELETE operations.
    """
    if ignore_dirs is None:
        ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if ignore_files is None:
        ignore_files = set(DEFAULT_IGNORE_FILES)

    repo_path = Path(repo_dir).resolve()
    output_path = Path(output_file).resolve()

    # Validate git repo
    try:
        run_git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    except Exception as e:
        print(f"Error: '{repo_path}' is not a valid git repository: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate both commits
    for commit, label in [(commit_base, "Base commit"), (commit_target, "Target commit")]:
        try:
            run_git_command(["git", "rev-parse", "--verify", commit], cwd=repo_path)
        except Exception as e:
            print(f"Error: {label} '{commit}' not found: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Analyzing git diff between '{commit_base}' and '{commit_target}'...")

    # Fetch status changes
    status_res = run_git_command(
        ["git", "diff", "--name-status", commit_base, commit_target],
        cwd=repo_path,
    )
    status_text = status_res.stdout.decode("utf-8", errors="replace").strip()

    if not status_text:
        print("Notice: No changes detected between the two commits.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Git Diff Sync: No changes between {commit_base} and {commit_target}\n")
        return str(output_path)

    operations: list[dict] = []
    ignored_count = 0

    for line in status_text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status_token = parts[0].strip()

        # Handle Renames: R<score> \t old_path \t new_path
        if status_token.startswith("R") and len(parts) >= 3:
            old_path = parts[1].strip()
            new_path = parts[2].strip()

            if is_ignored(old_path, ignore_dirs, ignore_files):
                ignored_count += 1
            else:
                operations.append({"op": "DELETE", "path": old_path})

            if is_ignored(new_path, ignore_dirs, ignore_files):
                ignored_count += 1
            else:
                operations.append({"op": "CREATE", "path": new_path})
            continue

        # Handle Copies: C<score> \t old_path \t new_path
        if status_token.startswith("C") and len(parts) >= 3:
            new_path = parts[2].strip()
            if is_ignored(new_path, ignore_dirs, ignore_files):
                ignored_count += 1
            else:
                operations.append({"op": "CREATE", "path": new_path})
            continue

        # Standard changes: A, M, D, T
        filepath = parts[1].strip() if len(parts) > 1 else ""
        if not filepath:
            continue

        if is_ignored(filepath, ignore_dirs, ignore_files):
            ignored_count += 1
            continue

        if status_token == "D":
            operations.append({"op": "DELETE", "path": filepath})
        else:
            # Added (A), Modified (M), or Type changed (T)
            # In all these cases, we blatantly extract the entire target file content
            operations.append({"op": "CREATE", "path": filepath})

    print(f"\nOperations planned ({len(operations)} total, {ignored_count} ignored):")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_count = 0
    delete_count = 0

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"# Git Diff Sync Package\n")
        out.write(f"# Base Commit:   {commit_base}\n")
        out.write(f"# Target Commit: {commit_target}\n")
        out.write(f"# Operations:    CREATE (whole content), DELETE\n\n")

        for item in operations:
            op = item["op"]
            rel_path = item["path"]

            if op == "DELETE":
                print(f"  [DELETE] {rel_path}")
                out.write(f"=== DELETE: {rel_path} ===\n\n")
                delete_count += 1
            elif op == "CREATE":
                try:
                    content_str, is_bin = get_file_content_at_commit(
                        commit_target, rel_path, repo_path
                    )
                except Exception as e:
                    print(f"  [ERROR] Could not read '{rel_path}' at {commit_target}: {e}", file=sys.stderr)
                    continue

                if is_bin:
                    print(f"  [CREATE (binary)] {rel_path}")
                    out.write(f"=== CREATE_BASE64: {rel_path} ===\n")
                    out.write(content_str)
                    out.write("\n\n")
                else:
                    print(f"  [CREATE (text)]   {rel_path}")
                    out.write(f"=== CREATE: {rel_path} ===\n")
                    out.write(content_str)
                    if not content_str.endswith("\n"):
                        out.write("\n")
                    out.write("\n")
                create_count += 1

    print(f"\nDiff package generated successfully:")
    print(f"  Output File:   {output_path}")
    print(f"  CREATE items:  {create_count} (full files packaged)")
    print(f"  DELETE items:  {delete_count}")
    print(f"  Ignored items: {ignored_count}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Export git changes between two commits using CREATE (whole content) and DELETE operations."
    )
    parser.add_argument(
        "commit1",
        nargs="?",
        help="Base / older commit hash or reference (e.g. HEAD~1, main)",
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
        help="Output package filename (default: files.txt)",
    )
    parser.add_argument(
        "-r",
        "--repo",
        default=".",
        help="Path to git repository root (default: current directory)",
    )
    parser.add_argument(
        "--ignore-dirs",
        help="Comma-separated directories to ignore (overrides defaults)",
    )
    parser.add_argument(
        "--ignore-files",
        help="Comma-separated filenames to ignore (overrides defaults)",
    )
    parser.add_argument(
        "--add-ignore-dirs",
        help="Comma-separated additional directories to ignore (appends to defaults)",
    )
    parser.add_argument(
        "--add-ignore-files",
        help="Comma-separated additional filenames to ignore (appends to defaults)",
    )

    args = parser.parse_args()

    commit1 = args.commit1
    commit2 = args.commit2

    if not commit1:
        commit1 = input("Enter base / older commit hash (e.g. HEAD~1): ").strip()
    if not commit2:
        commit2 = input("Enter target / newer commit hash (e.g. HEAD): ").strip()

    if not commit1 or not commit2:
        print("Error: Both commit hashes must be provided.", file=sys.stderr)
        sys.exit(1)

    ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if args.ignore_dirs:
        ignore_dirs = {d.strip() for d in args.ignore_dirs.split(",") if d.strip()}
    if args.add_ignore_dirs:
        ignore_dirs.update(d.strip() for d in args.add_ignore_dirs.split(",") if d.strip())

    ignore_files = set(DEFAULT_IGNORE_FILES)
    if args.ignore_files:
        ignore_files = {f.strip() for f in args.ignore_files.split(",") if f.strip()}
    if args.add_ignore_files:
        ignore_files.update(f.strip() for f in args.add_ignore_files.split(",") if f.strip())

    export_diff(
        commit_base=commit1,
        commit_target=commit2,
        output_file=args.output,
        repo_dir=args.repo,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
    )


if __name__ == "__main__":
    main()
