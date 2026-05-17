"""Load few-shot examples from JSON files, optionally filtered by board."""
from __future__ import annotations

import json
from pathlib import Path

FEWSHOTS_DIR = Path(__file__).parent


def load_fewshots(category: str, board_key: str = "default") -> list[dict]:
    """Load few-shot examples for a given category and board configuration.

    Args:
        category: e.g. "day_speech", "vote", "wolf_kill"
        board_key: e.g. "default" or a specific board key like
            "wolf3_seer1_witch1_civ4"

    Returns:
        List of example dicts, or empty list if file not found.
    """
    path = FEWSHOTS_DIR / f"{category}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    examples = data.get("examples", {})
    return examples.get(board_key, examples.get("default", []))
