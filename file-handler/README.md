# Git Diff File Handler

A complementary pair of Python utilities to extract all git diff changes between two commits into a single portable `files.txt` and apply those changes (creation, modification, and deletion) to another project.

---

## Scripts Overview

### 1. File A: `export_diff.py`
Placed inside a Git repository. Takes two commit hashes (or branch/tag references) and generates `files.txt` containing all changes that occurred between the commits:
- **New files** (creation)
- **Modified files** (updates & diffs)
- **Deleted files** (removals)
- **Binary & file mode changes**

### 2. File B: `apply_diff.py`
Placed inside another project. Takes `files.txt` as input and applies all the changes directly into that project's working tree (creating new files/directories, editing modified files, and removing deleted files). Works whether the target directory is a Git repository or a plain folder.

---

## Usage

### Step 1: Export changes from your Git repo (`export_diff.py`)

Run inside the source Git repository:
```bash
# Provide base (older) commit and target (newer) commit
python export_diff.py <commit1_base> <commit2_target>

# Example:
python export_diff.py HEAD~1 HEAD
# or with full hashes:
python export_diff.py 42f395b a8c130d
```

Or run interactively (it will prompt you for the commit hashes):
```bash
python export_diff.py
```

Options:
- `-o`, `--output`: Custom output filename (default: `files.txt`)
- `-r`, `--repo`: Path to Git repository (default: current directory `.`)

---

### Step 2: Apply changes in another project (`apply_diff.py`)

Move `files.txt` (and optionally `apply_diff.py`) to the target project, then run:

```bash
# Apply changes from files.txt to the current directory
python apply_diff.py files.txt

# Or specify a target project directory
python apply_diff.py files.txt -t /path/to/target-project

# Test / dry-run without touching files
python apply_diff.py files.txt --check

# Reverse-apply the changes if needed
python apply_diff.py files.txt --reverse
```
