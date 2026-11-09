#!/usr/bin/env python3
"""
export_diff.py - Simple Adjacent Git Diff Exporter (Two-Operation Engine: CREATE & DELETE)

Designed for projects with a simple adjacent folder structure:
  my-project/
  ├── BE/
  ├── FE/
  └── file-handler/
      ├── export_diff.py
      ├── apply_diff.py
      └── files.txt

Exports git changes across BE and FE into a SINGLE files.txt package inside file-handler/.
No separate folders or multiple diff files.

Supports two export modes:
1. Commit Diff Mode:
   - First commit hash is mandatory.
   - Second commit hash is optional (defaults to HEAD, including all changes till end).
   - Example: python export_diff.py HEAD~2
2. Active Changes Mode (-a / --active):
   - Does NOT require or ask for commit hashes.
   - Exports all active working tree changes (both tracked staged/unstaged and untracked files).
   - Example: python export_diff.py -a

Two-Operation Engine:
1. CREATE: Full file content snapshot for Added, Modified, Renamed, or Untracked files.
2. DELETE: Explicit deletion instructions for Deleted or Renamed files.
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
    'export_diff.py',
    'apply_diff.py',
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


def is_valid_git_commit(ref: str, git_root: Path) -> bool:
    """Checks whether ref resolves to a valid git commit object."""
    res = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=git_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


def resolve_project_root(current_dir: Path, git_root: Path, folders: list[str]) -> Path:
    """
    Identifies the project root directory containing the adjacent folders (BE, FE, file-handler):
    1. If current_dir is 'file-handler' or similar, check current_dir.parent
    2. Check if current_dir directly contains the folders
    3. Check if git_root contains the folders
    4. Fallback to current_dir.parent if inside file-handler, else current_dir
    """
    # If running from inside file-handler, the parent is the natural project root
    if current_dir.name.lower() in ("file-handler", "file_handler", "scripts"):
        parent = current_dir.parent.resolve()
        if any((parent / f).is_dir() for f in folders):
            return parent
        return parent

    # Check current directory
    if any((current_dir / f).is_dir() for f in folders):
        return current_dir

    # Check git root
    if any((git_root / f).is_dir() for f in folders):
        return git_root

    return current_dir


def resolve_output_file(output_arg: str | None, current_dir: Path, project_root: Path) -> Path:
    """Determines where the single files.txt will be saved."""
    if output_arg:
        return Path(output_arg).resolve()

    # If running directly inside file-handler
    if current_dir.name.lower() in ("file-handler", "file_handler"):
        return current_dir / "files.txt"

    # If running from project root and file-handler directory exists
    fh_dir = project_root / "file-handler"
    if fh_dir.is_dir():
        return fh_dir / "files.txt"

    fh_alt = project_root / "file_handler"
    if fh_alt.is_dir():
        return fh_alt / "files.txt"

    return current_dir / "files.txt"


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
        text = text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
        return text, False
    except UnicodeDecodeError:
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        return b64_str, True


def get_file_content_from_disk(file_path: Path) -> tuple[str, bool]:
    """
    Reads active file content from the local filesystem.
    Returns (content_string, is_binary).
    """
    raw_bytes = file_path.read_bytes()

    if is_binary_bytes(raw_bytes):
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        return b64_str, True

    try:
        text = raw_bytes.decode("utf-8")
        text = text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
        return text, False
    except UnicodeDecodeError:
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        return b64_str, True


def export_diff(
    commit_base: str,
    commit_target: str = "HEAD",
    folders: list[str] | None = None,
    current_dir: Path | None = None,
    output_file: Path | None = None,
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
) -> Path:
    """
    Exports CREATE and DELETE operations across specified folders (BE, FE) between two commits into a single files.txt.
    If commit_target is omitted or empty, it defaults to HEAD (including all changes till end).
    """
    if not commit_target:
        commit_target = "HEAD"
    if folders is None:
        folders = ["BE", "FE"]
    if ignore_dirs is None:
        ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if ignore_files is None:
        ignore_files = set(DEFAULT_IGNORE_FILES)

    if current_dir is None:
        current_dir = Path.cwd().resolve()
    else:
        current_dir = current_dir.resolve()

    git_root = find_git_root(current_dir)
    project_root = resolve_project_root(current_dir, git_root, folders)

    # Validate commits
    for commit, label in [(commit_base, "Base commit"), (commit_target, "Target commit")]:
        try:
            run_git_command(["git", "rev-parse", "--verify", commit], cwd=git_root)
        except Exception as e:
            print(f"Error: {label} '{commit}' not found in git repository: {e}", file=sys.stderr)
            sys.exit(1)

    final_output_path = output_file if output_file else resolve_output_file(None, current_dir, project_root)

    print(f"Repository Root: {git_root}")
    print(f"Project Root:    {project_root}")
    print(f"Output File:     {final_output_path}")
    print(f"Mode:            Commit diff ('{commit_base}' -> '{commit_target}')")
    print(f"Target Folders:  {', '.join(folders)}\n")

    out_content = []
    out_content.append(f"# Simple Diff Sync Package: {', '.join(folders)}\n")
    out_content.append(f"# Base Commit:   {commit_base}\n")
    out_content.append(f"# Target Commit: {commit_target}\n")
    out_content.append(f"# Operations:    CREATE (whole content), DELETE\n\n")

    total_created = 0
    total_deleted = 0
    total_ignored = 0

    for folder in folders:
        folder_dir = (project_root / folder).resolve()

        try:
            folder_rel_to_git = folder_dir.relative_to(git_root).as_posix()
        except ValueError:
            print(f"Warning: Folder '{folder}' ({folder_dir}) is outside git root. Skipping.", file=sys.stderr)
            continue

        print(f"=== Processing [{folder}] ===")

        # Run git diff for this folder
        try:
            status_res = run_git_command(
                [
                    "git",
                    "diff",
                    "--name-status",
                    commit_base,
                    commit_target,
                    "--",
                    folder_rel_to_git,
                ],
                cwd=git_root,
            )
            status_text = status_res.stdout.decode("utf-8", errors="replace").strip()
        except Exception as e:
            print(f"  Warning: Could not fetch git diff status for '{folder}': {e}", file=sys.stderr)
            continue

        if not status_text:
            print(f"  No changes detected in '{folder}'.\n")
            continue

        folder_created = 0
        folder_deleted = 0
        folder_ignored = 0

        for line in status_text.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status_token = parts[0].strip()

            # Handle Renames: R<score> \t old \t new
            if status_token.startswith("R") and len(parts) >= 3:
                git_old = parts[1].strip()
                git_new = parts[2].strip()

                try:
                    rel_old = (git_root / git_old).relative_to(project_root).as_posix()
                except ValueError:
                    rel_old = git_old

                try:
                    rel_new = (git_root / git_new).relative_to(project_root).as_posix()
                except ValueError:
                    rel_new = git_new

                # Deletion of old path
                if is_ignored(rel_old, ignore_dirs, ignore_files):
                    folder_ignored += 1
                else:
                    print(f"  [DELETE (renamed from)] {rel_old}")
                    out_content.append(f"=== DELETE: {rel_old} ===\n\n")
                    folder_deleted += 1

                # Creation of new path
                if is_ignored(rel_new, ignore_dirs, ignore_files):
                    folder_ignored += 1
                else:
                    try:
                        content_str, is_bin = get_file_content_at_commit(commit_target, git_new, git_root)
                        if is_bin:
                            print(f"  [CREATE (binary renamed to)] {rel_new}")
                            out_content.append(f"=== CREATE_BASE64: {rel_new} ===\n")
                            out_content.append(content_str)
                            out_content.append("\n\n")
                        else:
                            print(f"  [CREATE (text renamed to)]   {rel_new}")
                            out_content.append(f"=== CREATE: {rel_new} ===\n")
                            out_content.append(content_str)
                            if not content_str.endswith("\n"):
                                out_content.append("\n")
                            out_content.append("\n")
                        folder_created += 1
                    except Exception as e:
                        print(f"  [ERROR] Could not read '{git_new}' at {commit_target}: {e}", file=sys.stderr)
                continue

            # Handle Copies: C<score> \t old \t new
            if status_token.startswith("C") and len(parts) >= 3:
                git_new = parts[2].strip()
                try:
                    rel_new = (git_root / git_new).relative_to(project_root).as_posix()
                except ValueError:
                    rel_new = git_new

                if is_ignored(rel_new, ignore_dirs, ignore_files):
                    folder_ignored += 1
                else:
                    try:
                        content_str, is_bin = get_file_content_at_commit(commit_target, git_new, git_root)
                        if is_bin:
                            print(f"  [CREATE (binary copy)] {rel_new}")
                            out_content.append(f"=== CREATE_BASE64: {rel_new} ===\n")
                            out_content.append(content_str)
                            out_content.append("\n\n")
                        else:
                            print(f"  [CREATE (text copy)]   {rel_new}")
                            out_content.append(f"=== CREATE: {rel_new} ===\n")
                            out_content.append(content_str)
                            if not content_str.endswith("\n"):
                                out_content.append("\n")
                            out_content.append("\n")
                        folder_created += 1
                    except Exception as e:
                        print(f"  [ERROR] Could not read '{git_new}' at {commit_target}: {e}", file=sys.stderr)
                continue

            git_path = parts[1].strip() if len(parts) > 1 else ""
            if not git_path:
                continue

            try:
                rel_path = (git_root / git_path).relative_to(project_root).as_posix()
            except ValueError:
                rel_path = git_path

            if is_ignored(rel_path, ignore_dirs, ignore_files):
                folder_ignored += 1
                continue

            if status_token == "D":
                print(f"  [DELETE] {rel_path}")
                out_content.append(f"=== DELETE: {rel_path} ===\n\n")
                folder_deleted += 1
            else:
                # Added (A), Modified (M), Type change (T)
                try:
                    content_str, is_bin = get_file_content_at_commit(commit_target, git_path, git_root)
                except Exception as e:
                    print(f"  [ERROR] Could not read '{git_path}' at {commit_target}: {e}", file=sys.stderr)
                    continue

                # Check if content actually changed from base commit
                if not is_bin and status_token in ("M", "T"):
                    try:
                        base_content, base_is_bin = get_file_content_at_commit(commit_base, git_path, git_root)
                        if not base_is_bin and content_str == base_content:
                            folder_ignored += 1
                            continue
                    except Exception:
                        pass

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
                folder_created += 1

        print(f"  [{folder} Summary] CREATE: {folder_created}, DELETE: {folder_deleted}, Ignored: {folder_ignored}\n")
        total_created += folder_created
        total_deleted += folder_deleted
        total_ignored += folder_ignored

    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(final_output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out_content))

    print(f"Done! Diff package saved to: {final_output_path}")
    print(f"Total Operations -> CREATE: {total_created}, DELETE: {total_deleted}, Ignored: {total_ignored}")
    return final_output_path


def export_active_diff(
    folders: list[str] | None = None,
    current_dir: Path | None = None,
    output_file: Path | None = None,
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
) -> Path:
    """
    Exports all active git changes (both tracked staged/unstaged and untracked files)
    across the specified folders (BE, FE) into a single files.txt package.
    Does NOT require or ask for commit hashes.
    """
    if folders is None:
        folders = ["BE", "FE"]
    if ignore_dirs is None:
        ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if ignore_files is None:
        ignore_files = set(DEFAULT_IGNORE_FILES)

    if current_dir is None:
        current_dir = Path.cwd().resolve()
    else:
        current_dir = current_dir.resolve()

    git_root = find_git_root(current_dir)
    project_root = resolve_project_root(current_dir, git_root, folders)
    final_output_path = output_file if output_file else resolve_output_file(None, current_dir, project_root)

    print(f"Repository Root: {git_root}")
    print(f"Project Root:    {project_root}")
    print(f"Output File:     {final_output_path}")
    print(f"Mode:            Active git changes (tracked + untracked)")
    print(f"Target Folders:  {', '.join(folders)}\n")

    out_content = []
    out_content.append(f"# Simple Diff Sync Package: {', '.join(folders)}\n")
    out_content.append(f"# Mode:          Active changes (tracked + untracked)\n")
    out_content.append(f"# Operations:    CREATE (whole content), DELETE\n\n")

    total_created = 0
    total_deleted = 0
    total_ignored = 0

    for folder in folders:
        folder_dir = (project_root / folder).resolve()

        try:
            folder_rel_to_git = folder_dir.relative_to(git_root).as_posix()
        except ValueError:
            print(f"Warning: Folder '{folder}' ({folder_dir}) is outside git root. Skipping.", file=sys.stderr)
            continue

        print(f"=== Processing Active Changes [{folder}] ===")

        # Run git status with untracked files included (-uall)
        try:
            status_res = run_git_command(
                [
                    "git",
                    "status",
                    "--porcelain=v1",
                    "-uall",
                    "--",
                    folder_rel_to_git,
                ],
                cwd=git_root,
            )
            status_text = status_res.stdout.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  Warning: Could not fetch active git status for '{folder}': {e}", file=sys.stderr)
            continue

        lines = [l for l in status_text.splitlines() if l.strip()]
        if not lines:
            print(f"  No active changes detected in '{folder}'.\n")
            continue

        folder_created = 0
        folder_deleted = 0
        folder_ignored = 0

        for line in lines:
            status_code = line[:2]
            rest = line[3:].strip()

            # Handle renames: 'R  old -> new'
            if "R" in status_code and " -> " in rest:
                old_part, new_part = rest.split(" -> ", 1)
                git_old = old_part.strip().strip('"')
                git_new = new_part.strip().strip('"')

                try:
                    rel_old = (git_root / git_old).relative_to(project_root).as_posix()
                except ValueError:
                    rel_old = git_old

                try:
                    rel_new = (git_root / git_new).relative_to(project_root).as_posix()
                except ValueError:
                    rel_new = git_new

                # Old path is deleted
                if is_ignored(rel_old, ignore_dirs, ignore_files):
                    folder_ignored += 1
                else:
                    print(f"  [DELETE (renamed from)] {rel_old}")
                    out_content.append(f"=== DELETE: {rel_old} ===\n\n")
                    folder_deleted += 1

                # New path is created
                if is_ignored(rel_new, ignore_dirs, ignore_files):
                    folder_ignored += 1
                else:
                    new_abs = git_root / git_new
                    if new_abs.is_file():
                        try:
                            content_str, is_bin = get_file_content_from_disk(new_abs)
                            if is_bin:
                                print(f"  [CREATE (binary renamed to)] {rel_new}")
                                out_content.append(f"=== CREATE_BASE64: {rel_new} ===\n")
                                out_content.append(content_str)
                                out_content.append("\n\n")
                            else:
                                print(f"  [CREATE (text renamed to)]   {rel_new}")
                                out_content.append(f"=== CREATE: {rel_new} ===\n")
                                out_content.append(content_str)
                                if not content_str.endswith("\n"):
                                    out_content.append("\n")
                                out_content.append("\n")
                            folder_created += 1
                        except Exception as e:
                            print(f"  [ERROR] Could not read active file '{new_abs}': {e}", file=sys.stderr)
                continue

            git_path = rest.strip('"')
            if not git_path:
                continue

            abs_path = git_root / git_path
            try:
                rel_path = abs_path.relative_to(project_root).as_posix()
            except ValueError:
                rel_path = git_path

            if is_ignored(rel_path, ignore_dirs, ignore_files):
                folder_ignored += 1
                continue

            # Check if file was deleted (status code contains 'D' or no longer exists on disk)
            if "D" in status_code or not abs_path.exists():
                print(f"  [DELETE] {rel_path}")
                out_content.append(f"=== DELETE: {rel_path} ===\n\n")
                folder_deleted += 1
            elif abs_path.is_file():
                # Added (A), Untracked (??), or Modified (M)
                try:
                    content_str, is_bin = get_file_content_from_disk(abs_path)
                except Exception as e:
                    print(f"  [ERROR] Could not read active file '{abs_path}': {e}", file=sys.stderr)
                    continue

                # Check if content actually changed from HEAD for tracked files
                is_untracked = "??" in status_code
                if not is_untracked and not is_bin:
                    try:
                        head_content, head_is_bin = get_file_content_at_commit("HEAD", git_path, git_root)
                        if not head_is_bin and content_str == head_content:
                            folder_ignored += 1
                            continue
                    except Exception:
                        pass

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
                folder_created += 1

        print(f"  [{folder} Summary] CREATE: {folder_created}, DELETE: {folder_deleted}, Ignored: {folder_ignored}\n")
        total_created += folder_created
        total_deleted += folder_deleted
        total_ignored += folder_ignored

    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(final_output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out_content))

    print(f"Done! Active diff package saved to: {final_output_path}")
    print(f"Total Operations -> CREATE: {total_created}, DELETE: {total_deleted}, Ignored: {total_ignored}")
    return final_output_path


def main():
    parser = argparse.ArgumentParser(
        description="Simple Adjacent Git Diff Exporter (BE, FE -> single files.txt in file-handler/)."
    )
    parser.add_argument(
        "commit1",
        nargs="?",
        default=None,
        help="Base / older commit hash (mandatory unless -a / --active is specified)",
    )
    parser.add_argument(
        "commit2",
        nargs="?",
        default=None,
        help="Target / newer commit hash (default: HEAD, including all commits till end)",
    )
    parser.add_argument(
        "folders",
        nargs="*",
        default=None,
        help="Adjacent folders to diff (default: BE FE)",
    )
    parser.add_argument(
        "-a",
        "--active",
        action="store_true",
        help="Export all active git changes (tracked and untracked) in working tree without commit hashes",
    )
    parser.add_argument(
        "--folders",
        dest="flag_folders",
        nargs="+",
        help="Explicit adjacent folders list (e.g. --folders BE FE)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path for single output diff file (default: files.txt in file-handler/)",
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

    output_path = Path(args.output).resolve() if args.output else None

    # MODE 1: Active Changes (-a / --active)
    if args.active:
        # Determine folders for active mode
        if args.flag_folders:
            folders = args.flag_folders
        else:
            # If positional arguments were supplied with -a (e.g. export_diff.py -a BE FE)
            pos = [f for f in [args.commit1, args.commit2] + (args.folders or []) if f]
            folders = pos if pos else ["BE", "FE"]

        export_active_diff(
            folders=folders,
            output_file=output_path,
            ignore_dirs=ignore_dirs,
            ignore_files=ignore_files,
        )
        return

    # MODE 2: Commit Diff Mode
    commit1 = args.commit1
    commit2 = args.commit2
    raw_folders = args.folders or []

    if not commit1:
        # Prompt interactively
        commit1 = input("Enter base / older commit hash (mandatory, e.g. HEAD~1, main): ").strip()
        if not commit1:
            print("Error: Base commit hash is mandatory (or run with -a / --active for active uncommitted changes).", file=sys.stderr)
            sys.exit(1)

        commit2_input = input("Enter target / newer commit hash [default: HEAD]: ").strip()
        commit2 = commit2_input if commit2_input else "HEAD"
    else:
        # commit1 was provided via CLI.
        # Check if commit2 was provided or if it is actually a folder name
        # (e.g. python export_diff.py HEAD~1 BE FE)
        git_root = find_git_root(Path.cwd())
        if commit2 is not None:
            if not is_valid_git_commit(commit2, git_root):
                raw_folders = [commit2] + raw_folders
                commit2 = "HEAD"
        else:
            commit2 = "HEAD"

    if args.flag_folders:
        folders = args.flag_folders
    elif raw_folders:
        folders = raw_folders
    else:
        folders = ["BE", "FE"]

    export_diff(
        commit_base=commit1,
        commit_target=commit2,
        folders=folders,
        output_file=output_path,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
    )


if __name__ == "__main__":
    main()