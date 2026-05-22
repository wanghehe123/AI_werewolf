#!/usr/bin/env python3
"""Create phase-specific scoring task files from collected artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PHASES = [
    ("night", "Night Eval"),
    ("day_speech", "Day Speech Eval"),
    ("vote", "Vote Eval"),
    ("memory", "Memory Eval"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    artifacts = json.loads((run_dir / "artifacts.json").read_text(encoding="utf-8"))
    tasks_dir = run_dir / "phase-tasks"
    tasks_dir.mkdir(exist_ok=True)

    for phase_key, title in PHASES:
        task_path = tasks_dir / f"{phase_key}.md"
        task_path.write_text(_task_content(title, phase_key, artifacts), encoding="utf-8")
        score_path = run_dir / f"score-{phase_key}.md"
        if not score_path.exists():
            score_path.write_text(_score_stub(title), encoding="utf-8")
    print(tasks_dir)


def _task_content(title: str, phase_key: str, artifacts: dict) -> str:
    return f"""# {title}

Read these files:

- `{artifacts.get('response_path')}`
- `{artifacts.get('events_path')}`
- `{artifacts.get('backend_log_path')}`
- `{artifacts.get('prompt_trace_dir')}`
- `{artifacts.get('run_dir')}/01-game-log.md`

Focus phase: `{phase_key}`.

Score every relevant player from 0 to 10 for legality, consistency, reasoning quality, and memory use.
Write evidence-backed findings to `{artifacts.get('run_dir')}/score-{phase_key}.md`.
"""


def _score_stub(title: str) -> str:
    return f"""# {title} Scores

Status: not reviewed

| Player | Score | Evidence | Notes |
| --- | ---: | --- | --- |
"""


if __name__ == "__main__":
    main()
