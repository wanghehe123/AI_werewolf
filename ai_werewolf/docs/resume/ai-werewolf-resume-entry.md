### AI狼人杀 -- 基于 LangChain/LangGraph 的 Multi-Agent AI 对战平台
技术栈：FastAPI + LangChain + LangGraph + Redis + Pydantic + Socket.IO + SSE + SiliconFlow
项目简介：基于多智能体架构的 AI 狼人杀对战平台，多个 AI 玩家通过 LLM 驱动进行博弈对抗，支持人类玩家旁观或参与，后端通过 SSE 实时推送游戏状态。
- **Multi-Agent 博弈架构**：为 5 种游戏角色（狼人/预言家/女巫/猎人/平民）绑定不同 LLM 模型（DeepSeek-V3.2 / Qwen3.6 / DeepSeek-R1 / MiniMax-M2.5），每个 Agent 拥有独立的角色 Prompt 和决策链，实现异构模型驱动的多智能体博弈。

- **LangGraph 6 节点决策管道**：构建 analyze → update_suspicion → decide_strategy → decide_action → generate_decision → validate 六阶段决策图，引入语义分析节点对局势进行结构化推理，各阶段通过 LangGraph StateGraph 串联，支持节点级错误隔离和降级回退。

- **4 层 LLM 降级链**：基于 ProviderChain 实现 primary → secondary → cheap_fallback → rule_engine 四级降级链路，实时分类错误类型（timeout / 5xx / 429 / json_parse_error），自动触发降级切换，确保任一 Provider 故障时游戏不中断。

- **LangChain 客户端池化与限流**：基于 LangChain ChatOpenAI 封装可复用客户端池，按模型/API Key/base_url 缓存连接实例；引入 asyncio.Semaphore 全局限流，控制最大并发 LLM 调用数，配合 max_retries=0 消除 SDK 层与降级链的双重重试，有效规避 API 限流(429)问题。

- **结构化记忆系统**：设计 4 种记忆类型（DaySummary / PlayerSuspicionMemory / PrivateRoleMemory / DecisionTrace），通过 RedisMemoryEnvelope 统一序列化存储至 Redis，支持按玩家/角色/全局三维度区分记忆可见性，配合 MemoryContextBuilder 双源聚合实现跨回合情境连贯性。

- **多狼人共识机制**：实现狼群议事图（Werewolf Council），采用 fan-out 提议 + 投票的共识模式，多个狼人 AI 并行提交击杀提议后汇总投票，超时自动回退至首候选目标，确保多狼人协同决策的一致性。

- **实时游戏引擎**：基于 FastAPI + Socket.IO + SSE 构建实时通信层，支持游戏状态分阶段广播、AI 发言流式输出、人类玩家干预等交互场景，384+ 单元测试覆盖核心逻辑。