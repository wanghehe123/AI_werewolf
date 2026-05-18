import pytest

from ai_werewolf.llm.prompts.template_loader import (
    PromptTemplateNotFoundError,
    render_template,
)


def test_render_template_reads_st_template_and_substitutes_variables():
    rendered = render_template(
        "fragments/phase_focus_default.st",
        {"decision_kind": "custom_phase"},
    )

    assert "【阶段目标】" in rendered
    assert "当前阶段：custom_phase" in rendered


def test_render_template_raises_for_missing_template():
    with pytest.raises(PromptTemplateNotFoundError) as excinfo:
        render_template("missing/not_found.st", {})

    assert "missing/not_found.st" in str(excinfo.value)


def test_render_template_raises_key_error_for_missing_variable():
    with pytest.raises(KeyError):
        render_template("fragments/phase_focus_default.st", {})


def test_render_template_caches_template_file_reads(monkeypatch):
    from ai_werewolf.llm.prompts import template_loader

    original = template_loader._load_template_source
    calls = {"count": 0}

    def counting_loader(template_name: str) -> str:
        calls["count"] += 1
        return original(template_name)

    template_loader._read_template.cache_clear()
    monkeypatch.setattr(template_loader, "_load_template_source", counting_loader)

    first = render_template("fragments/phase_focus_default.st", {"decision_kind": "first"})
    second = render_template("fragments/phase_focus_default.st", {"decision_kind": "second"})

    assert "first" in first
    assert "second" in second
    assert calls["count"] == 1
