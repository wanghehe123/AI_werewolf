from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.schemas import PlayerDecision


class FakeModel:
    def decide(self, prompt: str) -> dict:
        return {
            "speech": "我先投 3 号，他像是在躲视角。",
            "action_type": "vote",
            "target_id": "p3",
            "public_reason": "躲视角",
            "private_memory_update": "观察 5 号",
        }


def test_decider_returns_valid_player_decision():
    decider = PlayerDecider(FakeModel())

    decision = decider.decide("prompt")

    assert isinstance(decision, PlayerDecision)
    assert decision.action_type == PlayerActionType.VOTE
    assert decision.target_id == "p3"
