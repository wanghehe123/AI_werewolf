from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.llm.action_scheduler import AIActionResult, AIActionScheduler
from ai_werewolf.llm.schemas import PlayerDecision


def test_night_scheduler_creates_tasks_only_for_alive_ai_with_night_actions():
    scheduler = AIActionScheduler()
    state = make_state(
        GamePhase.NIGHT,
        [
            player("human", "villager", is_human=True),
            player("wolf_ai", "werewolf"),
            player("seer_ai", "seer"),
            player("villager_ai", "villager"),
            player("dead_witch", "witch", alive=False),
        ],
    )

    tasks = scheduler.schedule(
        state=state,
        agents=agents_for(state),
        private_infos={"wolf_ai": PlayerPrivateInfo(wolf_teammates=["wolf_2"])},
        game_context="[phase_changed] 第 1 夜降临。",
    )

    assert [task.player_id for task in tasks] == ["wolf_ai", "seer_ai"]
    assert {task.prompt_kind for task in tasks} == {"night_action"}
    assert all(task.phase == GamePhase.NIGHT for task in tasks)
    wolf_task = next(task for task in tasks if task.player_id == "wolf_ai")
    assert "狼队友" in wolf_task.private_info
    assert "第 1 夜降临" in wolf_task.context
    assert "wolf_kill" in wolf_task.prompt


def test_day_speech_and_exile_vote_scheduler_create_tasks_for_alive_ai_in_seat_order():
    speech_state = make_state(
        GamePhase.DAY_SPEECH,
        [
            player("human", "villager", seat=1, is_human=True),
            player("p3", "seer", seat=3),
            player("p2", "werewolf", seat=2),
            player("dead", "villager", seat=4, alive=False),
        ],
    )
    vote_state = speech_state.model_copy(update={"phase": GamePhase.EXILE_VOTE})
    scheduler = AIActionScheduler()

    speech_tasks = scheduler.schedule(speech_state, agents_for(speech_state), {}, "公开历史")
    vote_tasks = scheduler.schedule(vote_state, agents_for(vote_state), {}, "公开历史")

    assert [(task.player_id, task.prompt_kind) for task in speech_tasks] == [
        ("p2", "day_speech"),
        ("p3", "day_speech"),
    ]
    assert [(task.player_id, task.prompt_kind) for task in vote_tasks] == [
        ("p2", "exile_vote"),
        ("p3", "exile_vote"),
    ]
    assert all("公开历史" in task.prompt for task in speech_tasks + vote_tasks)


def test_last_words_scheduler_creates_task_only_for_pending_exiled_ai():
    state = make_state(
        GamePhase.LAST_WORDS,
        [
            player("human", "villager", is_human=True),
            player("exiled_ai", "seer", alive=False),
            player("alive_ai", "werewolf", alive=True),
        ],
    )

    tasks = AIActionScheduler().schedule(
        state=state,
        agents=agents_for(state),
        private_infos={"exiled_ai": PlayerPrivateInfo(seer_results=[{"round": "night1", "target": "alive_ai", "result": "werewolf"}])},
        game_context="[exile] exiled_ai 被投票放逐。",
        pending_last_words_player_id="exiled_ai",
    )

    assert len(tasks) == 1
    assert tasks[0].player_id == "exiled_ai"
    assert tasks[0].prompt_kind == "last_words"
    assert "当前阶段：last_words" in tasks[0].prompt


def test_sheriff_scheduler_returns_no_tasks_for_now():
    state = make_state(GamePhase.SHERIFF_ELECTION, [player("human", "villager", is_human=True), player("p2", "werewolf")])

    tasks = AIActionScheduler().schedule(state, agents_for(state), {}, "")

    assert tasks == []


def test_ai_action_result_wraps_decision_without_mutating_game_state():
    decision = PlayerDecision(
        speech="我投 2 号，他今天的站边变化太快。",
        action_type="vote",
        target_id="p2",
        public_reason="站边变化太快",
        private_memory_update="继续观察 3 号",
    )

    result = AIActionResult(
        player_id="p1",
        phase=GamePhase.EXILE_VOTE,
        decision=decision,
        source="fake",
        fallback_used=False,
    )

    assert result.player_id == "p1"
    assert result.decision.target_id == "p2"
    assert result.fallback_used is False


def make_state(phase: GamePhase, players: list[PlayerState]) -> GameState:
    return GameState(game_id="game_1", board_id="board_6_beginner", phase=phase, day_count=1, players=players)


def player(
    player_id: str,
    role_key: str,
    seat: int = 1,
    alive: bool = True,
    is_human: bool = False,
) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        agent_id=None if is_human else player_id,
        seat=seat,
        role_key=role_key,
        alive=alive,
        is_human=is_human,
    )


def agents_for(state: GameState) -> dict[str, AgentProfile]:
    return {
        p.player_id: AgentProfile(
            agent_id=p.player_id,
            name=p.player_id,
            persona="谨慎",
            speech_style="短句",
            reasoning_level=3,
            deception_level=3,
            aggression_level=3,
            cooperation_level=3,
            risk_preference=RiskPreference.BALANCED,
            memory_style="focus_on_votes",
        )
        for p in state.players
        if not p.is_human
    }
