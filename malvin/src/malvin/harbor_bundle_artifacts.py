from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .harbor_bundle_paths import to_relative_posix


def compute_source_tree_sha256(repo_root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(files, key=lambda path: to_relative_posix(repo_root, path)):
        digest.update(to_relative_posix(repo_root, file_path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def write_bundle_tar_gz(repo_root: Path, files: list[Path], bundle_path: Path) -> None:
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle_path, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
        for file_path in sorted(files, key=lambda path: to_relative_posix(repo_root, path)):
            tar_info = tar.gettarinfo(
                str(file_path), arcname=to_relative_posix(repo_root, file_path)
            )
            tar_info.uid = 0
            tar_info.gid = 0
            tar_info.uname = ""
            tar_info.gname = ""
            tar_info.mtime = 0
            with file_path.open("rb") as file_obj:
                tar.addfile(tar_info, file_obj)


def write_bundle_metadata(metadata_path: Path, metadata) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(asdict(metadata), indent=2, sort_keys=True), encoding="utf-8"
    )


def get_git_sha(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    git_sha = completed.stdout.strip()
    return git_sha or None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while chunk := file_obj.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def make_bundle_path(output_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return output_dir / f"malvin-harbor-bundle-{timestamp}.tar.gz"
