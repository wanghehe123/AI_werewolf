# engine/helpers.py
"""Shared helper functions for event building, display names, and allowed actions."""
from __future__ import annotations

from typing import Any

from ai_werewolf.domain.game_state import GamePhase, GameState
from ai_werewolf.engine.session import GameSession


def event(event_type: str, message: str, **payload: Any) -> dict[str, Any]:
    """Build a public event dict."""
    return {
        "event_type": event_type,
        "actor_id": payload.pop("actor_id", None),
        "target_id": payload.pop("target_id", None),
        "payload": {"message": message, **payload},
        "public": True,
    }


def display_name(player_id: str, session: GameSession) -> str:
    """Get display name for a player. Human player shows as '你'."""
    if player_id == session.human_player_id:
        return "你"
    agent = session.agents.get(player_id)
    return agent.name if agent is not None else player_id


def player_label(player_id: str, session: GameSession) -> str:
    """Return the in-game reference users and AI should see."""
    player = session.state.player_by_id(player_id)
    return f"{player.seat}号 {display_name(player_id, session)}"


def player_references(session: GameSession) -> dict[str, str]:
    """Map player IDs to seat/name labels while preserving IDs for target fields."""
    return {player.player_id: player_label(player.player_id, session) for player in session.state.players}


def avatar_url(player_id: str, session: GameSession) -> str | None:
    """Get avatar URL for a player."""
    agent = session.agents.get(player_id)
    return agent.avatar_url if agent is not None else None


def allowed_actions(state: GameState, human_player_id: str | None = None, session: GameSession | None = None) -> list[dict[str, Any]]:
    """Return available actions for human player based on current phase."""
    if state.winner is not None or state.phase == GamePhase.GAME_OVER:
        return []
    if state.phase == GamePhase.SETUP:
        return [{"action_type": "start_game", "label": "开始游戏"}]
    if state.phase == GamePhase.NIGHT:
        human = _human_player(state, human_player_id)
        if human is None or not human.alive:
            return []
        if human.role_key == "werewolf":
            targets = [player for player in state.players if player.alive and player.role_key != "werewolf"]
            return [_target_action("wolf_kill", "击杀玩家", targets, session)]
        if human.role_key == "seer":
            targets = [player for player in state.players if player.alive and player.player_id != human.player_id]
            return [_target_action("seer_check", "查验玩家", targets, session)]
        if human.role_key in {"guard", "guardian"}:
            targets = [player for player in state.players if player.alive]
            return [_target_action("guard", "守护玩家", targets, session)]
        if human.role_key == "witch":
            targets = [player for player in state.players if player.alive]
            return [
                _target_action("witch_save", "使用解药", targets, session),
                _target_action("witch_poison", "使用毒药", targets, session),
                {"action_type": "no_action", "label": "不使用药"},
            ]
        return [{"action_type": "skip", "label": "确认夜晚行动"}]
    if state.phase == GamePhase.DAY_ANNOUNCEMENT:
        return [{"action_type": "continue", "label": "进入白天发言"}]
    if state.phase == GamePhase.DAY_SPEECH:
        return [{"action_type": "speech", "label": "提交发言"}]
    if state.phase == GamePhase.EXILE_VOTE:
        return [{"action_type": "vote", "label": "投票"}, {"action_type": "abstain", "label": "弃票"}]
    if state.phase == GamePhase.LAST_WORDS:
        return [{"action_type": "continue", "label": "继续"}]
    return []


def frontend_state(session: GameSession, model_registry: Any, role_model_bindings: list) -> dict[str, Any]:
    """Build the full game state dict for the frontend."""
    state = session.state
    game_over = state.phase == GamePhase.GAME_OVER or state.winner is not None
    actions = allowed_actions(state, session.human_player_id, session)

    def _provider_id(role_key: str) -> str:
        return model_registry.provider_for_role(role_key, role_model_bindings).config.provider_id

    return {
        "game_id": state.game_id,
        "board_id": state.board_id,
        "phase": state.phase.value,
        "day_count": state.day_count,
        "human_player_id": session.human_player_id,
        "current_turn_player_id": session.human_player_id if actions else None,
        "players": [
            {
                "player_id": player.player_id,
                "agent_id": player.agent_id,
                "seat": player.seat,
                "role_key": player.role_key if player.is_human or game_over else None,
                "alive": player.alive,
                "is_human": player.is_human,
                "sheriff": player.sheriff,
                "display_name": display_name(player.player_id, session),
                "avatar_url": avatar_url(player.player_id, session),
                "model_provider_id": _provider_id(player.role_key),
                "speaking": state.phase == GamePhase.DAY_SPEECH and player.is_human,
                "voted": player.player_id in session.voted_player_ids,
            }
            for player in state.players
        ],
        "winner": state.winner,
        "public_events": session.public_events,
        "allowed_actions": actions,
    }


def _human_player(state: GameState, human_player_id: str | None):
    if human_player_id:
        return next((player for player in state.players if player.player_id == human_player_id), None)
    return next((player for player in state.players if player.is_human), None)


def _target_action(action_type: str, label: str, targets: list, session: GameSession | None) -> dict[str, Any]:
    return {
        "action_type": action_type,
        "label": label,
        "requires_target": True,
        "target_options": [
            {"player_id": player.player_id, "label": _option_label(player, session)}
            for player in targets
        ],
    }


def _option_label(player, session: GameSession | None) -> str:
    if session is not None:
        return player_label(player.player_id, session)
    return f"{player.seat}号 {player.agent_id or player.player_id}"
