"""
游戏 API 路由
==============
提供游戏创建、状态查询和行动提交等 REST API 端点。

核心功能：
- 创建游戏：选择板子和 AI 玩家，初始化游戏状态
- 查询游戏：获取当前游戏状态、玩家信息、事件历史
- 提交行动：人类玩家提交行动（发言、投票等），触发游戏阶段推进
- AI 决策：游戏阶段推进时，AI 玩家通过 LLM 自动生成发言和决策

游戏状态机：
  SETUP → NIGHT → DAY_ANNOUNCEMENT → DAY_SPEECH → EXILE_VOTE → LAST_WORDS → (循环回 NIGHT 或 GAME_OVER)

API 设计：
- POST /games          创建新游戏
- GET  /games/{id}     获取游戏状态
- POST /games/{id}/actions  提交玩家行动
"""

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo
from ai_werewolf.domain.roles import Faction
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.model_config import default_provider_configs, default_role_model_bindings
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import evaluate_winner
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards

logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================

class CreateGameRequest(BaseModel):
    """创建游戏的请求体"""
    board_id: str                # 选择的板子 ID
    human_player_id: str         # 人类玩家的 ID
    agent_ids: list[str]         # 选择的 AI 玩家 ID 列表


class SubmitActionRequest(BaseModel):
    """提交行动的请求体"""
    actor_player_id: str                          # 执行行动的玩家 ID
    action_type: str                              # 行动类型（speak, vote, wolf_kill 等）
    target_player_id: str | None = None           # 目标玩家 ID（如投票目标）
    content: str | None = None                    # 行动内容（如发言文本）
    client_action_id: str                         # 客户端行动 ID（用于幂等性）


# ==================== 游戏会话 ====================

@dataclass
class GameSession:
    """
    游戏会话，保存一局游戏的完整运行时状态

    Attributes:
        state:           游戏状态（阶段、玩家、胜负等）
        agents:          本局使用的 AI 玩家配置，key 为 agent_id
        human_player_id: 人类玩家的 player_id
        public_events:   公开事件列表，按时间顺序记录所有公开事件
        voted_player_ids: 已投票的玩家 ID 集合（用于前端显示投票状态）
        night_actions:   当前夜晚收集到的行动（用于夜晚结算）
        witch_has_save_potion:  女巫是否还有解药
        witch_has_poison:       女巫是否还有毒药
    """

    state: GameState
    agents: dict[str, AgentProfile]
    human_player_id: str
    public_events: list[dict[str, Any]] = field(default_factory=list)
    voted_player_ids: set[str] = field(default_factory=set)
    night_actions: list[dict[str, Any]] = field(default_factory=list)
    witch_has_save_potion: bool = True
    witch_has_poison: bool = True
    private_infos: dict[str, PlayerPrivateInfo] = field(default_factory=dict)
    pending_last_words_player_id: str | None = None


# ==================== 全局状态 ====================

router = APIRouter(prefix="/games", tags=["games"])

# 所有活跃游戏会话，key 为 game_id
_games: dict[str, GameSession] = {}

# 角色注册表（内置角色定义）
_role_registry = BuiltInRoleRegistry()
_ai_action_scheduler = AIActionScheduler(_role_registry)

# 数据库持久化仓库（可选，通过 configure_game_repository 注入）
_game_repository: Any | None = None

# LLM 模型注册中心和角色绑定
_model_registry = ModelProviderRegistry()
for provider_config in default_provider_configs():
    _model_registry.register(build_provider(provider_config))
_role_model_bindings = default_role_model_bindings()


# ==================== 配置接口 ====================

def configure_game_repository(repository: Any | None) -> None:
    """配置数据库持久化仓库"""
    global _game_repository
    _game_repository = repository


def configure_model_registry(registry: ModelProviderRegistry, role_model_bindings: list) -> None:
    """配置 LLM 模型注册中心和角色绑定"""
    global _model_registry, _role_model_bindings
    _model_registry = registry
    _role_model_bindings = role_model_bindings


# ==================== 工具函数 ====================

def _event(event_type: str, message: str, **payload: Any) -> dict[str, Any]:
    """
    构建一个事件 dict

    Args:
        event_type: 事件类型（如 "speech", "vote", "exile"）
        message:    事件描述消息
        **payload:  额外的负载数据

    Returns:
        事件 dict，包含 type, actor_id, target_id, payload, public 等字段
    """
    return {
        "event_type": event_type,
        "actor_id": payload.pop("actor_id", None),
        "target_id": payload.pop("target_id", None),
        "payload": {"message": message, **payload},
        "public": True,
    }


def _allowed_actions(state: GameState) -> list[dict[str, Any]]:
    """
    根据当前游戏阶段，返回人类玩家可以执行的行动列表

    不同的阶段允许不同的行动：
    - SETUP:           开始游戏
    - NIGHT:           确认夜晚行动（AI 自动执行夜晚技能）
    - DAY_ANNOUNCEMENT: 进入白天发言
    - DAY_SPEECH:      提交发言
    - EXILE_VOTE:      投票或弃票
    - LAST_WORDS:      进入下一阶段
    - GAME_OVER:       无操作

    Args:
        state: 当前游戏状态

    Returns:
        可执行行动的列表
    """
    if state.winner is not None or state.phase == GamePhase.GAME_OVER:
        return []
    if state.phase == GamePhase.SETUP:
        return [{"action_type": "start_game", "label": "开始游戏"}]
    if state.phase == GamePhase.NIGHT:
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


def _display_name(player_id: str, session: GameSession) -> str:
    """获取玩家的显示名称（人类玩家显示为"你"）"""
    if player_id == session.human_player_id:
        return "你"
    agent = session.agents.get(player_id)
    return agent.name if agent is not None else player_id


def _avatar_url(player_id: str, session: GameSession) -> str | None:
    """获取玩家的头像 URL"""
    agent = session.agents.get(player_id)
    return agent.avatar_url if agent is not None else None


def _model_provider_for_role(role_key: str) -> str:
    """获取角色对应的 LLM Provider ID"""
    return _model_registry.provider_for_role(role_key, _role_model_bindings).config.provider_id


def _player_model_bindings(state: GameState) -> dict[str, str]:
    """获取所有玩家的模型绑定映射"""
    return {player.player_id: _model_provider_for_role(player.role_key) for player in state.players}


def _build_private_infos(state: GameState) -> dict[str, PlayerPrivateInfo]:
    """初始化每个玩家的私有信息。"""
    infos = {player.player_id: PlayerPrivateInfo() for player in state.players}
    wolf_ids = [player.player_id for player in state.players if player.role_key == "werewolf"]
    for wolf_id in wolf_ids:
        infos[wolf_id].wolf_teammates = [other_id for other_id in wolf_ids if other_id != wolf_id]
    return infos


def _ai_request_for_player(session: GameSession, player_id: str):
    """为当前阶段的指定 AI 玩家生成 Prompt 请求。"""
    context = _build_game_context(session)
    tasks = _ai_action_scheduler.schedule(
        state=session.state,
        agents=session.agents,
        private_infos=session.private_infos,
        game_context=context,
        pending_last_words_player_id=session.pending_last_words_player_id,
    )
    return next((task for task in tasks if task.player_id == player_id), None)


# ==================== AI 决策函数 ====================

def _get_ai_speech(session: GameSession, player_id: str) -> str:
    """
    让 AI 玩家通过 LLM 生成发言

    流程：
    1. 查找玩家对应的 LLM Provider
    2. 构建发言 Prompt
    3. 调用 LLM 获取决策
    4. 返回发言文本（如果 LLM 失败则返回默认发言）

    Args:
        session:   游戏会话
        player_id: AI 玩家的 ID

    Returns:
        AI 玩家的发言文本
    """
    state = session.state
    player = state.player_by_id(player_id)
    agent = session.agents.get(player_id)

    if agent is None:
        return "我暂时没有想说的。"

    try:
        # 获取角色对应的 LLM Provider
        provider = _model_registry.provider_for_role(player.role_key, _role_model_bindings)
        decider = PlayerDecider(provider)

        request = _ai_request_for_player(session, player_id)
        if request is None:
            return "我暂时没有想说的。"

        # 调用 LLM 获取决策
        decision = decider.decide(request.prompt)
        return decision.speech

    except Exception:
        logger.exception("AI 玩家 %s 发言生成失败，使用默认发言", player_id)
        return f"我先听听大家的意见，再做判断。"


def _get_ai_vote(session: GameSession, player_id: str) -> tuple[str | None, str]:
    """
    让 AI 玩家通过 LLM 决定投票目标

    Args:
        session:   游戏会话
        player_id: AI 玩家的 ID

    Returns:
        (target_id, reason) 元组
        - target_id: 投票目标的玩家 ID，None 表示弃票
        - reason: 投票理由
    """
    state = session.state
    player = state.player_by_id(player_id)
    agent = session.agents.get(player_id)

    if agent is None:
        return None, "弃票"

    try:
        provider = _model_registry.provider_for_role(player.role_key, _role_model_bindings)
        decider = PlayerDecider(provider)

        request = _ai_request_for_player(session, player_id)
        if request is None:
            return None, "弃票"

        decision = decider.decide(request.prompt)

        # 验证投票目标是否合法（必须是存活的玩家，不能投自己）
        target = decision.target_id
        if target is not None:
            alive_player_ids = {p.player_id for p in state.players if p.alive}
            if target not in alive_player_ids or target == player_id:
                logger.warning("AI %s 投票目标 %s 不合法，改为弃票", player_id, target)
                target = None

        return target, decision.speech

    except Exception:
        logger.exception("AI 玩家 %s 投票决策失败，弃票", player_id)
        return None, "弃票"


def _build_game_context(session: GameSession) -> str:
    """
    从事件历史中构建游戏上下文字符串，供 LLM 理解当前局势

    将所有公开事件整理为文本格式，包括：
    - 阶段变化
    - 玩家发言
    - 投票结果
    - 死亡公告

    Args:
        session: 游戏会话

    Returns:
        游戏上下文的文本字符串
    """
    lines = []
    for event in session.public_events:
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        message = payload.get("message", "")
        lines.append(f"[{etype}] {message}")
    return "\n".join(lines[-20:])  # 只保留最近 20 条事件，避免 prompt 过长


# ==================== 前端状态 ====================

def _frontend_state(session: GameSession) -> dict[str, Any]:
    """
    构建返回给前端的完整游戏状态

    包含：
    - 游戏基本信息（ID、板子、阶段、天数）
    - 玩家列表（座位、角色、存活状态、显示名、头像等）
    - 事件历史
    - 可执行行动
    - 胜负信息

    Args:
        session: 游戏会话

    Returns:
        前端渲染所需的完整状态 dict
    """
    state = session.state
    game_over = state.phase == GamePhase.GAME_OVER or state.winner is not None

    return {
        "game_id": state.game_id,
        "board_id": state.board_id,
        "phase": state.phase.value,
        "day_count": state.day_count,
        "human_player_id": session.human_player_id,
        "current_turn_player_id": session.human_player_id if _allowed_actions(state) else None,
        "players": [
            {
                "player_id": player.player_id,
                "agent_id": player.agent_id,
                "seat": player.seat,
                # 游戏结束或本人才能看到角色
                "role_key": player.role_key if player.is_human or game_over else None,
                "alive": player.alive,
                "is_human": player.is_human,
                "sheriff": player.sheriff,
                "display_name": _display_name(player.player_id, session),
                "avatar_url": _avatar_url(player.player_id, session),
                "model_provider_id": _model_provider_for_role(player.role_key),
                "speaking": state.phase == GamePhase.DAY_SPEECH and player.is_human,
                "voted": player.player_id in session.voted_player_ids,
            }
            for player in state.players
        ],
        "winner": state.winner,
        "public_events": session.public_events,
        "allowed_actions": _allowed_actions(state),
    }


# ==================== 游戏阶段推进 ====================

def _get_session(game_id: str) -> GameSession:
    """获取游戏会话，不存在则抛出 404"""
    try:
        return _games[game_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown game: {game_id}") from exc


def _append_ai_speeches(session: GameSession) -> None:
    """
    在白天发言阶段，让所有 AI 玩家通过 LLM 生成发言

    按座位顺序，每个存活的 AI 玩家依次发言。
    发言内容由 LLM 根据当前局势和角色设定生成。
    """
    for player in session.state.players:
        if player.is_human or not player.alive:
            continue
        # 通过 LLM 生成发言
        speech = _get_ai_speech(session, player.player_id)
        name = _display_name(player.player_id, session)
        session.public_events.append(
            _event("speech", f"{name}：{speech}", actor_id=player.player_id)
        )


def _process_ai_votes(session: GameSession) -> dict[str, str]:
    """
    在投票阶段，让所有 AI 玩家通过 LLM 决定投票目标

    Returns:
        投票结果 dict: {voter_id -> target_id}
    """
    votes: dict[str, str] = {}
    for player in session.state.players:
        if player.is_human or not player.alive:
            continue
        target_id, reason = _get_ai_vote(session, player.player_id)
        name = _display_name(player.player_id, session)
        if target_id:
            target_name = _display_name(target_id, session)
            session.public_events.append(
                _event("vote", f"{name} 投票给了 {target_name}。", actor_id=player.player_id, target_id=target_id)
            )
            votes[player.player_id] = target_id
        else:
            session.public_events.append(
                _event("vote", f"{name} 选择弃票。", actor_id=player.player_id)
            )
    return votes


def _resolve_night_deaths_for_session(session: GameSession) -> list[str]:
    """
    结算当前夜晚的死亡情况

    夜晚行动包括：
    - 狼人杀人（AI 狼人通过 LLM 选择目标）
    - 预言家查验（AI 预言家通过 LLM 选择目标）
    - 女巫用药（AI 女巫通过 LLM 决策）

    为简化实现，目前使用简化的夜晚逻辑：
    - 狼人随机选择一个存活的非狼人玩家击杀
    - 可通过 LLM 增强（后续迭代）

    Returns:
        本夜死亡的玩家 ID 列表
    """
    state = session.state

    session.night_actions.clear()

    # 找到所有存活的狼人
    alive_wolves = [p for p in state.players if p.alive and p.role_key == "werewolf"]
    # 找到所有存活的非狼人玩家
    alive_non_wolves = [p for p in state.players if p.alive and p.role_key != "werewolf"]

    deaths: list[str] = []
    wolf_target_id: str | None = None

    if alive_wolves and alive_non_wolves:
        # 狼人选择击杀目标（简化版：选择第一个存活的非狼人）
        # TODO: 通过 LLM 让狼人策略性选择目标
        target = alive_non_wolves[0]
        wolf_target_id = target.player_id
        session.night_actions.append(
            {
                "actor_player_id": alive_wolves[0].player_id,
                "action_type": "night_kill",
                "target_player_id": wolf_target_id,
                "round": f"night{state.day_count}",
            }
        )

    alive_seer = next((p for p in state.players if p.alive and p.role_key == "seer"), None)
    if alive_seer is not None:
        check_target = next((p for p in state.players if p.alive and p.player_id != alive_seer.player_id), None)
        if check_target is not None:
            result = "werewolf" if check_target.role_key == "werewolf" else "good"
            session.private_infos.setdefault(alive_seer.player_id, PlayerPrivateInfo()).seer_results.append(
                {"round": f"night{state.day_count}", "target": check_target.player_id, "result": result}
            )
            session.night_actions.append(
                {
                    "actor_player_id": alive_seer.player_id,
                    "action_type": "check",
                    "target_player_id": check_target.player_id,
                    "round": f"night{state.day_count}",
                }
            )

    protected_id = None
    alive_guard = next((p for p in state.players if p.alive and p.role_key in {"guard", "guardian"}), None)
    if alive_guard is not None:
        protected_id = alive_guard.player_id
        session.private_infos.setdefault(alive_guard.player_id, PlayerPrivateInfo()).guard_history.append(protected_id)
        session.night_actions.append(
            {
                "actor_player_id": alive_guard.player_id,
                "action_type": "guard",
                "target_player_id": protected_id,
                "round": f"night{state.day_count}",
            }
        )

    if wolf_target_id is not None and wolf_target_id != protected_id:
        deaths.append(wolf_target_id)

    # 标记死亡
    for player_id in deaths:
        player = state.player_by_id(player_id)
        player.alive = False

    return deaths


def _finish_or_next_night(session: GameSession) -> None:
    """
    检查胜负条件，决定是进入下一夜还是结束游戏

    如果已满足胜负条件（狼人全灭或狼人数量 >= 好人数量），游戏结束。
    否则进入下一夜。
    """
    winner = evaluate_winner(session.state, _role_registry)
    if winner is not None:
        session.state.phase = GamePhase.GAME_OVER
        session.state.winner = winner.value
        # 公布胜负信息
        winner_name = "狼人阵营" if winner == Faction.WEREWOLF else "好人阵营"
        session.public_events.append(_event("game_end", f"游戏结束，{winner_name}获胜！"))
        # 游戏结束时公布所有角色
        for player in session.state.players:
            role_name = {"werewolf": "狼人", "seer": "预言家", "witch": "女巫",
                         "hunter": "猎人", "villager": "平民"}.get(player.role_key, player.role_key)
            name = _display_name(player.player_id, session)
            status = "存活" if player.alive else "出局"
            session.public_events.append(
                _event("role_reveal", f"{name} 的身份是：{role_name}（{status}）", actor_id=player.player_id)
            )
        return

    # 进入下一夜
    session.state.day_count += 1
    session.state.phase = GamePhase.NIGHT
    session.voted_player_ids.clear()
    session.public_events.append(_event("phase_changed", f"第 {session.state.day_count} 夜降临。"))


def _advance_game(session: GameSession, action: SubmitActionRequest) -> None:
    """
    游戏状态机：根据当前阶段和玩家行动，推进游戏到下一阶段

    状态转移逻辑：
    SETUP + start_game  → NIGHT（初始化完成，夜幕降临）
    NIGHT + skip        → DAY_ANNOUNCEMENT（夜晚行动完成，天亮了）
    DAY_ANNOUNCEMENT + continue → DAY_SPEECH（进入发言，AI 自动发言）
    DAY_SPEECH + speech → EXILE_VOTE（人类发言完毕，进入投票）
    EXILE_VOTE + vote/abstain → 结算投票 → LAST_WORDS 或 NIGHT
    LAST_WORDS + continue → NIGHT 或 GAME_OVER

    Args:
        session: 游戏会话
        action:  玩家提交的行动

    Raises:
        HTTPException: 行动在当前阶段不被允许时抛出 400
    """
    state = session.state

    # ---- SETUP → NIGHT：开始游戏 ----
    if state.phase == GamePhase.SETUP and action.action_type == "start_game":
        state.phase = GamePhase.NIGHT
        state.day_count = 1
        session.public_events.append(_event("phase_changed", "夜幕降临，所有玩家闭眼。"))
        return

    # ---- NIGHT → DAY_ANNOUNCEMENT：结算夜晚行动 ----
    if state.phase == GamePhase.NIGHT and action.action_type in {"skip", "wolf_kill", "seer_check"}:
        # 结算夜晚死亡
        deaths = _resolve_night_deaths_for_session(session)

        state.phase = GamePhase.DAY_ANNOUNCEMENT
        if deaths:
            death_names = [_display_name(pid, session) for pid in deaths]
            session.public_events.append(
                _event("night_result", f"昨夜，{', '.join(death_names)} 倒在了血泊中。")
            )
        else:
            session.public_events.append(_event("night_result", "昨夜平安夜，没有玩家出局。"))
        return

    # ---- DAY_ANNOUNCEMENT → DAY_SPEECH：进入白天发言 ----
    if state.phase == GamePhase.DAY_ANNOUNCEMENT and action.action_type == "continue":
        state.phase = GamePhase.DAY_SPEECH
        # AI 玩家自动发言（通过 LLM 生成）
        _append_ai_speeches(session)
        session.public_events.append(_event("phase_changed", "进入白天发言阶段，现在轮到你发言。"))
        return

    # ---- DAY_SPEECH → EXILE_VOTE：人类玩家发言完毕 ----
    if state.phase == GamePhase.DAY_SPEECH and action.action_type == "speech":
        # 记录人类玩家的发言
        session.public_events.append(
            _event("speech", f"你：{action.content or '我先过。'}", actor_id=action.actor_player_id)
        )
        state.phase = GamePhase.EXILE_VOTE
        session.public_events.append(_event("phase_changed", "发言结束，进入放逐投票。"))

        # AI 玩家自动投票（通过 LLM 决策）
        ai_votes = _process_ai_votes(session)

        # 人类玩家也标记为已投票（等待前端提交投票行动）
        session.public_events.append(_event("phase_changed", "现在轮到你投票。"))
        return

    # ---- EXILE_VOTE：人类玩家投票 ----
    if state.phase == GamePhase.EXILE_VOTE and action.action_type in {"vote", "abstain"}:
        session.voted_player_ids.add(action.actor_player_id)

        # 收集所有投票（AI 已投票 + 人类投票）
        all_votes: dict[str, str] = {}

        # AI 的投票（之前已收集并记录在事件中）
        for event in session.public_events:
            if event.get("event_type") == "vote" and event.get("actor_id") != session.human_player_id:
                voter = event["actor_id"]
                target = event.get("target_id")
                if voter and target:
                    all_votes[voter] = target

        # 人类的投票
        if action.action_type == "vote" and action.target_player_id:
            all_votes[action.actor_player_id] = action.target_player_id
            target = state.player_by_id(action.target_player_id)
            session.public_events.append(
                _event("vote", f"你投票给了 {_display_name(target.player_id, session)}。",
                       actor_id=action.actor_player_id, target_id=target.player_id)
            )
        else:
            session.public_events.append(_event("vote", "你选择弃票。", actor_id=action.actor_player_id))

        # 结算投票结果（使用 Counter 统计票数）
        exiled_player_id: str | None = None
        if all_votes:
            from collections import Counter
            vote_counts = Counter(all_votes.values())
            if vote_counts:
                top_count = max(vote_counts.values())
                tied = sorted(pid for pid, cnt in vote_counts.items() if cnt == top_count)
                if len(tied) == 1:
                    exiled = state.player_by_id(tied[0])
                    exiled.alive = False
                    exiled_player_id = exiled.player_id
                    session.public_events.append(
                        _event("exile", f"{_display_name(exiled.player_id, session)} 被投票放逐。",
                               target_id=exiled.player_id)
                    )
                else:
                    session.public_events.append(_event("exile", "投票平局，无人被放逐。"))
        else:
            session.public_events.append(_event("exile", "所有人都弃票，无人被放逐。"))

        if exiled_player_id is not None:
            session.pending_last_words_player_id = exiled_player_id
            state.phase = GamePhase.LAST_WORDS
            session.public_events.append(
                _event(
                    "last_words",
                    f"{_display_name(exiled_player_id, session)} 留下遗言，白天即将结束。",
                    actor_id=exiled_player_id,
                )
            )
        else:
            _finish_or_next_night(session)
        return

    # ---- LAST_WORDS：遗言结束，检查胜负或进入下一夜 ----
    if state.phase == GamePhase.LAST_WORDS and action.action_type == "continue":
        session.pending_last_words_player_id = None
        session.public_events.append(_event("phase_changed", "遗言结束，进入下一阶段。"))
        _finish_or_next_night(session)
        return

    # 不合法的行动
    raise HTTPException(status_code=400, detail=f"action {action.action_type} is not allowed in {state.phase.value}")


# ==================== API 端点 ====================

@router.post("")
def create_game(request: CreateGameRequest):
    """
    创建一局新游戏

    流程：
    1. 验证板子和 AI 玩家是否存在
    2. 初始化游戏状态（分配角色）
    3. 创建游戏会话
    4. 可选：持久化到数据库

    Args:
        request: 创建游戏请求

    Returns:
        初始化后的前端游戏状态
    """
    boards = {board.board_id: board for board in default_boards()}
    agents = {agent.agent_id: agent for agent in default_agents()}

    try:
        board = boards[request.board_id]
        selected_agents = [agents[agent_id] for agent_id in request.agent_ids]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown id: {exc.args[0]}") from exc

    if len(selected_agents) != board.player_count - 1:
        raise HTTPException(status_code=400, detail="agent count must fill board seats after human player")

    # 初始化游戏状态（分配角色、设置座位）
    state = initialize_game_node(board, request.human_player_id, selected_agents, seed=1)
    state.game_id = f"game_{uuid4().hex[:12]}"

    # 创建游戏会话
    session = GameSession(
        state=state,
        agents={agent.agent_id: agent for agent in selected_agents},
        human_player_id=request.human_player_id,
        public_events=[_event("game_created", f"{board.name} 已创建，等待开始。")],
        private_infos=_build_private_infos(state),
    )

    # 保存到内存
    _games[state.game_id] = session

    # 可选：持久化到数据库
    if _game_repository is not None:
        _game_repository.save_game(state, request.human_player_id, _player_model_bindings(state))

    return _frontend_state(session)


@router.get("/{game_id}")
def get_game(game_id: str):
    """
    获取游戏当前状态

    Args:
        game_id: 游戏 ID

    Returns:
        前端渲染所需的完整游戏状态
    """
    return _frontend_state(_get_session(game_id))


@router.post("/{game_id}/actions")
def submit_action(game_id: str, action: SubmitActionRequest):
    """
    提交玩家行动，推进游戏

    根据当前阶段和行动类型，执行对应的状态转移。
    可能触发 AI 玩家的自动决策（发言、投票等）。

    Args:
        game_id: 游戏 ID
        action:  玩家行动

    Returns:
        更新后的前端游戏状态
    """
    session = _get_session(game_id)
    _advance_game(session, action)
    return _frontend_state(session)
