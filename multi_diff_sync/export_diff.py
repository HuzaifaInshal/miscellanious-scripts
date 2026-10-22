#!/usr/bin/env python3
"""
export_diff.py - Multi-Folder Git Diff Exporter (Two-Operation Engine: CREATE & DELETE)

Exports git changes between two commits for specified root folders (defaulting to FE and BE).
Designed for monorepo / multi-root setups where folders like FE, BE, and file-handler
live side-by-side, specifically to synchronize with a DIFFERENT REPOSITORY having
the same structure without git apply / index dependencies.

Only 2 operations:
1. CREATE: If a file is Added or Modified, exports its ENTIRE whole content so the
   target repository can blatantly overwrite/create it.
2. DELETE: If a file is Deleted, records a deletion instruction so the target repository
   can delete it.

Spits out separate diff packages for each folder:
  - files_<folder>.txt in the current directory
  - <folder>/files.txt
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


def find_git_root(start_dir: Path) -> Path:
    """Locates the git root directory containing start_dir."""
    try:
        res = run_git_command(["git", "rev-parse", "--show-toplevel"], cwd=start_dir)
        return Path(res.stdout.decode("utf-8", errors="replace").strip()).resolve()
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
    return (git_root / folder_name).resolve()


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
    """Heuristic check if byte data is binary."""
    return b"\x00" in data[:8000]


def get_file_content_at_commit(
    commit: str,
    git_rel_path: str,
    repo_root: Path,
) -> tuple[str, bool]:
    """
    Retrieves full content of git_rel_path at commit.
    Returns (content_string, is_binary).
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


def export_multi_diff(
    commit_base: str,
    commit_target: str,
    folders: list[str],
    current_dir: Path | None = None,
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
) -> dict[str, list[str]]:
    """
    Exports CREATE and DELETE operations for each folder between commit_base and commit_target.
    """
    if ignore_dirs is None:
        ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if ignore_files is None:
        ignore_files = set(DEFAULT_IGNORE_FILES)

    if current_dir is None:
        current_dir = Path.cwd().resolve()
    else:
        current_dir = current_dir.resolve()

    git_root = find_git_root(current_dir)

    # Validate commits
    for commit, label in [(commit_base, "Base commit"), (commit_target, "Target commit")]:
        try:
            run_git_command(["git", "rev-parse", "--verify", commit], cwd=git_root)
        except Exception as e:
            print(f"Error: {label} '{commit}' not found in git repository: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Repository Root: {git_root}")
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

        # Fetch git changes inside this folder
        try:
            status_res = run_git_command(
                [
                    "git",
                    "diff",
                    "--name-status",
                    commit_base,
                    commit_target,
                    "--",
                    rel_to_git_root,
                ],
                cwd=git_root,
            )
            status_text = status_res.stdout.decode("utf-8", errors="replace").strip()
        except Exception as e:
            print(f"  Warning: Could not fetch status for '{folder}': {e}", file=sys.stderr)
            continue

        prefix = rel_to_git_root + "/" if rel_to_git_root != "." else ""

        operations: list[dict] = []
        ignored_count = 0

        if status_text:
            for line in status_text.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                status_token = parts[0].strip()

                # Handle Renames: R<score> \t old \t new
                if status_token.startswith("R") and len(parts) >= 3:
                    full_old = parts[1].strip()
                    full_new = parts[2].strip()

                    rel_old = full_old[len(prefix):] if full_old.startswith(prefix) else full_old
                    rel_new = full_new[len(prefix):] if full_new.startswith(prefix) else full_new

                    if is_ignored(rel_old, ignore_dirs, ignore_files):
                        ignored_count += 1
                    else:
                        operations.append({"op": "DELETE", "rel_path": rel_old, "full_path": full_old})

                    if is_ignored(rel_new, ignore_dirs, ignore_files):
                        ignored_count += 1
                    else:
                        operations.append({"op": "CREATE", "rel_path": rel_new, "full_path": full_new})
                    continue

                # Handle Copies: C<score> \t old \t new
                if status_token.startswith("C") and len(parts) >= 3:
                    full_new = parts[2].strip()
                    rel_new = full_new[len(prefix):] if full_new.startswith(prefix) else full_new
                    if is_ignored(rel_new, ignore_dirs, ignore_files):
                        ignored_count += 1
                    else:
                        operations.append({"op": "CREATE", "rel_path": rel_new, "full_path": full_new})
                    continue

                full_path = parts[1].strip() if len(parts) > 1 else ""
                if not full_path:
                    continue

                rel_path = full_path[len(prefix):] if full_path.startswith(prefix) else full_path

                if is_ignored(rel_path, ignore_dirs, ignore_files):
                    ignored_count += 1
                    continue

                if status_token == "D":
                    operations.append({"op": "DELETE", "rel_path": rel_path, "full_path": full_path})
                else:
                    # Added (A), Modified (M), or Type changed (T)
                    # Blatantly copy the whole content
                    operations.append({"op": "CREATE", "rel_path": rel_path, "full_path": full_path})

        out_content = []
        out_content.append(f"# Multi Diff Sync Package: {folder}\n")
        out_content.append(f"# Base Commit:   {commit_base}\n")
        out_content.append(f"# Target Commit: {commit_target}\n")
        out_content.append(f"# Operations:    CREATE (whole content), DELETE\n\n")

        create_count = 0
        delete_count = 0

        for item in operations:
            op = item["op"]
            rel_path = item["rel_path"]
            full_path = item["full_path"]

            if op == "DELETE":
                print(f"  [DELETE] {rel_path}")
                out_content.append(f"=== DELETE: {rel_path} ===\n\n")
                delete_count += 1
            elif op == "CREATE":
                try:
                    content_str, is_bin = get_file_content_at_commit(
                        commit_target, full_path, git_root
                    )
                except Exception as e:
                    print(f"  [ERROR] Could not read '{full_path}' at {commit_target}: {e}", file=sys.stderr)
                    continue

                if is_bin:
                    print(f"  [CREATE (binary)] {rel_path}")
                    out_content.append(f"=== CREATE_BASE64: {rel_path} ===\n")
                    out_content.append(content_str)
                    out_content.append("\n\n")
                else:
                    print(f"  [CREATE (text)]   {rel_path}")
                    out_content.append(f"=== CREATE: {rel_path} ===\n")
                    out_content.append(content_str)
                    if not content_str.endswith("\n"):
                        out_content.append("\n")
                    out_content.append("\n")
                create_count += 1

        combined_text = "".join(out_content)

        # Output targets:
        # 1. files_<folder>.txt in current directory
        # 2. <folder>/files.txt in current directory
        # 3. Inside the actual folder itself: folder_path / "files.txt"
        out1 = current_dir / f"files_{folder}.txt"
        out2 = current_dir / folder / "files.txt"

        out_list = [out1, out2]

        # Also write directly inside the resolved folder path if it exists
        if folder_path.exists() and folder_path.is_dir():
            out3 = folder_path / "files.txt"
            if out3 not in out_list:
                out_list.append(out3)
            # If folder has its own file-handler subfolder
            if (folder_path / "file-handler").exists():
                out4 = folder_path / "file-handler" / "files.txt"
                out5 = folder_path / "file-handler" / f"files_{folder}.txt"
                out_list.extend([out4, out5])

        for target_out in out_list:
            target_out.parent.mkdir(parents=True, exist_ok=True)
            with open(target_out, "w", encoding="utf-8") as f:
                f.write(combined_text)

        generated_files[folder] = [str(p) for p in out_list]
        print(f"  -> Generated: {out1.name}")
        for p in out_list[1:]:
            try:
                rel_display = p.relative_to(git_root).as_posix()
            except ValueError:
                rel_display = p.name
            print(f"     and {rel_display}")
        print(f"     CREATE: {create_count}, DELETE: {delete_count}, Ignored: {ignored_count}\n")


    print("Diff export complete!")
    return generated_files


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Folder Git Diff Exporter using CREATE (whole content) and DELETE operations."
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
        "folders",
        nargs="*",
        default=["FE", "BE"],
        help="Root folders to generate diffs for (default: FE BE)",
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
    folders = args.folders if args.folders else ["FE", "BE"]

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

    export_multi_diff(
        commit_base=commit1,
        commit_target=commit2,
        folders=folders,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
    )


if __name__ == "__main__":
    main()
