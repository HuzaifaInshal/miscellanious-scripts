#!/usr/bin/env python3
"""
apply_diff.py - Simple Adjacent Git Diff Applier (Two-Operation Engine: CREATE & DELETE)

Designed for projects with a simple adjacent folder structure:
  my-project/
  ├── BE/
  ├── FE/
  └── file-handler/
      ├── export_diff.py
      ├── apply_diff.py
      └── files.txt

Reads the single files.txt package inside file-handler/ and applies whole-file
creations, modifications, and deletions directly into the adjacent BE/ and FE/ folders.

Does NOT depend on git apply, git trees, or commit shas.
"""

import argparse
import base64
import os
import re
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


def resolve_diff_file(input_arg: str | None, current_dir: Path) -> Path | None:
    """
    Locates the diff package file:
    1. Explicit path passed as argument
    2. files.txt in the current directory
    3. files.txt inside adjacent/child file-handler/ directory
    """
    if input_arg:
        p = Path(input_arg).resolve()
        if p.exists():
            return p
        return p  # Let caller report not found

    # Check current directory
    candidate = current_dir / "files.txt"
    if candidate.exists():
        return candidate

    # Check child file-handler
    candidate_fh = current_dir / "file-handler" / "files.txt"
    if candidate_fh.exists():
        return candidate_fh

    candidate_fh_alt = current_dir / "file_handler" / "files.txt"
    if candidate_fh_alt.exists():
        return candidate_fh_alt

    return None


def resolve_target_dir(target_arg: str | None, current_dir: Path) -> Path:
    """
    Resolves the destination project root containing BE/ and FE/:
    - Explicit -t argument if provided.
    - If running inside file-handler/, targets parent directory (..) where BE and FE are adjacent.
    - If running inside project root (containing BE/ or FE/), targets current directory (.).
    - Defaults to parent if current directory looks like a subfolder, else current.
    """
    if target_arg:
        return Path(target_arg).resolve()

    # If running from inside file-handler, target is parent directory (..)
    if current_dir.name.lower() in ("file-handler", "file_handler", "scripts"):
        return current_dir.parent.resolve()

    # If running from project root where BE or FE exists directly
    if (current_dir / "BE").is_dir() or (current_dir / "FE").is_dir():
        return current_dir

    return current_dir


def apply_diff(
    diff_path: Path,
    target_path: Path,
    check_only: bool = False,
    overwrite: bool = True,
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
) -> bool:
    """Applies CREATE and DELETE operations from files.txt into target_path."""
    if ignore_dirs is None:
        ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    if ignore_files is None:
        ignore_files = set(DEFAULT_IGNORE_FILES)

    if not diff_path.exists():
        print(f"Error: Diff file '{diff_path}' does not exist.", file=sys.stderr)
        return False

    if not target_path.exists():
        if check_only:
            print(f"[Check] Target directory '{target_path}' does not exist (would be created).")
        else:
            print(f"Target directory '{target_path}' does not exist. Creating it...")
            target_path.mkdir(parents=True, exist_ok=True)

    with open(diff_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        content = f.read()

    # Normalize CRLF and double newlines in package
    content = content.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")

    header_pattern = re.compile(r"^=== (.+?) ===$", re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        print(f"Notice: No file operations found in '{diff_path.name}'.")
        return True

    mode_label = "DRY RUN (Check only)" if check_only else "APPLYING CHANGES"
    print(f"\n[{mode_label}] From '{diff_path.name}' -> Target: '{target_path}'")
    print(f"Total operations in package: {len(matches)}\n")

    created_count = 0
    deleted_count = 0
    skipped_count = 0
    error_count = 0

    for i, match in enumerate(matches):
        raw_header = match.group(1).strip()

        if raw_header.startswith("DELETE:"):
            op = "DELETE"
            rel_path = raw_header[len("DELETE:"):].strip()
        elif raw_header.startswith("CREATE_BASE64:"):
            op = "CREATE_BASE64"
            rel_path = raw_header[len("CREATE_BASE64:"):].strip()
        elif raw_header.startswith("CREATE:"):
            op = "CREATE"
            rel_path = raw_header[len("CREATE:"):].strip()
        else:
            op = "CREATE"
            rel_path = raw_header

        if is_ignored(rel_path, ignore_dirs, ignore_files):
            print(f"  [Ignored]  {rel_path}")
            skipped_count += 1
            continue

        dest_file = (target_path / rel_path).resolve()

        # Security check: prevent directory traversal outside target_path
        try:
            dest_file.relative_to(target_path)
        except ValueError:
            print(f"  [Security] Skipping unsafe path outside target: {rel_path}", file=sys.stderr)
            error_count += 1
            continue

        start_idx = match.end()
        if start_idx < len(content) and content[start_idx] == "\n":
            start_idx += 1
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block_content = content[start_idx:end_idx]

        if block_content in ("\n\n", "\n"):
            block_content = ""
        elif block_content.endswith("\n\n"):
            block_content = block_content[:-1]

        if op == "DELETE":
            if dest_file.exists():
                if check_only:
                    print(f"  [Check: DELETE]  {rel_path}")
                else:
                    try:
                        dest_file.unlink()
                        print(f"  [DELETED]        {rel_path}")
                    except Exception as e:
                        print(f"  [ERROR] Failed to delete '{rel_path}': {e}", file=sys.stderr)
                        error_count += 1
                        continue
                deleted_count += 1
            else:
                if check_only:
                    print(f"  [Check: DELETE]  {rel_path} (already absent)")
                else:
                    print(f"  [DELETED]        {rel_path} (already absent)")
                deleted_count += 1

        elif op in ("CREATE", "CREATE_BASE64"):
            if dest_file.exists() and not overwrite:
                print(f"  [Skipped]        {rel_path} (already exists, overwrite=False)")
                skipped_count += 1
                continue

            action_desc = "OVERWRITE" if dest_file.exists() else "CREATE"
            action_past = "OVERWRITTEN" if dest_file.exists() else "CREATED"

            if check_only:
                print(f"  [Check: {action_desc}] {rel_path}")
                created_count += 1
                continue

            try:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if op == "CREATE_BASE64":
                    binary_data = base64.b64decode(block_content.strip())
                    with open(dest_file, "wb") as out:
                        out.write(binary_data)
                else:
                    with open(dest_file, "w", encoding="utf-8", newline="\n") as out:
                        out.write(block_content)
                print(f"  [{action_past}]      {rel_path}")
                created_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed writing '{rel_path}': {e}", file=sys.stderr)
                error_count += 1

    print(f"\nSummary for '{diff_path.name}':")
    print(f"  Created/Updated: {created_count}")
    print(f"  Deleted:         {deleted_count}")
    print(f"  Skipped/Ignored: {skipped_count}")
    if error_count > 0:
        print(f"  Errors:          {error_count}")

    return error_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="Simple Adjacent Git Diff Applier (Applies single files.txt into adjacent BE/ and FE/)."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to diff package file (default: files.txt in current or file-handler/ directory)",
    )
    parser.add_argument(
        "-t",
        "--target",
        default=None,
        help="Destination project directory (auto-detected as parent '..' when inside file-handler/)",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="Dry run: inspect what changes would be applied without modifying files",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not overwrite existing files",
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

    current_dir = Path.cwd().resolve()
    diff_file = resolve_diff_file(args.input, current_dir)

    if not diff_file or not diff_file.exists():
        print(f"Error: Diff file '{diff_file or 'files.txt'}' not found.", file=sys.stderr)
        print("Usage: python apply_diff.py [files.txt] [-t <target_dir>]", file=sys.stderr)
        sys.exit(1)

    target_path = resolve_target_dir(args.target, current_dir)

    success = apply_diff(
        diff_path=diff_file,
        target_path=target_path,
        check_only=args.check,
        overwrite=not args.no_overwrite,
        ignore_dirs=ignore_dirs,
        ignore_files=ignore_files,
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()