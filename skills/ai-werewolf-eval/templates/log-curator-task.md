# Log Curator Task

Read the run directory files:

- `response.json`
- `events.jsonl`
- `backend.log`
- `artifacts.json`
- prompt trace metadata listed in `artifacts.json`

Write `01-game-log.md`.

Required sections:

- Summary: game id, board, winner, status, step count.
- Werewolf Night Tactics: proposals, vote/consensus, kill target, suspicious errors.
- Day Speeches: each player's public speech in order, with notable claims.
- Vote Logic: each vote target, stated reason, and whether it matches prior speech.
- Errors and Stability: provider fallback, timeout, parser/validator errors, max-step stops.
- Open Questions: missing logs or ambiguous evidence.

Use concise evidence. Do not invent events not present in artifacts.
