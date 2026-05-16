"""Prompt trace files for local LLM debugging."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from ai_werewolf.engine.helpers import player_label
from ai_werewolf.engine.session import GameSession

logger = logging.getLogger(__name__)


def record_prompt_trace(session: GameSession, player_id: str, prompt_kind: str, prompt: str) -> Path:
    """Write the full prompt to a trace file and log only compact metadata."""
    player = session.state.player_by_id(player_id)
    trace_dir = Path.cwd() / "logs" / "prompt_traces" / session.state.game_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    seq = len(list(trace_dir.glob("*.md"))) + 1
    filename = (
        f"{seq:06d}_day{session.state.day_count}_{_safe(session.state.phase.value)}_"
        f"{_safe(prompt_kind)}_seat{player.seat}_{_safe(player_id)}.md"
    )
    path = trace_dir / filename
    path.write_text(prompt, encoding="utf-8")

    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    payload = {
        "event": "prompt_trace",
        "game_id": session.state.game_id,
        "board_id": session.state.board_id,
        "phase": session.state.phase.value,
        "day_count": session.state.day_count,
        "prompt_kind": prompt_kind,
        "actor_id": player_id,
        "actor_label": player_label(player_id, session),
        "role_key": player.role_key,
        "prompt_chars": len(prompt),
        "prompt_sha256": digest,
        "path": str(path),
    }
    logger.info("prompt_trace %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return path


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "unknown"
