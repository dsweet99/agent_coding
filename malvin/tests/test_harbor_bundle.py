from __future__ import annotations

import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from malvin import harbor_bundle, harbor_bundle_artifacts, harbor_bundle_paths


def _init_repo(repo_root: Path) -> None:
    (repo_root / "src" / "malvin").mkdir(parents=True)
    (repo_root / "src" / "malvin" / "cli.py").write_text("print('hi')\n", encoding="utf-8")
    (repo_root / "README.md").write_text("# test\n", encoding="utf-8")
    (repo_root / "requirements.txt").write_text("click>=8.1\n", encoding="utf-8")
    (repo_root / ".kissconfig").write_text("[tool.kiss]\n", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")


def _relative_paths(repo_root: Path, files: list[Path]) -> list[str]:
    return [path.relative_to(repo_root).as_posix() for path in files]


def test_collect_bundle_inputs_includes_required_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    files = harbor_bundle.collect_bundle_inputs(tmp_path)
    relative_paths = _relative_paths(tmp_path, files)

    assert "README.md" in relative_paths
    assert "pyproject.toml" in relative_paths
    assert "requirements.txt" in relative_paths
    assert ".kissconfig" in relative_paths
    assert "src/malvin/cli.py" in relative_paths


def test_collect_bundle_inputs_respects_prompts_toggle(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "kpop.md").write_text("prompt", encoding="utf-8")

    with_prompts = _relative_paths(tmp_path, harbor_bundle.collect_bundle_inputs(tmp_path))
    without_prompts = _relative_paths(
        tmp_path,
        harbor_bundle.collect_bundle_inputs(tmp_path, include_prompts=False),
    )

    assert "prompts/kpop.md" in with_prompts
    assert "prompts/kpop.md" not in without_prompts


def test_collect_bundle_inputs_excludes_noisy_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src" / "malvin" / "__pycache__").mkdir()
    (tmp_path / "src" / "malvin" / "__pycache__" / "cli.pyc").write_bytes(b"x")
    (tmp_path / "src" / "malvin" / ".coverage").write_text("x", encoding="utf-8")
    (tmp_path / "src" / "malvin" / "jobs").mkdir()
    (tmp_path / "src" / "malvin" / "jobs" / "out.txt").write_text("x", encoding="utf-8")

    files = _relative_paths(tmp_path, harbor_bundle.collect_bundle_inputs(tmp_path))

    assert "src/malvin/cli.py" in files
    assert "src/malvin/__pycache__/cli.pyc" not in files
    assert "src/malvin/.coverage" not in files
    assert "src/malvin/jobs/out.txt" not in files


def test_create_harbor_bundle_writes_tar_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path / "repo")
    output_dir = tmp_path / "out"
    monkeypatch.setattr(harbor_bundle, "get_git_sha", lambda _repo_root: "deadbeef")

    result = harbor_bundle.create_harbor_bundle(tmp_path / "repo", output_dir=output_dir)

    assert result.bundle_path.exists()
    assert result.metadata_path.exists()
    with tarfile.open(result.bundle_path, "r:gz") as tar:
        names = tar.getnames()
    assert "README.md" in names
    assert "pyproject.toml" in names
    assert "src/malvin/cli.py" in names
    assert all(not name.startswith("/") for name in names)

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["git_sha"] == "deadbeef"
    assert metadata["included_count"] == len(metadata["included_files"])
    assert len(metadata["bundle_sha256"]) == 64
    assert len(metadata["source_tree_sha256"]) == 64


def test_create_harbor_bundle_missing_required_inputs_fails(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("x", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        harbor_bundle.create_harbor_bundle(tmp_path)


def test_should_exclude_path_rules() -> None:
    assert harbor_bundle.should_exclude_path(Path("src/malvin/__pycache__/x.pyc")) is True
    assert harbor_bundle.should_exclude_path(Path("src/malvin/pkg.egg-info/PKG-INFO")) is True
    assert harbor_bundle.should_exclude_path(Path("src/malvin/cli.py")) is False


def test_compute_source_tree_sha256_is_stable_for_input_order(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    file_a = tmp_path / "src" / "malvin" / "a.py"
    file_b = tmp_path / "src" / "malvin" / "b.py"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")

    files = [file_a, file_b]
    hash_one = harbor_bundle.compute_source_tree_sha256(tmp_path, files)
    hash_two = harbor_bundle.compute_source_tree_sha256(tmp_path, list(reversed(files)))
    assert hash_one == hash_two


def test_write_bundle_metadata_and_sha256_file(tmp_path: Path) -> None:
    bundle_file = tmp_path / "bundle.tar.gz"
    bundle_file.write_bytes(b"bundle-bytes")
    metadata = harbor_bundle.BundleMetadata(
        created_at_utc="2026-03-15T00:00:00Z",
        git_sha=None,
        source_tree_sha256="a" * 64,
        bundle_sha256="b" * 64,
        included_files=("README.md",),
        included_count=1,
        repo_root=str(tmp_path),
    )
    metadata_path = tmp_path / "bundle.metadata.json"

    harbor_bundle.write_bundle_metadata(metadata_path, metadata)
    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert loaded["included_count"] == 1
    assert harbor_bundle.sha256_file(bundle_file) == harbor_bundle.sha256_file(bundle_file)


def test_get_git_sha_handles_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_success(*_args, **_kwargs):  # noqa: ANN001
        return SimpleNamespace(returncode=0, stdout="abc123\n")

    monkeypatch.setattr(harbor_bundle_artifacts.subprocess, "run", fake_success)
    assert harbor_bundle.get_git_sha(tmp_path) == "abc123"

    def fake_failure(*_args, **_kwargs):  # noqa: ANN001
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(harbor_bundle_artifacts.subprocess, "run", fake_failure)
    assert harbor_bundle.get_git_sha(tmp_path) is None


def test_write_bundle_tar_gz_normalizes_tar_headers(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    files = harbor_bundle.collect_bundle_inputs(tmp_path)
    bundle_path = tmp_path / "out" / "bundle.tar.gz"

    harbor_bundle.write_bundle_tar_gz(tmp_path, files, bundle_path)

    with tarfile.open(bundle_path, "r:gz") as tar:
        member = tar.getmember("src/malvin/cli.py")
        assert member.uid == 0
        assert member.gid == 0
        assert member.uname == ""
        assert member.gname == ""
        assert member.mtime == 0


def test_bundle_paths_helpers(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    rel = harbor_bundle_paths.to_relative_posix(tmp_path, tmp_path / "src" / "malvin" / "cli.py")
    assert rel == "src/malvin/cli.py"
    assert harbor_bundle_paths.include_directories(True) == ("src", "prompts")
    assert harbor_bundle_paths.include_directories(False) == ("src",)

    required = harbor_bundle_paths.collect_required_root_files(tmp_path)
    required_rels = {path.relative_to(tmp_path).as_posix() for path in required}
    assert required_rels == {"README.md", "pyproject.toml", "requirements.txt", ".kissconfig"}

    included = harbor_bundle_paths.iter_included_files(tmp_path, tmp_path / "src")
    included_rels = {path.relative_to(tmp_path).as_posix() for path in included}
    assert "src/malvin/cli.py" in included_rels

    harbor_bundle_paths.validate_required_inputs(tmp_path)
    with pytest.raises(FileNotFoundError):
        harbor_bundle_paths.validate_required_inputs(tmp_path / "missing")


def test_make_bundle_path_uses_expected_format(tmp_path: Path) -> None:
    bundle_path = harbor_bundle_artifacts.make_bundle_path(tmp_path)
    assert bundle_path.parent == tmp_path
    assert bundle_path.name.startswith("malvin-harbor-bundle-")
    assert bundle_path.name.endswith(".tar.gz")
