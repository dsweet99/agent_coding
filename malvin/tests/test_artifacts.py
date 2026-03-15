from __future__ import annotations

from pathlib import Path

from malvin.artifacts import create_run_artifacts


def test_create_run_artifacts_creates_run_dir_and_copies_plan(tmp_path: Path) -> None:
    source_plan = tmp_path / "plan.md"
    source_plan.write_text("test plan", encoding="utf-8")

    artifacts = create_run_artifacts(source_plan, base_dir=tmp_path)

    assert artifacts.run_dir.exists()
    assert artifacts.run_dir.parent.name == "_malvin"
    assert artifacts.plan_path.exists()
    assert artifacts.plan_path.read_text(encoding="utf-8") == "test plan"
    assert artifacts.work_dir == tmp_path.resolve()
