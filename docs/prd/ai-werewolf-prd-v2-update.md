## 15. PRD 修订版：可配置 AI 狼人杀平台

<callout emoji="🧭" background-color="light-blue">
本修订版覆盖前文“固定 8 人标准局”的 MVP 定义。新版 MVP 的核心不是写死某一种狼人杀板子，而是让用户通过“游戏设定模块 + AI 玩家配置模块”快速组出一局可玩的 AI 狼人杀。
</callout>

### 15.1 修订背景

用户希望完成的产品形态是：只要定义好每个 AI Agent 的特点，再选择或配置一套狼人杀板子，就可以立即开局。参考产品也强调了 AI 玩家独立记忆、鲜明性格、自定义智能体和智能体广场等方向。

因此新版产品从“固定玩法 Demo”调整为“可配置玩法引擎 + AI 玩家库”的单人狼人杀平台。

### 15.2 新版一句话描述

AI 狼人杀是一个支持自定义游戏板子、自定义 AI 玩家人格和头像的单人狼人杀平台。用户选择一套规则配置和一组 AI 玩家后，即可与具备不同性格、发言风格、推理能力和策略倾向的 AI 玩家开局。

### 15.3 新版 MVP 目标

1. 用户可以创建或选择一套游戏板子，包括角色组成、警长竞选、发言顺序、投票规则和胜利条件。
2. 用户可以创建 AI 玩家，定义其昵称、头像、人设、发言风格、推理能力、撒谎倾向、攻击性和记忆风格。
3. 用户可以把若干 AI 玩家加入一局游戏，并由系统按板子配置自动分配身份。
4. 系统可以根据板子配置动态生成 LangGraph 对局流程，而不是固定 8 人局流程。
5. 一局游戏可以完整运行到胜负结算，并输出身份真相、关键事件和复盘。
6. MVP 暂不做语音播报、真人多人联机、公开智能体市场和复杂商业化系统。

## 16. 核心产品模块

### 16.1 游戏设定模块

游戏设定模块负责定义一局狼人杀的“规则板子”。它决定有哪些角色、人数是多少、是否有警长竞选、夜晚技能顺序、发言和投票规则，以及胜负条件。

#### 16.1.1 板子配置能力

| 配置项 | MVP 是否支持 | 说明 |
| --- | --- | --- |
| 板子名称 | 支持 | 例如“8人预女猎”“9人预女猎白”“自定义娱乐局” |
| 总人数 | 支持 | 由角色数量自动计算，也允许手动校验 |
| 角色列表 | 支持 | 从系统内置角色库中选择角色和数量 |
| 阵营配置 | 支持 | 狼人阵营、好人阵营，可扩展第三方阵营 |
| 警长竞选 | 支持 | 可开启或关闭；开启后增加竞选、退水、警徽流、警长归票流程 |
| 发言顺序 | 支持 | 顺序发言、逆序发言、警长指定发言方向 |
| 投票规则 | 支持 | 单轮投票、平票 PK、警长 1.5 票可作为后续增强 |
| 夜晚行动顺序 | 支持 | 根据角色技能定义动态生成 |
| 胜利条件 | 支持 | 狼人全灭好人胜；狼人屠边或屠城胜 |
| 角色自定义技能 | 暂不支持 | MVP 只允许选择内置角色，不开放用户写技能脚本 |

#### 16.1.2 MVP 内置角色库

| 角色 | 阵营 | 行动阶段 | MVP 说明 |
| --- | --- | --- | --- |
| 狼人 | 狼人阵营 | 夜晚 | 狼队共同选择击杀目标 |
| 平民 | 好人阵营 | 白天 | 无夜晚技能 |
| 预言家 | 好人阵营 | 夜晚 | 查验一名玩家阵营 |
| 女巫 | 好人阵营 | 夜晚 | 解药和毒药各一次 |
| 猎人 | 好人阵营 | 死亡后 | 出局后可带走一名玩家 |
| 守卫 | 好人阵营 | 夜晚 | 守护一名玩家，MVP 可作为增强项 |

MVP 推荐默认提供三套模板：

1. 6 人新手局：2 狼人、1 预言家、3 平民，无警长。
2. 8 人标准局：2 狼人、1 预言家、1 女巫、1 猎人、3 平民，可选警长。
3. 9 人进阶局：3 狼人、1 预言家、1 女巫、1 猎人、3 平民，可选警长。

### 16.2 AI 玩家配置模块

AI 玩家配置模块负责定义“一个 AI 玩家像什么样的人”。它不决定玩家本局身份，身份由板子分配；它决定 AI 在拿到身份后如何发言、推理、伪装、攻击、防守和投票。

#### 16.2.1 AI 玩家基础字段

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| agent_id | AI 玩家唯一 ID | agent_001 |
| name | 昵称 | 林野 |
| avatar_url | 虚拟头像 | 图片地址或本地资源路径 |
| avatar_prompt | 头像生成提示词 | 冷静的年轻侦探，半身像，暗色背景 |
| persona | 人设简介 | 理性、谨慎、讨厌无逻辑发言 |
| speech_style | 发言风格 | 短句、强势、爱反问 |
| reasoning_level | 推理强度 | 1 到 5 |
| deception_level | 撒谎/伪装能力 | 1 到 5 |
| aggression_level | 攻击性 | 1 到 5 |
| cooperation_level | 合作倾向 | 1 到 5 |
| risk_preference | 风险偏好 | 保守、均衡、激进 |
| memory_style | 记忆风格 | 记投票、记发言矛盾、记身份跳法 |
| model_config | 模型配置 | 默认模型或用户指定模型 |

#### 16.2.2 AI 玩家可视化头像

每个 AI 玩家最好有虚拟形象，MVP 支持两种方式：

1. 系统默认头像库：提供 20 个预置头像，创建 Agent 时可直接选择。
2. AI 作画生成：用户输入人设或头像提示词，系统生成头像并绑定到 Agent。

MVP 中头像生成不影响游戏逻辑。如果生成失败，系统使用默认头像兜底。头像资源需要保存原始提示词、图片 URL、生成模型和生成时间，方便后续重新生成或风格统一。

#### 16.2.3 AI 玩家发言控制

AI 发言由三层信息共同决定：

1. 固定人设：昵称、性格、语言风格、攻击性。
2. 本局身份：狼人、预言家、平民等隐藏身份。
3. 对局记忆：公开发言、投票记录、夜晚结果、私有信息。

系统必须保证 AI 的人设稳定，但允许其根据身份调整策略。例如同一个“理性分析师”拿到预言家时会认真报验人，拿到狼人时会用理性话术隐藏狼队视角。

### 16.3 开局编排模块

开局流程从“选板子 + 选 AI 玩家”开始。

1. 用户选择一个板子模板，或创建自定义板子。
2. 用户选择自己是否参与，以及自己的座位和身份策略：随机身份或指定身份。
3. 用户从 AI 玩家库中选择若干 Agent；数量必须满足板子总人数减去真人用户数量。
4. 系统校验板子合法性：角色数量、阵营数量、技能顺序、胜利条件。
5. 系统创建对局，分配身份，生成初始私有记忆和公开玩家列表。
6. LangGraph 根据板子配置生成本局状态图并开始运行。

### 16.4 对局运行模块

对局运行模块负责让一局游戏按规则推进。规则裁决由确定性代码完成，AI 只负责生成发言、行动意图和投票理由。

核心阶段包括：

- 身份分配。
- 警长竞选，可选。
- 夜晚行动。
- 死亡公布。
- 白天发言。
- 投票放逐。
- 遗言或技能触发。
- 胜负判断。
- 复盘总结。

## 17. 新版关键用户故事

| 编号 | 用户故事 | 验收标准 |
| --- | --- | --- |
| US-01 | 作为用户，我想创建一套自定义板子 | 可以选择角色和数量，并开启或关闭警长竞选 |
| US-02 | 作为用户，我想保存常用板子 | 创建后可在开局时复用 |
| US-03 | 作为用户，我想创建 AI 玩家 | 可以填写昵称、人设、发言风格和能力参数 |
| US-04 | 作为用户，我想给 AI 玩家生成头像 | 输入头像提示词后生成头像，失败时使用默认头像 |
| US-05 | 作为用户，我想选择一组 AI 玩家开局 | 系统校验人数匹配后进入游戏 |
| US-06 | 作为用户，我想感受到不同 AI 的性格差异 | 同一阶段不同 AI 的发言长度、语气、攻击性和推理方式有差异 |
| US-07 | 作为用户，我想看到本局规则 | 对局中可查看板子、角色组成、警长规则和胜利条件 |
| US-08 | 作为用户，我想复盘 AI 的表现 | 结束后展示每个 AI 的身份、关键发言、投票和策略摘要 |

## 18. 第一版技术方案

### 18.1 技术目标

第一版技术方案服务于三个核心能力：

1. 板子可配置：用数据结构描述规则，而不是写死流程。
2. Agent 可配置：AI 玩家的人格、发言和头像可以独立创建和复用。
3. 对局可运行：LangGraph 根据板子配置推进游戏，规则由代码裁决。

### 18.2 推荐技术栈

| 层 | 技术选型 | 说明 |
| --- | --- | --- |
| 前端 | React 或 Next.js | 负责板子编辑、Agent 编辑、对局界面 |
| 后端 | FastAPI | 提供 REST API 和流式对局事件 |
| Agent 编排 | LangGraph | 管理游戏状态图、阶段跳转和中断恢复 |
| LLM 调用 | LangChain ChatModel 或 OpenAI SDK | 统一封装模型调用和结构化输出 |
| 头像生成 | 图片生成模型 API | MVP 可抽象为 ImageGenerationProvider |
| 存储 | SQLite + SQLModel | 开发快，后续可迁移 PostgreSQL |
| 后台任务 | asyncio / Celery 后续可选 | 处理头像生成和 AI 并发行动 |
| 测试 | pytest | 覆盖规则引擎、板子校验和对局模拟 |

### 18.3 后端模块划分

```text
app/
  api/
    boards.py              # 板子 CRUD、合法性校验
    agents.py              # AI 玩家 CRUD、头像生成
    games.py               # 创建对局、查询状态、提交用户行动
  domain/
    board_schema.py        # 板子、角色、阶段、胜利条件定义
    agent_profile.py       # AI 玩家人格与能力参数
    game_state.py          # 对局状态、玩家状态、事件日志
    rules_engine.py        # 确定性规则裁决
  graph/
    builder.py             # 根据 BoardConfig 构建 LangGraph
    nodes.py               # 夜晚、发言、投票、结算等节点
    reducers.py            # 状态合并与事件追加
  services/
    llm_player.py          # AI 玩家决策与发言
    avatar_service.py      # AI 头像生成与兜底
    recap_service.py       # 对局复盘
  storage/
    models.py              # SQLModel 数据表
    repository.py          # 数据访问
```

### 18.4 核心数据模型

#### BoardConfig

```json
{
  "board_id": "board_8_standard",
  "name": "8人预女猎",
  "player_count": 8,
  "roles": [
    {"role_key": "werewolf", "count": 2},
    {"role_key": "seer", "count": 1},
    {"role_key": "witch", "count": 1},
    {"role_key": "hunter", "count": 1},
    {"role_key": "villager", "count": 3}
  ],
  "sheriff_enabled": true,
  "speech_rule": "sheriff_select_direction",
  "vote_rule": "single_vote_with_pk",
  "win_condition": "wolves_eliminated_or_wolves_reach_parity"
}
```

#### AgentProfile

```json
{
  "agent_id": "agent_linye",
  "name": "林野",
  "avatar_url": "https://example.com/avatar.png",
  "avatar_prompt": "冷静的年轻侦探，半身像，暗色背景",
  "persona": "理性、谨慎、讨厌无逻辑发言",
  "speech_style": "短句、克制、会引用投票细节",
  "reasoning_level": 5,
  "deception_level": 3,
  "aggression_level": 2,
  "cooperation_level": 4,
  "risk_preference": "balanced",
  "memory_style": "focus_on_votes_and_claims"
}
```

#### GameState

```json
{
  "game_id": "game_001",
  "board_id": "board_8_standard",
  "phase": "day_speech",
  "day_count": 1,
  "players": [],
  "events": [],
  "public_memory": [],
  "private_memories": {},
  "pending_user_action": null,
  "winner": null
}
```

### 18.5 LangGraph 动态编排

LangGraph 不再写死“狼人、预言家、女巫”三个夜晚节点，而是由 `BoardConfig.roles` 和角色注册表生成阶段列表。

角色注册表示例：

```python
ROLE_REGISTRY = {
    "werewolf": {
        "night_action": "wolf_kill",
        "phase_order": 10,
        "action_schema": "KillAction"
    },
    "seer": {
        "night_action": "seer_check",
        "phase_order": 20,
        "action_schema": "CheckAction"
    },
    "witch": {
        "night_action": "witch_use_potion",
        "phase_order": 30,
        "action_schema": "PotionAction"
    }
}
```

构图策略：

1. `initialize_game` 根据板子和玩家列表分配身份。
2. 如果 `sheriff_enabled = true`，插入警长竞选子图。
3. 根据角色注册表生成夜晚行动节点。
4. 固定插入白天公布、发言、投票、结算和胜负判断节点。
5. 每个节点只产出事件和候选动作，最终合法性由 `rules_engine` 校验。

### 18.6 AI 玩家调用流程

每次需要 AI 行动时，后端组装 `PlayerDecisionContext`：

```json
{
  "agent_profile": {},
  "secret_role": "werewolf",
  "phase": "day_speech",
  "board_rules": {},
  "public_events": [],
  "private_memory": [],
  "alive_players": [],
  "available_actions": ["speak", "vote"],
  "strategy_hint": "hide_identity_and_shift_suspicion"
}
```

LLM 必须返回结构化结果：

```json
{
  "speech": "我不太认同 3 号的逻辑，他一直在回避昨晚的刀口。",
  "action": {
    "type": "vote",
    "target_player_id": "player_3"
  },
  "public_reason": "3 号发言缺少明确站边",
  "private_memory_update": "继续观察 5 号是否可能是预言家"
}
```

系统拿到结果后进行三层校验：

1. Schema 校验：字段完整，动作类型合法。
2. 规则校验：目标玩家存活、当前阶段允许该动作。
3. 内容校验：发言不包含系统提示、JSON 字段、未公开身份信息。

### 18.7 头像生成方案

头像生成作为独立服务，不参与对局主链路。

流程：

1. 用户创建 Agent 时填写 `avatar_prompt`。
2. 前端调用 `POST /agents/{id}/avatar:generate`。
3. 后端调用图片生成模型，生成方形头像。
4. 图片上传到对象存储或保存本地静态目录。
5. 更新 `avatar_url`。
6. 如果生成失败，使用默认头像并记录错误。

MVP 约束：

- 头像只在 Agent 创建和编辑时生成。
- 对局中不实时生成头像。
- 不做语音播报。
- 不做复杂形象一致性训练。

### 18.8 API 草案

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /boards | 查询板子列表 |
| POST | /boards | 创建自定义板子 |
| GET | /boards/{board_id} | 查询板子详情 |
| POST | /boards/{board_id}/validate | 校验板子合法性 |
| GET | /agents | 查询 AI 玩家列表 |
| POST | /agents | 创建 AI 玩家 |
| PATCH | /agents/{agent_id} | 修改 AI 玩家 |
| POST | /agents/{agent_id}/avatar:generate | 生成头像 |
| POST | /games | 创建对局 |
| GET | /games/{game_id} | 查询对局状态 |
| POST | /games/{game_id}/actions | 提交用户行动 |
| GET | /games/{game_id}/events | 查询或流式获取事件 |
| GET | /games/{game_id}/recap | 查询复盘 |

### 18.9 MVP 里程碑

#### M1：规则与板子引擎

- 内置角色注册表。
- 板子 CRUD。
- 板子合法性校验。
- 固定模板：6 人、8 人、9 人。

#### M2：AI 玩家配置

- Agent CRUD。
- 人设和能力参数。
- 默认头像库。
- AI 作画生成头像。

#### M3：LangGraph 对局原型

- 根据 BoardConfig 构建状态图。
- 支持无警长局完整运行。
- AI 玩家可发言、投票、夜晚行动。

#### M4：Web MVP

- 板子编辑页。
- Agent 编辑页。
- 开局配置页。
- 对局主界面。
- 复盘页。

#### M5：体验和稳定性

- 增加警长竞选流程。
- 增加 10 局自动模拟测试。
- 增加发言越界检测和重试。
- 增加事件日志和调试面板。

### 18.10 第一版验收标准

MVP 完成时必须满足：

- 可以创建至少一套自定义板子，并通过合法性校验。
- 可以创建至少 6 个 AI 玩家，并配置不同人设和发言风格。
- 每个 AI 玩家可以绑定头像，头像生成失败时有默认兜底。
- 用户可以选择板子和 AI 玩家开局。
- 至少支持无警长局完整跑通。
- 至少支持一套带警长竞选的板子进入可玩状态。
- AI 发言体现人设差异，不全部使用同一模板。
- 规则裁决不依赖 LLM 自行判断。
- 10 局自动模拟对局中至少 9 局能正常结束。

## 19. 修订后的产品结论

<callout emoji="✅" background-color="light-green">
新版 MVP 应聚焦“可配置”。游戏板子定义规则，AI 玩家定义人格和表现，LangGraph 根据板子动态编排对局。这样第一版既能快速做出可玩的产品，又能为后续智能体广场、更多角色、更多模型和语音播报留下扩展空间。
</callout>
