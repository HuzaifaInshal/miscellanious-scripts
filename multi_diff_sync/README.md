# Multi-Folder Git Diff Sync (`multi_diff_sync`)

Designed to transfer changes across **two DIFFERENT repositories or repository setups**.

Specifically handles the real-world workflow where:
1. **Source Repo**: A monorepo or parent project containing `FE/`, `BE/`, and `file-handler/` side-by-side.
2. **Destination Repos**: Separate standalone repositories for Frontend and Backend, each containing their own `file-handler/` folder.

```text
Source Repository (Monorepo):
my-monorepo/
├── FE/
├── BE/
└── file-handler/
    ├── export_diff.py
    ├── files_FE.txt  (also generated into FE/files.txt)
    └── files_BE.txt  (also generated into BE/files.txt)

Destination Repositories (Separate Projects):
frontend-project/
├── src/
├── package.json
└── file-handler/
    ├── apply_diff.py
    └── files_FE.txt (or files.txt)

backend-project/
├── src/
├── package.json
└── file-handler/
    ├── apply_diff.py
    └── files_BE.txt (or files.txt)
```

---

## The Two-Operation Architecture: `CREATE` & `DELETE`

Instead of relying on fragile Git patch hunks or index pre-image hashes that fail across different repositories, this system uses strictly two operations:

1. **`CREATE` (Whole Content)**: If a file is **Added**, **Modified**, or **Renamed**, `export_diff.py` captures the **entire file content** from the target commit. When applied, `apply_diff.py` blatantly overwrites/creates the entire file in the target repository.
2. **`DELETE`**: If a file is **Deleted** in the source repository, `apply_diff.py` removes the file from the target repository.

This guarantees:
- No Git merge conflicts, index rejections, or pre-image sha mismatch errors.
- Seamless synchronization between two completely different Git repositories and branches.
- The target repository does not even need Git installed or initialized.
- Inside `files_FE.txt`, file paths are scoped relative to the Frontend root (e.g. `src/App.tsx`, not `FE/src/App.tsx`).
- Inside `files_BE.txt`, file paths are scoped relative to the Backend root (e.g. `src/main.ts`, not `BE/src/main.ts`).

---

## Directory & File Ignore Rules

Just like `file_packer`, the scripts automatically exclude non-essential and build directories/files by default:

- **Default Ignored Directories**: `node_modules`, `reports`, `dist`, `.git`, `__pycache__`, `.venv`, `venv`, `build`, `.vscode`, `public`, `.next`
- **Default Ignored Files**: `package-lock.json`, `test.py`, `files.txt`, `files_FE.txt`, `files_BE.txt`, `final.txt`, `.DS_Store`

Customizable via flags:
- `--ignore-dirs dir1,dir2`: Override default ignored directories.
- `--ignore-files file1,file2`: Override default ignored files.
- `--add-ignore-dirs dir1,dir2`: Add extra directories to ignore without removing defaults.
- `--add-ignore-files file1,file2`: Add extra files to ignore without removing defaults.

---

## Usage

### 1. Export FE and BE packages from Source (`export_diff.py`)

Run inside the source Git repository (from `file-handler/` or repo root):

```bash
# Provide base (older) commit and target (newer) commit (default targets: FE and BE)
python export_diff.py <commit_base> <commit_target>

# Example:
python export_diff.py HEAD~1 HEAD

# Or specify custom root folders:
python export_diff.py HEAD~1 HEAD FE BE
```

Generates:
- `files_FE.txt` (and `FE/files.txt`)
- `files_BE.txt` (and `BE/files.txt`)

---

### 2. Apply in Separate Destination Projects (`apply_diff.py`)

#### For Frontend Project:
Copy `files_FE.txt` into `frontend-project/file-handler/` (or rename to `files.txt`), then run:
```bash
cd frontend-project/file-handler
python apply_diff.py
```
> **Auto-Targeting**: Because `apply_diff.py` is running inside `file-handler/` and `../FE` does not exist as a subfolder, it automatically targets the parent project directory `..` (`frontend-project`). The files are placed directly into `frontend-project/src/...`.

#### For Backend Project:
Copy `files_BE.txt` into `backend-project/file-handler/` (or rename to `files.txt`), then run:
```bash
cd backend-project/file-handler
python apply_diff.py
```
> **Auto-Targeting**: Automatically targets `..` (`backend-project`), updating `backend-project/src/...` and `package.json`.

#### Optional Flags:
```bash
# Explicitly specify target path if desired:
python apply_diff.py files_FE.txt -t ..

# Dry-run inspection without modifying files:
python apply_diff.py files_FE.txt --check

# Prevent overwriting existing files:
python apply_diff.py files_FE.txt --no-overwrite
```
