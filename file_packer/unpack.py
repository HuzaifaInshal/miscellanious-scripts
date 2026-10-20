import argparse
from pathlib import Path
import re


def unpack_files(
    input_file: str = 'final.txt',
    target_dir: str = '.',
    overwrite: bool = True,
):
    """
    Reverse of testytest / pack_files:
    Reads the consolidated text file and unpacks/restores each file
    back into its original directory structure.
    """
    input_path = Path(input_file).resolve()
    target_path = Path(target_dir).resolve()

    if not input_path.exists():
        print(f"Error: Input file '{input_path}' not found.")
        return

    with open(input_path, 'r', encoding='utf-8', errors='replace') as infile:
        content = infile.read()

    # Match header format: '=== relative/path/to/file.ext ==='
    pattern = re.compile(r"^=== (.+?) ===$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        print(f"No file headers matching '=== <file_path> ===' found in '{input_path}'.")
        return

    print(f"Found {len(matches)} file(s) in '{input_path}'. Unpacking into '{target_path}'...")

    for i, match in enumerate(matches):
        rel_path_str = match.group(1).strip()
        # Content starts immediately after the header's newline
        start_idx = match.end()
        if start_idx < len(content) and content[start_idx] == '\n':
            start_idx += 1

        # Content ends at the start of next header or end of file
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        file_content = content[start_idx:end_idx]

        # The packer appends an extra newline as a delimiter between files:
        # outfile.write("\n")
        # Strip off the single delimiter newline at the end if present.
        if file_content in ("\n\n", "\n"):
            file_content = ""
        elif file_content.endswith("\n\n"):
            file_content = file_content[:-1]

        # Validate path to prevent directory traversal outside target_path
        out_file_path = (target_path / rel_path_str).resolve()
        try:
            out_file_path.relative_to(target_path)
        except ValueError:
            print(f"Security Warning: Skipping path outside target directory: {rel_path_str}")
            continue

        if out_file_path.exists() and not overwrite:
            print(f"Skipping existing file (overwrite=False): {rel_path_str}")
            continue

        try:
            out_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file_path, 'w', encoding='utf-8') as outfile:
                outfile.write(file_content)
            print(f"Restored: {rel_path_str}")
        except Exception as e:
            print(f"Error occurred writing {rel_path_str}: {e}")

    print("Unpacking completed.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Reverse of testytest: unpack consolidated text file into files and folders."
    )
    parser.add_argument(
        '-i', '--input',
        default='final.txt',
        help="Path to the consolidated input text file (default: final.txt)"
    )
    parser.add_argument(
        '-t', '--target',
        default='.',
        help="Destination directory to restore files into (default: .)"
    )
    parser.add_argument(
        '--no-overwrite',
        action='store_true',
        help="Do not overwrite existing files"
    )

    args = parser.parse_args()
    unpack_files(
        input_file=args.input,
        target_dir=args.target,
        overwrite=not args.no_overwrite,
    )
