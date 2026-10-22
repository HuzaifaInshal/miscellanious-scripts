# Multi-Folder Git Diff Sync (`multi_diff_sync`)

Designed for projects and monorepos where multiple service folders (like `FE` and `BE`) and a utility folder (`file-handler`) sit side-by-side at the same directory level, specifically to transfer changes across **two DIFFERENT repositories** sharing the same folder structure:

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

## The Two-Operation Architecture: `CREATE` & `DELETE`

Instead of relying on fragile Git patch hunks or index pre-image hashes that fail across different repositories, this system uses strictly two operations:

1. **`CREATE` (Whole Content)**: If a file is **Added**, **Modified**, or **Renamed**, `export_diff.py` captures the **entire file content** from the target commit. When applied, `apply_diff.py` blatantly overwrites/creates the entire file in the target repository.
2. **`DELETE`**: If a file is **Deleted** in the source repository, `apply_diff.py` removes the file from the target repository.

This guarantees:
- No Git merge conflicts, index rejections, or pre-image sha mismatch errors.
- Seamless synchronization between two completely different Git repositories and branches.
- The target repository does not even need Git installed or initialized.

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

### 1. Export FE and BE packages (`export_diff.py`)

Run inside the source Git repository:

```bash
# Provide base (older) commit and target (newer) commit (default targets: FE and BE)
python export_diff.py <commit_base> <commit_target>

# Example:
python export_diff.py HEAD~1 HEAD

# Or specify custom root folders:
python export_diff.py HEAD~1 HEAD FE BE microservice-c
```

Generates:
- `files_FE.txt` (and `FE/files.txt`)
- `files_BE.txt` (and `BE/files.txt`)

---

### 2. Apply packages in target repository (`apply_diff.py`)

Copy the generated `files_FE.txt` and `files_BE.txt` to the target repository.

#### Auto-apply both folders:
If run without arguments, it auto-discovers all `files_*.txt` in the folder and applies each to its corresponding destination directory:
```bash
python apply_diff.py
```

#### Apply a specific folder package:
```bash
# Apply FE changes
python apply_diff.py files_FE.txt

# Apply BE changes
python apply_diff.py files_BE.txt

# Explicitly specify a target path
python apply_diff.py files_FE.txt -t /path/to/target/FE

# Dry-run inspection without modifying files
python apply_diff.py files_FE.txt --check

# Prevent overwriting existing files
python apply_diff.py files_FE.txt --no-overwrite
```
