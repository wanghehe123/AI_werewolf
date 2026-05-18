# AI Werewolf 系统现状与后续工作梳理

## 1. 文档目的

本文用于梳理当前分支 `codex/ai-werewolf-experience-sse` 上，围绕“LangGraph 决策链 + 记忆系统优化”所做的工作、系统当前真实状态，以及尚未完成的部分，供继续开发、联调和测试使用。

## 2. 当前代码状态

- 当前分支：`codex/ai-werewolf-experience-sse`
- 当前头提交：
  - `2bda186 Merge branch 'codex/langgraph-memory-implementation' into codex/ai-werewolf-experience-sse`
  - `7e0cd7d chore: update llm provider config`
- 当前工作区状态：
  - 已无冲突
  - 仅剩一个未跟踪文件：`docs/superpowers/plans/2026-05-17-langgraph-memory-implementation.md`
- 已验证测试：
  - 决策链/记忆相关回归：`121 passed`
  - 配置相关测试：`6 passed`

## 3. 这轮工作的核心目标

本轮目标原本是两件事：

1. 将 DaySummary、怀疑链、私有记忆真正写入 Redis，而不是只读骨架。
2. 将投票和夜晚行为接入统一的结构化决策图，使“发言链”和“行为链”统一。

目前这两件事的“基础设施”和“主链路接入”已经完成，但仍有若干重要差距，尤其在“智能程度”和“摘要质量”上。

## 4. 当前系统总体架构

### 4.1 游戏主流程

当前游戏主流程仍由 [orchestrator.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/engine/orchestrator.py) 驱动：

- `PhaseOrchestrator`
- `NightResolver`
- `VoteResolver`
- `HunterResolver`
- `AIActionScheduler`

阶段流转仍是既有模式：

- `SETUP`
- `NIGHT`
- `DAY_ANNOUNCEMENT`
- `DAY_SPEECH`
- `EXILE_VOTE`
- `LAST_WORDS`
- `GAME_OVER`

### 4.2 AI 决策相关核心模块

本轮新增/强化的模块主要有：

- 统一决策图：[player_decision_graph.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/graphs/player_decision_graph.py)
- 决策图状态：[player_decision_state.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/graphs/player_decision_state.py)
- 记忆上下文构建：[context_builder.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/context_builder.py)
- 记忆模型：[models.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/models.py)
- 记忆存储：[store.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/store.py)
- 每日摘要构建：[summary_builder.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/summary_builder.py)

## 5. 已完成的工作

## 5.1 白天发言已接入结构化决策图

白天发言现在通过 `run_player_speech_graph()` 进入统一决策图，再由 orchestrator 调用。

关键入口：
- [orchestrator.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/engine/orchestrator.py)
- `PhaseOrchestrator._run_ai_speech_graph()`

当前图节点逻辑为：

- `n1_analyze_situation`
- `n2_update_suspicion`
- `n3_decide_strategy`
- `n4_decide_action`
- `n5_generate_decision`
- `n6_validate_and_repair`

也就是说，形式上已经实现了“分析 -> 怀疑链 -> 策略 -> 行为 -> 发言/决策 -> 校验”的链路拆分。

## 5.2 投票阶段已接入统一决策图

投票链路已在 [vote.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/engine/vote.py) 中接入 `run_player_decision_graph()`：

- `VoteResolver._get_ai_vote()`
- `VoteResolver._persist_player_memories()`

投票前会先构建 `MemoryContext`，然后通过统一图产出 `PlayerDecision`，再做目标校验和落地。

## 5.3 夜晚单人行动已接入统一决策图

夜晚单人角色行为已在 [night.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/engine/night.py) 中接入统一图：

- `NightResolver._get_ai_decision()`
- `NightResolver._persist_player_memories()`

当前可走这条统一图的，主要是“单 AI 角色的夜晚行为”，例如：

- 预言家查验
- 守卫守护
- 单狼时的击杀决策

## 5.4 记忆上下文已结构化，不再只是一段纯字符串

现在 AI 决策前会先构建结构化 `MemoryContext`，包含：

- `recent_events`
- `day_summaries`
- `suspicion_memory`
- `private_role_memory`

关键文件：
- [context_builder.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/context_builder.py)

并且在 Redis 没有私有记忆时，会从 `session.private_infos` 回填，避免直接断链。

## 5.5 Redis 记忆落库链路已打通

当前 Redis 存储已真实可用，PostgreSQL 仍是空实现。

关键文件：
- [store.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/store.py)

当前 Redis key 设计：

- `aiw:memory:{game_id}:global:day:{day}:summary`
- `aiw:memory:{game_id}:global:day:index`
- `aiw:memory:{game_id}:player:{player_id}:suspicion`
- `aiw:memory:{game_id}:player:{player_id}:private_role`
- `aiw:memory:{game_id}:player:{player_id}:decision_trace:{phase}:{seq}`

其中：

- `DaySummary` 已可写入
- `PlayerSuspicionMemory` 已可写入
- `PrivateRoleMemory` 已可写入
- `DecisionTrace` 已可写入，但目前只在白天发言链写入

## 5.6 每日摘要 DaySummary 已可生成并写回 Redis

现在在白天结束、进入下一夜前，会调用：

- `PhaseOrchestrator._persist_day_memory()`

它内部使用：
- `build_day_summary(session)`

当前摘要生成逻辑是规则版，不是 LLM 摘要版。能提取的信息包括：

- 发言中的起跳信息
- 攻击关系
- 共边关系
- 票型汇总
- 低信息玩家

## 5.7 决策与 Prompt 的基线问题已修好

之前顺手修掉了两个重要基础问题：

- [player_decider.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/player_decider.py)
  - 空发言 fallback
  - 非法 `action_type` 兜底
- [prompt_builder.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/prompt_builder.py)
  - few-shot 按板子角色裁剪
  - 避免不存在的角色知识污染 prompt

## 6. 当前系统“真实能力”与“实际限制”

## 6.1 形式上已经是多级决策链，但当前节点智能度仍偏弱

虽然已经有了 LangGraph 多级结构，但要特别诚实地说：

- `n1_analyze_situation` 目前主要是拼接 `recent_events + day_summaries`
- `n2_update_suspicion` 目前主要是读取已有 `suspicion_memory.records`
- `n3_decide_strategy` 目前是基于 `primary_target` 的规则分支
- `n4_decide_action` 目前是按 `decision_kind` 和 `role_key` 做规则决策

也就是说：

**当前图已经是“结构上的多级链”，但还不是“每个节点都由 LLM 做强推理”的版本。**

## 6.2 发言链仍是“图驱动 + 旧 prompt 生成”的混合模式

白天发言虽然进入了决策图，但最终自然语言发言内容，仍然复用了旧链路：

- `AIActionScheduler.schedule()`
- `PlayerDecider.decide()`
- 原有 prompt 生成流程

换句话说：

- 分析/策略框架是新的
- 最终发言生成能力主体还是旧 prompt 驱动

这比“一次性纯 prompt”已经前进了一步，但还没完全演进到“节点级 structured output LLM graph”。

## 6.3 怀疑链“写回能力”已打通，但“增量演化能力”仍然很弱

这是当前最重要的现实问题之一。

现在 `suspicion_memory` 会被写回 Redis，但统一图里的 `n2_update_suspicion()` 目前只是：

- 读取已有 `records`
- 取第一个 `primary_target`

它**不会真正根据当前新发言、新票型、新公开事件生成一套新的怀疑记录**。

这意味着当前状态更像是：

- 怀疑链存储 plumbing 已完成
- 怀疑链的“智能更新逻辑”仍未完成

因此现在的怀疑链更接近“可存可读的骨架”，而不是成熟的动态推理资产。

## 6.4 DaySummary 已能落库，但仍是规则摘要，不是高质量语义摘要

当前 [summary_builder.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/memory/summary_builder.py) 使用的是规则方法：

- 正则抽取 “X号”
- 关键词判断“攻击/怀疑/像狼”
- 简单识别起跳
- 简单汇总票型

它的优点：

- 快
- 可解释
- 不依赖额外模型
- 能立刻缓解上下文膨胀

它的缺点：

- `conflicts` 基本还没真正构建
- `alliances` 很粗糙
- 复杂站边关系、悍跳逻辑、倒钩、冲锋、划水等识别弱
- 对自然语言表达方式比较敏感

## 6.5 夜晚行动的统一仍未完全覆盖全体角色/模式

虽然夜晚单人决策接入了统一图，但并不是全夜晚系统都已经统一：

- 多狼人协商仍走 [werewolf_council.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/graphs/werewolf_council.py)
- 女巫仍走 [witch_council.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/llm/graphs/witch_council.py)
- 猎人开枪仍是原引擎逻辑
- 多角色联动夜晚博弈还没有收束到统一图协议下

所以目前是：

**“单人行为统一了不少，但多人协商型夜晚链路仍是并行存在的专用图。”**

## 6.6 决策 trace 还没有完全统一

当前 `DecisionTrace` 的写入，在 orchestrator 中对白天发言已落库。  
但投票和夜晚目前主要做了“记忆回写”，**没有像白天发言那样完整落一份统一 trace**。

这会影响：

- 调试
- 复盘
- 评估 AI 推理链质量
- 后台可视化分析

## 6.7 最后一天的 DaySummary 可能不会落库

`_check_win_or_next_night()` 目前是先判断胜负，再决定是否写 `DaySummary`。  
这意味着如果白天结束后直接判胜，最后一天的摘要可能不会写入 Redis。

这是一个真实存在的边界缺口。

## 7. 当前系统在各阶段的实际行为

## 7.1 白天发言

当前行为：

- 先构建 `MemoryContext`
- 进入 `run_player_speech_graph`
- 图内做分析/策略/行为草稿
- 最终复用旧 prompt 生成发言
- 发言后写回怀疑链和私有记忆
- 写入 `day_speech` trace

## 7.2 投票阶段

当前行为：

- 先构建 `MemoryContext`
- 进入 `run_player_decision_graph(decision_kind="exile_vote")`
- 图内做策略和投票草稿
- 最终还是通过旧 prompt 生成 `PlayerDecision`
- 再做目标合法性校验
- 写回怀疑链和私有记忆

## 7.3 夜晚阶段

当前行为：

- 单人夜晚行为：会走统一图
- 多狼人协商：仍走 `werewolf_council`
- 女巫：仍走 `witch_council`
- 夜晚后单角色会写回怀疑链和私有记忆

## 8. 测试覆盖现状

本轮新增/强化的测试主要覆盖了这些行为：

- 发言链优先使用图：
  - [test_engine_orchestrator.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/ai_werewolf/tests/test_engine_orchestrator.py)
- 白天结束保存 DaySummary：
  - `test_check_win_or_next_night_saves_day_summary`
- 发言后持久化怀疑链：
  - `test_run_ai_speech_graph_persists_suspicion_memory`
- 投票走统一图：
  - `test_get_ai_vote_uses_unified_decision_graph`
- 夜晚单人行为走统一图：
  - `test_get_ai_decision_uses_unified_decision_graph`
- 决策图支持 vote/night：
  - [test_player_decision_graph.py](/Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/tests/llm/test_player_decision_graph.py)

## 9. 未完成工作清单

## 9.1 高优先级

- 让 `n2_update_suspicion` 真正根据当前局势生成新的怀疑链，而不是仅复用旧 records
- 让 `DaySummary` 升级为“规则预处理 + LLM 结构化摘要”
- 给投票和夜晚链路补齐 `DecisionTrace` 持久化
- 修复“终局最后一天摘要不落库”的边界问题
- 明确 `PlayerSuspicionMemory.records` 的结构 schema，减少 dict 自由度

## 9.2 中优先级

- 把多狼人协商与女巫决策逐步纳入统一图协议
- 给怀疑链增加“关系类型”而不只是 target list
- 区分公共怀疑链与阵营/身份私有解读
- 增加后台可视化调试能力：按玩家查看 day summary / suspicion / trace

## 9.3 低优先级

- PostgreSQL 真正落库实现
- Redis TTL 与归档策略
- 记忆版本迁移策略
- 更细粒度的 prompt/graph 质量指标

## 10. 结论

当前系统已经完成了“从一次性 prompt 决策”向“结构化决策链 + 记忆层”的第一阶段迁移：

- 统一决策图已落地
- Redis 记忆层已落地
- DaySummary 已落地
- 发言、投票、夜晚单人行为都已接入新框架

但它还不是最终形态。更准确地说，当前系统处于：

**“架构骨架已经成立，基础 plumbing 已打通，但真正高质量的节点级推理与记忆演化还没有完成”的阶段。**

如果下一阶段继续推进，最值得优先做的是：

1. 强化怀疑链更新逻辑  
2. 强化 DaySummary 质量  
3. 补齐 vote/night 的 trace  
4. 逐步统一 werewolf/witch 的专用图接口
