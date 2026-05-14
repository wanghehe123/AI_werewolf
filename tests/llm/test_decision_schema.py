import pytest

from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.llm.schemas import PlayerDecision


def test_player_decision_parses_structured_vote():
    decision = PlayerDecision(
        speech="我投 3 号，他的发言前后矛盾。",
        action_type=PlayerActionType.VOTE,
        target_id="p3",
        public_reason="发言矛盾",
        private_memory_update="继续观察 5 号",
    )

    assert decision.target_id == "p3"


def test_player_decision_requires_speech():
    with pytest.raises(ValueError, match="speech cannot be empty"):
        PlayerDecision(
            speech="",
            action_type=PlayerActionType.SPEAK,
            target_id=None,
            public_reason=None,
            private_memory_update=None,
        )
