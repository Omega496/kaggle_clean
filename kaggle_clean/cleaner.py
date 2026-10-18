"""Core sanitization and renaming logic for Kaggle compliance."""

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

COMPOUND_EXTENSIONS = {
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
}

DEFAULT_TARGET_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".mp3",
    ".opus",
    ".wav",
}


@dataclass
class RenameResult:
    source: Path
    target: Path
    status: str  # 'renamed', 'already_clean', 'collision_resolved', 'error'
    error_message: Optional[str] = None

    @property
    def changed(self) -> bool:
        return self.status in ("renamed", "collision_resolved")


def split_filename(filename: str) -> Tuple[str, str]:
    """
    Split filename into (stem, extension).
    Recognizes compound extensions like .tar.gz and normalizes extension to lowercase.
    """
    lower_filename = filename.lower()
    for compound in COMPOUND_EXTENSIONS:
        if lower_filename.endswith(compound):
            stem = filename[: -len(compound)]
            return stem, compound

    parts = filename.rsplit(".", 1)
    if len(parts) == 2 and parts[0]:
        stem, ext = parts[0], "." + parts[1].lower()
    else:
        stem, ext = filename, ""

    return stem, ext


def sanitize_filename(
    filename: str,
    separator: str = "_",
    lowercase: bool = False,
) -> str:
    """
    Sanitize filename to be Kaggle compliant.

    Kaggle allows: letters (a-z, A-Z), numbers (0-9), hyphens (-), underscores (_),
    and periods (.) strictly for file extensions.
    Spaces, brackets, colons, quotes, accents, and non-ASCII chars are replaced.
    """
    stem, ext = split_filename(filename)

    # Normalize Unicode characters (strip accents like é -> e)
    stem_norm = unicodedata.normalize("NFKD", stem)
    stem_ascii = "".join(c for c in stem_norm if not unicodedata.combining(c))

    # If lowercase flag is requested, lowercase stem
    if lowercase:
        stem_ascii = stem_ascii.lower()

    # Replace any character that is not alphanumeric, hyphen, or underscore with separator
    # This also converts internal dots to separator (e.g. file.v1.pdf -> file_v1.pdf)
    cleaned_stem = re.sub(r"[^a-zA-Z0-9_\-]+", separator, stem_ascii)

    # Collapse multiple consecutive separators or mixed hyphens/underscores
    cleaned_stem = re.sub(r"[-_]{2,}", separator, cleaned_stem)

    # Strip leading and trailing separators and periods
    cleaned_stem = cleaned_stem.strip("._- ")

    # If stem ended up completely empty (e.g. original was "???.pdf" or "  .pdf")
    if not cleaned_stem:
        cleaned_stem = "kaggle_file"

    return f"{cleaned_stem}{ext}"


def resolve_collision(target_path: Path, source_path: Path) -> Tuple[Path, bool]:
    """
    Find a non-colliding destination path if target_path already exists.
    Returns (resolved_path, was_collision).
    """
    # If the target path is already identical to the source path, no collision
    try:
        if source_path.resolve() == target_path.resolve():
            return target_path, False
    except FileNotFoundError:
        # If file doesn't exist yet, standard string comparison
        if source_path == target_path:
            return target_path, False

    if not target_path.exists():
        return target_path, False

    stem, ext = split_filename(target_path.name)
    parent = target_path.parent
    counter = 1

    while True:
        candidate_name = f"{stem}_{counter}{ext}"
        candidate_path = parent / candidate_name
        if not candidate_path.exists():
            return candidate_path, True
        counter += 1


def clean_file(
    file_path: Path,
    dry_run: bool = False,
    separator: str = "_",
    lowercase: bool = False,
) -> RenameResult:
    """
    Clean an individual file to comply with Kaggle standards.
    """
    if not file_path.exists():
        return RenameResult(
            source=file_path,
            target=file_path,
            status="error",
            error_message="File does not exist",
        )

    if not file_path.is_file():
        return RenameResult(
            source=file_path,
            target=file_path,
            status="error",
            error_message="Path is not a regular file",
        )

    original_name = file_path.name
    cleaned_name = sanitize_filename(
        original_name,
        separator=separator,
        lowercase=lowercase,
    )

    if original_name == cleaned_name:
        return RenameResult(
            source=file_path,
            target=file_path,
            status="already_clean",
        )

    candidate_target = file_path.parent / cleaned_name
    final_target, had_collision = resolve_collision(candidate_target, file_path)

    status = "collision_resolved" if had_collision else "renamed"

    if not dry_run:
        try:
            file_path.rename(final_target)
        except OSError as e:
            return RenameResult(
                source=file_path,
                target=final_target,
                status="error",
                error_message=str(e),
            )

    return RenameResult(
        source=file_path,
        target=final_target,
        status=status,
    )


def clean_directory(
    dir_path: Path,
    extensions: Optional[Set[str]] = None,
    recursive: bool = False,
    dry_run: bool = False,
    separator: str = "_",
    lowercase: bool = False,
) -> List[RenameResult]:
    """
    Clean files in directory.
    If extensions is specified, only clean files with matching extensions.
    Ignores hidden files and directories (names starting with '.').
    """
    results: List[RenameResult] = []

    if not dir_path.exists():
        return [
            RenameResult(
                source=dir_path,
                target=dir_path,
                status="error",
                error_message="Directory does not exist",
            )
        ]

    normalized_extensions = (
        {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
        if extensions
        else None
    )

    # Collect files
    files_to_process: List[Path] = []
    if recursive:
        for root, dirs, files in os.walk(dir_path):
            # Skip hidden directories like .git
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            root_path = Path(root)
            for f in sorted(files):
                if f.startswith("."):
                    continue
                file_path = root_path / f
                if normalized_extensions is not None:
                    _, ext = split_filename(f)
                    if ext not in normalized_extensions:
                        continue
                files_to_process.append(file_path)
    else:
        for item in sorted(dir_path.iterdir()):
            if item.is_file() and not item.name.startswith("."):
                if normalized_extensions is not None:
                    _, ext = split_filename(item.name)
                    if ext not in normalized_extensions:
                        continue
                files_to_process.append(item)

    for file_path in files_to_process:
        res = clean_file(
            file_path,
            dry_run=dry_run,
            separator=separator,
            lowercase=lowercase,
        )
        results.append(res)

    return results
