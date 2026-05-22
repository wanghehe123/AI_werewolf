# Agent Adapters

## Codex

Use `spawn_agent` only when the current environment supports it and the user permits parallel agent work. Otherwise execute generated task files in order.

## Claude Code

Use the `Task` tool for independent scoring tasks:

- Log Curator
- Night Eval
- Day Speech Eval
- Vote Eval
- Memory Eval

Each task must read files from the run directory and write its assigned Markdown output.

## OpenClaw and Generic Agents

Run the scripts with shell/Python. If parallel workers are unavailable, process:

1. `phase-tasks/night.md`
2. `phase-tasks/day_speech.md`
3. `phase-tasks/vote.md`
4. `phase-tasks/memory.md`

Then run `render_report.py`.

## Portability Rules

- Do not rely on hidden conversation state.
- Do not rely on platform memory stores.
- Use file paths and command output as the source of truth.
- Keep outputs deterministic enough for another agent to resume from files alone.
