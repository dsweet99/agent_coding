from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .harbor_agent_commands import (
    build_malvin_run_command,
    build_plan_write_command,
    normalize_harbor_model_name,
)
from .harbor_bundle import BundleResult, create_harbor_bundle

try:
    from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext

    _HARBOR_IMPORT_ERROR: Exception | None = None
except Exception as exc:

    @dataclass
    class ExecInput:
        command: str
        cwd: str | None = None
        env: dict[str, str] | None = None
        timeout_sec: int | None = None

    class BaseInstalledAgent:
        def __init__(
            self, logs_dir: Path, model_name: str | None = None, *args: Any, **kwargs: Any
        ):
            _ = args
            _ = kwargs
            self.logs_dir = logs_dir
            self.model_name = model_name

        def _setup_env(self) -> dict[str, str]:
            return {"DEBIAN_FRONTEND": "noninteractive"}

        async def setup(self, environment: Any) -> None:
            script_path = self.logs_dir / "install.sh"
            script_path.write_text(
                self._install_agent_template_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
            await environment.upload_file(
                source_path=script_path,
                target_path="/installed-agent/install.sh",
            )
            result = await environment.exec(
                command="bash /installed-agent/install.sh",
                env=self._setup_env(),
            )
            setup_dir = self.logs_dir / "setup"
            setup_dir.mkdir(parents=True, exist_ok=True)
            (setup_dir / "return-code.txt").write_text(str(result.return_code), encoding="utf-8")
            if getattr(result, "stdout", ""):
                (setup_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
            if getattr(result, "stderr", ""):
                (setup_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
            if result.return_code != 0:
                raise RuntimeError(
                    "Agent setup failed with exit code "
                    f"{result.return_code}. See logs in {setup_dir}"
                )

    class BaseEnvironment:
        pass

    class AgentContext:
        pass

    _HARBOR_IMPORT_ERROR = exc


class MalvinHarborAgent(BaseInstalledAgent):
    @staticmethod
    def name() -> str:
        return "malvin-local"

    def __init__(
        self,
        logs_dir: Path,
        *args: Any,
        repo_root: str | Path | None = None,
        include_prompts: bool = True,
        **kwargs: Any,
    ) -> None:
        if _HARBOR_IMPORT_ERROR is None:
            super().__init__(logs_dir, *args, **kwargs)
        else:
            self.logs_dir = logs_dir
            self.model_name = kwargs.get("model_name")
        self._repo_root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
        self._include_prompts = include_prompts

    @property
    def _install_agent_template_path(self) -> Path:
        return Path(__file__).with_name("harbor_install_template.sh.j2")

    async def setup(self, environment: BaseEnvironment) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        prep_result = await environment.exec(command="mkdir -p /installed-agent /logs/agent")
        if prep_result.return_code != 0:
            raise RuntimeError(
                "MalvinHarborAgent setup failed before install script: "
                f"mkdir returned {prep_result.return_code}"
            )

        bundle_result = create_harbor_bundle(
            repo_root=self._repo_root,
            include_prompts=self._include_prompts,
        )
        self._persist_bundle_provenance(bundle_result)

        await environment.upload_file(
            source_path=bundle_result.bundle_path,
            target_path="/installed-agent/malvin.tar.gz",
        )
        await environment.upload_file(
            source_path=bundle_result.metadata_path,
            target_path="/installed-agent/malvin.tar.gz.metadata.json",
        )

        await super().setup(environment)

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        plan_path = "/tmp/malvin_plan.md"
        model_name = normalize_harbor_model_name(self.model_name)
        return [
            ExecInput(
                command=build_plan_write_command(
                    plan_path,
                    instruction,
                    python_bin="/opt/malvin-venv/bin/python",
                )
            ),
            ExecInput(
                command=build_malvin_run_command(
                    plan_path=plan_path,
                    model_name=model_name,
                    log_path="/logs/agent/malvin.txt",
                )
            ),
        ]

    def populate_context_post_run(self, context: AgentContext) -> None:
        _ = context

    def _persist_bundle_provenance(self, bundle_result: BundleResult) -> None:
        provenance_path = self.logs_dir / "bundle-metadata.json"
        provenance_path.write_text(
            json.dumps(bundle_result.metadata.__dict__, indent=2, sort_keys=True),
            encoding="utf-8",
        )


__all__ = [
    "MalvinHarborAgent",
    "build_malvin_run_command",
    "build_plan_write_command",
    "normalize_harbor_model_name",
]
