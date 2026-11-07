# Simple Adjacent Git Diff Sync (`simple_diff_sync`)

Designed for projects with a **simple adjacent folder structure** where Backend (`BE/`), Frontend (`FE/`), and utility (`file-handler/`) live side-by-side:

```text
Source & Destination Project Structure:
my-project/
├── BE/
├── FE/
└── file-handler/
    ├── export_diff.py
    ├── apply_diff.py
    └── files.txt
```

Inside `file-handler/`, there are **strictly 3 items**:
1. `export_diff.py`
2. `apply_diff.py`
3. `files.txt`

Unlike `multi_diff_sync` (which generates separate `files_FE.txt` and `files_BE.txt` for separate destination repositories), `simple_diff_sync` packages all Frontend and Backend changes into a **single unified `files.txt`** diff file.

---

## The Two-Operation Architecture: `CREATE` & `DELETE`

Instead of fragile git patch hunks or index pre-image blob matching, this tool uses two deterministic operations:

1. **`CREATE` (Whole Content)**: If a file is **Added**, **Modified**, or **Renamed**, `export_diff.py` captures the **entire file content** from the target commit. When applied, `apply_diff.py` writes/overwrites the whole file into the target directory.
2. **`DELETE`**: If a file is **Deleted** in the source repository, `apply_diff.py` removes the file from the destination directory.

### Benefits
- **No Git Conflicts**: Overcomes git patch failures, index rejections, or commit sha mismatches.
- **Cross-Repository Portable**: Transfers changes seamlessly across different Git repositories or branches.
- **Git-Free Target**: The destination repository does not even need Git installed or initialized.
- **Adjacent Folder Scoping**: Files are captured as `BE/...` and `FE/...`. When applied from `file-handler/`, they naturally update the sibling `../BE/` and `../FE/` folders.

---

## Directory & File Ignore Rules

The scripts exclude non-essential and build directories/files by default:

- **Default Ignored Directories**: `node_modules`, `reports`, `dist`, `.git`, `__pycache__`, `.venv`, `venv`, `build`, `.vscode`, `public`, `.next`
- **Default Ignored Files**: `package-lock.json`, `test.py`, `files.txt`, `files_FE.txt`, `files_BE.txt`, `final.txt`, `.DS_Store`

### Customizable Ignore Flags
- `--ignore-dirs dir1,dir2`: Override default ignored directories.
- `--ignore-files file1,file2`: Override default ignored files.
- `--add-ignore-dirs dir1,dir2`: Add extra directories to ignore.
- `--add-ignore-files file1,file2`: Add extra files to ignore.

---

## Usage Guide

### 1. Export Changes from Source (`export_diff.py`)

Run inside `file-handler/` (or from project root):

```bash
# Pass base commit and target commit (defaults to BE and FE):
python export_diff.py <commit_base> <commit_target>

# Example:
python export_diff.py HEAD~1 HEAD
```

Or run interactively (prompts for commit hashes):
```bash
python export_diff.py
```

Optional flags:
- `folders`: Specify adjacent folders to diff (default: `BE FE`):
  ```bash
  python export_diff.py HEAD~1 HEAD BE FE
  ```
- `-o`, `--output`: Custom output path (default: `files.txt` inside `file-handler/`)

**Result:** Generates a single `files.txt` inside `file-handler/`.

---

### 2. Apply Changes in Destination (`apply_diff.py`)

Copy `files.txt` into the destination project's `file-handler/` folder and run:

```bash
cd my-project/file-handler
python apply_diff.py
```

> **Auto-Targeting**: Running inside `file-handler/` automatically detects the parent directory (`..`) as the project root. Since `files.txt` stores paths prefixed with `BE/` and `FE/`, files are written directly into `../BE/...` and `../FE/...`.

Optional flags:
- `-t`, `--target <path>`: Explicit destination project directory:
  ```bash
  python apply_diff.py -t /path/to/my-project
  ```
- `-c`, `--check`: Dry run to inspect changes without writing or deleting any files:
  ```bash
  python apply_diff.py --check
  ```
- `--no-overwrite`: Skip files that already exist in the target directory:
  ```bash
  python apply_diff.py --no-overwrite
  ```
