# Multi-Folder Git Diff Sync (`multi_diff_sync`)

Designed for projects and monorepos where multiple service folders (like `FE` and `BE`) and a utility folder (`file-handler`) sit side-by-side at the same directory level:

```text
my-project/
├── FE/
├── BE/
└── file-handler/
    ├── export_diff.py
    ├── apply_diff.py
    ├── files_FE.txt  (also FE/files.txt)
    └── files_BE.txt  (also BE/files.txt)
```

---

## What It Does

1. **File A: `export_diff.py`**
   - Takes 2 commit hashes (e.g. `HEAD~1` and `HEAD` or full hashes).
   - Accepts folder names to diff (defaults to `FE` and `BE`).
   - Automatically scopes the git diff to each root folder and makes file paths inside each diff relative to that specific folder's root.
   - Outputs separate diffs for each folder:
     - `files_FE.txt` (and `FE/files.txt`)
     - `files_BE.txt` (and `BE/files.txt`)

2. **File B: `apply_diff.py`**
   - Placed inside the destination FE or BE project.
   - Takes the corresponding diff file (`files.txt`, `files_FE.txt`, etc.).
   - Applies all creations, modifications, deletions, and binary changes directly to the project.
   - If placed inside a `file-handler` subfolder within the target project, it automatically applies changes to the parent project directory (`..`).

---

## Usage

### 1. Generate FE and BE diffs (`export_diff.py`)

Run inside the source Git repository (either from `file-handler/` or the repo root):

```bash
# Default targets FE and BE
python export_diff.py <commit_base> <commit_target>

# Example:
python export_diff.py HEAD~1 HEAD

# Or specify custom folders:
python export_diff.py HEAD~1 HEAD FE BE
```

If run without arguments, it will prompt for the commit hashes interactively:
```bash
python export_diff.py
```

### 2. Apply diffs in target projects (`apply_diff.py`)

Copy the generated `files_FE.txt` (or `FE/files.txt`) and `apply_diff.py` to your target Frontend project:
```bash
python apply_diff.py files_FE.txt
```

Similarly, copy `files_BE.txt` (or `BE/files.txt`) and `apply_diff.py` to your target Backend project:
```bash
python apply_diff.py files_BE.txt
```

Options:
- `-t <path>`: Explicit target directory (e.g. `-t ..` or `-t /path/to/project`)
- `-c`, `--check`: Dry-run mode to verify changes before applying
- `-R`, `--reverse`: Reverse-apply the diff
