from __future__ import annotations

from pathlib import Path

REQUIRED_ROOT_FILES = ("pyproject.toml", "README.md", "requirements-harbor.txt")
REQUIRED_INCLUDE_DIRS = ("src",)
OPTIONAL_INCLUDE_DIRS = ("prompts",)

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "__pycache__",
    "jobs",
    "_malvin",
    "dist",
    "build",
    ".eggs",
    "htmlcov",
}
EXCLUDED_FILE_NAMES = {".coverage"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def to_relative_posix(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def should_exclude_path(rel_path: Path) -> bool:
    return (
        any(part in EXCLUDED_PARTS for part in rel_path.parts)
        or any(part.endswith(".egg-info") for part in rel_path.parts)
        or rel_path.name in EXCLUDED_FILE_NAMES
        or rel_path.suffix in EXCLUDED_SUFFIXES
    )


def validate_required_inputs(repo_root: Path) -> None:
    required_src = repo_root / "src"
    if not required_src.exists() or not required_src.is_dir():
        raise FileNotFoundError(f"Required bundle directory not found: {required_src}")
    for required_name in REQUIRED_ROOT_FILES:
        required_path = repo_root / required_name
        if not required_path.exists() or not required_path.is_file():
            raise FileNotFoundError(f"Required bundle input not found: {required_path}")


def collect_required_root_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for required_name in REQUIRED_ROOT_FILES:
        required_path = repo_root / required_name
        if not required_path.exists():
            raise FileNotFoundError(f"Required bundle input not found: {required_path}")
        if not required_path.is_file():
            raise FileNotFoundError(f"Required bundle input is not a file: {required_path}")
        files.append(required_path)
    return files


def include_directories(include_prompts: bool) -> tuple[str, ...]:
    if include_prompts:
        return REQUIRED_INCLUDE_DIRS + OPTIONAL_INCLUDE_DIRS
    return REQUIRED_INCLUDE_DIRS


def iter_included_files(repo_root: Path, base_dir: Path) -> list[Path]:
    included: list[Path] = []
    for file_path in base_dir.rglob("*"):
        if file_path.is_file() and not should_exclude_path(file_path.relative_to(repo_root)):
            included.append(file_path)
    return included
