# Scoring Rubric

Use 0-10 scores. Prefer evidence from events, logs, prompt traces, and memory artifacts over impressions.

## Speech Quality

- 9-10: natural, role-consistent, specific, and useful to the table.
- 6-8: mostly useful but generic or missing concrete evidence.
- 3-5: low information, repetitive, or weakly grounded.
- 0-2: breaks immersion, mentions AI/prompt/system, or contradicts the role badly.

## Logic Consistency

- Check whether suspicions, claimed evidence, target choices, and final actions align.
- Penalize invented facts, conflicting claims, and vote targets that do not match the speech.

## Action Legality

- Night actions must obey role constraints and target legal players.
- Votes must target legal candidates or alive players, depending on phase.
- Special roles must not use unavailable skills.

## Memory Quality

- Reward use of recent public facts and prior suspicion memory.
- Penalize leaking private role memory into public speech.
- Penalize memory writes that omit important day results or persist false facts.

## Stability

- Track provider failures, fallback frequency, validation errors, empty responses, and max-step stops.
- A completed game with recoverable fallbacks can still score well; repeated fallbacks that degrade player behavior should lower scores.
