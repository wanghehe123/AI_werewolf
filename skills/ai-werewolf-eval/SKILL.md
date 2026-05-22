---
name: ai-werewolf-eval
description: Run cross-agent AI Werewolf evaluations by starting the backend, calling the blocking all-AI evaluation API with curl, collecting logs, splitting phase review tasks, scoring player behavior and memory, and producing Markdown reports for human review before implementation planning.
---

# AI Werewolf Evaluation

Use this skill to run an automated all-AI Werewolf game and produce portable evaluation artifacts. The workflow is intentionally platform-neutral: any agent can run shell/Python scripts, read and write files, and use the prompt templates.

## Principles

- Do not depend on a platform-specific subagent API.
- Use HTTP, shell, Python, JSONL, and Markdown as the shared interface.
- Persist every intermediate artifact under one run directory.
- Parallel scoring is optional; when unavailable, execute the same task templates sequentially.
- Stop after the prompt/code review report and wait for human review before writing an implementation plan.

## Quick Start

```bash
skills/ai-werewolf-eval/scripts/run_eval.sh \
  --base-url http://localhost:8000 \
  --board-id <board_id> \
  --seed 123 \
  --max-steps 80
```

The script prints the run directory. Continue with:

```bash
python3 skills/ai-werewolf-eval/scripts/collect_artifacts.py --run-dir <run_dir>
python3 skills/ai-werewolf-eval/scripts/split_phase_tasks.py --run-dir <run_dir>
python3 skills/ai-werewolf-eval/scripts/render_report.py --run-dir <run_dir>
```

## Workflow

1. **Run game and collect raw logs**
   - Run `scripts/run_eval.sh`.
   - If backend is not healthy, the script starts it and tees logs to `backend.log`.
   - It calls `POST /evaluations/ai-games/run` with curl and saves `response.json`.
   - It extracts `events.jsonl` from the response when present.

2. **Curate game log**
   - Use `templates/log-curator-task.md`.
   - Input: `backend.log`, `events.jsonl`, `response.json`, prompt trace metadata.
   - Output: `01-game-log.md`.

3. **Score phases**
   - Run `collect_artifacts.py` and `split_phase_tasks.py`.
   - Use `templates/phase-scorer-task.md` for Night, Day Speech, Vote, and Memory.
   - Each scorer writes one `score-<phase>.md`.
   - Run `render_report.py` to create `02-phase-scores.md`.

4. **Review low scores**
   - Use `templates/prompt-review-task.md`.
   - Read low scoring players, related prompt traces, memory snapshots, and relevant code.
   - Output `03-low-score-prompt-review.md`.
   - Pause here for human review.

5. **Write implementation plan after review**
   - After the human gives feedback, use `templates/implementation-plan-template.md`.
   - Output `04-implementation-plan.md`.

## References

- `references/workflow.md`: detailed phase workflow and artifact contracts.
- `references/scoring-rubric.md`: scoring criteria.
- `references/agent-adapters.md`: how Codex, Claude Code, OpenClaw, and generic agents run the same workflow.
