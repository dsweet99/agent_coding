from __future__ import annotations

from pathlib import Path

import pytest

from malvin.prompts import REQUIRED_PROMPTS, PromptError, PromptStore


def test_ensure_defaults_materializes_all_required_prompts(tmp_path: Path) -> None:
    store = PromptStore(root=tmp_path / "prompts")
    store.ensure_defaults()

    existing = {path.name for path in store.root.iterdir()}
    assert set(REQUIRED_PROMPTS).issubset(existing)
    assert "learn.md" in existing
    assert "coding_rules.md" in existing


def test_validate_required_fails_fast_with_clear_message(tmp_path: Path) -> None:
    store = PromptStore(root=tmp_path / "prompts")
    store.root.mkdir(parents=True)
    (store.root / "implement.md").write_text("hello", encoding="utf-8")

    with pytest.raises(PromptError) as error:
        store.validate_required()

    assert "Missing required prompt files" in str(error.value)
    assert "review_1.md" in str(error.value)


def test_render_supports_plan_path_template(tmp_path: Path) -> None:
    store = PromptStore(root=tmp_path / "prompts")
    store.root.mkdir(parents=True)
    (store.root / "implement.md").write_text(
        "Implement plan `{{ plan_path }}` now.",
        encoding="utf-8",
    )

    rendered = store.render("implement.md", {"plan_path": "_malvin/run123/plan.md"})

    assert "_malvin/run123/plan.md" in rendered


def test_render_supports_kpop_log_dir_template(tmp_path: Path) -> None:
    store = PromptStore(root=tmp_path / "prompts")
    store.root.mkdir(parents=True)
    (store.root / "kpop.md").write_text(
        "Write logs to `{{ kpop_log_dir }}/exp_log_{name}.md`.",
        encoding="utf-8",
    )

    rendered = store.render("kpop.md", {"kpop_log_dir": "./_malvin/run123/_kpop"})

    assert "./_malvin/run123/_kpop/exp_log_{name}.md" in rendered


def test_render_injects_coding_rules_contents(tmp_path: Path) -> None:
    store = PromptStore(root=tmp_path / "prompts")
    store.root.mkdir(parents=True)
    (store.root / "implement.md").write_text(
        "Rules:\n{{ coding_rules }}\nPlan: {{ plan_path }}",
        encoding="utf-8",
    )
    (store.root / "coding_rules.md").write_text(
        "- Always run tests\n- Keep diffs small\n",
        encoding="utf-8",
    )

    rendered = store.render("implement.md", {"plan_path": "plan.md"})

    assert "- Always run tests\n- Keep diffs small" in rendered
    assert "{{ coding_rules }}" not in rendered
