# Git Diff Sync (`git_diff_sync`)

A portable synchronization utility designed to transfer changes between **two DIFFERENT repositories** or project folders that share files, folders, and indexes, without requiring identical Git histories, index shas, or `git apply`.

---

## The Two-Operation Architecture: `CREATE` & `DELETE`

Instead of relying on fragile Git patch hunks or pre-image blob indexes that fail across different repositories, this system uses strictly two operations:

1. **`CREATE` (Whole Content)**: If a file is **Added**, **Modified**, or **Renamed**, `export_diff.py` extracts the **entire file content** from the target commit. When applied, `apply_diff.py` blatantly writes/overwrites the whole file into the target repository.
2. **`DELETE`**: If a file is **Deleted** in the source repository, `apply_diff.py` removes the file from the target repository.

This guarantees:
- No Git merge conflicts or blob mismatch errors.
- Fully compatible across completely different Git repositories and remotes.
- Target directory does not even need Git installed or initialized.

---

## Directory & File Ignore Rules

Just like `file_packer`, the scripts automatically exclude non-essential and build directories/files by default:

- **Default Ignored Directories**: `node_modules`, `reports`, `dist`, `.git`, `__pycache__`, `.venv`, `venv`, `build`, `.vscode`, `public`, `.next`
- **Default Ignored Files**: `package-lock.json`, `test.py`, `files.txt`, `files_FE.txt`, `files_BE.txt`, `final.txt`, `.DS_Store`

You can customize or extend these via CLI flags:
- `--ignore-dirs dir1,dir2`: Override default ignored directories.
- `--ignore-files file1,file2`: Override default ignored files.
- `--add-ignore-dirs dir1,dir2`: Add extra directories to ignore without removing defaults.
- `--add-ignore-files file1,file2`: Add extra files to ignore without removing defaults.

---

## Usage

### 1. Export changes from source repository (`export_diff.py`)

Run inside the source Git repository:

```bash
# Provide base (older) commit and target (newer) commit
python export_diff.py <commit1_base> <commit2_target>

# Examples:
python export_diff.py HEAD~1 HEAD
python export_diff.py 42f395b a8c130d
```

Or run interactively (prompts for commit hashes):
```bash
python export_diff.py
```

Options:
- `-o`, `--output`: Custom output filename (default: `files.txt`)
- `-r`, `--repo`: Path to Git repository (default: current directory `.`)
- `--add-ignore-dirs`: Add extra directories to ignore
- `--add-ignore-files`: Add extra files to ignore

---

### 2. Apply changes in target repository (`apply_diff.py`)

Copy `files.txt` to the target repository and run:

```bash
# Apply changes directly to the current directory
python apply_diff.py files.txt

# Specify target project directory
python apply_diff.py files.txt -t /path/to/target-repo

# Dry-run inspection without modifying files
python apply_diff.py files.txt --check

# Prevent overwriting existing files
python apply_diff.py files.txt --no-overwrite
```
