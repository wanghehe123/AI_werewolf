#!/usr/bin/env python3
"""Collect portable evaluation artifacts into one manifest."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    repo_root = Path(args.repo_root)
    response = _read_json(run_dir / "response.json")
    data = response.get("data") or response
    game_id = data.get("game_id") or _read_env(run_dir / "run.env").get("GAME_ID", "")
    prompt_dir = repo_root / "logs" / "prompt_traces" / game_id

    prompt_files = []
    if prompt_dir.exists():
        prompt_files = [
            {
                "path": str(path),
                "name": path.name,
                "chars": len(path.read_text(encoding="utf-8", errors="replace")),
            }
            for path in sorted(prompt_dir.glob("*.md"))
        ]

    events = []
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))

    backend_log = run_dir / "backend.log"
    manifest = {
        "run_dir": str(run_dir),
        "game_id": game_id,
        "status": data.get("status"),
        "winner": data.get("winner"),
        "response_path": str(run_dir / "response.json"),
        "events_path": str(events_path),
        "backend_log_path": str(backend_log),
        "prompt_trace_dir": str(prompt_dir),
        "prompt_files": prompt_files,
        "event_counts": _count_by(events, "event_type"),
        "phase_counts": _count_by(events, "phase"),
        "players": data.get("players", []),
    }
    (run_dir / "artifacts.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_game_log_stub(run_dir, manifest, events)
    print(run_dir / "artifacts.json")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _count_by(events: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        value = str(event.get(key) or "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _write_game_log_stub(run_dir: Path, manifest: dict, events: list[dict]) -> None:
    lines = [
        "# Game Log Curation",
        "",
        f"- game_id: `{manifest.get('game_id')}`",
        f"- status: `{manifest.get('status')}`",
        f"- winner: `{manifest.get('winner')}`",
        "",
        "## Key Events",
    ]
    for event in events:
        payload = event.get("payload") or {}
        message = payload.get("message") or payload.get("speech") or ""
        if message:
            lines.append(f"- `{event.get('phase')}` `{event.get('event_type')}`: {message}")
    lines.extend([
        "",
        "## Curator Notes",
        "",
        "Use `templates/log-curator-task.md` to replace this stub with a full narrative.",
    ])
    (run_dir / "01-game-log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
