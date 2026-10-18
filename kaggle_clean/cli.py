"""Command line interface for kaggle_clean."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from kaggle_clean import __version__
from kaggle_clean.cleaner import RenameResult, clean_directory, clean_file, split_filename


class Colors:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def format_message(msg: str, color: str, use_color: bool) -> str:
    if not use_color:
        return msg
    return f"{color}{msg}{Colors.RESET}"


def print_result(result: RenameResult, use_color: bool, verbose: bool, dry_run: bool) -> None:
    prefix = "[DRY RUN] " if dry_run else ""
    if result.status == "renamed":
        tag = format_message("✔ RENAMED", Colors.GREEN + Colors.BOLD, use_color)
        src = result.source.name
        dst = result.target.name
        print(f"  {prefix}{tag}  '{src}' -> '{dst}'")
    elif result.status == "collision_resolved":
        tag = format_message("⚠ RENAMED (collision)", Colors.YELLOW + Colors.BOLD, use_color)
        src = result.source.name
        dst = result.target.name
        print(f"  {prefix}{tag}  '{src}' -> '{dst}'")
    elif result.status == "already_clean":
        if verbose:
            tag = format_message("ℹ CLEAN", Colors.BLUE, use_color)
            print(f"  {prefix}{tag}  '{result.source.name}' is already Kaggle compliant")
    elif result.status == "error":
        tag = format_message("✖ ERROR", Colors.RED + Colors.BOLD, use_color)
        print(f"  {prefix}{tag}  '{result.source.name}': {result.error_message}")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="kaggle_clean",
        description="Rename and sanitize files to meet Kaggle upload requirements (POSIX compliant).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  kaggle_clean my_file.pdf               # Clean a single file
  kaggle_clean .                         # Clean all files in current directory
  kaggle_clean . -e pdf,txt,md           # Clean only specific file types
  kaggle_clean . --dry-run               # Preview renames without modifying files
  kaggle_clean /path/to/data -r          # Clean recursively in subdirectories
""",
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="One or more files or directories to clean (defaults to current directory '.').",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Preview changes without renaming any files.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively process subdirectories.",
    )
    parser.add_argument(
        "-e",
        "--ext",
        help="Comma-separated list of file extensions to include (e.g. 'pdf,txt,md,mp3,opus,wav').",
    )
    parser.add_argument(
        "-l",
        "--lower",
        action="store_true",
        help="Convert entire filename stem to lowercase.",
    )
    parser.add_argument(
        "-s",
        "--separator",
        default="_",
        help="Replacement character for spaces and special characters (default: '_').",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output including already-compliant files.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in output.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)

    use_color = not args.no_color and sys.stdout.isatty()

    # Parse extensions
    extensions = None
    if args.ext:
        extensions = {ext.strip() for ext in args.ext.split(",") if ext.strip()}

    all_results: List[RenameResult] = []

    for path_str in args.paths:
        p = Path(path_str)
        if not p.exists():
            all_results.append(
                RenameResult(
                    source=p,
                    target=p,
                    status="error",
                    error_message="Path does not exist",
                )
            )
            continue

        if p.is_dir():
            res = clean_directory(
                p,
                extensions=extensions,
                recursive=args.recursive,
                dry_run=args.dry_run,
                separator=args.separator,
                lowercase=args.lower,
            )
            all_results.extend(res)
        else:
            # Single file
            if extensions is not None:
                _, ext = split_filename(p.name)
                # Normalize extension check
                norm_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
                if ext not in norm_exts:
                    continue

            res_single = clean_file(
                p,
                dry_run=args.dry_run,
                separator=args.separator,
                lowercase=args.lower,
            )
            all_results.append(res_single)

    renamed_count = sum(1 for r in all_results if r.status in ("renamed", "collision_resolved"))
    clean_count = sum(1 for r in all_results if r.status == "already_clean")
    error_count = sum(1 for r in all_results if r.status == "error")

    # Print results
    for r in all_results:
        print_result(r, use_color=use_color, verbose=args.verbose, dry_run=args.dry_run)

    # Print summary
    prefix = "[DRY RUN] " if args.dry_run else ""
    if all_results:
        summary = (
            f"\n{prefix}Summary: "
            f"{renamed_count} renamed, "
            f"{clean_count} already compliant, "
            f"{error_count} errors."
        )
        if renamed_count > 0:
            print(format_message(summary, Colors.BOLD, use_color))
        else:
            print(format_message(summary, Colors.DIM, use_color))
    else:
        print(f"{prefix}No files found matching criteria.")

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
