from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .harbor_bundle_artifacts import (
    compute_source_tree_sha256,
    get_git_sha,
    make_bundle_path,
    sha256_file,
    write_bundle_metadata,
    write_bundle_tar_gz,
)
from .harbor_bundle_paths import (
    collect_required_root_files,
    include_directories,
    iter_included_files,
    should_exclude_path,
    to_relative_posix,
    validate_required_inputs,
)


@dataclass(frozen=True)
class BundleMetadata:
    created_at_utc: str
    git_sha: str | None
    source_tree_sha256: str
    bundle_sha256: str
    included_files: tuple[str, ...]
    included_count: int
    repo_root: str


@dataclass(frozen=True)
class BundleResult:
    bundle_path: Path
    metadata_path: Path
    metadata: BundleMetadata


def create_harbor_bundle(
    repo_root: Path,
    output_dir: Path | None = None,
    *,
    include_prompts: bool = True,
) -> BundleResult:
    repo_root = repo_root.resolve()
    validate_required_inputs(repo_root)
    files = collect_bundle_inputs(repo_root, include_prompts=include_prompts)
    bundle_path = _build_bundle_archive(repo_root, files, output_dir=output_dir)
    metadata_path = Path(f"{bundle_path}.metadata.json")
    metadata = _build_metadata(repo_root, files, bundle_path)
    write_bundle_metadata(metadata_path, metadata)
    return BundleResult(bundle_path=bundle_path, metadata_path=metadata_path, metadata=metadata)


def collect_bundle_inputs(repo_root: Path, *, include_prompts: bool = True) -> list[Path]:
    repo_root = repo_root.resolve()
    files = collect_required_root_files(repo_root)
    for include_dir in include_directories(include_prompts):
        base_dir = repo_root / include_dir
        if not base_dir.exists():
            if include_dir == "src":
                raise FileNotFoundError(f"Required bundle directory not found: {base_dir}")
            continue
        if not base_dir.is_dir():
            raise FileNotFoundError(f"Bundle input is not a directory: {base_dir}")
        files.extend(iter_included_files(repo_root, base_dir))
    return sorted(set(files), key=lambda path: to_relative_posix(repo_root, path))


def _build_bundle_archive(repo_root: Path, files: list[Path], *, output_dir: Path | None) -> Path:
    resolved_output_dir = (output_dir or Path(tempfile.gettempdir())).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = make_bundle_path(resolved_output_dir)
    write_bundle_tar_gz(repo_root, files, bundle_path)
    return bundle_path


def _build_metadata(repo_root: Path, files: list[Path], bundle_path: Path) -> BundleMetadata:
    return BundleMetadata(
        created_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_sha=get_git_sha(repo_root),
        source_tree_sha256=compute_source_tree_sha256(repo_root, files),
        bundle_sha256=sha256_file(bundle_path),
        included_files=tuple(to_relative_posix(repo_root, file_path) for file_path in files),
        included_count=len(files),
        repo_root=str(repo_root),
    )


__all__ = [
    "BundleMetadata",
    "BundleResult",
    "collect_bundle_inputs",
    "compute_source_tree_sha256",
    "create_harbor_bundle",
    "get_git_sha",
    "sha256_file",
    "should_exclude_path",
    "write_bundle_metadata",
    "write_bundle_tar_gz",
]
