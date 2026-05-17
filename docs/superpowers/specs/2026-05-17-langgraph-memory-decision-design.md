# AI Werewolf 玩家决策链与记忆系统优化设计

> 生成日期：2026-05-17  
> 参考文档：飞书《AI Werewolf 系统现状报告》  
> 设计范围：基于 LangGraph + LangChain 优化玩家决策链，并重构记忆系统  
> 执行约束：本文档仅描述设计方案，不包含代码修改

---

## 1. 背景与现状

当前系统已经具备完整的狼人杀游戏流程、LLM 玩家决策、ProviderChain 降级链、狼人/女巫 LangGraph 基础图、板子角色约束和发言进度约束。

但玩家决策质量仍受上下文组织方式限制。当前主链路仍是从公开事件构造 `game_context`，再拼入 prompt，由 `PlayerDecider` 一次性输出发言、行动、目标、理由和记忆更新。

关键代码现状：

- `ai_werewolf/engine/context.py` 的 `build_game_context()` 从 `public_events` 构造上下文，只保留最近 20 条公开事件。
- `ai_werewolf/llm/action_scheduler.py` 在白天发言、投票、夜晚行动时仍以完整 prompt 字符串作为 AI 决策输入。
- `ai_werewolf/llm/player_decider.py` 负责一次调用、解析、校验和兜底。
- `ai_werewolf/llm/graphs/werewolf_council.py` 已有狼人协商图，但反驳节点 `n3_rebut` 仍是占位逻辑。
- `private_memory_update` 已存在于 LLM 输出 schema 中，但还没有沉淀为可检索、可摘要、可跨轮使用的记忆层。

---

## 2. 当前问题

### 2.1 分析与发言混在一起

现有 prompt 让模型同时完成以下任务：

1. 理解局势。
2. 判断玩家身份。
3. 更新自己的记忆。
4. 选择策略。
5. 决定行动。
6. 生成发言。

这些任务全放在一次 LLM 调用里，容易导致模型直接把粗糙推理变成公开发言，出现立场弱、逻辑跳、攻击无依据、发言像模板的问题。

### 2.2 上下文膨胀与 lost in middle

当前设计虽然只截取最近 20 条公开事件，但随着对局推进，仍存在两个问题：

- 早期关键事件容易被截断，例如第 1 天起跳、投票关系、强冲突关系。
- 中段事件即使保留，也只是原始事件串，缺少结构化重点，模型容易忽略中间事实。

### 2.3 记忆没有稳定沉淀

`private_memory_update` 只是模型输出字段，没有形成稳定的记忆对象。下一轮 prompt 并不会可靠读取“我上一轮为什么怀疑 5 号”“3 号和 5 号为什么共边”“7 号为什么被标记划水”。

### 2.4 玩家怀疑链不可解释

AI 玩家的怀疑对象、信任对象、共边关系、冲突关系没有显式维护，导致后续发言缺少连续性。

---

## 3. 优化目标

本次优化目标分为两类。

### 3.1 决策链目标

用 LangGraph + LangChain 将玩家决策拆成多级节点：

```text
分析局势
  ↓
更新怀疑链
  ↓
决定策略
  ↓
决定行为
  ↓
生成发言
```

核心要求：

- 分析和发言必须拆开。
- 每个节点只负责一个明确任务。
- 前置节点输出结构化结果，后置节点只读取必要结论。
- 最终公开发言不得包含私有推理痕迹、系统信息或未发生事实。

### 3.2 记忆系统目标

每天结束后生成对局摘要，不再把上一局或整局所有对话全部塞给模型。

摘要示例：

```text
第2天总结：
- 5号持续攻击1号，理由集中在1号站边摇摆。
- 3号与5号形成共边，多次互相补充逻辑。
- 7号发言偏划水，未给出明确投票理由。
```

后续 prompt 只注入：

- 当前阶段必要信息。
- 最近短期事件。
- 每日摘要。
- 玩家怀疑链。
- 私有角色记忆。
- Agent 人设与发言风格。

---

## 4. 总体架构

新增通用玩家决策图：`PlayerDecisionGraph`。

该图服务于白天发言、投票、夜晚普通行动、遗言等场景。狼人协商图和女巫图可以保留，但应复用新的记忆上下文和结构化分析能力。

### 4.1 改造前链路

```text
public_events
  ↓
build_game_context()
  ↓
build_*_prompt()
  ↓
PlayerDecider.decide()
  ↓
PlayerDecision
```

### 4.2 改造后链路

```text
public_events + memory_store + private_infos
  ↓
MemoryContextBuilder
  ↓
PlayerDecisionGraph
  ├─ n1_analyze_situation
  ├─ n2_update_suspicion
  ├─ n3_decide_strategy
  ├─ n4_decide_action
  ├─ n5_generate_speech
  └─ n6_validate_and_repair
  ↓
PlayerDecision
  ↓
MemoryWriteBack
```

---

## 5. 玩家决策图设计

### 5.1 节点一：分析局势

节点名：`n1_analyze_situation`

职责：

- 读取当前阶段、存活玩家、死亡玩家、短期事件、每日摘要和私有信息。
- 分析当前焦点位、身份声明、冲突关系、共边关系、投票压力。
- 不生成公开发言。

输入：

- `game_id`
- `player_id`
- `role_key`
- `phase`
- `alive_players`
- `dead_players`
- `recent_events`
- `day_summaries`
- `private_role_memory`
- `board_roles`

输出结构：

```json
{
  "focus_players": ["p5", "p1"],
  "claimed_roles": [{"player_id": "p3", "role": "seer", "confidence": 0.7}],
  "conflicts": [{"a": "p1", "b": "p5", "reason": "连续互打"}],
  "alliances": [{"players": ["p3", "p5"], "reason": "互相补充逻辑"}],
  "low_signal_players": ["p7"],
  "key_facts": ["5号持续攻击1号", "7号没有明确投票理由"],
  "uncertainties": ["3号是否真预言家仍未验证"]
}
```

### 5.2 节点二：更新怀疑链

节点名：`n2_update_suspicion`

职责：

- 基于局势分析和旧怀疑链，更新当前玩家视角下的怀疑记录。
- 区分“公开事实”和“当前玩家的主观判断”。
- 每个 AI 玩家独立维护，不共享主观怀疑链。

输出结构：

```json
{
  "updates": [
    {
      "player_id": "p5",
      "suspicion_score": 72,
      "trust_score": 28,
      "evidence": ["持续攻击1号", "与3号互相补强"],
      "trend": "up",
      "reason": "攻击线明确但解释空间不足"
    }
  ],
  "global_notes": ["3号和5号共边关系需要继续观察"]
}
```

分数约束：

- `suspicion_score`：0 到 100，越高越像狼人。
- `trust_score`：0 到 100，越高越像好人。
- 同一玩家两项分数不要求严格相加为 100，因为信息可以不足。

### 5.3 节点三：决定策略

节点名：`n3_decide_strategy`

职责：

- 根据角色、阵营目标、人设、怀疑链和当前压力决定本轮策略。
- 只输出打法，不输出具体发言文本。

策略枚举建议：

- `attack`：进攻某个目标。
- `defend`：防守自己或保护他人。
- `build_alliance`：拉共识或站边。
- `observe`：低调观察。
- `claim_role`：起跳身份。
- `fake_claim`：狼人悍跳。
- `counter_claim`：对跳。
- `vote_push`：推动投票。
- `distance_teammate`：狼人倒钩或切割队友。

输出结构：

```json
{
  "stance": "怀疑5号，暂时信任1号",
  "goal": "推动大家重新审视5号的攻击动机",
  "strategy_type": "attack",
  "primary_target": "p5",
  "secondary_targets": ["p3"],
  "tone": "克制但明确",
  "risk_level": 3,
  "should_claim_role": false,
  "must_not_reveal": ["狼队友", "查验私有结果"]
}
```

### 5.4 节点四：决定行为

节点名：`n4_decide_action`

职责：

- 将策略转成合法行动。
- 白天发言阶段通常输出 `action_type=speak`。
- 投票阶段输出 `vote` 和 `target_id`。
- 夜晚阶段输出对应技能行动。

输出结构：

```json
{
  "action_type": "vote",
  "target_id": "p5",
  "public_reason": "5号连续攻击1号但没有解释清楚自己的身份视角",
  "private_memory_update": "继续重点观察3号和5号是否共边"
}
```

合法性要求：

- `target_id` 必须在当前阶段合法目标列表中。
- 不能投自己。
- 已死亡玩家不能成为常规投票目标。
- 夜晚技能必须符合当前角色能力。

### 5.5 节点五：生成发言

节点名：`n5_generate_speech`

职责：

- 根据前面节点的结构化结论生成自然语言发言。
- 不重新读取全量历史，不重新做局势推理。
- 只允许使用公开可见事实和当前玩家允许表达的信息。

输入重点：

- `strategy`
- `decision_draft`
- `public_key_facts`
- `agent.persona`
- `agent.speech_style`
- `speech_progress`

发言要求：

- 有明确立场。
- 有事实依据。
- 保持人设语气。
- 不引用未发言玩家的具体观点。
- 不提及板子不存在的角色。
- 不泄露私有信息。

示例输出：

```text
我这轮会重点看5号。5号一直在打1号，但他的理由基本停留在“站边摇摆”，没有把1号的狼坑逻辑补完整。反而3号一直在帮5号补话，这两个人的关系我觉得要一起盘。7号今天信息量偏低，我暂时不会优先出7号，但不能完全放掉。
```

### 5.6 节点六：校验与修复

节点名：`n6_validate_and_repair`

职责：

- 校验最终 `PlayerDecision` 是否满足规则。
- 对轻微违规做局部修复。
- 对严重违规触发降级或规则兜底。

校验项：

- JSON schema 合法。
- `action_type` 合法。
- `target_id` 合法。
- 发言非空，且长度在限制内。
- 不泄露私有信息。
- 不出现 AI、prompt、系统、模型等出戏词。
- 不讨论当前板子不存在的角色。
- 不引用未发言玩家的具体观点。
- 角色声明保持一致。

---

## 6. 记忆系统设计

### 6.1 记忆分层

新增四层记忆。

| 记忆层 | 可见性 | 用途 | 是否直接进 prompt |
| --- | --- | --- | --- |
| `RawEventLog` | 系统 | 完整回放、审计、重新摘要 | 否 |
| `DaySummary` | 公开 | 每天结束后的公开局势摘要 | 是 |
| `PlayerSuspicionMemory` | 单个 AI 私有 | 玩家主观怀疑链 | 是 |
| `PrivateRoleMemory` | 单个玩家私有 | 狼队友、查验、药品等角色信息 | 是 |

### 6.2 RawEventLog

保留完整事件，不再作为默认 prompt 输入。

事件来源：

- 发言事件。
- 投票事件。
- 死亡公布。
- 遗言。
- 身份公开。
- 阶段变化。
- 夜晚公开结果。

用途：

- 对局回放。
- 重新生成摘要。
- 质量评估。
- prompt trace 排查。

### 6.3 DaySummary

每天结束后生成一次公开摘要。

建议结构：

```json
{
  "game_id": "game_001",
  "day": 2,
  "summary_items": [
    "5号持续攻击1号，理由集中在1号站边摇摆",
    "3号与5号形成共边，多次互相补充逻辑",
    "7号发言偏划水，未给出明确投票理由"
  ],
  "claims": [
    {"player_id": "p3", "claim": "seer", "status": "unverified"}
  ],
  "conflicts": [
    {"a": "p1", "b": "p5", "reason": "5号连续攻击1号，1号反打5号逻辑不完整"}
  ],
  "alliances": [
    {"players": ["p3", "p5"], "reason": "3号多次补充5号攻击线"}
  ],
  "vote_summary": {
    "exiled": "p1",
    "main_votes": [{"target": "p1", "voters": ["p3", "p5"]}]
  },
  "low_signal_players": ["p7"]
}
```

生成原则：

- 只总结公开事实。
- 不加入系统知道但玩家不知道的信息。
- 不包含预言家私有查验结果，除非该结果已经被公开发言表达。
- 摘要必须短，优先保留身份声明、冲突、共边、投票、死亡、低信息玩家。

### 6.4 PlayerSuspicionMemory

每个 AI 玩家维护一份私有怀疑链。

建议结构：

```json
{
  "game_id": "game_001",
  "player_id": "ai_2",
  "day": 2,
  "records": [
    {
      "target_player_id": "p5",
      "suspicion_score": 72,
      "trust_score": 28,
      "evidence": ["持续攻击1号", "与3号疑似共边"],
      "relationship_tags": ["aggressive", "possible_pair_with_p3"],
      "last_reason": "攻击线明确但身份视角不足",
      "updated_at_phase": "day_speech"
    }
  ]
}
```

怀疑链更新规则：

- 每次 AI 做发言、投票、夜晚行动后都可以局部更新。
- 每天结束后根据 DaySummary 做一次全量压缩。
- 旧证据超过 2 天未被新事实支撑时降低权重。
- 被公开证伪的信息必须降权或删除。

### 6.5 PrivateRoleMemory

继续沿用现有 `PlayerPrivateInfo`，但在 prompt 中应结构化展示。

示例：

```text
【你的预言家查验记录】
- 第1晚：你查验6号，结果为【狼人】
- 第2晚：你查验2号，结果为【好人】
- 未查验：1号、3号、4号、5号、7号、8号
```

```text
【你的狼队友】
- 2号 林野（存活）
- 5号 陈默（已出局）
- 当前存活狼队友：2号
```

---

## 7. 每日摘要生成流程

### 7.1 触发时机

推荐在白天结束后、进入下一夜之前生成摘要。

当前可接入位置：

- `PhaseOrchestrator._check_win_or_next_night()`
- 或抽象为 `DayCloseService.close_day(session)`

流程：

```text
白天投票结束
  ↓
遗言与技能结算完成
  ↓
胜负判断
  ↓
若游戏未结束：
    生成 DaySummary
    更新每个 AI 的 PlayerSuspicionMemory
    写入 MemoryStore
    清理当天可压缩事件
    进入下一夜
```

### 7.2 摘要输入范围

每次摘要只读取当天公开信息：

- 当天死亡公布。
- 当天公开发言。
- 当天投票行为。
- 当天遗言。
- 当天公开身份揭示。
- 当天公开技能结果。

不读取：

- 狼队夜聊私有内容。
- 预言家未公开查验结果。
- 女巫药品状态。
- 守卫守护目标。
- 系统真实身份表。

### 7.3 摘要质量约束

摘要必须满足：

- 每天 5 到 10 条要点。
- 每条要点不超过 40 个中文字符。
- 优先描述关系和变化，而不是复述原话。
- 保留玩家编号。
- 不使用“可能吧”“感觉上”等空泛表达。

---

## 8. Prompt 输入重组

### 8.1 新的 MemoryContext

新增统一上下文对象：

```json
{
  "current_state": {
    "phase": "day_speech",
    "day": 3,
    "alive_players": [],
    "dead_players": []
  },
  "recent_events": [],
  "day_summaries": [],
  "suspicion_memory": {},
  "private_role_memory": {},
  "board_context": {},
  "speech_progress": {}
}
```

### 8.2 Prompt 中保留的信息

每次决策只注入：

- 当前阶段。
- 当前玩家身份和人设。
- 当前合法行动。
- 当前存活/死亡玩家。
- 本局板子角色清单。
- 最近短期事件，建议 5 到 8 条。
- 历史每日摘要。
- 当前玩家自己的怀疑链。
- 当前玩家自己的私有角色记忆。

### 8.3 Prompt 中移除的信息

默认不再注入：

- 整局逐字发言历史。
- 已被摘要覆盖的早期事件。
- 与当前玩家无关的私有信息。
- 系统真实身份表。
- 中段未压缩的长历史。

---

## 9. 与现有模块的关系

### 9.1 PlayerDecider

`PlayerDecider` 保持为底层 LLM 调用、解析、降级和安全过滤入口。

新增图节点内部仍可以调用 `PlayerDecider`，但每个节点应使用更窄的 prompt 和结构化 schema。

### 9.2 AIActionScheduler

`AIActionScheduler` 从“构造完整 prompt”调整为“构造 AIActionRequest + MemoryContext”。

短期兼容方式：

- 保留现有 prompt 构造方法。
- 白天发言优先走 `PlayerDecisionGraph`。
- 图失败时 fallback 到现有 `build_speech_prompt()`。

### 9.3 WerewolfCouncilGraph

现有狼人协商图继续保留，但需要增强：

- `n3_rebut` 从 no-op 改为真实反驳节点。
- 狼人提案读取 `DaySummary` 和狼队私有记忆。
- 投票结果写入狼队局部记忆。
- 图最终输出写入 `PlayerDecisionGraph` 可读的行动结果。

### 9.4 WitchCouncilGraph

女巫图继续保留，但应读取新的记忆上下文：

- 被刀玩家的公开身份价值。
- 当天谁最像神职。
- 谁是高狼面。
- 是否值得救。
- 是否值得毒。

---

## 10. 数据模型建议

### 10.1 DaySummary

```python
class DaySummary(BaseModel):
    game_id: str
    day: int
    summary_items: list[str]
    claims: list[RoleClaim]
    conflicts: list[PlayerConflict]
    alliances: list[PlayerAlliance]
    vote_summary: VoteSummary | None
    low_signal_players: list[str]
```

### 10.2 PlayerSuspicionRecord

```python
class PlayerSuspicionRecord(BaseModel):
    target_player_id: str
    suspicion_score: int
    trust_score: int
    evidence: list[str]
    relationship_tags: list[str]
    last_reason: str
    last_updated_day: int
    last_updated_phase: str
```

### 10.3 PlayerDecisionGraphState

```python
class PlayerDecisionGraphState(TypedDict, total=False):
    game_id: str
    player_id: str
    role_key: str
    phase: str
    memory_context: dict
    situation_analysis: dict
    suspicion_update: dict
    strategy: dict
    action_draft: dict
    speech: str
    decision: dict
    error: str | None
```

---

## 11. 迭代计划

### M1：记忆上下文基础设施

目标：

- 新增 `MemoryContextBuilder`。
- 新增 `DaySummary` 数据结构。
- 新增 `PlayerSuspicionMemory` 数据结构。
- 将 `build_game_context()` 的纯字符串输出升级为可组合上下文。

验收：

- 第 3 天以后，prompt 不再包含第 1 天完整逐字发言。
- `DaySummary` 能准确列出冲突、共边、低信息玩家和投票结果。

### M2：白天发言接入决策图

目标：

- 新增 `PlayerDecisionGraph`。
- 白天发言走五段式链路。
- 分析和发言彻底拆开。

验收：

- trace 中能看到局势分析、怀疑链、策略、行为、发言。
- 公开发言不包含分析节点的内部字段。
- 发言至少包含明确立场、事实依据、目标中的两项。

### M3：投票和夜晚行动读取怀疑链

目标：

- 投票阶段读取 `PlayerSuspicionMemory`。
- 预言家查验、狼人刀人、女巫用药读取摘要和怀疑链。
- 降低随机投票、随机刀人比例。

验收：

- AI 投票理由能引用当天摘要或怀疑链证据。
- 狼人刀人优先考虑强逻辑好人、疑似神职或局势关键位。

### M4：补全狼人协商反驳节点

目标：

- 将 `n3_rebut` 从占位改为真实 LLM 反驳。
- 狼队每个成员能评价其他提案风险。
- 决议节点综合票数、风险和角色价值。

验收：

- 3 狼场景下，狼人能给出不同提案并通过反驳收敛。
- 平票时按低风险和高收益目标决策。

### M5：质量评估与可观测性

目标：

- 增加决策 trace。
- 增加 prompt token 统计。
- 增加发言质量评估脚本。

验收：

- 可查看每个 AI 为什么说这句话、为什么投这个人。
- 单次 prompt token 数随对局天数增长趋于稳定。
- 100 场模拟中，不出现引用未发言玩家观点的违规发言。

---

## 12. 验收标准

整体完成后应满足：

1. 第 3 天以后，单次 prompt 不再包含第 1 天完整逐字发言，只包含摘要。
2. 白天发言链路中，分析节点输出不出现在玩家公开发言中。
3. 同一 AI 的立场具有连续性，例如前一天怀疑 5 号，第二天会解释是否继续怀疑。
4. 100 场模拟中，不出现引用未发言玩家具体观点的违规发言。
5. 决策 trace 能看到局势分析、怀疑链变化、策略、行为、最终发言。
6. 玩家发言平均信息密度提升，至少包含明确站边、理由、目标三者中的两项。
7. 长对局中 prompt token 数不会线性增长。
8. 私有信息隔离不被破坏，预言家查验、狼队友、女巫药品等只进入对应玩家私有上下文。

---

## 13. 风险与缓解

### 13.1 多节点调用导致延迟上升

缓解：

- 白天发言先使用完整链路。
- 投票和夜晚行动可跳过发言节点。
- 低风险节点使用 cheap model。
- 图设置整体超时，超时后 fallback 到现有单 prompt 链路。

### 13.2 摘要错误污染后续判断

缓解：

- 摘要只写公开事实，不写强推断。
- 保留 RawEventLog，可重新摘要。
- 摘要 schema 中区分 `fact`、`inference` 和 `uncertainty`。

### 13.3 玩家发言变得过度理性

缓解：

- `n5_generate_speech` 单独注入 Agent 人设、语气、攻击性、风险偏好。
- 策略节点输出 tone 和 stance，发言节点只做风格化表达。

### 13.4 记忆过度固化导致 AI 不会改观点

缓解：

- 怀疑链加入 `trend` 和 `confidence`。
- 新证据可以覆盖旧证据。
- 每天摘要后做一次衰减，过期证据降低权重。

---

## 14. 推荐落地顺序

建议按以下顺序执行：

1. 先做 `DaySummary` 和 `MemoryContextBuilder`，解决上下文膨胀。
2. 再做白天发言 `PlayerDecisionGraph`，解决分析和发言混杂。
3. 然后让投票和夜晚行动读取怀疑链，提升行为合理性。
4. 最后补全狼人协商图和质量评估。

这条路径风险较低，因为前两步可以保留现有 `PlayerDecider` 和 prompt 链路作为 fallback。
