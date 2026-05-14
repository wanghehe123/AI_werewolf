## 结论

AI 狼人杀的游戏体验应该由后端权威状态机驱动，前端只负责订阅事件、切换场景、展示等待态和提交用户动作。第一版建议采用 **HTTP 提交动作 + SSE 推送事件 + REST 补偿拉取** 的组合，而不是一开始就全量 WebSocket。

核心理由：

- 当前是单人用户与多名 AI 玩，通信方向以“服务端推送阶段变化、AI 发言、行动要求”为主，SSE 足够简单稳定。
- 用户动作天然是离散命令，使用 HTTP 更容易做幂等、鉴权、重试和审计。
- 后续若支持多人实时房间、语音、弹幕式互动、观战聊天，再升级或并行引入 WebSocket。

## 总体交互模型

<whiteboard type="blank"></whiteboard>

### 推荐通信通道

| 通道 | 用途 | MVP 是否实现 | 说明 |
| --- | --- | --- | --- |
| REST | 创建游戏、查询状态、提交玩家动作、后台配置 | 是 | 可靠、简单、便于幂等 |
| SSE | 推送游戏事件、AI 发言片段、阶段变化、行动要求 | 是 | 单向下行，适合单人对局 |
| WebSocket | 多人房间、实时语音、用户间聊天、低延迟双向同步 | 预留 | 不作为当前 MVP 主链路 |
| 轮询 | SSE 断线兜底 | 是 | 每 3 秒拉一次 `/games/{id}` |

### 事件驱动原则

后端每推进一步都写入事件，再把事件推给前端。前端不猜规则，只响应事件与状态快照。

事件分为四类：

| 类型 | 示例 | 前端用途 |
| --- | --- | --- |
| state | `state_snapshot`, `phase_changed` | 切换场景、刷新座位、刷新按钮 |
| public | `player_spoke`, `vote_cast`, `night_result`, `last_words` | 展示公开时间线 |
| private | `seer_result`, `witch_prompt`, `wolf_team_info` | 仅推给当前人类玩家 |
| control | `action_required`, `ai_thinking`, `timer_started`, `error` | 展示等待、倒计时、可操作面板 |

## 事件协议建议

### SSE 连接

```http
GET /games/{game_id}/stream?player_id=human
Accept: text/event-stream
Last-Event-ID: evt_000123
```

连接建立后，后端先推一次状态快照：

```json
{
  "event_id": "evt_000001",
  "event_type": "state_snapshot",
  "game_id": "game_xxx",
  "phase": "night",
  "day_count": 1,
  "visibility": "self",
  "payload": {
    "game_state": {}
  },
  "created_at": "2026-05-14T16:00:00+08:00"
}
```

### 通用事件字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| event_id | string | 全局递增或按局递增，用于断线续传 |
| event_type | string | 事件类型 |
| game_id | string | 对局 ID |
| phase | string | 事件发生时的阶段 |
| day_count | number | 当前天数 |
| visibility | public/self/system | 事件可见性 |
| actor_player_id | string/null | 行动发起人 |
| target_player_id | string/null | 行动目标 |
| payload | object | 事件负载 |
| created_at | string | 服务端时间 |

### 用户动作提交

```http
POST /games/{game_id}/actions
```

```json
{
  "actor_player_id": "human",
  "action_type": "vote",
  "target_player_id": "agent_linye",
  "content": null,
  "client_action_id": "client_uuid"
}
```

提交成功后后端返回最新状态，同时通过 SSE 推送对应事件。前端以 SSE 为主更新，以 HTTP 返回作为即时反馈兜底。

## 阶段交互设计

### 1. setup 准备阶段

玩家交互：

- 用户在大厅选择可用板子和 AI 玩家。
- 进入游戏桌后看到座位、头像、人设摘要、自己的身份。
- 页面主按钮为“开始游戏”。

AI 交互：

- 暂不调用 LLM。
- 后端完成身份分配、私有信息初始化、模型绑定初始化。

服务端事件：

| 顺序 | 事件 | 说明 |
| --- | --- | --- |
| 1 | `game_created` | 对局创建 |
| 2 | `state_snapshot` | 返回完整初始状态 |
| 3 | `action_required` | 要求人类玩家点击开始 |

进入下一阶段：

- 用户提交 `start_game`。
- 后端切到 `night`，推送 `phase_changed`。

### 2. night 夜晚阶段

玩家交互：

- 如果人类是平民或无夜间技能角色，展示“夜晚等待中/确认夜晚行动”。
- 如果人类是狼人，展示可刀目标与狼队友信息。
- 如果人类是预言家，展示查验目标列表。
- 如果人类是女巫，展示今晚刀口、解药/毒药状态。
- 如果人类是守卫，展示守护目标列表和上夜守护限制。

AI 交互：

- 后端按角色行动顺序生成 AI 决策任务。
- 每个 AI 只收到自己可见的上下文：公开历史、私有信息、角色约束、可选目标。
- LLM 返回结构化动作，后端校验合法性后写入 `night_actions`。
- 超时或非法输出时使用 deterministic fallback。

服务端事件：

| 顺序 | 事件 | 可见性 | 说明 |
| --- | --- | --- | --- |
| 1 | `phase_changed` | public | 夜晚开始 |
| 2 | `private_info` | self | 推送人类夜间可见信息 |
| 3 | `ai_thinking` | system | 某类 AI 正在行动，可聚合展示 |
| 4 | `action_required` | self | 如果人类有夜间技能，要求选择目标 |
| 5 | `night_action_committed` | system/self | 行动已提交，不泄露他人隐私 |
| 6 | `phase_changed` | public | 进入天亮公告 |

进入下一阶段：

- 所有必要夜间行动完成后，后端统一结算死亡。
- 切到 `day_announcement`。

### 3. day_announcement 天亮公告

玩家交互：

- 展示昨夜死亡结果：平安夜、单死、双死。
- 如果用户死亡，提示当前状态和是否可继续观战。
- 用户点击“进入白天发言”。

AI 交互：

- 不做新的 LLM 决策。
- 可为后续发言阶段预热上下文摘要，但不改变状态。

服务端事件：

| 顺序 | 事件 | 说明 |
| --- | --- | --- |
| 1 | `night_result` | 昨夜死亡信息 |
| 2 | `state_snapshot` | 更新存活状态 |
| 3 | `action_required` | 要求人类确认继续 |

进入下一阶段：

- 用户提交 `continue`。
- 暂时跳过警长竞选，直接进入 `day_speech`。

### 4. day_speech 白天发言

玩家交互：

- 前端展示发言顺序、当前发言人、历史发言。
- AI 发言时展示“思考中”到“逐段出现”的过程。
- 轮到用户时，展示发言输入框、草稿自动保存、提交按钮。

AI 交互：

- 后端按座位或板子配置顺序逐个调用 AI。
- 每个 AI 的 prompt 包含：公开事件摘要、自己身份、人设、已知私有信息、当前阶段目标。
- LLM 输出结构化结果：`speech`, `intent`, `claim`, `suspicions`, `vote_hint`。
- 后端只公开 `speech` 和必要摘要，不公开隐藏推理字段。

服务端事件：

| 顺序 | 事件 | 说明 |
| --- | --- | --- |
| 1 | `speech_order_created` | 发言顺序确定 |
| 2 | `current_speaker_changed` | 当前发言人变化 |
| 3 | `ai_thinking` | AI 正在生成发言 |
| 4 | `player_spoke` | 公开发言 |
| 5 | `action_required` | 轮到人类发言 |
| 6 | `phase_changed` | 发言结束，进入放逐投票 |

进入下一阶段：

- 人类提交 `speech` 后，后端补齐剩余发言或确认发言完成。
- 切到 `exile_vote`。

### 5. exile_vote 放逐投票

玩家交互：

- 展示所有存活可投目标。
- 展示 AI 的投票过程，可以先显示“正在投票”，再逐条公开结果。
- 用户可投票或弃票。

AI 交互：

- 后端先让 AI 根据公开发言和自身阵营做投票决策。
- AI 输出：`target_player_id`, `speech/reason`, `confidence`。
- 后端校验：不能投自己、不能投死亡玩家、不能投不存在玩家。

服务端事件：

| 顺序 | 事件 | 说明 |
| --- | --- | --- |
| 1 | `phase_changed` | 进入放逐投票 |
| 2 | `ai_thinking` | AI 投票中 |
| 3 | `vote_cast` | 公开某玩家投票或弃票 |
| 4 | `action_required` | 要求人类投票 |
| 5 | `vote_result` | 票型统计 |
| 6 | `exile_result` | 放逐结果 |

进入下一阶段：

- 如果有人被放逐，进入 `last_words`。
- 如果平票或无人放逐，直接检查胜负，未结束则进入下一夜。

### 6. last_words 遗言阶段

玩家交互：

- 展示出局玩家遗言。
- 如果人类是出局玩家，允许输入遗言。
- 如果是 AI 出局，展示 AI 自动生成遗言。
- 用户点击继续进入下一阶段。

AI 交互：

- 若出局者是 AI，调用 LLM 生成遗言。
- prompt 只给出局者可见信息，不允许泄露系统 prompt 或其他 AI 隐藏信息。
- 遗言应只影响公开事件，不直接改变状态。

服务端事件：

| 顺序 | 事件 | 说明 |
| --- | --- | --- |
| 1 | `phase_changed` | 进入遗言 |
| 2 | `ai_thinking` | AI 遗言生成中 |
| 3 | `last_words` | 遗言公开 |
| 4 | `action_required` | 要求人类确认继续 |

进入下一阶段：

- 后端检查胜负。
- 若胜负成立，进入 `game_over`。
- 否则 `day_count += 1`，进入下一夜。

### 7. game_over 复盘阶段

玩家交互：

- 展示胜利阵营、全部身份、关键事件时间线。
- 展示每名 AI 的模型、人格、关键发言和投票。
- 提供“再开一局”“换板子”“导出复盘”。

AI 交互：

- 不再参与规则行动。
- 可选调用一个复盘总结 Agent，生成本局摘要。

服务端事件：

| 顺序 | 事件 | 说明 |
| --- | --- | --- |
| 1 | `game_end` | 胜负结果 |
| 2 | `role_reveal` | 身份公开 |
| 3 | `replay_summary` | 可选复盘总结 |

## 前端场景切换策略

前端以 `game.phase` 作为唯一场景入口：

| phase | Scene | 主要 UI |
| --- | --- | --- |
| setup | SetupScene | 开始按钮、座位预览 |
| night | NightScene | 夜晚技能面板或等待态 |
| day_announcement | AnnouncementScene | 昨夜公告、继续按钮 |
| day_speech | SpeechScene | 发言流、输入框、当前发言人 |
| exile_vote | VoteScene | 投票目标、弃票、票型展示 |
| last_words | LastWordsScene | 遗言展示、继续按钮 |
| game_over | ReplayScene | 身份公开、复盘时间线 |

前端渲染规则：

- `allowed_actions` 决定按钮，不由前端硬编码权限。
- `current_turn_player_id` 决定是否高亮“轮到你”。
- `public_events` 渲染时间线。
- `private_events` 只进入当前阶段面板，不写入公开时间线。
- 未知 phase 展示兜底页，并上报错误。

## 后端编排策略

### Phase Orchestrator

后端应把阶段推进拆为可测试的编排器：

| 模块 | 职责 |
| --- | --- |
| PhaseOrchestrator | 根据当前 phase 和 action 决定下一步 |
| ActionValidator | 校验用户动作是否合法 |
| AIActionScheduler | 为当前阶段生成 AI 决策任务 |
| EventOutbox | 记录事件并推送到 SSE |
| VisibilityFilter | 区分公开事件、私有事件、系统事件 |
| SnapshotBuilder | 构建前端状态快照 |

### AI 决策任务

AI 不直接修改游戏状态。推荐流程：

1. Orchestrator 创建 `AIActionRequest`。
2. PromptBuilder 构造角色视角输入。
3. ModelProvider 执行 LLM 调用。
4. StructuredOutputParser 解析决策。
5. ActionValidator 校验目标和动作。
6. RulesEngine 应用动作。
7. EventOutbox 写入公开或私有事件。

### 超时与失败兜底

| 场景 | 处理 |
| --- | --- |
| LLM 超时 | 使用角色默认策略 |
| LLM 返回非法 JSON | 重试一次，仍失败则 fallback |
| 目标非法 | 改为弃权或选择第一个合法目标 |
| SSE 断线 | 前端用 Last-Event-ID 重连 |
| 事件缺失 | 前端 REST 拉全量状态补偿 |
| 用户重复提交 | 根据 client_action_id 幂等去重 |

## 为什么 MVP 先用 SSE，而不是直接 WebSocket

### SSE 更适合当前单人 AI 对局

- 下行事件多，上行动作少。
- 浏览器原生支持 EventSource，断线重连简单。
- 服务端实现成本低，便于日志审计。
- 与 HTTP 动作提交天然配合。

### WebSocket 适合后续场景

| 后续需求 | 为什么需要 WebSocket |
| --- | --- |
| 多名真人同时玩 | 多客户端双向实时同步 |
| 实时聊天 | 高频双向消息 |
| 语音播报/语音输入 | 需要低延迟流式交互 |
| 观战弹幕 | 高频互动事件 |
| AI 发言 token 级流式展示 | WebSocket 更灵活，但 SSE 也可支撑文本流 |

推荐架构是：MVP 用 SSE；协议层事件模型保持中立，未来可以把同一套事件通过 WebSocket 广播。

## MVP 开发拆分建议

1. 新增 `GET /games/{game_id}/stream`，先推 `state_snapshot` 和后续 public events。
2. 后端引入 EventOutbox，所有状态变化先写事件。
3. 前端接入 EventSource，根据 `phase_changed` 和 `state_snapshot` 刷新 GameState。
4. 为 `action_required` 建立统一 ActionPanel。
5. 引入 private event 过滤，先支持人类预言家查验结果和狼人队友信息。
6. AI 发言阶段加入 `ai_thinking` 与 `player_spoke` 分段事件。
7. 增加 Last-Event-ID 断线续传。
8. 增加轮询兜底和用户可见的“连接恢复中”状态。

## 验收标准

- 用户打开游戏桌后，无需手动刷新即可看到阶段切换。
- AI 发言、投票、夜晚结算都能以事件形式逐步出现在时间线。
- 用户只在自己可行动时看到可点击按钮。
- 用户的私有信息不会进入公开事件。
- SSE 断开后可以自动重连，重连后不会丢关键事件。
- 同一个 `client_action_id` 重复提交不会造成重复投票或重复发言。
- 前端收到未知事件或未知 phase 时可以降级展示，不会白屏。

## 后续演进

- 接入 WebSocket Gateway：支持多人真人房间。
- 引入 Redis Stream 或 Postgres Outbox：支持多实例部署和事件恢复。
- 引入 AI token streaming：AI 发言逐字出现，提升临场感。
- 引入倒计时和自动托管：用户超时后由默认策略提交动作。
- 引入复盘 Agent：根据事件日志生成战术复盘和每个 AI 的表现总结。
