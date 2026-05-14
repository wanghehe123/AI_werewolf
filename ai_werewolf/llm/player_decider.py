from typing import Protocol

from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.llm.safety import is_safe_speech


class DecisionModel(Protocol):
    def decide(self, prompt: str) -> dict:
        ...


class PlayerDecider:
    def __init__(self, model: DecisionModel) -> None:
        self.model = model

    def decide(self, prompt: str) -> PlayerDecision:
        decision = PlayerDecision.model_validate(self.model.decide(prompt))
        if not is_safe_speech(decision.speech):
            raise ValueError("unsafe speech")
        return decision
