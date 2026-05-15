# AI 狼人杀体验改造文档

## 背景

本次改造解决三类体验问题：

- 夜晚阶段原先只在结算后给出 `night_result`，玩家看不到狼人、预言家等夜间行动顺序。
- LLM Prompt 缺少当前板子和座位编号上下文，导致 6 人新手局也会聊到女巫、猎人、守卫等不存在角色，并直接输出玩家 ID。
- AI 白天发言原先由 REST 请求阻塞生成，前端只能等所有发言结束后一次性看到整段文本。

## 后端事件协议

新增 `GET /games/{game_id}/stream?player_id=human`，响应类型为 `text/event-stream`。首次连接会推送 `state_snapshot`，带 `Last-Event-ID` 重连时会从内存事件日志补发后续事件。

SSE 事件字段：

- `event_id`
- `event_type`
- `game_id`
- `phase`
- `day_count`
- `visibility`
- `actor_id`
- `target_id`
- `payload`
- `created_at`

关键事件：

- `state_snapshot`：完整前端状态快照。
- `night_step_started` / `night_step_finished`：夜晚角色行动开始/完成，只公开角色阶段，不公开目标。
- `speech_delta`：AI 发言流式片段。
- `speech_completed`：AI 发言完成，固化为公开发言。

6 人新手局角色构成为 `狼人x2、预言家x1、村民x3`，夜晚播报顺序固定为：

1. 狼人开始行动
2. 狼人行动完成
3. 预言家开始行动
4. 预言家行动完成
5. 天亮公告
6. 昨夜结果

该板子不会播报女巫、猎人、守卫。

## Prompt 上下文规则

Prompt 现在包含：

- 板子信息：板子名、角色构成、胜利条件。
- 玩家编号：格式为 `真实player_id（座位号 玩家名）`，要求发言时使用座位号和玩家名，不直接念 ID。
- 存活和出局列表：同时保留可提交给后端校验的 `target_id`。
- 私有信息：狼队友、查验结果、守卫历史等显示为座位编号和昵称。

角色约束按当前板子裁剪。6 人新手局只会向模型提示狼人、预言家、村民相关能力，不会把不存在角色加入行动建议。

## SSE 与降级策略

OpenAI-compatible Provider 为白天发言提供 `stream=True` 的流式输出。Fake Provider 提供稳定分片，便于测试和本地开发。

如果 Provider 没有 API Key、不支持流式或流式请求失败，后端会退回到普通 `decide()`，再把完整 `speech` 按短片段推送为 `speech_delta`，保证前端仍有流式展示体验。

REST 接口保持不变：

- `POST /games/{game_id}/actions` 仍返回完整 `GameStateDto`。
- SSE 是主展示通道，REST 返回是最终状态兜底。

## 前端渲染逻辑

游戏页加载后会自动建立 `EventSource` 订阅。

- 收到 `state_snapshot`：替换当前权威状态。
- 收到 `speech_delta`：在事件时间线底部显示临时发言行。
- 收到 `speech_completed`：移除临时发言，等待快照或 REST 结果固化公开事件。
- SSE 出错：调用 `GET /games/{game_id}` 拉取最新状态作为兜底。

## 验证方式

后端：

```bash
.venv/bin/pytest
```

前端：

```bash
cd frontend
npm test
npm run build
```
