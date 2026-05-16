# engine/vote.py
"""VoteResolver - collect AI votes after human, resolve exile."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)


class VoteResolver:
    """Resolves exile vote: human votes first, then AI votes via LLM."""

    def __init__(self, model_registry: Any, role_model_bindings: list, role_registry: BuiltInRoleRegistry) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)

    def resolve(self, session: GameSession, human_vote: dict) -> dict[str, Any]:
        """Collect all votes and resolve exile.

        Args:
            session: Game session.
            human_vote: Human vote dict with actor_player_id, action_type, target_player_id.

        Returns:
            Dict with keys: exiled_player_id (str|None), events (list).
        """
        events: list[dict[str, Any]] = []
        all_votes: dict[str, str] = {}  # voter_id -> target_id
        state = session.state

        # 1. Record human vote unless the human is already out and the engine is auto-advancing the table.
        if not human_vote.get("skip_human_vote"):
            session.voted_player_ids.add(human_vote["actor_player_id"])
            if human_vote["action_type"] == "vote" and human_vote.get("target_player_id"):
                all_votes[human_vote["actor_player_id"]] = human_vote["target_player_id"]
                events.append(event("vote", f"你投票给了 {display_name(human_vote['target_player_id'], session)}。",
                                   actor_id=human_vote["actor_player_id"], target_id=human_vote["target_player_id"]))
            else:
                events.append(event("vote", "你选择弃票。", actor_id=human_vote["actor_player_id"]))

        # 2. AI votes via LLM
        context = build_game_context(session)
        for player in state.players:
            if player.is_human or not player.alive:
                continue
            target_id, speech = self._get_ai_vote(session, player.player_id, context)
            if target_id:
                all_votes[player.player_id] = target_id
                events.append(event("vote", f"{display_name(player.player_id, session)} 投票给了 {display_name(target_id, session)}。",
                                   actor_id=player.player_id, target_id=target_id))
            else:
                events.append(event("vote", f"{display_name(player.player_id, session)} 选择弃票。", actor_id=player.player_id))

        # 3. Tally and resolve
        exiled_player_id: str | None = None
        if all_votes:
            vote_counts = Counter(all_votes.values())
            top_count = max(vote_counts.values())
            tied = sorted(pid for pid, cnt in vote_counts.items() if cnt == top_count)
            if len(tied) == 1:
                exiled = state.player_by_id(tied[0])
                exiled.alive = False
                exiled_player_id = exiled.player_id
                events.append(event("exile", f"{display_name(exiled.player_id, session)} 被投票放逐。", target_id=exiled.player_id))
            else:
                events.append(event("exile", "投票平局，无人被放逐。"))
        else:
            events.append(event("exile", "所有人都弃票，无人被放逐。"))

        session.public_events.extend(events)
        return {"exiled_player_id": exiled_player_id, "events": events}

    def _get_ai_vote(self, session: GameSession, player_id: str, context: str) -> tuple[str | None, str]:
        """Get AI vote decision via LLM. Returns (target_id, speech)."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return None, "弃票"

        try:
            tasks = self.scheduler.schedule(
                state=session.state,
                agents=session.agents,
                private_infos=session.private_infos,
                game_context=context,
            )
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return None, "弃票"

            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            decision = decider.decide(task.prompt)

            target = decision.target_id
            if target is not None:
                alive_ids = {p.player_id for p in session.state.players if p.alive}
                if target not in alive_ids or target == player_id:
                    logger.warning("AI %s vote target %s invalid, abstain", player_id, target)
                    target = None

            return target, decision.speech
        except Exception:
            logger.exception("AI %s vote failed", player_id)
            return None, "弃票"

    def _get_ai_vote_decision(self, player_id: str, prompt: str) -> PlayerDecision:
        """Mock-friendly wrapper for testing."""
        return PlayerDecision(speech="弃票", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)
