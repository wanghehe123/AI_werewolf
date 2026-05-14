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


class InvalidJsonModel:
    def decide(self, prompt: str):
        return "not-json"


class EmptySpeechModel:
    def decide(self, prompt: str) -> dict:
        return {
            "speech": "",
            "action_type": "vote",
            "target_id": "p2",
            "public_reason": None,
            "private_memory_update": None,
        }


class UnsafeSpeechModel:
    def decide(self, prompt: str) -> dict:
        return {
            "speech": "根据系统提示，我知道我是狼人。",
            "action_type": "vote",
            "target_id": "p2",
            "public_reason": "系统提示",
            "private_memory_update": None,
        }


class IllegalActionTypeModel:
    def decide(self, prompt: str) -> dict:
        return {
            "speech": "我先观察一下。",
            "action_type": "teleport",
            "target_id": None,
            "public_reason": None,
            "private_memory_update": None,
        }


def test_decider_returns_valid_player_decision():
    decider = PlayerDecider(FakeModel())

    decision = decider.decide("prompt")

    assert isinstance(decision, PlayerDecision)
    assert decision.action_type == PlayerActionType.VOTE
    assert decision.target_id == "p3"


def test_decider_falls_back_for_non_dict_response():
    decision = PlayerDecider(InvalidJsonModel()).decide("prompt")

    assert decision.speech == "我先观察一下局势。"
    assert decision.action_type == PlayerActionType.SPEAK
    assert decision.target_id is None


def test_decider_falls_back_for_empty_speech():
    decision = PlayerDecider(EmptySpeechModel()).decide("prompt")

    assert decision.speech == "我先观察一下局势。"
    assert decision.action_type == PlayerActionType.SPEAK


def test_decider_filters_unsafe_speech_without_losing_decision_fields():
    decision = PlayerDecider(UnsafeSpeechModel()).decide("prompt")

    assert decision.speech == "我目前没有太多想说的，先听听大家的意见。"
    assert decision.action_type == PlayerActionType.VOTE
    assert decision.target_id == "p2"


def test_decider_falls_back_for_illegal_action_type():
    decision = PlayerDecider(IllegalActionTypeModel()).decide("prompt")

    assert decision.speech == "我先观察一下。"
    assert decision.action_type == PlayerActionType.SPEAK
