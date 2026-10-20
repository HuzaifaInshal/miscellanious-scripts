import os
from pathlib import Path


def testytest(
    root_dir: str = '.',
    output_file: str = 'final.txt',
    ignore_dirs: set[str] | None = None,
    ignore_files: set[str] | None = None,
):
    """
    Traverses the directory tree starting at root_dir, gathers the content
    of text files, and writes them into a single consolidated output file.
    Each file section is prefixed with '=== <relative_path> ==='.
    """
    if ignore_dirs is None:
        ignore_dirs = {
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
    if ignore_files is None:
        ignore_files = {'package-lock.json', 'test.py'}

    root_path = Path(root_dir).resolve()
    outputh_path = Path(output_file).resolve()

    with open(outputh_path, 'w', encoding='utf-8') as outfile:
        for current_dir, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for file_name in sorted(files):
                if file_name in ignore_files:
                    continue

                file_path = Path(current_dir) / file_name

                if file_path.resolve() == outputh_path:
                    continue

                rel_path = file_path.relative_to(root_path).as_posix()

                try:
                    with open(
                        file_path, 'r', encoding='utf-8', errors='replace'
                    ) as infile:
                        content = infile.read()

                    outfile.write(f"=== {rel_path} ===\n")
                    outfile.write(content)
                    if not content.endswith("\n"):
                        outfile.write("\n")
                    outfile.write("\n")
                except Exception as e:
                    print(f"Error occurred reading {rel_path}: {e}")


# Alias for intuitive naming
pack_files = testytest

if __name__ == '__main__':
    testytest()
