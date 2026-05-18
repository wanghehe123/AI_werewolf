"""Runtime helpers for loading and rendering packaged `.st` prompt templates."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from string import Template
from typing import Mapping


class PromptTemplateError(RuntimeError):
    """Base error for prompt template loading/rendering."""


class PromptTemplateNotFoundError(PromptTemplateError):
    """Raised when a named prompt template cannot be found."""


def render_template(template_name: str, context: Mapping[str, str]) -> str:
    """Render a packaged `.st` template with strict variable substitution."""
    try:
        template = Template(_read_template(template_name))
        return template.substitute(dict(context))
    except FileNotFoundError as exc:
        raise PromptTemplateNotFoundError(f"Prompt template not found: {template_name}") from exc
    except KeyError as exc:
        missing_key = exc.args[0]
        raise KeyError(f"Missing variable '{missing_key}' for prompt template {template_name}") from exc


@lru_cache(maxsize=None)
def _read_template(template_name: str) -> str:
    return _load_template_source(template_name)


def _load_template_source(template_name: str) -> str:
    package = resources.files("ai_werewolf.llm.prompts").joinpath("templates")
    template_path = package.joinpath(*template_name.split("/"))
    return template_path.read_text(encoding="utf-8")
