"""NightResolver - collect LLM night actions and resolve deaths."""
from __future__ import annotations

import logging
import random
from typing import Any

from ai_werewolf.domain.game_state import GamePhase, PlayerPrivateInfo
from ai_werewolf.engine.action_log import log_player_action
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event, player_label, player_references, resolve_player_id
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import role_camp_goal, role_display_name
from ai_werewolf.llm.graphs.player_decision_graph import configured_semantic_nodes, run_player_decision_graph
from ai_werewolf.llm.graphs.werewolf_council import run_werewolf_council
from ai_werewolf.llm.graphs.witch_council import run_witch_council
from ai_werewolf.llm.memory.context_builder import MemoryContextBuilder
from ai_werewolf.llm.memory.summary_builder import build_player_suspicion_memory, build_private_role_memory
from ai_werewolf.llm.memory.store import MemoryStore, get_shared_redis_memory_store
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.prompt_builder import build_night_action_prompt, format_private_info
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)


def _append_locked_decision_block(prompt: str, state: dict[str, Any]) -> str:
    draft = state.get("action_draft", {})
    strategy = state.get("strategy", {})
    role_key = state.get("role_key", "unknown")
    return (
        f"{prompt}\n\n"
        "【结构化决策已锁定】\n"
        f"- 你的真实身份: {role_display_name(role_key)}\n"
        f"- 你的阵营目标: {role_camp_goal(role_key)}\n"
        f"- strategy_type: {strategy.get('strategy_type')}\n"
        f"- strategy_goal: {strategy.get('goal')}\n"
        f"- action_type: {draft.get('action_type')}\n"
        f"- target_id: {draft.get('target_id')}\n"
        f"- public_reason: {draft.get('public_reason')}\n"
        f"- private_memory_update: {draft.get('private_memory_update')}\n"
        "你必须继续以真实身份进行内在推理，不能把自己真的当成另一个阵营。\n"
        "你可以伪装，但不能用“我是普通好人”“我是平民”这种自我代入替代真实身份思考，除非当前策略明确要求你悍跳具体身份。\n"
        "如果你的 speech 提到投票或行动对象，必须与 locked target_id 保持一致；如果做不到，就不要在 speech 里写具体座位号。\n"
        "你只能生成自然发言和理由，不能改变 action_type 或 target_id。\n"
    )


class NightResolver:
    """Resolves the night phase by collecting LLM decisions and computing deaths."""

    def __init__(
        self,
        model_registry: Any,
        role_model_bindings: list,
        role_registry: BuiltInRoleRegistry,
        *,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)
        self.memory_store = memory_store or get_shared_redis_memory_store()
        self.memory_context_builder = MemoryContextBuilder(store=self.memory_store)

    def resolve(self, session: GameSession, human_action: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Collect all night actions via LLM and resolve deaths.

        Returns a list of new public events.
        """
        session.night_actions.clear()
        state = session.state
        context = build_game_context(session)
        events: list[dict[str, Any]] = []
        # 优化点，统一封装为夜晚存在行动的角色，通过策略模式和注册期模式直接包起来
        # 1. Wolf kill
        if self._has_alive_role(session, {"werewolf"}):
            events.append(event("night_step_started", "狼人开始行动。", step="werewolf"))
        wolf_target_id = self._collect_wolf_kill(session, context, human_action)
        if self._has_alive_role(session, {"werewolf"}):
            events.append(event("night_step_finished", "狼人行动完成。", step="werewolf"))

        # 2. Seer check
        if self._has_alive_role(session, {"seer"}):
            events.append(event("night_step_started", "预言家开始行动。", step="seer"))
        events.extend(self._collect_seer_check(session, context, human_action))
        if self._has_alive_role(session, {"seer"}):
            events.append(event("night_step_finished", "预言家行动完成。", step="seer"))

        # 3. Guard protect
        if self._has_alive_role(session, {"guard", "guardian"}):
            events.append(event("night_step_started", "守卫开始行动。", step="guard"))
        guard_target_id = self._collect_guard(session, context, human_action)
        if self._has_alive_role(session, {"guard", "guardian"}):
            events.append(event("night_step_finished", "守卫行动完成。", step="guard"))

        # 4. Witch decision (needs to know wolf target)
        if self._has_alive_role(session, {"witch"}):
            events.append(event("night_step_started", "女巫开始行动。", step="witch"))
        witch_poison_target = self._collect_witch(session, context, wolf_target_id, human_action)
        if self._has_alive_role(session, {"witch"}):
            events.append(event("night_step_finished", "女巫行动完成。", step="witch"))

        # 5. Resolve deaths
        deaths = self._resolve_deaths(session, wolf_target_id, guard_target_id, witch_poison_target)

        # 6. Record deaths and set phase
        state.phase = GamePhase.DAY_ANNOUNCEMENT
        events.append(event("phase_changed", "天亮了，所有玩家睁眼。"))
        if deaths:
            death_names = [player_label(pid, session) for pid in deaths]
            events.append(event("night_result", f"昨夜，玩家{', '.join(death_names)} 出局。"))
        else:
            events.append(event("night_result", "昨夜平安夜，没有玩家出局。"))

        return events

    def resolve_pre_witch(self, session: GameSession, human_action: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run wolf/seer/guard steps only.  Store wolf kill target in session.

        Used for the two-step night when the human player is a witch.
        """
        session.night_actions.clear()
        context = build_game_context(session)
        events: list[dict[str, Any]] = []

        # 1. Wolf kill
        if self._has_alive_role(session, {"werewolf"}):
            events.append(event("night_step_started", "狼人开始行动。", step="werewolf"))
        wolf_target_id = self._collect_wolf_kill(session, context, human_action)
        if self._has_alive_role(session, {"werewolf"}):
            events.append(event("night_step_finished", "狼人行动完成。", step="werewolf"))

        # 2. Seer check
        if self._has_alive_role(session, {"seer"}):
            events.append(event("night_step_started", "预言家开始行动。", step="seer"))
        events.extend(self._collect_seer_check(session, context, human_action))
        if self._has_alive_role(session, {"seer"}):
            events.append(event("night_step_finished", "预言家行动完成。", step="seer"))

        # 3. Guard protect
        if self._has_alive_role(session, {"guard", "guardian"}):
            events.append(event("night_step_started", "守卫开始行动。", step="guard"))
        guard_target_id = self._collect_guard(session, context, human_action)
        if self._has_alive_role(session, {"guard", "guardian"}):
            events.append(event("night_step_finished", "守卫行动完成。", step="guard"))

        # Cache wolf kill target and guard target for the witch step
        session.night_pending_kill_target_id = wolf_target_id
        session.night_pending_guard_target_id = guard_target_id

        return events

    def resolve_witch_step(self, session: GameSession, human_action: dict[str, Any]) -> list[dict[str, Any]]:
        """Run witch step and resolve deaths.  Uses cached wolf kill target.

        Called after resolve_pre_witch() when the human witch submits their action.
        """
        wolf_target_id = session.night_pending_kill_target_id
        guard_target_id = getattr(session, "night_pending_guard_target_id", None)
        context = build_game_context(session)
        events: list[dict[str, Any]] = []

        # 4. Witch decision
        if self._has_alive_role(session, {"witch"}):
            events.append(event("night_step_started", "女巫开始行动。", step="witch"))
        witch_poison_target = self._collect_witch(session, context, wolf_target_id, human_action)
        if self._has_alive_role(session, {"witch"}):
            events.append(event("night_step_finished", "女巫行动完成。", step="witch"))

        # 5. Resolve deaths
        deaths = self._resolve_deaths(session, wolf_target_id, guard_target_id, witch_poison_target)

        # 6. Record deaths and set phase
        session.state.phase = GamePhase.DAY_ANNOUNCEMENT
        events.append(event("phase_changed", "天亮了，所有玩家睁眼。"))
        if deaths:
            death_names = [player_label(pid, session) for pid in deaths]
            events.append(event("night_result", f"昨夜，玩家{', '.join(death_names)} 出局。"))
        else:
            events.append(event("night_result", "昨夜平安夜，没有玩家出局。"))

        # Clean up
        session.night_pending_kill_target_id = None
        session.night_pending_guard_target_id = None

        return events

    def _collect_wolf_kill(self, session: GameSession, context: str, human_action: dict[str, Any] | None = None) -> str | None:
        """Ask wolf AI(s) to choose a kill target.

        When two or more AI wolves are alive, the werewolf council graph is
        used so that each wolf proposes, votes, and reaches consensus.  For a
        single AI wolf (or when the council times out) the original
        single-wolf path is used as fallback.
        """
        # ================================================================
        # Step 1: 获取所有存活狼人（含人类狼人）
        # ================================================================
        alive_wolves = [p for p in session.state.players if p.alive and p.role_key == "werewolf"]
        if not alive_wolves:
            logger.info("[COLLECT_WOLF_KILL] day=%s 无存活狼人，跳过刀人阶段", session.state.day_count)
            return None

        wolf_labels = {w.player_id: player_label(w.player_id, session) for w in alive_wolves}
        wolf_is_human_flags = {w.player_id: w.is_human for w in alive_wolves}
        logger.info(
            "[COLLECT_WOLF_KILL] day=%s 存活狼人数量=%d: %s",
            session.state.day_count,
            len(alive_wolves),
            {player_label: f"human={wolf_is_human_flags[pid]}" for pid, player_label in wolf_labels.items()},
        )

        # ================================================================
        # Step 2: 处理人类狼人的行动（如果有）
        # ================================================================
        human_target = self._human_night_target(session, human_action, "werewolf", {"wolf_kill"})
        if human_target:
            logger.info(
                "[COLLECT_WOLF_KILL] day=%s 检测到人类狼人行动 target_raw=%s",
                session.state.day_count, human_target,
            )
            target_id = self._validate_target(human_target, session, exclude_wolves=True)
            if target_id:
                logger.info(
                    "[COLLECT_WOLF_KILL] day=%s 人类狼人目标验证通过 target=%s (%s)",
                    session.state.day_count, target_id, player_label(target_id, session),
                )
                human_wolf_id = session.human_player_id
                session.night_actions.append({
                    "actor_player_id": human_wolf_id,
                    "action_type": "wolf_kill",
                    "target_player_id": target_id,
                    "round": f"night{session.state.day_count}",
                })
                log_player_action(
                    session,
                    actor_id=human_wolf_id,
                    action_type="wolf_kill",
                    target_id=target_id,
                    source="human",
                    decision=human_action,
                )
                # 如果人类是唯一的狼人，直接返回
                if len(alive_wolves) <= 1:
                    logger.info(
                        "[COLLECT_WOLF_KILL] day=%s 人类是唯一狼人，直接返回 target=%s",
                        session.state.day_count, target_id,
                    )
                    return target_id
                # 多狼场景：将人类提议注入议会，让AI狼人投票时参考
                human_proposal = {
                    "wolf_id": human_wolf_id,
                    "target_id": target_id,
                    "reason": "人类狼人选定",
                    "risk": 3,
                }
                # 从 alive_wolves 中排除人类狼人，得到纯AI狼人列表
                alive_ai_wolves = [w for w in alive_wolves if not w.is_human]
                logger.info(
                    "[COLLECT_WOLF_KILL] day=%s 人类狼人+AI狼人=%d人，将人类提议注入议会 AI狼人=%s",
                    session.state.day_count,
                    len(alive_wolves),
                    [player_label(w.player_id, session) for w in alive_ai_wolves],
                )
                return self._run_council_or_fallback(
                    session, context, alive_ai_wolves, human_proposal=human_proposal,
                )
            else:
                logger.warning(
                    "[COLLECT_WOLF_KILL] day=%s 人类狼人目标验证失败 target_raw=%s，跳过人类行动",
                    session.state.day_count, human_target,
                )
        else:
            logger.info(
                "[COLLECT_WOLF_KILL] day=%s 无人类狼人行动（human_action=%s）",
                session.state.day_count,
                human_action.get("action_type") if human_action else "None",
            )

        # ================================================================
        # Step 3: 筛选纯AI狼人，选择执行路径
        # ================================================================
        # 注意：此处重新计算 alive_ai_wolves ——
        # 如果上面人类狼人提交了行动但目标验证失败，代码会落到这里，
        # 此时 alive_ai_wolves 需要包含所有AI狼人（人类狼人的行动被忽略）
        alive_ai_wolves = [w for w in alive_wolves if not w.is_human]

        if len(alive_ai_wolves) <= 1:
            # 路径A: 单AI狼人 → 直接调用 _single_wolf_kill（原逻辑）
            logger.info(
                "[COLLECT_WOLF_KILL] day=%s AI狼人数量=%d（≤1），走单狼路径 _single_wolf_kill AI狼人=%s",
                session.state.day_count,
                len(alive_ai_wolves),
                [player_label(w.player_id, session) for w in alive_ai_wolves],
            )
            return self._single_wolf_kill(session, context, alive_ai_wolves)

        # 路径B: 多AI狼人 → 走狼人议会（LangGraph council）
        logger.info(
            "[COLLECT_WOLF_KILL] day=%s AI狼人数量=%d（≥2），走议会路径 _run_council_or_fallback AI狼人=%s",
            session.state.day_count,
            len(alive_ai_wolves),
            [player_label(w.player_id, session) for w in alive_ai_wolves],
        )
        return self._run_council_or_fallback(session, context, alive_ai_wolves)

    def _single_wolf_kill(
        self,
        session: GameSession,
        context: str,
        ai_wolves: list,
    ) -> str | None:
        """Original single-wolf kill path (used as fallback)."""
        wolf = next(iter(ai_wolves), None)
        if wolf is None:
            return None
        decision = self._get_ai_decision(session, wolf.player_id, context)

        target_id = self._validate_target(decision.target_id, session, exclude_wolves=True)
        if target_id:
            session.night_actions.append({
                "actor_player_id": wolf.player_id,
                "action_type": "wolf_kill",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            log_player_action(
                session,
                actor_id=wolf.player_id,
                action_type="wolf_kill",
                target_id=target_id,
                source="ai",
                decision=decision,
            )
            return target_id
        return None

    def _run_council_or_fallback(
        self,
        session: GameSession,
        context: str,
        ai_wolves: list,
        *,
        human_proposal: dict[str, Any] | None = None,
    ) -> str | None:
        """Run the werewolf council graph.  Falls back to single-wolf on error.

        关键反偏见措施：
        1. candidate_labels 将原始 player_id（如 "human", UUID）映射为可读标签（如 "1号 你", "2号 小灰"）
           —— 防止 LLM 对裸 "human" 字符串产生强烈偏好
        2. random.shuffle(candidates) 打乱候选顺序
           —— 防止 LLM 对列表第一位的位置偏见（positional bias）
        """
        # ================================================================
        # Step 1: 收集候选目标（存活非狼人玩家）
        # ================================================================
        candidates = [
            p.player_id for p in session.state.players
            if p.alive and p.role_key != "werewolf"
        ]
        if not candidates:
            logger.info("[WOLF_COUNCIL] day=%s 无可选目标（所有存活玩家都是狼人），返回None", session.state.day_count)
            return None

        logger.info(
            "[WOLF_COUNCIL] day=%s 候选目标数量=%d 原始顺序=%s",
            session.state.day_count,
            len(candidates),
            [player_label(pid, session) for pid in candidates],
        )

        # ================================================================
        # Step 2: 构建 display labels —— 核心防偏见机制
        # ================================================================
        # 将原始 player_id 映射为 "X号 名称" 格式的标签
        # 这对于防止 LLM 偏见至关重要：裸 "human" 字符串在语义上过于显眼
        candidate_labels = {pid: player_label(pid, session) for pid in candidates}
        # 狼人本身也需要标签（在议会提示词中显示"你的狼队友：2号 小明"）
        wolf_ids = [w.player_id for w in ai_wolves]
        for wid in wolf_ids:
            candidate_labels[wid] = player_label(wid, session)

        logger.info(
            "[WOLF_COUNCIL] day=%s candidate_labels: 目标=%s 狼人=%s",
            session.state.day_count,
            {pid: candidate_labels[pid] for pid in candidates},  # 仅目标，不含狼人
            {wid: candidate_labels[wid] for wid in wolf_ids},    # 狼人标签
        )

        # ================================================================
        # Step 3: Shuffle 候选列表 —— 防位置偏见
        # ================================================================
        # LLM 对列表第一个元素有天然偏好（primacy bias）
        # 不 shuffle 会导致每次都倾向于刀第一个候选（通常是座次最小的玩家）
        candidates_before = candidates.copy()  # 保存一份用于对比日志
        random.shuffle(candidates)

        logger.info(
            "[WOLF_COUNCIL] day=%s shuffle后候选顺序=%s (之前=%s)",
            session.state.day_count,
            [player_label(pid, session) for pid in candidates],
            [player_label(pid, session) for pid in candidates_before],
        )

        # ================================================================
        # Step 4: 调用狼人议会图
        # ================================================================
        participants = wolf_ids
        round_id = f"night_{session.state.day_count}"
        # 上下文截断至最后500字符——控制提示词长度，LLM只需要近期事件
        truncated_context = context[-500:] if context else ""

        logger.info(
            "[WOLF_COUNCIL] day=%s 即将调用狼人议会 participants=%s candidates=%s human_proposal=%s context_len=%d timeout=45s",
            session.state.day_count,
            [player_label(pid, session) for pid in participants],
            [player_label(pid, session) for pid in candidates],
            bool(human_proposal),
            len(truncated_context),
        )

        # ---- 构造 decider_factory ----
        # 每个狼人调用 LLM 时需要自己的 PlayerDecider 实例
        def decider_factory(wolf_id: str) -> PlayerDecider:
            player = session.state.player_by_id(wolf_id)
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            return PlayerDecider(provider)

        try:
            result = run_werewolf_council(
                game_id=session.state.game_id,
                round_id=round_id,
                participants=participants,
                candidates=candidates,
                candidate_labels=candidate_labels,
                decider_factory=decider_factory,
                game_context=truncated_context,
                human_proposal=human_proposal,
                timeout_s=45.0,
            )
        except Exception:
            logger.exception(
                "[WOLF_COUNCIL] day=%s 狼人议会异常，回退到单狼路径 _single_wolf_kill",
                session.state.day_count,
            )
            return self._single_wolf_kill(session, context, ai_wolves)

        # ================================================================
        # Step 5: 解析并验证议会结果
        # ================================================================
        raw_decision = result.get("decision")
        tally = result.get("tally", {})
        rationale = result.get("rationale", "")
        council_error = result.get("error")

        logger.info(
            "[WOLF_COUNCIL] day=%s 议会结果: decision=%s rationale=%s tally=%s error=%s proposals=%d votes=%d",
            session.state.day_count,
            raw_decision,
            rationale,
            tally,
            council_error,
            len(result.get("proposals", [])),
            len(result.get("votes", [])),
        )

        # 记录每个狼人的提案和投票详情（调试用）
        for p in result.get("proposals", []):
            logger.info(
                "[WOLF_COUNCIL] day=%s 提案: wolf=%s target=%s risk=%s reason=%s",
                session.state.day_count,
                player_label(p.get("wolf_id", "?"), session),
                player_label(p.get("target_id", "?"), session) if p.get("target_id") else "None",
                p.get("risk", "?"),
                p.get("reason", "")[:60],
            )
        for v in result.get("votes", []):
            logger.info(
                "[WOLF_COUNCIL] day=%s 投票: wolf=%s target=%s",
                session.state.day_count,
                player_label(v.get("wolf_id", "?"), session),
                player_label(v.get("target_id", "?"), session) if v.get("target_id") else "None",
            )

        # ---- 验证目标合法性 ----
        target_id = raw_decision
        if target_id:
            target_id = self._validate_target(target_id, session, exclude_wolves=True)
            if target_id != raw_decision:
                logger.warning(
                    "[WOLF_COUNCIL] day=%s _validate_target 修改了目标: %s → %s",
                    session.state.day_count, raw_decision, target_id,
                )

        if not target_id:
            logger.warning(
                "[WOLF_COUNCIL] day=%s 议会未能产生有效目标（decision=%s），回退到 _single_wolf_kill",
                session.state.day_count, raw_decision,
            )
            return self._single_wolf_kill(session, context, ai_wolves)

        # ================================================================
        # Step 6: 记录行动并返回
        # ================================================================
        actor_id = participants[0]
        logger.info(
            "[WOLF_COUNCIL] day=%s 最终刀人目标: %s (%s), tally=%s source=ai_council",
            session.state.day_count, target_id, player_label(target_id, session), tally,
        )

        session.night_actions.append({
            "actor_player_id": actor_id,
            "action_type": "wolf_kill",
            "target_player_id": target_id,
            "round": f"night{session.state.day_count}",
        })
        log_player_action(
            session,
            actor_id=actor_id,
            action_type="wolf_kill",
            target_id=target_id,
            source="ai_council",
            decision={"action_type": "wolf_kill", "target_id": target_id, "rationale": rationale},
            metadata={"council": True, "tally": tally},
        )
        return target_id

    def _collect_seer_check(self, session: GameSession, context: str, human_action: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Ask seer AI to choose a check target."""
        alive_seer = next((p for p in session.state.players if p.alive and p.role_key == "seer"), None)
        if alive_seer is None:
            return []

        human_target = self._human_night_target(session, human_action, "seer", {"seer_check"})
        if alive_seer.is_human:
            target_id = self._validate_target(human_target, session, exclude_player_id=alive_seer.player_id)
            if target_id:
                self._record_seer_result(session, alive_seer.player_id, target_id)
                target_player = session.state.player_by_id(target_id)
                camp = "狼人阵营" if target_player.role_key == "werewolf" else "好人阵营"
                log_player_action(
                    session,
                    actor_id=alive_seer.player_id,
                    action_type="seer_check",
                    target_id=target_id,
                    source="human",
                    decision=human_action,
                    metadata={"result": camp},
                )
                return [{
                    "event_type": "private_info",
                    "actor_id": alive_seer.player_id,
                    "target_id": target_id,
                    "payload": {"message": f"你的查验结果：{player_label(target_id, session)} 是{camp}。"},
                    "public": False,
                    "visibility": "self",
                }]
            return []

        decision = self._get_ai_decision(session, alive_seer.player_id, context)
        target_id = self._validate_target(decision.target_id, session, exclude_player_id=alive_seer.player_id)
        if target_id:
            self._record_seer_result(session, alive_seer.player_id, target_id)
            target_player = session.state.player_by_id(target_id)
            camp = "werewolf" if target_player.role_key == "werewolf" else "good"
            log_player_action(
                session,
                actor_id=alive_seer.player_id,
                action_type="seer_check",
                target_id=target_id,
                source="ai",
                decision=decision,
                metadata={"result": camp},
            )
        return []

    def _collect_guard(self, session: GameSession, context: str, human_action: dict[str, Any] | None = None) -> str | None:
        """Ask guard AI to choose a protect target."""
        alive_guard = next((p for p in session.state.players if p.alive and p.role_key in {"guard", "guardian"}), None)
        if alive_guard is None:
            return None

        info = session.private_infos.setdefault(alive_guard.player_id, PlayerPrivateInfo())
        last_guarded = info.guard_history[-1] if info.guard_history else None

        if alive_guard.is_human:
            target_id = self._human_night_target(session, human_action, alive_guard.role_key, {"guard"})
        else:
            decision = self._get_ai_decision(session, alive_guard.player_id, context)
            target_id = decision.target_id

        # Enforce: cannot guard same person two nights in a row
        target_id = self._validate_target(target_id, session)
        if target_id and target_id == last_guarded:
            # Fallback: pick a different valid target
            valid_targets = [p.player_id for p in session.state.players if p.alive and p.player_id != last_guarded]
            target_id = valid_targets[0] if valid_targets else None

        if target_id:
            info.guard_history.append(target_id)
            session.night_actions.append({
                "actor_player_id": alive_guard.player_id,
                "action_type": "guard",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            log_player_action(
                session,
                actor_id=alive_guard.player_id,
                action_type="guard",
                target_id=target_id,
                source="human" if alive_guard.is_human else "ai",
                decision=human_action if alive_guard.is_human else decision,
            )
            return target_id
        return None

    def _collect_witch(
        self,
        session: GameSession,
        context: str,
        wolf_target_id: str | None,
        human_action: dict[str, Any] | None = None,
    ) -> str | None:
        """Ask witch AI to decide save/poison. Returns poison target if used.

        When the witch is AI, the witch decision graph is used for multi-step
        reasoning (assess -> decide_save -> decide_poison -> finalize).
        On error or timeout, falls back to the original single-decision path.
        """
        alive_witch = next((p for p in session.state.players if p.alive and p.role_key == "witch"), None)
        if alive_witch is None:
            return None

        info = session.private_infos.setdefault(alive_witch.player_id, PlayerPrivateInfo())

        if alive_witch.is_human:
            action = human_action.get("action_type") if human_action else "no_action"
            target_id = human_action.get("target_player_id") if human_action else None
            return self._apply_witch_decision(session, alive_witch.player_id, info, action, target_id)

        # --- Try witch council graph first ---
        try:
            return self._run_witch_graph_or_fallback(session, context, alive_witch, info, wolf_target_id)
        except Exception:
            logger.exception("Witch graph failed, falling back to single-decision path")
            return self._witch_single_decision(session, context, alive_witch, info, wolf_target_id)

    def _run_witch_graph_or_fallback(
        self,
        session: GameSession,
        context: str,
        alive_witch: Any,
        info: PlayerPrivateInfo,
        wolf_target_id: str | None,
    ) -> str | None:
        """Run the witch decision graph, falling back to single-decision on error."""

        def decider_factory(witch_id: str) -> PlayerDecider:
            player = session.state.player_by_id(witch_id)
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            return PlayerDecider(provider)

        result = run_witch_council(
            game_id=session.state.game_id,
            round_id=f"night_{session.state.day_count}",
            witch_id=alive_witch.player_id,
            killed_player_id=wolf_target_id,
            has_save_potion=info.witch_medicine.get("save", False),
            has_poison=info.witch_medicine.get("poison", False),
            night_number=session.state.day_count,
            alive_players=session.state.alive_player_ids(),
            decider_factory=decider_factory,
            timeout_s=45.0,
        )

        action_type = result.get("action_type", "no_action")
        target_id = result.get("target_id")

        if result.get("error"):
            logger.warning("Witch graph returned error '%s', falling back to single-decision", result["error"])
            return self._witch_single_decision(session, context, alive_witch, info, wolf_target_id)

        return self._apply_witch_decision(session, alive_witch.player_id, info, action_type, target_id)

    def _witch_single_decision(
        self,
        session: GameSession,
        context: str,
        alive_witch: Any,
        info: PlayerPrivateInfo,
        wolf_target_id: str | None,
    ) -> str | None:
        """Original single-decision path for the witch (used as fallback)."""
        # Build death info string to pass in private_info
        death_info = ""
        if wolf_target_id and info.witch_medicine.get("save", False):
            can_save_self = session.state.day_count == 1
            if wolf_target_id == alive_witch.player_id and not can_save_self:
                death_info = f"今晚 {player_label(wolf_target_id, session)} 被狼人击杀（你不能自救）。"
            else:
                death_info = f"今晚 {player_label(wolf_target_id, session)} 被狼人击杀。"

        if death_info:
            base_private = format_private_info(info, "witch", player_label=lambda player_id: player_label(player_id, session))
            augmented_private = base_private + "\n" + death_info if base_private else death_info
        else:
            augmented_private = format_private_info(info, "witch", player_label=lambda player_id: player_label(player_id, session))

        agent = session.agents.get(alive_witch.player_id)
        if agent is None:
            return None

        prompt = build_night_action_prompt(
            agent=agent,
            role_key="witch",
            night_action="witch_potion",
            game_id=session.state.game_id,
            round_info=f"night{session.state.day_count}",
            alive_players=session.state.alive_player_ids(),
            game_context=context,
            private_info=augmented_private,
            board_context=self._board_context(session),
            board_roles=self._board_roles(session),
            player_references=player_references(session),
            enabled_role_keys={player.role_key for player in session.state.players},
        )

        decision = self._get_ai_decision_with_prompt(session, alive_witch.player_id, prompt)
        return self._apply_witch_decision(session, alive_witch.player_id, info, str(decision.action_type), decision.target_id)

    def _apply_witch_decision(
        self,
        session: GameSession,
        witch_player_id: str,
        info: PlayerPrivateInfo,
        action: str,
        target_id: str | None,
    ) -> str | None:
        poison_target: str | None = None

        if action == "witch_save" and info.witch_medicine.get("save", False) and target_id:
            # Check self-save rule
            can_save_self = session.state.day_count == 1
            if target_id == witch_player_id and not can_save_self:
                pass  # Cannot save self after first night
            else:
                info.witch_medicine["save"] = False
                session.witch_has_save_potion = False
                session.night_actions.append({
                    "actor_player_id": witch_player_id,
                    "action_type": "witch_save",
                    "target_player_id": target_id,
                    "round": f"night{session.state.day_count}",
                })
                log_player_action(
                    session,
                    actor_id=witch_player_id,
                    action_type="witch_save",
                    target_id=target_id,
                    source="human" if session.state.player_by_id(witch_player_id).is_human else "ai",
                    decision={"action_type": action, "target_id": target_id},
                )

        elif action == "witch_poison" and info.witch_medicine.get("poison", False) and target_id:
            valid_target = self._validate_target(target_id, session)
            if valid_target:
                info.witch_medicine["poison"] = False
                session.witch_has_poison = False
                poison_target = valid_target
                session.night_actions.append({
                    "actor_player_id": witch_player_id,
                    "action_type": "witch_poison",
                    "target_player_id": valid_target,
                    "round": f"night{session.state.day_count}",
                })
                log_player_action(
                    session,
                    actor_id=witch_player_id,
                    action_type="witch_poison",
                    target_id=valid_target,
                    source="human" if session.state.player_by_id(witch_player_id).is_human else "ai",
                    decision={"action_type": action, "target_id": target_id},
                )

        return poison_target

    def _record_seer_result(self, session: GameSession, seer_id: str, target_id: str) -> None:
        target_player = session.state.player_by_id(target_id)
        result = "werewolf" if target_player.role_key == "werewolf" else "good"
        info = session.private_infos.setdefault(seer_id, PlayerPrivateInfo())
        info.seer_results.append({
            "round": f"night{session.state.day_count}",
            "target": target_id,
            "result": result,
        })
        session.night_actions.append({
            "actor_player_id": seer_id,
            "action_type": "check",
            "target_player_id": target_id,
            "round": f"night{session.state.day_count}",
        })

    def _human_night_target(
        self,
        session: GameSession,
        human_action: dict[str, Any] | None,
        role_key: str,
        action_types: set[str],
    ) -> str | None:
        if not human_action or human_action.get("action_type") not in action_types:
            return None
        actor_id = human_action.get("actor_player_id")
        if actor_id != session.human_player_id:
            return None
        human = session.state.player_by_id(session.human_player_id)
        if not human.alive or human.role_key != role_key:
            return None
        return human_action.get("target_player_id")

    def _resolve_deaths(
        self,
        session: GameSession,
        wolf_target_id: str | None,
        guard_target_id: str | None,
        poison_target: str | None,
    ) -> list[str]:
        """Compute final death list based on all night actions."""
        state = session.state
        deaths: list[str] = []

        # Wolf kill resolution
        if wolf_target_id is not None:
            guarded = wolf_target_id == guard_target_id
            if not guarded:
                # Check if witch saved
                saved = any(
                    a["action_type"] == "witch_save" and a["target_player_id"] == wolf_target_id
                    for a in session.night_actions
                )
                if not saved:
                    deaths.append(wolf_target_id)

        # Witch poison
        if poison_target is not None:
            if poison_target not in deaths:
                deaths.append(poison_target)

        # Mark deaths
        for pid in deaths:
            state.player_by_id(pid).alive = False

        return deaths

    def _get_ai_decision(self, session: GameSession, player_id: str, context: str) -> PlayerDecision:
        """Get LLM decision for a player using the unified night decision graph."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return PlayerDecision(speech="无行动", action_type="no_action", target_id=None, public_reason=None, private_memory_update=None)

        memory_context = self.memory_context_builder.build_for_player(session, player_id)
        provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
        decider = PlayerDecider(provider)

        def decision_generator(state: dict[str, Any]) -> PlayerDecision:
            tasks = self.scheduler.schedule(
                state=session.state,
                agents=session.agents,
                private_infos=session.private_infos,
                game_context=context,
            )
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return PlayerDecision(speech="无行动", action_type="no_action", target_id=None, public_reason=None, private_memory_update=None)
            locked_prompt = _append_locked_decision_block(task.prompt, state)
            return self._get_ai_decision_with_prompt(session, player_id, locked_prompt, decider=decider)

        result = run_player_decision_graph(
            agent=agent,
            player=player,
            memory_context=memory_context,
            decision_kind="night_action",
            decision_generator=decision_generator,
            semantic_decider=decider,
            semantic_nodes=configured_semantic_nodes(),
        )
        self._persist_player_memories(session, player_id, result)
        return result["decision"]

    def _get_ai_decision_with_prompt(
        self,
        session: GameSession,
        player_id: str,
        prompt: str,
        decider: PlayerDecider | None = None,
    ) -> PlayerDecision:
        """Call LLM with a specific prompt and return PlayerDecision."""
        player = session.state.player_by_id(player_id)
        try:
            decision_decider = decider
            if decision_decider is None:
                provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
                decision_decider = PlayerDecider(provider)
            record_prompt_trace(session, player_id, "night_action", prompt)
            decision = decision_decider.decide(prompt)

            # ---- 全链路诊断：夜晚私有行动不需要发言，空speech正常 ----
            if not decision.speech.strip():
                logger.info(
                    "[NIGHT_DECISION_EMPTY_SPEECH] player=%s(%s) role=%s action=%s target=%s "
                    "day=%s -- 夜晚私有行动，Decider层已保留原动作，视为正常",
                    player_label(player_id, session), player_id[:8],
                    player.role_key, decision.action_type, decision.target_id,
                    session.state.day_count,
                )

            log_player_action(
                session,
                actor_id=player_id,
                action_type=str(decision.action_type),
                target_id=decision.target_id,
                source="ai",
                decision=decision,
                metadata={"stage": "night_decision"},
            )
            return decision
        except Exception:
            logger.exception("AI %s night decision failed, using fallback", player_id)
            fallback = PlayerDecision(speech="无行动", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)
            log_player_action(
                session,
                actor_id=player_id,
                action_type="speak",
                source="ai",
                decision=fallback,
                metadata={"stage": "night_decision_fallback"},
            )
            return fallback

    def _persist_player_memories(self, session: GameSession, player_id: str, result: dict[str, Any]) -> None:
        previous = self.memory_store.get_player_suspicion(session.state.game_id, player_id)
        suspicion_memory = build_player_suspicion_memory(
            game_id=session.state.game_id,
            player_id=player_id,
            day=session.state.day_count,
            suspicion_update=result.get("suspicion_update"),
            previous=previous,
        )
        if suspicion_memory is not None:
            logger.info("夜晚决策后写回怀疑链 player_id=%s records=%d", player_id, len(suspicion_memory.records))
            self.memory_store.save_player_suspicion(suspicion_memory)
        private_role_memory = build_private_role_memory(
            game_id=session.state.game_id,
            player_id=player_id,
            private_info=session.private_infos.get(player_id),
        )
        if private_role_memory is not None:
            self.memory_store.save_private_role_memory(private_role_memory)

    def _validate_target(self, target_id: str | None, session: GameSession, exclude_wolves: bool = False, exclude_player_id: str | None = None) -> str | None:
        """Validate that a target is an alive player. Returns None if invalid."""
        if target_id is None:
            return None
        state = session.state
        resolved = resolve_player_id(target_id, session)
        if resolved is None:
            return None
        alive_ids = {p.player_id for p in state.players if p.alive}
        if resolved not in alive_ids:
            return None
        if resolved == exclude_player_id:
            return None
        if exclude_wolves:
            target_player = state.player_by_id(resolved)
            if target_player.role_key == "werewolf":
                non_wolves = [p.player_id for p in state.players if p.alive and p.role_key != "werewolf"]
                return random.choice(non_wolves) if non_wolves else None
        return resolved

    def _has_alive_role(self, session: GameSession, role_keys: set[str]) -> bool:
        return any(player.alive and player.role_key in role_keys for player in session.state.players)

    def _board_context(self, session: GameSession) -> str:
        role_counts: dict[str, int] = {}
        for player in session.state.players:
            role_counts[player.role_key] = role_counts.get(player.role_key, 0) + 1
        role_names = {
            "werewolf": "狼人",
            "seer": "预言家",
            "witch": "女巫",
            "hunter": "猎人",
            "villager": "村民",
            "guard": "守卫",
            "guardian": "守卫",
        }
        roles = "、".join(f"{role_names.get(role_key, role_key)}x{count}" for role_key, count in role_counts.items())
        return f"板子：{session.state.board_id}；角色构成：{roles}；胜利条件：狼人全部出局或狼人达到人数优势。"

    def _board_roles(self, session: GameSession) -> dict[str, int]:
        """Extract {role_key: count} from the board config for prompt constraints."""
        from ai_werewolf.seeds.boards import default_boards

        board = next((b for b in default_boards() if b.board_id == session.state.board_id), None)
        if board is not None:
            return board.roles_count_dict()
        # Fallback: derive from current player list
        role_counts: dict[str, int] = {}
        for player in session.state.players:
            role_counts[player.role_key] = role_counts.get(player.role_key, 0) + 1
        return role_counts
