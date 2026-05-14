from ai_werewolf.storage.models import AgentProfileRecord, Board, BoardRole, GamePlayerRecord, GameRecord, Player, RoleMetadata


def player_to_dict(player: Player) -> dict:
    return {
        "player_id": player.player_id,
        "name": player.name,
        "is_ai": player.is_ai,
        "agent_id": player.agent_id,
        "created_at": player.created_at,
    }


def agent_to_dict(agent: AgentProfileRecord) -> dict:
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "avatar_url": agent.avatar_url,
        "avatar_prompt": agent.avatar_prompt,
        "persona": agent.persona,
        "speech_style": agent.speech_style,
        "reasoning_level": agent.reasoning_level,
        "deception_level": agent.deception_level,
        "aggression_level": agent.aggression_level,
        "cooperation_level": agent.cooperation_level,
        "risk_preference": agent.risk_preference,
        "memory_style": agent.memory_style,
        "default_model_provider_id": agent.default_model_provider_id,
        "enabled": agent.enabled,
        "created_at": agent.created_at,
    }


def board_role_to_dict(role: BoardRole) -> dict:
    return {
        "board_id": role.board_id,
        "role_key": role.role_key,
        "count": role.count,
    }


def board_to_dict(board: Board, roles: list[BoardRole] | None = None) -> dict:
    return {
        "board_id": board.board_id,
        "name": board.name,
        "description": board.description,
        "min_players": board.min_players,
        "max_players": board.max_players,
        "sheriff_enabled": board.sheriff_enabled,
        "enabled": board.enabled,
        "created_at": board.created_at,
        "roles": [board_role_to_dict(role) for role in (roles if roles is not None else board.roles)],
    }


def role_metadata_to_dict(role: RoleMetadata) -> dict:
    return {
        "role_key": role.role_key,
        "name": role.name,
        "faction": role.faction,
        "description": role.description,
        "night_action": role.night_action,
        "enabled": role.enabled,
    }


def game_to_dict(game: GameRecord, players: list[GamePlayerRecord] | None = None) -> dict:
    data = {
        "game_id": game.game_id,
        "board_id": game.board_id,
        "human_player_id": game.human_player_id,
        "phase": game.phase,
        "day_count": game.day_count,
        "winner": game.winner,
    }
    if players is not None:
        data["players"] = [
            {
                "game_id": player.game_id,
                "player_id": player.player_id,
                "agent_id": player.agent_id,
                "seat": player.seat,
                "role_key": player.role_key,
                "alive": player.alive,
                "is_human": player.is_human,
                "sheriff": player.sheriff,
                "model_provider_id": player.model_provider_id,
            }
            for player in players
        ]
    return data
