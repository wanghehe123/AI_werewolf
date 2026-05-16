# AI 狼人杀系统现状与改造工作记录（2026-05-16）

## 1. 文档目的

本文档用于完整记录当前代码库和运行系统的实际状态，覆盖：

- 系统当前可用能力（后端、前端、LLM、日志）
- 本轮已完成改造工作（按问题域分组）
- 仍未完成或需继续验证的工作
- 风险点与建议下一步
- 常用排障命令与入口

---

## 2. 当前运行状态（现场）

### 2.1 运行进程

- 后端监听端口：`127.0.0.1:8000`
- 后端进程 PID：`43832`
- 前端监听端口：`127.0.0.1:5173`
- 前端进程 PID：`80311`

### 2.2 健康检查

- `GET /health` 返回正常：`{"code":0,"message":"ok","data":{"status":"ok"}}`

### 2.3 日志入口

- 后端日志文件：`logs/backend.log`
- 推荐实时查看命令：

```bash
tail -n 200 -f /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/logs/backend.log
```

### 2.4 当前测试状态（最新）

后端全量测试已执行：

- 命令：`.venv/bin/pytest -q`
- 结果：`183 passed, 51 warnings`
- 结论：当前代码在测试层面可通过，warning 主要是第三方依赖 deprecation 提示

---

## 3. 系统架构现状（高层）

### 3.1 后端核心结构

- 游戏 API：`ai_werewolf/api/games.py`
- 状态推进与阶段编排：`ai_werewolf/engine/orchestrator.py`
- 夜晚结算：`ai_werewolf/engine/night.py`
- 投票结算：`ai_werewolf/engine/vote.py`
- LLM Provider：`ai_werewolf/llm/providers.py`
- LLM 决策器：`ai_werewolf/llm/player_decider.py`
- Prompt 构建：`ai_werewolf/llm/prompt_builder.py`

### 3.2 数据持久化

- 已启用数据库持久化（PostgreSQL）
- 配置来源：`ai_werewolf/config/application.yaml` + 环境变量覆盖
- 运行时日志可见 DB 连接标识：`postgresql+psycopg://.../ai_werewolf`

### 3.3 LLM 配置来源

- 启动日志显示：LLM 配置从数据库加载（而非仅 YAML）
- 当前角色绑定（DB 实际值）：
  - `werewolf -> deepseek`
  - `seer -> deepseek`
  - `villager -> deepseek`

---

## 4. 已完成工作（按主题）

## 4.1 夜晚分阶段播报与流程修复

已完成内容：

- 夜晚改为按角色步骤播报，不再“一次性跳过”
- 支持 `night_step_started` / `night_step_finished`
- 夜晚结果统一在所有步骤结束后发布 `night_result`
- 白天阶段切换保持 `phase_changed`

主要涉及文件：

- `ai_werewolf/engine/night.py`
- `ai_werewolf/engine/orchestrator.py`

---

## 4.2 Prompt 上下文与玩家显示改进

已完成内容：

- Prompt 已引入板子上下文、局面上下文
- 玩家显示从裸 UUID 转为座位编号+昵称（如 `4号 小王`）
- 私有信息格式中减少直接暴露 UUID 的使用场景

主要涉及文件：

- `ai_werewolf/llm/prompt_builder.py`
- `ai_werewolf/engine/helpers.py`

---

## 4.3 SSE 流式体验改造

已完成内容：

- 增加 `GET /games/{game_id}/stream?player_id=human`
- 事件流支持：
  - `state_snapshot`
  - `phase_changed`
  - `night_step_started` / `night_step_finished`
  - `speech_delta`
  - `speech_completed`
- AI 发言采用逐段推送，前端可实时刷新

主要涉及文件：

- `ai_werewolf/api/games.py`
- `ai_werewolf/engine/session.py`
- 前端 SSE 消费相关文件（已接入）

---

## 4.4 死亡玩家行为约束修复

已完成内容：

- 死亡玩家不可继续发言/投票/夜晚行动
- 若真人玩家已死亡，白天流程会自动观战跳过并推进

主要涉及文件：

- `ai_werewolf/engine/orchestrator.py`
- `ai_werewolf/engine/helpers.py`
- `ai_werewolf/engine/vote.py`
- 前端阶段渲染逻辑

---

## 4.5 开局前可选真人职业（测试友好）

已完成内容：

- 创建游戏接口支持 `human_role_key`
- 前端 Lobby 支持选择真人职业，便于场景复现和调试

主要涉及文件：

- `ai_werewolf/api/games.py`
- `ai_werewolf/graph/nodes.py`
- `ai_werewolf/rules/assignment.py`
- 前端 Lobby 页面

---

## 4.6 LLM fallback 问题排查与环境加载修复

已完成内容：

- 启动时自动加载本地 `.env`（避免后台进程拿不到 API Key）
- 增强 Provider 诊断日志（缺 key、调用异常、base_url 归一化）
- 修复 base_url 误填完整 endpoint 时的兼容处理

主要涉及文件：

- `ai_werewolf/config/env.py`
- `ai_werewolf/main.py`
- `ai_werewolf/llm/providers.py`
- `.gitignore`（忽略 `.env`、日志目录等）

---

## 4.7 AI 发言 JSON 直出问题修复

问题背景：

- 流式发言时模型偶尔输出完整 JSON 对象，前端直接展示了 JSON 文本

已完成内容：

- 在 `PlayerDecider.stream_speech` 增加 JSON 样式输出识别与提取逻辑
- 若流中是 JSON，对外只放出 `speech` 文本，屏蔽 `action_type` 等字段

主要涉及文件：

- `ai_werewolf/llm/player_decider.py`
- `tests/llm/test_player_decider.py`

---

## 4.8 行动日志增强（结构化）

已完成内容：

- 新增结构化日志模块：`ai_werewolf/engine/action_log.py`
- 开局打印全员身份（`game_start_roles`）
- 游戏中持续打印行动 JSON（`player_action`），覆盖：
  - 真人提交动作
  - AI 夜晚动作
  - AI 发言
  - AI/真人投票
  - AI 遗言

---

## 4.9 DeepSeek 空响应（200 但 content 空）诊断与缓解

问题现象：

- 日志出现：
  - `HTTP 200 OK`
  - `无法解析 LLM 响应为 JSON，使用 fallback`
  - `响应内容为空`

已完成改造：

- `OpenAICompatibleProvider.decide` 增加空内容诊断日志：
  - `finish_reason`
  - `content_chars`
  - `reasoning_chars`
  - `usage`
- 当返回空 `content` 时自动提高 `max_tokens` 重试一次（上限控制）
- 重试后仍空时再 fallback，并明确打印二次诊断日志

主要涉及文件：

- `ai_werewolf/llm/providers.py`
- `tests/llm/test_model_strategy.py`

---

## 4.10 Prompt Trace（优雅查看每轮 AI Prompt）

需求背景：

- 需要查看 AI 输入 Prompt，但不希望把全文塞进主日志

已完成实现：

- 新增 `record_prompt_trace`，每次调用 LLM 前把完整 prompt 写文件
- 主日志只打一条短索引 `prompt_trace`（不含全文），字段包括：
  - `game_id`
  - `phase`
  - `prompt_kind`
  - `actor_id` / `actor_label`
  - `prompt_chars`
  - `prompt_sha256`
  - `path`
- Prompt 文件目录：
  - `logs/prompt_traces/<game_id>/*.md`

主要涉及文件：

- `ai_werewolf/engine/prompt_trace.py`
- `ai_werewolf/engine/night.py`
- `ai_werewolf/engine/vote.py`
- `ai_werewolf/engine/orchestrator.py`
- `ai_werewolf/tests/test_prompt_trace.py`

---

## 5. 近期关键提交（节选）

- `f553043` `debug deepseek empty responses with prompt traces`
- `ea951bf` `fix streamed ai speech and add action logs`
- `06a301b` `load local env for llm keys`
- `549a6d6` `improve llm fallback diagnostics`
- `eb7181f` `fix dead player actions and persisted llm config`
- `c648df2` `add human role selection before game start`

---

## 6. 当前未完成工作 / 待继续验证

## 6.1 真实对局验证：空 content 重试策略

状态：

- 已有单测覆盖（mock 场景）
- 尚需在真实局中连续验证（特别是 `exile_vote` 阶段高并发/长上下文场景）

建议验收标准：

- `fallback` 触发频率显著下降
- 出现空 `content` 时能看到“重试后成功解析”路径

## 6.2 Prompt Trace 可视化入口

状态：

- 已有文件级 trace 和短日志索引
- 暂未提供管理端页面直读/检索 prompt trace 的 UI

建议：

- 后续可在 admin 增加“按 game_id + round + player 查看 prompt”的调试页

## 6.3 日志去重策略

状态：

- 当前某些场景会记录“决策日志 + 落地行动日志”两条，利于审计，但会增加噪音

建议：

- 增加日志级别或 `metadata.stage` 过滤开关，支持 `full` / `compact` 两种模式

## 6.4 前端联动验证（端到端）

状态：

- 后端改造已完成并测试通过
- 仍建议做一轮手工回归：SSE 断线重连、发言流显示、夜晚分阶段展示、观战模式

---

## 7. 风险与注意事项

## 7.1 重启导致内存局丢失

- 当前 `_games` 为内存态，后端重启后旧 `game_id` 会 404
- 这属于当前部署形态预期行为

## 7.2 日志体积增长

- `action_log` + `prompt_trace` 会持续增长
- 若长期运行，建议加轮转/归档策略

## 7.3 测试 warning（非阻断）

- `starlette` cookies deprecation
- `datetime.utcnow()` deprecation（部分模型定义默认值）
- 不影响当前功能，但建议后续逐步清理

---

## 8. 常用排障命令清单

```bash
# 1) 实时看后端日志
tail -n 200 -f /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/logs/backend.log

# 2) 查看最近 prompt trace 文件
find /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python/logs/prompt_traces -type f -name '*.md' -print | tail -n 20

# 3) 后端健康检查
curl -s http://127.0.0.1:8000/health

# 4) 后端全量测试
cd /Users/wish233/Documents/Codex/2026-05-14/java-langchain-angent-python-demo-python
.venv/bin/pytest -q
```

---

## 9. 结论

系统已从“功能可跑”进入“可观测、可排障、可验证”的阶段，核心体验问题（夜晚播报、流式发言、死亡玩家限制、角色选择、日志可观测）均已落地。当前主要收尾工作是：在真实对局中继续验证 DeepSeek 空内容重试策略效果，并决定日志精简与 Prompt Trace 管理策略。

