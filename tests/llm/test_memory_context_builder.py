from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.memory.context_builder import MemoryContextBuilder
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory, PrivateRoleMemory


class FakeMemoryStore:
    def __init__(self) -> None:
        self.summaries = {
            "game_1": [
                DaySummary(
                    game_id="game_1",
                    day=1,
                    summary_items=["1号起跳预言家"],
                    claims=[],
                    conflicts=[],
                    alliances=[],
                    vote_summary=None,
                    low_signal_players=[],
                ),
                DaySummary(
                    game_id="game_1",
                    day=2,
                    summary_items=["5号持续攻击1号"],
                    claims=[],
                    conflicts=[],
                    alliances=[],
                    vote_summary=None,
                    low_signal_players=["p7"],
                ),
            ]
        }
        self.suspicion = {
            ("game_1", "ai_2"): PlayerSuspicionMemory(
                game_id="game_1",
                player_id="ai_2",
                day=2,
                records=[
                    {
                        "target_player_id": "p5",
                        "suspicion_score": 72,
                        "trust_score": 28,
                        "evidence": ["持续攻击1号"],
                        "relationship_tags": ["possible_pair_with_p3"],
                        "last_reason": "攻击线明确",
                        "last_updated_day": 2,
                        "last_updated_phase": "day_speech",
                    }
                ],
            )
        }
        self.private_role = {
            ("game_1", "ai_2"): PrivateRoleMemory(
                game_id="game_1",
                player_id="ai_2",
                payload={"seer_results": [{"day": 1, "target": "p6", "result": "werewolf"}]},
            )
        }

    def get_day_summaries(self, game_id: str):
        return self.summaries.get(game_id, [])

    def save_day_summary(self, summary):
        raise NotImplementedError

    def get_player_suspicion(self, game_id: str, player_id: str):
        return self.suspicion.get((game_id, player_id))

    def save_player_suspicion(self, memory):
        raise NotImplementedError

    def get_private_role_memory(self, game_id: str, player_id: str):
        return self.private_role.get((game_id, player_id))

    def save_private_role_memory(self, memory):
        raise NotImplementedError

    def append_decision_trace(self, **kwargs):
        raise NotImplementedError


def _make_session() -> GameSession:
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="ai_2", agent_id="ai_2", seat=2, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="ai_3", agent_id="ai_3", seat=3, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="game_1", board_id="board_1", phase=GamePhase.DAY_SPEECH, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="human")
    session.public_events.extend(
        [
            {"event_type": "speech", "actor_id": "human", "target_id": None, "payload": {"message": "1号：我先听2号怎么聊。"}, "public": True},
            {"event_type": "speech", "actor_id": "ai_2", "target_id": None, "payload": {"message": "2号：我觉得5号有问题。"}, "public": True},
            {"event_type": "private_info", "actor_id": "ai_2", "target_id": None, "payload": {"message": "你昨晚验了6号是狼。"}, "public": False},
        ]
    )
    session.private_infos["ai_2"] = PlayerPrivateInfo(seer_results=[{"round": "1", "target": "p6", "result": "werewolf"}])
    return session


def test_memory_context_builder_returns_recent_public_events_and_day_summaries():
    builder = MemoryContextBuilder(store=FakeMemoryStore(), recent_event_limit=5)

    context = builder.build_for_player(_make_session(), "ai_2")

    assert len(context.recent_events) == 2
    assert context.recent_events[0].event_type == "speech"
    assert len(context.day_summaries) == 2
    assert context.day_summaries[1].summary_items == ["5号持续攻击1号"]


def test_memory_context_builder_reads_player_scoped_private_memory_only():
    builder = MemoryContextBuilder(store=FakeMemoryStore(), recent_event_limit=5)

    ai_context = builder.build_for_player(_make_session(), "ai_2")
    other_context = builder.build_for_player(_make_session(), "ai_3")

    assert ai_context.suspicion_memory is not None
    assert ai_context.private_role_memory is not None
    assert other_context.suspicion_memory is None
    assert other_context.private_role_memory is None


def test_memory_context_builder_never_leaks_non_public_events():
    builder = MemoryContextBuilder(store=FakeMemoryStore(), recent_event_limit=5)

    context = builder.build_for_player(_make_session(), "ai_2")

    joined = " ".join(event.message for event in context.recent_events)
    assert "你昨晚验了6号是狼" not in joined
