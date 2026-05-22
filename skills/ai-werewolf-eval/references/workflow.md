# AI Werewolf Eval Workflow

## Artifact Contract

Each run writes to `docs/evaluations/<run_id>/` by default.

- `request.json`: request sent to the backend.
- `response.json`: blocking evaluation API response.
- `events.jsonl`: one stream event per line when the backend returns events.
- `backend.log`: backend stdout/stderr when this skill started the server.
- `run.env`: shell-readable metadata with `GAME_ID`, `STATUS`, and `WINNER`.
- `artifacts.json`: normalized manifest from `collect_artifacts.py`.
- `01-game-log.md`: curated game timeline.
- `score-*.md`: phase-specific scorer outputs.
- `02-phase-scores.md`: merged score report.
- `03-low-score-prompt-review.md`: prompt/code review, produced by the main agent.
- `04-implementation-plan.md`: implementation plan, produced only after human review.

## Phase 1

Run the backend and trigger the blocking evaluation endpoint with `scripts/run_eval.sh`.
If the backend is already healthy, the script reuses it and leaves `backend.log` empty except for later manual appends.

## Phase 2

Run `collect_artifacts.py` and `split_phase_tasks.py`.
Assign the generated `phase-tasks/*.md` files to parallel agents if available; otherwise execute them sequentially.

## Phase 3

Read `02-phase-scores.md`, identify low-score players, inspect their prompt traces and relevant code, then write `03-low-score-prompt-review.md`.
Stop after writing that file.

## Phase 4

After human review, write `04-implementation-plan.md` from the template.
