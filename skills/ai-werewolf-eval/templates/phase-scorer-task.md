# Phase Scorer Task

Read:

- `01-game-log.md`
- `events.jsonl`
- `backend.log`
- `artifacts.json`
- relevant prompt traces and memory artifacts
- `skills/ai-werewolf-eval/references/scoring-rubric.md`

Write one score file named by the assigned phase, such as `score-night.md`.

Required output:

```markdown
# <Phase> Scores

| Player | Role | Score | Evidence | Issue Type |
| --- | --- | ---: | --- | --- |

## Findings

- ...

## Low Score Candidates

- ...
```

Score only what the phase can support with evidence.
