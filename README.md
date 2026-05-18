# 🐺 AI 狼人杀

> **基于 LangChain / LangGraph 的多智能体 AI 对战平台**
>
> Multi-Agent Werewolf Game powered by LangChain · LangGraph · FastAPI · Redis · MySQL/PostgreSQL

[![Python](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136%2B-green)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.2%2B-orange)](https://langchain.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 项目简介

AI 狼人杀是一个**多智能体 AI 对战平台**。平台中，多个 AI 玩家由不同的 LLM 模型驱动，在经典狼人杀规则框架下进行博弈对抗。系统支持人类玩家旁观或参与，后端通过 SSE 实时推送游戏状态。

**核心亮点：**

- 5 种角色（狼人 / 预言家 / 女巫 / 猎人 / 平民）分别绑定不同 LLM，实现**异构模型**多智能体博弈
- **LangGraph 6 节点**决策管道，每个 AI 玩家通过结构化图推理做出决策
- **4 层 LLM 降级链**，任一 Provider 故障时自动切换，游戏不中断
- **结构化记忆系统**，跨回合保持情境连贯，AI 有"记忆"
- **多狼人共识机制**，多个狼人 AI 通过 fan-out 投票协商击杀目标
- FastAPI + Socket.IO + SSE 构建**实时通信层**，支持 AI 发言流式输出

---
<img width="1024" height="1536" alt="image" src="https://github.com/user-attachments/assets/220c77cd-9940-4ba1-87d2-0ff2a7518736" />



## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.136+ |
| LLM 框架 | LangChain 0.2+ · LangGraph |
| AI 模型 | DeepSeek-V3.2 · Qwen3.6 · DeepSeek-R1 · MiniMax-M2.5 |
| 数据验证 | Pydantic V2 |
| 数据库 | MySQL 8+ / PostgreSQL 14+（SQLModel ORM） |
| 缓存 / 会话 | Redis 5+ |
| 实时通信 | Socket.IO · SSE |
| 语音合成 | edge-tts · MiniMax TTS |
| 测试 | pytest + pytest-asyncio |
| 包管理 | uv |

---

## 核心功能详解

### 1. Multi-Agent 编排引擎

```
GameOrchestrator（游戏状态机）
  └── AIActionScheduler（调度器）
       ├── 夜晚阶段：并行调用狼人 / 预言家 / 女巫 AI
       ├── 白天阶段：顺序触发各玩家发言决策
       └── 投票阶段：汇总投票 → 放逐结算
```

每个 AI 玩家都是独立的 Agent 实例，具有：
- 独立的角色 Prompt
- 独立的 LangGraph 决策管道
- 独立的记忆上下文

### 2. LangGraph 6 节点决策管道

```
N1: analyze           → 分析当前局势（存活玩家、历史发言）
N2: update_suspicion  → 更新对各玩家的怀疑度
N3: decide_strategy   → 制定本轮策略（隐藏 / 揭露 / 逻辑推演）
N4: decide_action     → 确定具体行动（夜晚击杀目标 / 投票目标）
N5: generate_decision → 生成自然语言发言
N6: validate          → Pydantic 校验输出格式，不合格则回退重试
```

各节点通过 `LangGraph StateGraph` 串联，支持节点级错误隔离与降级回退。

### 3. 4 层 LLM 降级链

```yaml
Tier 1 (primary)      : DeepSeek-V3.2     timeout=6s  retry=1
Tier 2 (secondary)    : Qwen3.6-27B       timeout=4s  retry=1
Tier 3 (cheap_fallback): DeepSeek-R1      timeout=3s  retry=0
Tier 4 (static)       : RuleEngine        timeout=50ms retry=0
```

错误分类触发降级：`timeout` / `5xx` / `429` / `json_parse_error`，确保游戏不因 API 故障中断。

### 4. 结构化记忆系统

| 记忆类型 | 内容 | 可见性 |
|---------|------|--------|
| `DaySummary` | 每日游戏摘要（发言 / 投票 / 死亡） | 全局 |
| `PlayerSuspicionMemory` | 对各玩家的怀疑度评分 | 玩家私有 |
| `PrivateRoleMemory` | 角色专属信息（狼人队友 / 预言家查验结果） | 角色私有 |
| `DecisionTrace` | 历史决策轨迹 | 玩家私有 |

所有记忆通过 `RedisMemoryEnvelope` 统一序列化存入 Redis，`MemoryContextBuilder` 聚合双源（Redis 持久 + Session 内存）构建推理上下文。

### 5. 多狼人共识机制（Werewolf Council）

```
n1_brief   → 同步当前局势给所有狼人
fan-out    → 每个狼人 AI 并行提交击杀提议
rebut      → 允许狼人基于其他提议进行反驳
fan-out    → 投票汇总
resolve    → 多数票决定；超时自动回退首候选
```

### 6. 客户端池化与并发限流

- `LangChain ChatOpenAI` 客户端按 `(model, api_key, base_url)` 缓存，避免重复创建连接
- `asyncio.Semaphore` 全局限流（默认 max_concurrent=3），防止并发过高触发 429
- `max_retries=0`，禁用 SDK 内置重试，由 ProviderChain 统一管理降级逻辑

---

## 项目结构

```
ai_werewolf/
├── api/                    # FastAPI 路由
│   ├── games.py            # 游戏 CRUD / 状态查询
│   ├── public.py           # SSE 推送接口
│   ├── admin.py            # 管理接口
│   └── socketio_bridge.py  # Socket.IO 集成
├── config/
│   └── llm.yaml            # LLM Provider 配置（API Key / 角色绑定 / 降级链）
├── domain/                 # 领域模型（GameSession / Player / Role）
├── engine/
│   ├── orchestrator.py     # GameOrchestrator 游戏主控引擎
│   ├── night.py            # NightResolver 夜晚阶段结算
│   ├── day.py              # 白天发言阶段
│   └── vote.py             # 投票阶段结算
├── llm/
│   ├── providers.py        # OpenAICompatibleProvider（LangChain 封装）
│   ├── client_pool.py      # ChatOpenAI 客户端池
│   ├── rate_limiter.py     # 并发限流器
│   ├── player_decider.py   # PlayerDecider 决策入口
│   ├── action_scheduler.py # AIActionScheduler
│   ├── chain/
│   │   ├── provider_chain.py   # 4 层降级链
│   │   └── rule_engine.py      # 静态规则引擎（兜底）
│   ├── graphs/
│   │   ├── player_decision_graph.py  # LangGraph 6 节点决策图
│   │   ├── werewolf_council.py       # 多狼共识图
│   │   └── witch_council.py          # 女巫决策图
│   ├── memory/
│   │   ├── models.py        # 记忆类型定义
│   │   ├── store.py         # RedisMemoryStore
│   │   └── context_builder.py  # MemoryContextBuilder
│   ├── model_config.py     # LLMProviderConfig Pydantic 模型
│   └── model_registry.py   # ModelProviderRegistry
├── infra/
│   └── redis_client.py     # Redis 连接管理
├── storage/                # 数据持久层（SQLModel + MySQL/PostgreSQL）
│   ├── models.py           # SQLModel 数据模型
│   ├── repositories.py     # 数据访问层
│   ├── database.py         # 数据库连接与表创建
│   └── catalog.py          # 数据库表目录
├── tts/                    # 语音合成模块
├── tests/                  # pytest 单元测试（384+）
└── main.py                 # FastAPI 应用入口
```

---

## 快速开始

### 前置要求

- Python 3.14+
- MySQL 8+ 或 PostgreSQL 14+（用于数据持久化）
- Redis 7+（本地运行 `redis-server` 或使用 Docker）
- [uv](https://docs.astral.sh/uv/) 包管理器

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/ai-werewolf.git
cd ai-werewolf/ai_werewolf
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 配置 API Key

复制配置模板并填入你的 API Key：

```bash
cp config/llm.yaml.example config/llm.yaml
```

编辑 `config/llm.yaml`，填写 `api_key` 字段（支持直接填写或通过环境变量 `api_key_env` 引用）：

```yaml
providers:
  - id: deepseek
    type: openai_compatible
    model_name: deepseek-ai/DeepSeek-V3.2
    base_url: https://api.siliconflow.cn/v1
    api_key: YOUR_SILICONFLOW_API_KEY   # 替换为你的 Key
    timeout: 30
```

> **推荐：** 生产环境使用 `api_key_env` 从环境变量读取，避免将 Key 提交到 Git：
>
> ```yaml
> api_key_env: SILICONFLOW_API_KEY
> ```

### 4. 配置数据库

项目支持 MySQL 和 PostgreSQL 两种数据库。选择其中一种进行配置。

#### 使用 MySQL

```bash
# 使用 Docker 启动 MySQL
docker run -d \
  --name ai-werewolf-mysql \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=ai_werewolf \
  -e MYSQL_USER=werewolf \
  -e MYSQL_PASSWORD=werewolf123 \
  -p 3306:3306 \
  mysql:8

# 等待 MySQL 启动后，创建数据库（如果未自动创建）
docker exec -i ai-werewolf-mysql mysql -uroot -prootpassword -e "CREATE DATABASE IF NOT EXISTS ai_werewolf;"
```

编辑 `ai_werewolf/config/application.yaml`：

```yaml
app:
  database:
    enabled: true
    username: werewolf
    password: werewolf123
    url: jdbc:mysql://127.0.0.1:3306/
    database: ai_werewolf
    schema: public
    echo: false
```

#### 使用 PostgreSQL（默认）

```bash
# 使用 Docker 启动 PostgreSQL
docker run -d \
  --name ai-werewolf-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_werewolf \
  -p 5432:5432 \
  postgres:16
```

编辑 `ai_werewolf/config/application.yaml`：

```yaml
app:
  database:
    enabled: true
    username: postgres
    password: postgres
    url: jdbc:postgresql://127.0.0.1:5432/
    database: ai_werewolf
    schema: public
    echo: false
```

#### 环境变量方式配置（推荐生产环境）

创建 `.env` 文件：

```bash
# MySQL 配置示例
AI_WEREWOLF_DATABASE_ENABLED=true
AI_WEREWOLF_DATABASE_USERNAME=werewolf
AI_WEREWOLF_DATABASE_PASSWORD=werewolf123
AI_WEREWOLF_DATABASE_JDBC_URL=jdbc:mysql://127.0.0.1:3306/
AI_WEREWOLF_DATABASE_NAME=ai_werewolf

# PostgreSQL 配置示例
# AI_WEREWOLF_DATABASE_ENABLED=true
# AI_WEREWOLF_DATABASE_USERNAME=postgres
# AI_WEREWOLF_DATABASE_PASSWORD=postgres
# AI_WEREWOLF_DATABASE_JDBC_URL=jdbc:postgresql://127.0.0.1:5432/
# AI_WEREWOLF_DATABASE_NAME=ai_werewolf
```

### 5. 启动 Redis

```bash
# 本地 Docker
docker run -d -p 6379:6379 redis:7

# 或直接启动本地 redis-server
redis-server
```

### 6. 启动后端

```bash
uv run uvicorn ai_werewolf.main:app --reload --port 8000
```

### 7. 运行测试

```bash
uv run pytest tests/ -v
```

---

## 配置说明

### 数据库配置

项目使用 SQLModel（基于 SQLAlchemy）作为 ORM，支持 MySQL 和 PostgreSQL。

#### MySQL 配置

确保安装 MySQL 驱动（项目默认包含）：

```bash
# 如果使用 MySQL，需要安装 pymysql 或 aiomysql
uv add pymysql
# 或异步版本
uv add aiomysql
```

在 `config/application.yaml` 中配置：

```yaml
app:
  database:
    enabled: true
    username: werewolf
    password: werewolf123
    url: jdbc:mysql://127.0.0.1:3306/
    database: ai_werewolf
    schema: public
    echo: false  # 设为 true 可在控制台看到 SQL 语句
```

支持的 MySQL URL 格式：
- `jdbc:mysql://host:port/`
- `mysql://host:port/`
- `mysql+pymysql://host:port/`

#### PostgreSQL 配置

PostgreSQL 是项目默认数据库，驱动 `psycopg[binary]` 已包含在依赖中。

在 `config/application.yaml` 中配置：

```yaml
app:
  database:
    enabled: true
    username: postgres
    password: postgres
    url: jdbc:postgresql://127.0.0.1:5432/
    database: ai_werewolf
    schema: public
    echo: false
```

支持的 PostgreSQL URL 格式：
- `jdbc:postgresql://host:port/`
- `postgresql://host:port/`
- `postgresql+psycopg://host:port/`

#### 禁用数据库持久化

如果仅使用 Redis 存储会话数据，可禁用数据库：

```yaml
app:
  database:
    enabled: false
```

或设置环境变量：

```bash
export AI_WEREWOLF_DATABASE_ENABLED=false
```

### 替换 LLM Provider

`config/llm.yaml` 支持任意 OpenAI 兼容接口（OpenAI / DeepSeek / 通义千问 / Ollama 等）：

```yaml
providers:
  - id: my-provider
    type: openai_compatible
    model_name: gpt-4o
    base_url: https://api.openai.com/v1   # 可留空，默认走 OpenAI
    api_key_env: OPENAI_API_KEY
    temperature: 0.7
    max_tokens: 2048
    timeout: 30
```

### 角色 → 模型绑定

```yaml
role_bindings:
  werewolf: my-provider    # 狼人使用你的 Provider
  seer: my-provider
  witch: my-provider
  hunter: my-provider
  villager: my-provider
```

### 降级链自定义

```yaml
chains:
  default:
    - tier: primary
      provider: my-fast-model
      timeout_ms: 5000
      max_retries: 1
      triggers_to_next: [timeout, 5xx, 429, json_parse_error]
    - tier: static
      provider: rule_engine   # 最终兜底，无需 API
      timeout_ms: 50
      max_retries: 0
```

---

## API 接口概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/games` | 创建新游戏 |
| `GET` | `/api/games/{id}` | 获取游戏状态 |
| `POST` | `/api/games/{id}/start` | 开始游戏 |
| `GET` | `/api/games/{id}/sse` | SSE 实时状态推送 |
| `POST` | `/api/games/{id}/action` | 人类玩家行动 |
| `GET` | `/api/llm-config/providers` | 查询 LLM Provider 配置 |

详细文档：启动后访问 `http://localhost:8000/docs`

---

## 开发指南

### 添加新的 LLM Provider

1. 在 `config/llm.yaml` 的 `providers` 列表中添加配置
2. 将新 Provider ID 写入 `role_bindings` 或 `chains`
3. 无需修改任何代码，系统自动加载

### 添加新的角色类型

1. 在 `domain/` 中定义新角色枚举
2. 在 `llm/prompts/` 中添加角色 Prompt 模板
3. 在 `config/llm.yaml` 的 `role_bindings` 中绑定 Provider
4. 在 `engine/` 中实现角色夜晚行动逻辑

### 运行特定测试

```bash
# 运行 LLM 相关测试
uv run pytest tests/ -k "llm" -v

# 运行引擎测试
uv run pytest tests/ -k "engine" -v

# 查看测试覆盖率
uv run pytest tests/ --cov=ai_werewolf --cov-report=html
```

---

## 安全注意事项

⚠️ **上传 GitHub 前必须处理 API Key：**

1. 将 `config/llm.yaml` 中所有 `api_key: sk-...` 替换为 `api_key_env: YOUR_ENV_VAR_NAME`
2. 将真实 Key 写入本地 `.env` 文件（已在 `.gitignore` 中排除）
3. 或使用 [git-secrets](https://github.com/awslabs/git-secrets) 防止意外提交

推荐 `.env` 文件格式：

```env
SILICONFLOW_API_KEY=sk-...
MINIMAX_API_KEY=sk-...
```

---

## 路线图

- [ ] 前端 UI（Vue 3 + WebSocket）
- [ ] 支持人类玩家参与游戏（不只是旁观）
- [ ] 更多角色（守卫 / 丘比特 / 白狼王）
- [ ] 游戏回放功能
- [ ] LLM 对局评测 Dashboard（LLM-as-Judge）
- [ ] Docker Compose 一键部署

---

## 参与贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的功能分支：`git checkout -b feature/your-feature`
3. 提交变更：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 发起 Pull Request

---

## License

[MIT](LICENSE) © 2026

---

> **声明**：本项目使用的 LLM 服务（SiliconFlow / MiniMax）均为第三方 API，使用时请遵守各平台的服务条款。游戏内容仅用于娱乐与技术研究目的。
