# AI 狼人杀项目当前工作与系统现状（最新）

更新时间：2026-05-16

## 1. 本轮已完成工作

### 1.1 体验改造主线（已落地）

已完成并合入当前分支的核心改造：

1. 夜晚流程改为分阶段播报，避免“一步跳过”。
2. Prompt 上下文增强：拼接当前板子、局面信息、角色约束，减少不存在角色误导。
3. 玩家显示改为“编号+昵称”语义，不直接面向玩家暴露 UUID。
4. SSE 流式事件链路接入，支持发言增量展示（含 delta/completed）。
5. 前后端相关测试与构建已通过（见下文验证状态）。

相关提交（节选）：

- `216899a fix night actions and AI fallback speech`
- `e83dd74 优化逻辑`

### 1.2 新增测试便利功能（已完成）

已支持“开局前让人类玩家选择职业”，用于联调与回归测试。

实现内容：

1. 后端创建游戏接口支持 `human_role_key`。
2. 角色分配支持固定人类角色并校验板子合法性。
3. 前端 Lobby 新增职业选择 UI（含“随机身份”）。
4. 覆盖后端/前端对应测试用例。

相关提交：

- `c648df2 add human role selection before game start`

### 1.3 死亡玩家权限修复（已完成）

已修复玩家死亡后仍可发言、投票的问题。

实现内容：

1. 后端 `allowed_actions` 不再给死亡人类返回白天发言和放逐投票动作。
2. 后端行动入口拒绝死亡玩家提交 `speech`、`vote`、`abstain` 以及主动夜间技能。
3. 死亡人类仍可用观战性质的 `continue/skip` 推进牌桌，不会被计入发言或投票。
4. 如果人类已出局，白天公告后会自动跳过人类发言和人类投票，只让存活 AI 继续流程。
5. 前端在 `allowed_actions` 为空时只显示观战状态，不渲染发言框或投票按钮。
6. 前端投票目标会在玩家死亡后自动切换到当前存活目标，避免保留旧的死亡目标。

### 1.4 LLM 配置链路修复（已完成）

已修复“后台数据库配置了 LLM Provider，但游戏引擎启动仍使用 YAML 配置”的问题。

实现内容：

1. 启用数据库持久化时，后端启动优先从数据库读取 LLM Provider 和角色绑定。
2. 数据库没有 LLM Provider 时才回退到 `ai_werewolf/config/llm.yaml`。
3. 启动时会检查被角色绑定使用的 OpenAI-compatible Provider 是否缺少环境变量。
4. 当前本机启动日志已确认游戏引擎加载数据库里的 `deepseek` 绑定。

## 2. 当前未完成工作

### 2.1 AI 真实请求链路仍需注入 API Key（阻塞项）

现象：

- 局内 AI 只输出预设/兜底语句（例如“我先观察一下局势”），看起来像“不会参与”。

根因（已从日志定位）：

- 旧日志中出现：`Provider minimax: API Key 未配置（环境变量 MINIMAX_API_KEY），使用 fallback 响应`
- 修复后，后端已从数据库加载 `deepseek` 绑定。
- 当前运行环境仍未检测到 `DEEPSEEK_API_KEY`，启动日志会提示：`LLM Provider deepseek 已被角色绑定使用，但环境变量 DEEPSEEK_API_KEY 未配置；调用时会进入 fallback`

结论：

- 这不是前端渲染问题，也不是 SSE 本身的问题；当前剩余阻塞是运行环境没有把真实模型 key 注入后端进程。

### 2.2 需要完成的收尾验证

在补齐可用 API Key 后，还需要完成一轮端到端回归：

1. 验证 AI 发言是否恢复为真实模型输出（非 fallback）。
2. 验证夜晚阶段中 AI/人类可行动角色均能看到正确操作入口。
3. 验证 SSE 流式发言体验（`speech_delta` 持续刷新，`speech_completed` 正确固化）。

## 3. 系统当前现状

### 3.1 代码与分支状态

- 当前分支：`codex/ai-werewolf-experience-sse`
- 最新提交：`c648df2 add human role selection before game start`
- 当前有本轮待提交修改，准备提交死亡玩家权限与 LLM 配置链路修复。

### 3.2 服务运行状态

- 后端：`http://127.0.0.1:8000`（健康检查正常）
- 前端：`http://127.0.0.1:5173`（HTTP 200 正常）

当前监听进程（本机）：

- 后端 `uvicorn`：PID `20459`
- 前端 `vite`：PID `80311`

### 3.3 配置状态（与 AI 异常直接相关）

- 当前后端进程未检测到以下关键环境变量：
  - `OPENAI_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `MINIMAX_API_KEY`
  - `ZHIPU_API_KEY`

备注：

- 当前数据库角色绑定以 `deepseek` 为主时，缺少 `DEEPSEEK_API_KEY` 会触发 fallback。

## 4. 建议的下一步执行顺序

1. 在运行后端的同一环境注入 `DEEPSEEK_API_KEY`，或在后台把角色绑定切到已有 key 的 Provider。
2. 重启后端并观察首轮 AI 行为日志，确认不再出现 fallback 警告。
3. 开一局 6 人板（可固定人类职业）做端到端验证：夜晚分阶段、白天流式发言、行动入口。
4. 若仍异常，按日志中的 Provider 错误继续定点修复（鉴权/超时/响应解析）。

## 5. 关键文档索引

- 本文档（最新）：`docs/current-work-status-2026-05-15-latest.md`
- 体验改造说明：`docs/ai-werewolf-experience-sse-refactor.md`
- 早期阶段总结（历史）：`docs/current-work-summary-2026-05-15.md`
