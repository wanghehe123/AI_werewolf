"""Tests for the few-shot example loader.

Tests cover:
- Loading examples from existing JSON files
- Fallback to default when board_key is not found
- Empty list for missing files
- Custom board key examples
"""
from __future__ import annotations

import json
import pytest

from ai_werewolf.llm.fewshots.loader import load_fewshots, FEWSHOTS_DIR


# =====================================================================
# Tests: Loading existing files
# =====================================================================


class TestLoadFewshots:
    """Tests for the load_fewshots function."""

    def test_load_day_speech_default(self):
        """Load default examples from day_speech.json."""
        examples = load_fewshots("day_speech")
        assert len(examples) == 2
        assert examples[0]["role"] == "villager"
        assert examples[1]["role"] == "werewolf"
        assert examples[0]["action_type"] == "speak"

    def test_load_vote_default(self):
        """Load default examples from vote.json."""
        examples = load_fewshots("vote")
        assert len(examples) == 1
        assert examples[0]["action_type"] == "vote"
        assert examples[0]["role"] == "villager"

    def test_missing_file_returns_empty(self):
        """Non-existent category file returns empty list."""
        examples = load_fewshots("nonexistent_category")
        assert examples == []

    def test_unknown_board_key_falls_back_to_default(self):
        """Unknown board_key falls back to 'default'."""
        examples = load_fewshots("day_speech", board_key="nonexistent_board")
        assert len(examples) == 2  # same as default

    def test_default_board_key(self):
        """Explicit 'default' board_key returns default examples."""
        examples = load_fewshots("day_speech", board_key="default")
        assert len(examples) == 2


class TestCustomBoardKey:
    """Tests for custom board_key handling."""

    def test_custom_board_key_with_fallback(self, tmp_path, monkeypatch):
        """Custom board_key returns board-specific examples when available."""
        # Create a temporary JSON file with a custom board key
        custom_data = {
            "version": 1,
            "examples": {
                "default": [
                    {"role": "villager", "speech": "default speech", "action_type": "speak"},
                ],
                "wolf3_seer1_witch1_civ4": [
                    {"role": "villager", "speech": "custom speech", "action_type": "speak"},
                    {"role": "seer", "speech": "custom seer speech", "action_type": "speak"},
                ],
            },
        }
        custom_file = tmp_path / "custom_category.json"
        custom_file.write_text(json.dumps(custom_data, ensure_ascii=False), encoding="utf-8")

        # Monkey-patch FEWSHOTS_DIR to use our temp directory
        import ai_werewolf.llm.fewshots.loader as loader_mod
        monkeypatch.setattr(loader_mod, "FEWSHOTS_DIR", tmp_path)

        # Load with custom board key
        examples = load_fewshots("custom_category", board_key="wolf3_seer1_witch1_civ4")
        assert len(examples) == 2
        assert examples[0]["speech"] == "custom speech"

        # Load with unknown board key -> fallback to default
        fallback = load_fewshots("custom_category", board_key="unknown")
        assert len(fallback) == 1
        assert fallback[0]["speech"] == "default speech"


class TestJsonStructure:
    """Tests that the JSON files are valid and have expected structure."""

    def test_day_speech_file_exists(self):
        assert (FEWSHOTS_DIR / "day_speech.json").exists()

    def test_vote_file_exists(self):
        assert (FEWSHOTS_DIR / "vote.json").exists()

    def test_day_speech_has_version(self):
        data = json.loads((FEWSHOTS_DIR / "day_speech.json").read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert "examples" in data
        assert "default" in data["examples"]

    def test_vote_has_version(self):
        data = json.loads((FEWSHOTS_DIR / "vote.json").read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert "examples" in data
