# File Packer & Unpacker

A pair of complementary Python utilities to consolidate an entire directory structure of text/source code files into a single text file and reconstruct the files back into their original hierarchy.

---

## Purpose of the Scripts

### 1. `pack.py` (File Bundler / Consolidated Export)
- **What it does:** Recursively traverses a target folder (`root_dir`), filters out unwanted directories (like `node_modules`, `.git`, `.venv`, etc.) and ignored files, and gathers the content of every file into a single consolidated file (`final.txt`).
- **Delimiter format:** Each file is prefixed with a distinctive header containing its relative path:
  ```text
  === relative/path/to/file.ext ===
  <file content here>
  ```
- **Use cases:**
  - Sharing entire codebases or folder trees with LLMs/chat interfaces in a single prompt.
  - Generating complete snapshot text files of projects for reviews, archiving, or auditing.

### 2. `unpack.py` (File Extractor / Reverse Unbundler)
- **What it does:** Reverses the packing operation. Reads the consolidated file (`final.txt`), parses each `=== <relative_path> ===` section, recreates any missing parent directories, and writes the contents back to their original relative file paths.
- **Key features:**
  - **Path Traversal Protection:** Validates paths to prevent writes outside the target folder.
  - **Directory Recreation:** Automatically creates nested subdirectories on demand.
  - **Configurable Overwriting:** Supports overwriting existing files or preserving them via options.

---

## Usage

### Packing Files (`pack.py`)

Run the script to bundle files into `final.txt`:
```bash
python pack.py
```

Or import and customize the parameters inside Python:
```python
from pack import pack_files # or testytest

pack_files(
    root_dir='.',
    output_file='final.txt',
    ignore_dirs={'node_modules', '.git', 'dist'},
    ignore_files={'package-lock.json'}
)
```

### Unpacking Files (`unpack.py`)

Restore all files from `final.txt` into the current directory:
```bash
python unpack.py
```

Or specify custom input files and target directories via command-line arguments:
```bash
# Unpack a specific bundle into an output directory
python unpack.py -i final.txt -t ./restored_project

# Prevent overwriting existing files
python unpack.py -i final.txt -t ./restored_project --no-overwrite
```

Or import into your Python script:
```python
from unpack import unpack_files

unpack_files(
    input_file='final.txt',
    target_dir='./restored_project',
    overwrite=True
)
```
