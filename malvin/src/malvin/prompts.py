from __future__ import annotations

import importlib.resources as resources
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Template

REQUIRED_PROMPTS = (
    "implement.md",
    "review_1.md",
    "review_2.md",
    "kpop.md",
    "concerns.md",
)
DEFAULT_PROMPTS = REQUIRED_PROMPTS + ("learn.md", "coding_rules.md")


class PromptError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromptStore:
    root: Path

    @classmethod
    def default(cls) -> PromptStore:
        return cls(root=Path.home() / ".malvin" / "prompts")

    def ensure_defaults(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        package_root = resources.files("malvin") / "default_prompts"
        for filename in DEFAULT_PROMPTS:
            self._copy_default_if_missing(package_root, filename)

    def validate_required(self) -> None:
        missing = [name for name in REQUIRED_PROMPTS if not (self.root / name).exists()]
        if not missing:
            return
        lines = ", ".join(missing)
        message = (
            "Missing required prompt files in ~/.malvin/prompts/: "
            f"{lines}. Reinstall malvin or copy the missing files there."
        )
        raise PromptError(message)

    def validate_exists(self, filename: str) -> None:
        if (self.root / filename).exists():
            return
        raise PromptError(
            f"Missing prompt file in ~/.malvin/prompts/: {filename}. "
            "Reinstall malvin or copy the missing file there."
        )

    def render(self, filename: str, context: Mapping[str, str]) -> str:
        try:
            prompt_text = (self.root / filename).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise PromptError(
                f"Missing prompt file in ~/.malvin/prompts/: {filename}. "
                "Reinstall malvin or copy the missing file there."
            ) from exc
        render_context = dict(context)
        render_context["coding_rules"] = self._load_coding_rules()
        return _render_template(prompt_text, render_context)

    def _copy_default_if_missing(
        self, package_root: resources.abc.Traversable, filename: str
    ) -> None:
        target = self.root / filename
        if target.exists():
            return
        source = package_root / filename
        with source.open("r", encoding="utf-8") as src:
            target.write_text(src.read(), encoding="utf-8")

    def _load_coding_rules(self) -> str:
        coding_rules_path = self.root / "coding_rules.md"
        if not coding_rules_path.exists():
            return ""
        return coding_rules_path.read_text(encoding="utf-8").strip()


def _render_template(prompt_text: str, context: Mapping[str, str]) -> str:
    translated = prompt_text
    for key in context:
        translated = translated.replace(f"{{{{ {key} }}}}", f"${key}")
    return Template(translated).safe_substitute(context)
