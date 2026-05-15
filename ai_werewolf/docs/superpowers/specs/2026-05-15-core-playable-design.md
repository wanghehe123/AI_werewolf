# AI Werewolf Core Playable - Design Spec

## Goal

Make the AI Werewolf game actually playable by extracting the game engine from the API layer and implementing LLM-driven night actions, proper vote timing, AI last words, and hunter shoot logic.

## Scope

- LLM-driven night actions (wolf kill, seer check, witch save/poison, guard protect)
- Fixed vote timing (human votes first, then AI)
- AI last words generation
- Hunter death-triggered shoot
- Game engine extraction from `api/games.py` into `engine/` module

Out of scope: SSE event streaming, sheriff election, WebSocket, frontend changes.

## Architecture

### Engine Module

```
engine/
├── __init__.py
├── session.py          # GameSession dataclass
├── orchestrator.py     # PhaseOrchestrator - state machine core
├── night.py            # NightResolver - LLM night action collection & resolution
├── vote.py             # VoteResolver - vote collection & resolution
├── hunter.py           # HunterResolver - hunter shoot on death
└── context.py          # Game context builder for LLM prompts
```

### PhaseOrchestrator

Single entry point for game progression:

```python
class PhaseOrchestrator:
    def advance(self, session: GameSession, action: SubmitActionRequest) -> list[dict]:
        # Routes to appropriate resolver based on current phase
        # All LLM calls happen here
        # Returns list of new public events
```

### State Transitions

```
SETUP + start_game → NIGHT
NIGHT + skip → [NightResolver.collect_and_resolve()] → DAY_ANNOUNCEMENT
DAY_ANNOUNCEMENT + continue → DAY_SPEECH
DAY_SPEECH + speech → EXILE_VOTE (only phase switch, no AI vote yet)
EXILE_VOTE + vote/abstain → [VoteResolver.collect_and_resolve()] → LAST_WORDS or next
LAST_WORDS + continue → [check win] → NIGHT or GAME_OVER
```

### API Layer (`api/games.py`)

Becomes a thin HTTP layer:

```python
@router.post("/{game_id}/actions")
def submit_action(game_id: str, action: SubmitActionRequest):
    session = _get_session(game_id)
    _orchestrator.advance(session, action)
    return success_response(data=_frontend_state(session))
```

## NightResolver

### Night Action Flow

1. Enter NIGHT phase
2. For each AI with night action, call LLM via existing `PlayerDecider`:
   - Wolves: `build_night_action_prompt(role_key="werewolf")` → get kill target
   - Seer: `build_night_action_prompt(role_key="seer")` → get check target → write to `private_infos[seer_id].seer_results`
   - Witch: After wolf kill resolved, pass death info via `private_info`, call LLM → get save/poison decision
   - Guard: `build_night_action_prompt(role_key="guardian")` → get guard target (cannot guard same person two nights in a row)
3. Resolve deaths based on rules

### Resolution Rules

- Guard protected the wolf target → no death from wolf kill
- Witch used save on the wolf target → no death from wolf kill
- Witch used poison on someone → that person dies (can stack with wolf kill)
- If both guard and witch protect the same person → the person dies (standard "same-guard-same-save" rule)

### Witch Special Logic

- Witch receives death info in `private_info` before deciding
- `witch_medicine` tracks save/poison availability in `PlayerPrivateInfo`
- First night: witch can save self. After first night: witch cannot save self.

### LLM Integration

Uses existing interfaces:
- `AIActionScheduler.schedule()` → `list[AIActionRequest]`
- `PlayerDecider(provider).decide(request.prompt)` → `PlayerDecision`
- `prompt_builder.build_night_action_prompt()` for role-specific prompts
- `prompt_builder.format_private_info()` for private info formatting

## VoteResolver

### Fixed Vote Timing

Current problem: AI votes before human, causing display confusion.

Fix:
1. `DAY_SPEECH + speech` → switch to `EXILE_VOTE` only (no AI vote)
2. Human submits vote/abstain
3. After human vote, call `_process_ai_votes()` to collect AI votes via LLM
4. Tally all votes and resolve exile

### Vote Resolution

- Count votes using Counter
- Single highest vote → exiled
- Tie → no exile (平票无人出局)
- All abstain → no exile

## HunterResolver

### Trigger Conditions

Hunter can shoot when:
- Killed by wolf at night (night resolution death)
- Voted out during exile

Hunter CANNOT shoot when:
- Poisoned by witch (standard rule simplification)

### Flow

1. When hunter dies, check `hunter_can_shoot` in `PlayerPrivateInfo`
2. If AI hunter: call LLM with `build_last_words_prompt` variant including shoot decision → get `hunter_shoot` target
3. If human hunter: auto-shoot the most suspicious player (simplified for this iteration)
4. Target dies, check win conditions again

### Simplification

For this iteration, human hunter auto-shoots. A proper UI for human hunter shoot choice can be added later.

## Last Words Enhancement

Current problem: LAST_WORDS phase just waits for human to click continue, no AI last words.

Fix:
- When entering LAST_WORDS, if the exiled player is AI:
  - Call `build_last_words_prompt()` + `PlayerDecider.decide()` to generate last words
  - Append speech event to public events
- If the exiled player is human:
  - Accept `speech` action type with content for last words
  - Then require `continue` to proceed

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `engine/__init__.py` | Create | Module init |
| `engine/session.py` | Create | GameSession dataclass (from api/games.py) |
| `engine/orchestrator.py` | Create | PhaseOrchestrator state machine |
| `engine/night.py` | Create | NightResolver |
| `engine/vote.py` | Create | VoteResolver |
| `engine/hunter.py` | Create | HunterResolver |
| `engine/context.py` | Create | Game context builder |
| `api/games.py` | Refactor | Thin HTTP layer, delegates to engine |
| `llm/prompt_builder.py` | Minor change | `_build_witch_action_hint` accepts death info parameter |

## Unchanged Files

- `llm/action_scheduler.py` - already provides correct interface
- `llm/player_decider.py` - already provides correct interface
- `llm/schemas.py` - PlayerDecision already has all needed fields
- `domain/game_state.py` - GamePhase, PlayerPrivateInfo already sufficient
- `domain/actions.py` - PlayerActionType already includes all action types
- `rules/role_registry.py` - BuiltInRoleRegistry already defines roles
- `rules/win_conditions.py` - evaluate_winner already works

## Error Handling

- LLM timeout/failure: use fallback strategies (first valid target for wolves, random for others)
- Invalid LLM target: clamp to first valid alive player
- Guard consecutive guard: enforced in NightResolver, not trusted from LLM
