# AI Werewolf 系统现状报告

**日期：** 2026-05-18
**分支：** `codex/ai-werewolf-experience-sse`
**测试：** 382 passed, 0 failed

---

## 一、系统架构概览

### 1.1 后端 (`ai_werewolf/`)

| 层 | 目录 | 职责 |
|---|---|---|
| API | `api/` | FastAPI 路由：games、admin、public、llm_config、socketio_bridge |
| 引擎 | `engine/` | 游戏流程编排、夜晚/投票/猎人解析、会话管理、上下文构建 |
| LLM | `llm/` | Provider 层、降级链、PlayerDecider、ActionScheduler、Prompt 构建 |
| LLM 图 | `llm/graphs/` | LangGraph 图：狼人议会、女巫决策、玩家统一决策 |
| 记忆 | `llm/memory/` | Redis 持久化记忆层：DaySummary、SuspicionMemory、PrivateRoleMemory |
| 规则 | `rules/` | 角色注册、板子验证、投票与胜利条件 |
| 领域 | `domain/` | 数据模型：GameState、PlayerPrivateInfo、AgentProfile |
| 基础设施 | `infra/` | Redis 客户端、SSE 流持久化 |
| TTS | `tts/` | 语音合成（MiniMax → Edge-TTS 降级） |

### 1.2 前端 (`frontend/src/`)

| 组件 | 文件 | 职责 |
|---|---|---|
| 路由 | `App.tsx` | React Router：大厅、游戏、管理后台 |
| 桌面 | `GameTable.tsx` | 玩家网格、事件时间轴、阶段路由 |
| 阶段 UI | `PhaseSceneRouter.tsx` | 设置、夜晚、黎明、发言、投票、遗言、复盘 |
| Store | `stores/gameStore.ts` | Zustand：SSE 事件处理、状态同步、音频生成 |
| Socket | `services/socket.ts` | Socket.IO 客户端（WebSocket 传输） |
| 类型 | `types.ts` | 完整的 TypeScript 类型定义 |

**技术栈：** React 19 + TypeScript + Vite + Zustand + Framer Motion + Socket.IO + Tailwind CSS v4

### 1.3 游戏阶段流转

```
SETUP ──[start_game]──▶ NIGHT ──▶ DAY_ANNOUNCEMENT ──[continue]──▶ DAY_SPEECH
                         │                                            │
                         │                                            [speech]
                         │                                            ▼
                         ◀──[win?]── LAST_WORDS ◀──[exiled]── EXILE_VOTE
                                        │
                           [continue]──▶ 回到 NIGHT 或 GAME_OVER
```

### 1.4 定义的角色

| 角色 | 阵营 | 夜晚行动 |
|---|---|---|
| 狼人 (werewolf) | 狼人阵营 | wolf_kill |
| 预言家 (seer) | 好人阵营 | seer_check |
| 女巫 (witch) | 好人阵营 | witch_save / witch_poison |
| 猎人 (hunter) | 好人阵营 | 被投票/被杀时开枪 |
| 平民 (villager) | 好人阵营 | 无 |

### 1.5 LLM Provider 体系

| 层级 | Provider | 超时 | 用途 |
|---|---|---|---|
| primary | deepseek | 6000ms | 主推理 |
| secondary | sf-glm | 4000ms | 降级 |
| cheap_fallback | sf-kimi | 3000ms | 廉价回退 |
| static | rule_engine | 50ms | 规则引擎（最终兜底） |

所有 provider 通过 `api.siliconflow.cn` 统一端点，支持 OpenAI 兼容协议。

### 1.6 LangGraph 图体系

| 图 | 节点数 | 用途 |
|---|---|---|
| `player_decision_graph` | 6 节点 | 统一的玩家决策链：分析局势 → 更新怀疑 → 决定策略 → 决定行动 → 生成决策 → 验证修复 |
| `werewolf_council` | 5 节点 | 多狼人共识议会：简述 → 提案(fan-out) → 反驳 → 投票(fan-out) → 裁决 |
| `witch_council` | 4 节点 | 女巫逐级推理：评估 → 救人决策 → 毒药决策 → 最终确定 |

---

## 二、本次会话工作内容

### 2.1 已修复的关键 Bug

#### Bug A：夜晚私有行动被错误转为 speak 兜底（上一会话延续）

**问题：** `PlayerDecider._build_default_speak_fallback()` 将非发言行动（seer_check、wolf_kill 等）的 `action_type` 和 `target_id` 全部销毁，强制改为 `action_type=speak, target_id=None`。预言家查验、狼人刀人等夜晚行动完全失效。

**修复文件：**
- `ai_werewolf/llm/player_decider.py:107-126` — 保留原始 `action_type` / `target_id`，仅替换 `speech` 占位
- `ai_werewolf/llm/player_decider.py:207-223` — Chain 路径同步修复（原先缺失空发言检查）
- `ai_werewolf/llm/providers.py:460-470` — 区分夜晚行动（DEBUG）vs 非预期空发言（INFO）日志级别

#### Bug B：女巫刀口信息显示为"预言家验人"卡片

**问题：** 前端 `gameStore.ts` 将所有 `private_info` 事件统一当作预言家查验结果处理。女巫收到"今晚 X 号被狼人击杀"的 `private_info` 事件时，消息不包含"狼人阵营"，被判定为 `camp="good"`，触发"查验结果：好人阵营"的弹窗覆盖。

**修复文件：**
- `frontend/src/types.ts:129` — `PrivateInfoPayload` 新增 `subtype?: "witch_kill"`
- `frontend/src/stores/gameStore.ts:120-122` — 检测 `subtype === "witch_kill"` 时跳过 seerResult 创建
- `ai_werewolf/engine/orchestrator.py:149` — 后端发送 `"subtype": "witch_kill"` 标记

#### Bug C：女巫用掉解药后仍知道每夜刀口

**问题：** 解药用完后，女巫不应再知道狼人击杀目标。但两处无条件泄露刀口：
1. `orchestrator.py:_resolve_night_pre_witch()` 始终发送 `private_info` SSE 事件
2. `helpers.py:allowed_actions()` 始终附加 `night_kill_info` 到 action options

**修复文件：**
- `ai_werewolf/engine/orchestrator.py:139-140` — 增加 `witch_info.witch_medicine.get("save", False)` 判断
- `ai_werewolf/engine/helpers.py:143` — 增加 `has_save` 判断，仅在解药可用时附加 `night_kill_info`

### 2.2 全链路诊断日志（上一会话）

| 标签 | 位置 | 用途 |
|---|---|---|
| `[COLLECT_WOLF_KILL]` | `engine/night.py` | 狼人击杀决策树全部分支（人类/单狼/议会、候选列表、shuffle 结果） |
| `[WOLF_COUNCIL]` | `engine/night.py` | 议会流程各阶段（候选标签映射、提案/投票详情、裁决结果、回退） |
| `[PROVIDER_PARSE]` | `llm/providers.py` | LLM 响应解析后标记空 speech（区分预期/非预期） |
| `[DECIDER_EMPTY_SPEECH]` | `llm/player_decider.py` | Decider 层空发言处理决策（保留原动作） |
| `[NIGHT_DECISION_EMPTY_SPEECH]` | `engine/night.py` | 夜晚最终决策空发言情况 |

### 2.3 本次会话未提交的文件

| 文件 | 变更类型 |
|---|---|
| `frontend/src/types.ts` | Bug B 修复 |
| `frontend/src/stores/gameStore.ts` | Bug B 修复 |
| `ai_werewolf/engine/orchestrator.py` | Bug B + Bug C 修复 |
| `ai_werewolf/engine/helpers.py` | Bug C 修复 |
| `ai_werewolf/llm/player_decider.py` | Bug A 修复（空发言处理） |
| `ai_werewolf/llm/providers.py` | Bug A 修复（日志级别） |
| `ai_werewolf/engine/night.py` | 日志优化 |

---

## 三、已完成功能清单

### 3.1 核心游戏系统
- [x] 端到端游戏流程（SETUP → NIGHT → DAY_SPEECH → VOTE → GAME_OVER）
- [x] 角色分配与注册（狼人/预言家/女巫/猎人/平民）
- [x] 人类 + AI 混合玩家模式
- [x] 人类角色指定（开局选择角色）
- [x] 胜利条件判定（狼人全灭 / 狼人数 >= 好人）
- [x] 猎人临死开枪

### 3.2 夜晚行动
- [x] 狼人击杀：单狼 LLM 决策 / 多狼 LangGraph 议会共识
- [x] 预言家查验：LLM 选择查验目标
- [x] 守卫守护：规则校验（不可连续两晚同目标）
- [x] 女巫用药：LangGraph 多步推理（评估 → 救人 → 毒药）
- [x] 人类女巫两步夜晚流程（先看刀口，再决定）
- [x] 死亡结算（狼刀 → 守卫 → 解救 → 毒药）
- [x] 反偏见：候选列表随机 shuffle、candidate_labels 标签映射

### 3.3 白天发言与投票
- [x] AI 发言生成（LLM 流式输出）
- [x] 流式发言前端展示（SSE speech_delta 实时渲染）
- [x] 人类发言提交
- [x] 放逐投票（多数决，平局无人出局）
- [x] 遗言系统

### 3.4 记忆与持久化
- [x] Redis 记忆存储：DaySummary、SuspicionMemory、PrivateRoleMemory、DecisionTrace
- [x] 每日天摘要压缩（防止 prompt 膨胀）
- [x] 玩家怀疑链持久化
- [x] 私有角色信息持久化（预言家查验记录、女巫药水状态）
- [x] 统一 6 节点 LangGraph 玩家决策图（发言/投票/夜晚）
- [x] MemoryContext 构建器（注入到决策图的 context 中）

### 3.5 Provider 与降级
- [x] OpenAI 兼容 Provider（所有兼容 API 的大模型服务）
- [x] 4 层降级链（primary → secondary → cheap_fallback → rule_engine）
- [x] 错误分类与自动回退（timeout / 5xx / 429 / json_parse_error）
- [x] Reasoning 模型空 content 自动重试（提高 max_tokens）
- [x] 三层 JSON 响应解析（直接解析 → 代码块提取 → 括号匹配）
- [x] FakeModelProvider（测试用，不调 API）
- [x] 上下文感知 fallback（夜晚/投票/发言不同模板）

### 3.6 通信与前端
- [x] SSE 实时事件流（phase_changed、speech_delta、speech_completed、private_info 等）
- [x] Socket.IO 双向通信（带重连）
- [x] SSE 事件重放（Last-Event-ID 机制 + Redis Stream 持久化）
- [x] 前端 Zustand 状态同步（SSE + REST 双源）
- [x] 预言家查验结果覆盖弹窗 + 玩家卡片标记
- [x] 女巫夜晚行动面板（刀口信息、救人/毒药/无行动选项）
- [x] Framer Motion 动画（标题、玩家卡、事件时间轴）

### 3.7 TTS 与音频
- [x] MiniMax TTS 语音合成（主）
- [x] Edge-TTS 回退（免费，中文语音）
- [x] 前端 TTS 播放（AudioContext / Web Audio API）
- [x] 背景音乐（夜晚/白天不同 BGM）
- [x] 音频公告队列（system / speech 分类）

### 3.8 管理后台
- [x] 管理面板认证
- [x] 玩家/Agent/板子/角色管理 CRUD
- [x] LLM Provider 配置管理
- [x] 游戏列表与详情

### 3.9 测试
- [x] 382 个测试全部通过
- [x] 覆盖：引擎（night/vote/hunter/orchestrator）、LLM 图（council/witch）、Provider 链、Redis 操作、验证器、流系统

---

## 四、未完成 / 可优化项

### 4.1 记忆与智能度（P1 - 高优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| 怀疑链更新 | 仅读取现有怀疑记录，不基于新信息推理生成 | 让 LLM 在 n2_update_suspicion 节点分析新事件并生成/更新怀疑目标 |
| DaySummary 质量 | 基于规则的字符串拼接，非语义摘要 | 改用 LLM 生成结构化语义摘要 |
| DecisionTrace 覆盖 | 仅白天发言路径写了 DecisionTrace | 投票和夜晚行动路径也需要写入 Debug Trace |
| 记忆 Schema 稳定性 | suspicion_memory.records 使用 `dict`，无强类型约束 | 引入 Pydantic 模型替代裸 dict |

### 4.2 游戏功能完善（P1 - 高优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| 警长选举 | `GamePhase.SHERIFF_ELECTION` 和 `SHERIFF_SPEECH` 枚举已定义，功能未实现 | 实现警长竞选流程（发言 → 投票），警长投票权重 1.5 票 |
| 守卫角色 | `guard`/`guardian` 在引擎代码中被引用但未在 BuiltInRoleRegistry 注册 | 正式注册守卫角色，加入板子配置 |
| 多回合反驳 | 狼人议会的 n3_rebut 是空操作占位 | 实现狼人间互相质疑提案的辩论回合 |
| 最终天摘要 | 立即胜利时不写 DaySummary 到 Redis | 在 `_end_game()` 前确保写入最终天的记忆 |
| PostgreSQL 持久化 | `PostgresMemoryStore` 是空存根 | 实现 PostgreSQL 的 MemoryStore 协议 |

### 4.3 架构统一（P2 - 中优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| 图协议统一 | 狼人议会和女巫议会有独立的图构建和执行方式 | 提取公共协议/基类，使所有 LangGraph 图遵循统一接口 |
| 夜晚角色注册 | NightResolver.resolve() 硬编码了狼人/预言家/守卫/女巫的顺序调用 | 使用策略模式 + 注册模式，通过 RoleRegistry 自动发现和调度夜晚角色 |
| 双路决策 | `_get_ai_decision()`（通过统一图）和 `_get_ai_decision_with_prompt()`（直接 LLM）并存 | 统一到单一决策路径，消除回退/旧路径的双轨 |
| Council 回退冗余 | 议会超时/异常时回退到 `_single_wolf_kill` / `_witch_single_decision`，这些又走统一图 | 可以简化为：议会失败 → 直接走统一图的单人路径 |

### 4.4 前端优化（P2 - 中优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| 大型 CSS 文件 | `index.css` 单文件 700+ 行 | 拆分为组件级 CSS 或使用 CSS Modules |
| 女巫无药场景 | 当女巫解药和毒药都用完后，仍进入两步夜晚流程（第二步只有 "不使用药" 选项） | 跳过两步流程，直接走完整夜晚 |
| 已出局玩家视角 | 部分场景下"你已出局"消息可能出现时机不对 | 细化 ObserverScene 的触发条件和消息内容 |
| 夜晚行动实时反馈 | 所有夜晚行动完成后统一展示结果 | 每个角色行动完成后立即推送该玩家的个人结果 |
| 移动端适配 | 3 列网格在小屏幕较拥挤 | 响应式布局优化 |

### 4.5 可观测性（P2 - 中优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| 结构化日志 | 已有 [COLLECT_WOLF_KILL] / [WOLF_COUNCIL] 等标签 | 统一日志格式（JSON Lines），便于 ELK/Loki 采集 |
| Prompt Trace | 已有 `record_prompt_trace()` | 增加 Trace 查询 API，可在管理后台回放历史决策 |
| 游戏统计 | 无 | 记录每局游戏的 LLM 调用次数、延迟分布、降级频率、各角色决策质量 |

### 4.6 部署与运维（P3 - 低优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| Docker 化 | 无 Dockerfile | 添加 Dockerfile + docker-compose（含 Redis + PostgreSQL） |
| 环境变量管理 | `.env` 文件 | 增加 `.env.example` 模板，标注必填/可选 |
| CI/CD | 无 | GitHub Actions：lint、test、type-check、build |
| Redis Sentinel | 单节点 Redis | 生产环境考虑 Redis Sentinel 或 Cluster |

### 4.7 前端功能缺失（P3 - 低优先）

| 项目 | 现状 | 优化方向 |
|---|---|---|
| 角色展示 | 游戏未结束时隐藏 AI 角色身份 | 游戏结束复盘阶段展示所有角色身份 |
| 历史回顾 | 无历史对局查看 | 实现历史游戏回放功能 |
| 音效增强 | 仅 BGM，无动作音效 | 添加刀人、投票、查验等音效反馈 |

---

## 五、关键文件索引

### 后端核心文件

| 文件 | 行数 | 职责 |
|---|---|---|
| `engine/orchestrator.py` | 509 | 阶段编排器，单入口 |
| `engine/night.py` | 974 | 夜晚解析：狼人/预言家/守卫/女巫/死亡 |
| `engine/vote.py` | 201 | 投票解析 |
| `engine/session.py` | 115 | GameSession 数据类 |
| `engine/helpers.py` | 240 | 工具函数：event()、player_label()、allowed_actions()、frontend_state() |
| `llm/player_decider.py` | 401 | PlayerDecider：LLM 响应校验与安全过滤 |
| `llm/providers.py` | 531 | OpenAI 兼容 Provider |
| `llm/chain/provider_chain.py` | 318 | 4 层降级链 |
| `llm/graphs/player_decision_graph.py` | 391 | 统一 6 节点决策图 |
| `llm/graphs/werewolf_council.py` | 320 | 多狼人议会图 |
| `llm/graphs/witch_council.py` | 371 | 女巫决策图 |
| `llm/memory/store.py` | 231 | Redis 记忆存储 |
| `llm/memory/context_builder.py` | - | 记忆上下文构建器 |
| `api/games.py` | 366 | 游戏 API：创建/查询/动作/SSE/TTS |
| `domain/game_state.py` | - | 数据模型 |

### 前端核心文件

| 文件 | 行数 | 职责 |
|---|---|---|
| `App.tsx` | 339 | 路由 + GameRoute 生命周期 |
| `GameTable.tsx` | 194 | 主游戏桌面 |
| `PhaseSceneRouter.tsx` | 338 | 各阶段 UI |
| `stores/gameStore.ts` | 295 | Zustand 状态管理 |
| `types.ts` | 264 | 类型定义 |
| `services/socket.ts` | 99 | Socket.IO 客户端 |

---

## 六、测试覆盖

- **总测试数：** 382 个（全部通过）
- **测试文件数：** 19 个 `.py` 文件
- **最大测试文件：** `test_werewolf_council.py`（狼人议会）、`test_session_repository.py`（会话持久化）、`test_witch_council.py`（女巫决策）
- **覆盖领域：** 引擎、LLM 图、Provider 链、Redis 操作、SSE 流、验证器、上下文构建、Prompt 约束
