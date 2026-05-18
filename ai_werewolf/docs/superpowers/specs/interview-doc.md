# AI 狼人杀面试技术深度解析

> 基于 LangChain/LangGraph 的 Multi-Agent AI 对战平台 — 面试问答手册

---

# 一、Multi-Agent 编排引擎

## 1.1 什么是"回合引擎"

游戏回合引擎（`GameOrchestrator`）是整个系统的核心调度器，它不直接调用 LLM，而是负责：

- **回合状态机**：维护 `SETUP → NIGHT → DAY_ANNOUNCEMENT → DAY_SPEECH → EXILE_VOTE → LAST_WORDS → GAME_OVER` 7 个阶段的流转
- **角色顺序调度**：按狼人→预言家→守卫→女巫的顺序执行夜晚行动（顺序固定不可更改，因女巫需要知道狼人击杀目标）
- **人类与 AI 的混合调度**：人类玩家的动作通过 Socket.IO 传入，引擎判断当前轮次是调用 LLM 还是等待人类输入

### 关键代码设计（orchestrator.py:89-127）

```python
def advance(self, session, action):
    """根据当前阶段和动作推进游戏"""
    state = session.state
    action_type = action["action_type"]
    self._validate_actor_action(session, action)  # 合法性校验

    if state.phase == SETUP and action_type == "start_game":
        self._start_game(session)           # 初始化夜晚
    elif state.phase == NIGHT:
        self._resolve_night(session, action) # 调用 NightResolver
    elif state.phase == DAY_SPEECH:
        self._enter_vote(session, action)    # 进入投票
    elif state.phase == EXILE_VOTE:
        self._resolve_vote(session, action)  # 计票、放逐
```

## 1.2 AIActionScheduler — 动态任务调度

`AIActionScheduler` 按游戏阶段动态决定"哪些 AI 玩家需要行动"：

| 阶段 | 调度的 Agent | 决策类型 |
|------|------------|---------|
| NIGHT | 所有存活且拥有夜晚行动的 AI（狼人/预言家/女巫/守卫/猎人） | `night_action` |
| DAY_SPEECH | 所有存活的 AI 玩家 | `day_speech` |
| EXILE_VOTE | 所有存活的 AI 玩家（不能投自己） | `exile_vote` |
| LAST_WORDS | 被淘汰的非人类玩家 | `last_words` |

```python
def schedule(self, state, agents, private_infos, game_context):
    if state.phase == NIGHT:
        return [self._build_request(...) for player in alive_ai_players
                if has_night_action(player.role_key)]
    elif state.phase == DAY_SPEECH:
        return [self._build_request(...) for player in alive_ai_players]
    elif state.phase == EXILE_VOTE:
        return [self._build_request(...) for player in alive_ai_players]
    ...
```

## 1.3 引擎层的核心职责

引擎层不直接调用 LLM，而是：

1. **调度**：通过 `AIActionScheduler` 生成任务列表
2. **委托**：将每个任务交给对应角色的 `Provider` + `PlayerDecider` 执行
3. **聚合**：收集所有 AI 决策，按游戏规则排序/冲突解决
4. **校验**：动作合法性（目标是否存活、是否允许该动作等）
5. **应用**：将合法决策写入游戏状态（扣血、标记死亡、更新私有信息）
6. **广播**：生成 public_event，通过 SSE 推送到前端

---

# 二、LangGraph 6 节点决策管道

## 2.1 为什么需要决策管道

直接让 LLM 返回 JSON 的问题：
- LLM 容易产生幻觉（胡编信息）
- 缺少中间推理，决策质量不稳定
- 错误扩散：一个字段错导致整体不可用

解决思路：将"决策"拆分为 6 个独立步骤，每步做一件具体的事。

## 2.2 六阶段详解

```
START
  │
  ▼
┌────────────────────────────────────────────────┐
│  N1: analyze_situation (分析局势)               │
│  LLM 分析当前局面：关键事实、矛盾点、关系边       │
│  输入：memory_context（记忆上下文）              │
│  输出：key_facts[], contradictions[], edges[]   │
│  容错：LLM 失败 → 回退到规则引擎（硬编码分析）    │
└──────────────┬─────────────────────────────────┘
               ▼
┌────────────────────────────────────────────────┐
│  N2: update_suspicion (更新怀疑链)              │
│  LLM 基于局势分析更新对每个玩家的怀疑度          │
│  输出：primary_target, records[{pid, score, reason}]│
│  容错：LLM 失败 → 保留上一轮怀疑链不变          │
└──────────────┬─────────────────────────────────┘
               ▼
┌────────────────────────────────────────────────┐
│  N3: decide_strategy (决策策略)                │
│  LLM 决定本回合的行动策略（攻击型/防御型/混淆型）  │
│  输出：strategy_type, primary_target, 发言基调   │
│  容错：LLM 失败 → 默认保守策略                  │
└──────────────┬─────────────────────────────────┘
               ▼
┌────────────────────────────────────────────────┐
│  N4: decide_action (决定行动)                  │
│  纯规则节点，不调用 LLM                         │
│  将策略映射为具体 action_type + target_id        │
│  例：strategy=attack → action=wolf_kill, target=最怀疑的人│
│  容错：无 LLM 调用，不会失败                    │
└──────────────┬─────────────────────────────────┘
               ▼
┌────────────────────────────────────────────────┐
│  N5: generate_decision (调用 LLM 生成行为)       │
│  调用 LLM 生成最终决策：speech + action_type + target│
│  使用锁定的 action_draft（确保 N4 结果不被覆盖）  │
│  示例 Prompt 结构：System（角色约束）+ User（游戏状态）│
└──────────────┬─────────────────────────────────┘
               ▼
┌────────────────────────────────────────────────┐
│  N6: validate_and_repair (LLM 生成校验)         │
│  校验产出的合法性：speech 非空、action_type 合法、│
│  目标存在于存活列表中                            │
│  修复策略：replace（替换非法 speech）、           │
│  override_action（修正非法 action）             │
└──────────────┬─────────────────────────────────┘
               ▼
              END
```

## 2.3 节点级错误隔离

每个节点都有独立的 try/except，节点失败不影响后续：

```python
def _make_analyze_situation_node(semantic_decider, enabled_nodes):
    if "n1" not in enabled_nodes:
        return lambda state: {}  # 跳过，不做语义分析

    def node(state):
        try:
            prompt = build_situation_analysis_prompt(state)
            raw = semantic_decider.decide_raw(prompt)
            analysis = SituationAnalysis.model_validate(raw)
            _log_analysis_node(state, "llm", analysis.model_dump())
            return {"situation_analysis": analysis.model_dump()}
        except Exception as exc:
            logger.warning("N1 节点失败，使用 fallback: %s", exc)
            return _with_semantic_metadata(
                state=state,
                payload={"situation_analysis": _fallback_analysis()},
                node_name="n1",
                source="fallback",
                error=str(exc)[:200],
            )
    return node
```

## 2.4 与前几代方案的对比

前代设计（已被 LangGraph 替代）：
- 旧方案：单一 prompt → LLM 返回全部决策 JSON → 校验/fallback
- 问题 1：LLM 输出不稳定，单次调用成功率约 80%（15-20% 需重试或 fallback）
- 问题 2：缺乏中间推理，决策质量不可控

用 LangGraph 6 节点优化后：
- 拆分推理与生成，单一节点失败不影响整体链路
- 职责明确：N1/N2 推理、N3 策略、N4 规则映射、N5 生成、N6 校验
- 中间状态可视化，便于调试和评估

---

# 三、结构化记忆系统

## 3.1 四种记忆类型

| 类型 | 可见性 | 持久化 | 用途 |
|------|--------|--------|------|
| DaySummary | GLOBAL（所有玩家可见） | Redis | 每日摘要：谁发言了什么、谁被投票出局、谁死亡 |
| PlayerSuspicionMemory | PLAYER（仅玩家自己） | Redis | 玩家对每个其他玩家的怀疑度评分 |
| PrivateRoleMemory | ROLE_PRIVATE（仅同角色） | Redis | 预言家的查验结果、女巫的药水状态等私密信息 |
| DecisionTrace | TRACE（仅用于审计） | Redis | 每次 LLM 调用的 prompt、response、诊断信息 |

## 3.2 RedisMemoryEnvelope — 统一序列化

所有记忆通过 `RedisMemoryEnvelope` 统一包装后存入 Redis：

```python
class RedisMemoryEnvelope(BaseModel):
    schema_version: int = 1          # 版本号，支持向后兼容
    game_id: str                     # 游戏ID
    visibility: MemoryVisibility     # 可见性控制
    owner_id: str | None             # 所属玩家
    payload_type: Literal["day_summary", "player_suspicion",
                          "private_role_memory", "decision_trace"]
    payload: dict[str, Any]          # 实际数据
    created_at: datetime
    updated_at: datetime
```

Redis Key 设计：
```
aiw:memory:{game_id}:day_index          (LIST)  每天索引
aiw:memory:{game_id}:day:{n}            (STRING) 单日摘要
aiw:memory:{game_id}:suspicion:{pid}    (STRING) 玩家怀疑链
aiw:memory:{game_id}:role_private:{pid} (STRING) 私有记忆
```

## 3.3 双源聚合 — MemoryContextBuilder

每个 Agent 做决策前，`MemoryContextBuilder` 从两个来源组装记忆：

```
┌─────────────────────────────────────────────┐
│            MemoryContextBuilder               │
│                                               │
│  ┌──────────────┐      ┌──────────────┐      │
│  │  Redis 持久层  │      │ Session 内存层  │    │
│  │              │      │              │      │
│  │ • 历史日摘要   │      │ • 当前回合事件  │      │
│  │ • 怀疑链      │      │ • 发言记录     │      │
│  │ • 角色记忆    │      │ • 死亡信息     │      │
│  │ • 决策审计    │      │ • 私有状态     │      │
│  └──────┬───────┘      └──────┬───────┘      │
│         │                     │               │
│         └──────────┬──────────┘               │
│                    ▼                          │
│           MemoryContext                       │
│  ┌─────────────────────────────────────┐     │
│  │ • recent_events (最近8个事件)          │     │
│  │ • day_summaries (所有历史日摘要)       │     │
│  │ • suspicion_memory (怀疑链)           │     │
│  │ • private_role_memory (私有记忆)      │     │
│  └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
```

### 为什么需要双源

- **Redis（持久层）**：跨请求/跨进程保持，即使服务重启也不丢失
- **Session（内存层）**：实时的、当回合发生的事件（如"刚才有人发言了"），不需要立即持久化

例如：女巫在 NIGHT 阶段需要知道"昨晚谁死了"（Redis 中的 DaySummary）、"我还有几瓶药"（Session 中的 private_infos）。

## 3.4 跨回合情境连贯性

没有记忆系统时的问题：
- 第 2 晚，狼人可能忘记第 1 天谁被投票出局
- 预言家可能不记得自己昨天查验了谁
- LLM 的 short-term memory 有限，长对局容易"失忆"

有了记忆系统后：
- Agent 每次决策前自动加载所有历史日摘要
- 自动恢复该玩家之前建立的怀疑链
- 自动注入私有角色信息（查验结果、药水消耗等）
- 发言自然连贯："昨天我查验了 X，他是好人，所以我今天觉得 Y 很可疑"

---

# 四、多狼人共识机制（Werewolf Council）

## 4.1 为什么需要共识

基础版狼人杀中，只有一个狼人做击杀决策。但本项目中一个游戏有 3-4 个狼人，如果每个狼人都独立选择击杀目标，可能出现：
- 狼人 A 想杀玩家 X，狼人 B 想杀玩家 Y
- 最终谁说了算？取第一个？随机？这不符合逻辑

解决方案：狼群议事（Werewolf Council）— 多狼人通过提议+投票达成共识。

## 4.2 5 节点议事图

```
START
  │
  ▼
┌────────────────────────────────────┐
│  N1: brief (格式化候选名单)        │
│  纯格式化节点，不调 LLM             │
│  输出：candidates[], game_context   │
└──────────────┬─────────────────────┘
               ▼
       ┌───────┴───────┐
       │ fan-out (Send) │  ← 每个狼人收到一个独立副本
       └───────┬───────┘
       ┌───────┼───────┬───────┐
       ▼       ▼       ▼       ▼
    [狼人A]  [狼人B]  [狼人C]  [狼人D]
    propose  propose  propose  propose
     LLM      LLM      LLM      LLM
   提议目标   提议目标   提议目标   提议目标
   + 理由    + 理由    + 理由    + 理由
   + 风险评估  + 风险评估  + 风险评估  + 风险评估
       │       │       │       │
       └───────┼───────┴───────┘
               ▼
┌────────────────────────────────────┐
│  N3: rebut (辩驳)                  │
│  每个狼人看到所有提议，可选质疑     │
└──────────────┬─────────────────────┘
               ▼
       ┌───────┴───────┐
       │ fan-out (Send) │  ← 再次并行
       └───────┬───────┘
       ┌───────┼───────┬───────┐
       ▼       ▼       ▼       ▼
    [狼人A]  [狼人B]  [狼人C]  [狼人D]
     vote     vote     vote     vote
     投票     投票     投票     投票
       │       │       │       │
       └───────┼───────┴───────┘
               ▼
┌────────────────────────────────────┐
│  N5: resolve (决议)                │
│  统计票数，多数获胜                 │
│  平票按 risk_score 最低破平        │
│  最多 2 轮，超时回退到首候选        │
└──────────────┬─────────────────────┘
               ▼
              END
```

## 4.3 关键设计点

### Fan-out 并行提议
使用 LangGraph 的 `Send` 机制，将每个狼人路由到独立的 `wolf_propose` 节点并行执行：

```python
def n2_route_to_proposals(state):
    return [Send("wolf_propose", {"wolf_id": wid, **state})
            for wid in state["participants"]]
```

### 投票决议
```python
def n5_resolve(state):
    tally = Counter(v["target_id"] for v in votes)
    winner = tally.most_common(1)[0][0]  # 多数获胜
    if tied:  # 平票 → 选风险最低的
        winner = min(tied_candidates, key=risk_score)
    return {"decision": winner, "rationale": f"投票结果: {tally}"}
```

### 超时与回退
整个议事过程有 45 秒超时，超时或异常时回退到首个候选目标（`candidates[0]`）：

```python
try:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(graph.invoke, initial)
        result = future.result(timeout=45.0)
    return result
except TimeoutError:
    return fallback_target(candidates)  # 回退
```

---

# 五、实时游戏引擎

## 5.1 技术栈

```
┌─────────────────────────────────────────────────┐
│                  前端 (React)                     │
│  Socket.IO Client  ←→ SSE Stream                 │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────┐
│              FastAPI Application                  │
│                                                   │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ CORS 中间件   │  │ socketio.AsyncServer (sio)│  │
│  └─────────────┘  └──────────────────────────┘  │
│                                                   │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │  REST API    │  │  Socket.IO Events          │  │
│  │  /api/...   │  │  game_action, join, ...    │  │
│  └─────────────┘  └──────────────────────────┘  │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │           GameOrchestrator                    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │ │
│  │  │NightResolver│VoteResolver│HunterResolver│  │ │
│  │  └──────────┘ └──────────┘ └──────────┘    │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  LLM     │ │  Redis   │ │  Memory  │         │
│  │ Providers │ │  Store   │ │  Store   │         │
│  └──────────┘ └──────────┘ └──────────┘         │
└─────────────────────────────────────────────────┘
```

## 5.2 SSE 事件广播

每个游戏阶段完成后，引擎生成 `public_event` 并推送：

```python
def _append_event_dict(self, session, public_event):
    payload = public_event.get("payload", {})
    session.append_public_event(
        public_event.get("event_type", "game_event"),
        payload.get("message", ""),
        actor_id=payload.get("actor_id"),
        target_id=payload.get("target_id"),
    )
    time.sleep(0.5)  # 控制事件间隔，前端逐步展示
```

事件类型：`phase_changed`、`night_step_started`、`night_step_finished`、`night_result`、`current_speaker_changed`、`vote_result`、`game_end`、`role_reveal`

## 5.3 AI 流式发言

AI 发言通过 `stream_speech` 流式输出，前端实时打字机效果：

```python
def stream_speech(self, prompt):
    llm = self._get_llm_client()  # 复用客户端
    messages = [SystemMessage(...), HumanMessage(prompt)]
    for chunk in llm.stream(messages):
        content = chunk.content
        if content:
            yield content  # 实时推送到 SSE
```

## 5.4 人类玩家干预

人类玩家通过 Socket.IO 发送动作（`game_action` 事件），engine 处理流程与 AI 一致，只是跳过 LLM 调用：

```python
@sio.on("game_action")
async def handle_game_action(sid, data):
    session = get_session(sid)
    action = {"actor_player_id": human_player_id, "action_type": ..., ...}
    orchestrator.advance(session, action)
    # 引擎自动推状态变更
```

---

# 六、架构全景图

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (React)                              │
│  Socket.IO Client ◄──► SSE Stream                                │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP + WebSocket
┌───────────────────────────┴──────────────────────────────────────┐
│                      FastAPI Application                          │
│                                                                   │
│  ┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  CORS        │  │  Socket.IO     │  │  API Routes          │  │
│  │  Middleware  │  │  Bridge        │  │  /games, /admin, ... │  │
│  └─────────────┘  └────────────────┘  └──────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Game Engine Layer                         │ │
│  │                                                              │ │
│  │  ┌──────────────────┐  ┌──────────────────────────────┐    │ │
│  │  │ GameOrchestrator  │  │    Phase Resolvers            │    │ │
│  │  │  • 回合状态机      │  │  ┌──────────┐ ┌──────────┐  │    │ │
│  │  │  • 阶段流转       │  │  │ NIGHT     │ │ VOTE      │  │    │ │
│  │  │  • 合法性校验      │  │  └──────────┘ └──────────┘  │    │ │
│  │  └──────────────────┘  │  ┌──────────┐ ┌──────────┐  │    │ │
│  │                          │  │ HUNTER   │ │ LAST      │  │    │ │
│  │  ┌──────────────────┐  │  │ SHOOT    │ │ WORDS     │  │    │ │
│  │  │ AIActionScheduler │  │  └──────────┘ └──────────┘  │    │ │
│  │  │  • 按阶段生成任务   │  └──────────────────────────────┘    │ │
│  │  │  • 角色过滤       │                                        │ │
│  │  └──────────────────┘                                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    AI Decision Layer                         │ │
│  │                                                              │ │
│  │  ┌────────────────────┐  ┌──────────────────────────────┐  │ │
│  │  │ PlayerDecider      │  │  LangGraph Decision Pipeline  │  │ │
│  │  │  • Pydantic 校验    │  │  6 Node StateGraph           │  │ │
│  │  │  • Safety Filter   │  │  N1→N2→N3→N4→N5→N6           │  │ │
│  │  └────────────────────┘  └──────────────────────────────┘  │ │
│  │                                                              │ │
│  │  ┌────────────────────┐  ┌──────────────────────────────┐  │ │
│  │  │ ProviderChain      │  │  Werewolf Council Graph       │  │ │
│  │  │  4-Tier Degradation │  │  Fan-out Propose + Vote       │  │ │
│  │  └────────────────────┘  └──────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  LLM Client Pool   │  │  Redis   │  │  Memory System        │ │
│  │  • ChatOpenAI(复用) │  │  • 会话   │  │  • 4 Types             │ │
│  │  • asyncio.Semaphore│  │  • 记忆   │  │  • Envelope 序列化    │ │
│  └────────────────────┘  └──────────┘  │  • 双源聚合            │ │
│                                          └──────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

# 七、游戏回合链路图

```
人类点击"开始游戏"
        │
        ▼
   ┌─────────┐
   │  SETUP  │
   │ 分配身份 │
   └────┬────┘
        │
   ┌────▼────────────────────────────────────────────────────┐
   │                     NIGHT (夜晚)                          │
   │                                                          │
   │  ① 狼人行动 (Werewolf Council)                            │
   │     → fan-out 提议 → 投票 → 决议击杀目标                    │
   │  ② 预言家查验 (Seer Check)                                 │
   │     → LLM 选择查验目标 → 引擎告知阵营                       │
   │  ③ 守卫守护 (Guard Protect)                                │
   │     → LLM 选择守护目标                                     │
   │  ④ 女巫行动 (Witch Council)                                │
   │     → LLM 决定是否用药、救谁、毒谁                           │
   │  ⑤ 结算死亡                                                │
   │     → 狼刀 + 毒药 - 守护 = 实际死亡                         │
   └────┬────────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────────┐
   │              DAY_ANNOUNCEMENT (天亮)                      │
   │  公布死亡信息 / 平安夜                                     │
   │  如有猎人死亡 → 猎人开枪                                    │
   └────┬────────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────────┐
   │                DAY_SPEECH (白天发言)                       │
   │  顺序发言 (按座位)                                         │
   │  每个 AI → 6 Node LangGraph → 生成发言                     │
   │  人类玩家 → 等待 Socket.IO 输入                            │
   └────┬────────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────────┐
   │               EXILE_VOTE (放逐投票)                        │
   │  所有存活玩家投票                                          │
   │  每个 AI → LLM 决定投票目标                                │
   │  统计结果 → 最高票放逐 → 公布身份                           │
   └────┬────────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────────┐
   │              LAST_WORDS (遗言)                            │
   │  被放逐者发表遗言（AI 调用 LLM，人类等待输入）               │
   └────┬────────────────────────────────────────────────────┘
        │
   ┌────▼────────────────────────────────────────────────────┐
   │              胜负判断                                      │
   │  狼人数量 >= 好人数量 → 狼人胜                               │
   │  狼人全部出局 → 好人胜                                     │
   │  未分胜负 → 回到 NIGHT                                    │
   └──────────────────────────────────────────────────────────┘
```

---

# 八、决策管道数据流图

```
                     MemoryContext
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│  N1: analyze_situation                             │
│  LLM → SituationAnalysis                           │
│  { key_facts, contradictions, relationship_edges }  │
├───────────────────────────────────────────────────┤
│  失败时：回退到规则引擎的 fallback_analysis()       │
└──────────┬────────────────────────────────────────┘
           │ situation_analysis
           ▼
┌───────────────────────────────────────────────────┐
│  N2: update_suspicion                              │
│  LLM → SuspicionUpdate                             │
│  { records[{player_id, score, reason}] }            │
├───────────────────────────────────────────────────┤
│  失败时：保留上一轮 suspicion_memory                │
└──────────┬────────────────────────────────────────┘
           │ suspicion_update
           ▼
┌───────────────────────────────────────────────────┐
│  N3: decide_strategy                               │
│  LLM → PlayerStrategy                              │
│  { strategy_type, primary_target, tone, goal }      │
├───────────────────────────────────────────────────┤
│  失败时：默认保守策略 "defensive_observe"           │
└──────────┬────────────────────────────────────────┘
           │ strategy
           ▼
┌───────────────────────────────────────────────────┐
│  N4: decide_action (纯规则, 无 LLM 调用)            │
│  策略 → action_type, target_id                      │
│  attack → wolf_kill/witch_poison                    │
│  investigate → seer_check                           │
│  accuse → vote                                     │
│  容错：无效映射 → "speak"                           │
└──────────┬────────────────────────────────────────┘
           │ action_draft {action_type, target_id}
           ▼
┌───────────────────────────────────────────────────┐
│  N5: generate_decision (LLM 生成)                   │
│  Prompt = System(角色约束) + User(游戏状态+锁定行动) │
│  LLM → {speech, action_type, target_id, ...}        │
├───────────────────────────────────────────────────┤
│  行动信息来自 action_draft（LLM 不可覆盖）           │
│  失败时：使用 fallback decision                     │
└──────────┬────────────────────────────────────────┘
           │ raw_decision
           ▼
┌───────────────────────────────────────────────────┐
│  N6: validate_and_repair                            │
│  校验：speech 非空、action_type 合法、target 存活    │
│  修复：空 speech → 默认文本                          │
│        非法 action → "speak"                        │
│        非法 target → None                           │
│        不安全 speech → 过滤替换                      │
└──────────┬────────────────────────────────────────┘
           │ final_decision
           ▼
          END
```

---

# 九、LLM 回复评测方案

## 9.1 评测维度矩阵

| 维度 | 指标 | 衡量方式 | 目标值 |
|------|------|---------|--------|
| **格式合规** | JSON 解析成功率 | 自动判定 | ≥ 95% |
| **动作合法性** | action_type 有效 / target_id 合法 | 规则引擎判定 | ≥ 98% |
| **安全过滤** | 不含禁止术语 | 关键词匹配 | 100% |
| **发言质量** | 无角色自曝（如狼人说"我是狼"） | LLM 评审 | ≥ 90% |
| **决策合理性** | 行为与身份一致 | LLM 评审 + 人工抽检 | ≥ 80% |
| **响应延迟** | P50 / P95 延迟 | 监控系统 | P95 ≤ 8s |
| **降级率** | 触发 ProviderChain 降级比例 | 日志统计 | ≤ 10% |

## 9.2 自动化评测 pipeline

```
每一轮游戏
    │
    ▼
┌─────────────────────────────────────────────┐
│  Step 1: 收集所有 LLM 请求/响应              │
│  所有 decision_trace 写入 Redis audit log     │
│  每条记录包含：prompt, response, 诊断信息     │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│  Step 2: 自动化格式与合法性校验               │
│                                              │
│  ① JSON 解析测试                             │
│     → try json.loads(response) 可解析        │
│     → Pydantic model_validate 是否成功        │
│                                              │
│  ② action_type 合法性                        │
│     → 是否在枚举值范围内                      │
│     → 是否与角色身份匹配                       │
│     （狼人不能 seer_check，预言家不能 wolf_kill）│
│                                              │
│  ③ target_id 合法性                          │
│     → 目标玩家是否存在                        │
│     → 目标是否存活                            │
│     → 是否合理（不能投死/查验自己）             │
│                                              │
│  ④ 安全过滤                                  │
│     → 是否包含禁止术语                         │
│     → 是否暴露了系统信息                       │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│  Step 3: LLM-as-Judge 质量评审               │
│                                              │
│  用 GPT-4o 作为评审模型，对上一步通过的        │
│  response 进行质量打分（1-5 分）               │
│                                              │
│  评审维度：                                   │
│  ① 角色一致性：发言是否符合角色身份            │
│     - 狼人应该伪装好人                         │
│     - 预言家应分享查验信息                      │
│     - 女巫应谨慎使用药品                       │
│                                              │
│  ② 逻辑一致性：发言是否有前后矛盾              │
│     - 是否与上一轮自己的发言一致               │
│     - 对同一玩家的判断是否前后一致              │
│                                              │
│  ③ 博弈合理性：决策是否符合游戏逻辑            │
│     - 狼人是否优先击杀预言家                    │
│     - 好人是否积极盘逻辑排狼坑                  │
│                                              │
│  ④ 发言自然度：是否像真人发言                  │
│     - 避免过于机械化的表述                     │
│     - 有质疑、辩护、推理等互动元素              │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│  Step 4: 生成评测报告                         │
│                                              │
│  自动生成每局报告：                            │
│  • 总 LLM 调用次数                            │
│  • JSON 解析成功率                            │
│  • 动作合法率                                 │
│  • 触发降级次数 / 降级层级                     │
│  • 平均响应延迟                               │
│  • LLM 质量评分分布                           │
│  • Top 3 质量问题及示例                       │
└─────────────────────────────────────────────┘
```

## 9.3 LLM-as-Judge Prompt 示例

```markdown
你是一个狼人杀游戏的资深玩家和裁判。

请评审以下 AI 玩家的发言，从四个维度打分（1-5）：

## 玩家信息
- 身份：{role_key}（这是你的真实身份，但需要伪装）
- 当前天数：{day}
- 发言内容：{speech}

## 评审维度

1. **角色一致性**：发言是否符合其真实身份的策略？
   - 狼人应伪装好人、引导错误方向
   - 预言家应分享查验信息、帮助好人推理
   - 1=直接暴露身份，5=完美扮演

2. **逻辑一致性**：发言与之前信息是否一致？
   - 1=前后严重矛盾，5=逻辑严密

3. **博弈合理性**：从游戏策略看是否合理？
   - 1=完全不合理，5=最优策略

4. **发言自然度**：是否像真人对话？
   - 1=机械/模板化，5=自然流畅

请按以下 JSON 格式返回：
{
  "role_consistency": <1-5>,
  "logic_consistency": <1-5>,
  "game_reasoning": <1-5>,
  "naturalness": <1-5>,
  "overall": <1-5>,
  "comment": "简要中文评语"
}
```

## 9.4 评测数据看板（建议）

| 指标 | 频率 | 触发条件 |
|------|------|---------|
| 实时异常告警 | 每次 LLM 调用 | 连续 3 次 JSON 解析失败 / 动作非法 |
| 每局评测 | 每局游戏结束 | 自动生成评测报告 |
| 每日汇总 | 每天 | 所有游戏的聚合指标 |
| 模型对比 | 每周 | 不同模型的平均质量评分 |

## 9.5 持续优化闭环

```
评测发现问题
     │
     ▼
┌─────────────────┐
│ 1. 分析根因       │  ← 哪些场景下 LLM 表现最差？
│    （如：狼人自曝、 │     哪个角色最容易出错？
│    空发言、逻辑矛盾）│     什么 prompt 结构导致问题？
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. Prompt 优化    │  ← 调整 System Prompt 约束
│    增加示例、加强  │     增加 few-shot examples
│    边界条件约束    │     针对特定角色细调 prompt
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. 系统策略调整    │  ← 调整 fallback 阈值
│    自动化修复策略   │     优化 validate_and_repair
│                  │     调整降级链触发条件
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. 重新评测验证    │  ← 跑一轮新游戏
│    对比优化前后    │     对比指标变化
│                  │     确认无回归
└─────────────────┘
```

---

# 十、面试常见追问及回答要点

### Q1: 为什么用 LangGraph 而不是直接用 LangChain 的 Chain？

A: LangChain 的 Chain 是线性流程，我们的决策需要条件分支和错误恢复。LangGraph 的 StateGraph 支持：
- 节点级错误隔离（一个节点失败不影响其他）
- 条件路由（根据角色/阶段走不同路径）
- 并行 fan-out（狼群议事中多个狼人并行提议）
- 状态在节点间传递（中间结果可被下游节点使用）

### Q2: ProviderChain 的降级逻辑是怎样的？

A: 4 层降级，每层有独立的超时和重试策略：
1. `primary` (DeepSeek-V3.2, 6s 超时, 1次重试) → 遇到 timeout/5xx/429/json_parse_error 降级
2. `secondary` (Qwen3.6, 4s 超时, 1次重试) → 遇到 timeout/5xx 降级
3. `cheap_fallback` (DeepSeek-R1, 3s 超时, 无重试) → always 下一层
4. `rule_engine` (静态度规则, 50ms, 无重试) → 最终兜底

### Q3: 如何保证 LLM 不泄露系统信息（如暴露自己是 AI）？

A: 三层防护：
1. Prompt 层面：System Prompt 明确禁止提及 AI/JSON/LangGraph 等术语
2. Safety Filter：`FORBIDDEN_TERMS` 关键词黑名单，出现即替换
3. LLM-as-Judge：评测时检查发言是否暴露系统身份

### Q4: 多狼人共识如果超时怎么办？

A: 45 秒超时后回退到 `fallback_target(candidates)`，即选取存活的可击杀目标列表中的第一个。同时记录 error 信息，上层引擎对超时完全透明。

### Q5: 384 个测试覆盖了哪些？

A: 覆盖范围：
- ProviderChain / RuleEngine 单元测试
- 游戏引擎（NightResolver、VoteResolver、HunterResolver）
- Memory 系统（增删改查、序列化/反序列化）
- API 路由（健康检查、游戏管理）
- Redis 配置与连接
- PlayerDecider 解析与安全过滤

