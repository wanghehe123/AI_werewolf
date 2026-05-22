#!/usr/bin/env python3
"""Render the phase score summary report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    artifacts_path = run_dir / "artifacts.json"
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8")) if artifacts_path.exists() else {}

    parts = [
        "# Phase Scores",
        "",
        f"- game_id: `{artifacts.get('game_id', '')}`",
        f"- status: `{artifacts.get('status', '')}`",
        f"- winner: `{artifacts.get('winner', '')}`",
        "",
        "## Score Files",
        "",
    ]
    for path in sorted(run_dir.glob("score-*.md")):
        parts.append(f"### {path.name}")
        parts.append("")
        parts.append(path.read_text(encoding="utf-8"))
        parts.append("")

    parts.extend([
        "## Low Score Follow-Up",
        "",
        "Use `templates/prompt-review-task.md` to inspect low-score players and write `03-low-score-prompt-review.md`.",
    ])
    output = run_dir / "02-phase-scores.md"
    output.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
