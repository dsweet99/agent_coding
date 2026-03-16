from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    plan_path: Path
    work_dir: Path

    def log_path(self, name: str) -> Path:
        safe_name = name.replace("/", "_")
        return self.run_dir / f"{safe_name}.log"


def create_run_artifacts(plan_source: Path, base_dir: Path | None = None) -> RunArtifacts:
    parent = base_dir or Path.cwd()
    run_root = parent / "_malvin"
    run_root.mkdir(parents=True, exist_ok=True)
    identifier = _build_identifier()
    run_dir = run_root / identifier
    run_dir.mkdir(parents=True, exist_ok=False)
    plan_target = run_dir / "plan.md"
    shutil.copy2(plan_source, plan_target)
    return RunArtifacts(
        run_dir=run_dir,
        plan_path=plan_target,
        work_dir=plan_source.resolve().parent,
    )


def _build_identifier() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    token = uuid.uuid4().hex[:8]
    return f"{stamp}_{token}"
