# AI狼人杀 - 后台管理系统设计

## 概述

为AI狼人杀游戏设计后台管理系统，支持玩家管理、AI配置、板子配置、游戏记录查看。

## 数据库表设计

### 1. players 表（玩家）

| 字段 | 类型 | 说明 |
|------|------|------|
| player_id | UUID | 主键 |
| name | VARCHAR(50) | 玩家名称（唯一） |
| is_ai | BOOLEAN | 是否AI玩家 |
| agent_id | UUID | 关联AgentProfile，外键可空 |
| created_at | TIMESTAMP | 创建时间 |

### 2. agents 表（AI配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| agent_id | UUID | 主键 |
| name | VARCHAR(50) | AI名称 |
| persona | TEXT | 人格描述 |
| speech_style | VARCHAR(100) | 发言风格 |
| reasoning_level | INT | 推理能力(1-5) |
| deception_level | INT | 伪装能力(1-5) |
| aggression_level | INT | 攻击性(1-5) |
| cooperation_level | INT | 配合度(1-5) |
| enabled | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |

### 3. boards 表（板子）

| 字段 | 类型 | 说明 |
|------|------|------|
| board_id | UUID | 主键 |
| name | VARCHAR(100) | 板子名称 |
| description | TEXT | 板子描述 |
| min_players | INT | 最少玩家数 |
| max_players | INT | 最多玩家数 |
| sheriff_enabled | BOOLEAN | 是否有警长 |
| enabled | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |

### 4. board_roles 表（板子角色关联）

| 字段 | 类型 | 说明 |
|------|------|------|
| board_id | UUID | 外键到boards |
| role_key | VARCHAR(50) | 角色key |
| count | INT | 角色数量 |

### 5. roles_metadata 表（角色元数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| role_key | VARCHAR(50) | 主键 |
| name | VARCHAR(50) | 显示名称 |
| faction | VARCHAR(20) | 阵营（good/wolf/third） |
| description | TEXT | 角色功能描述 |
| night_action | BOOLEAN | 是否有夜晚行动 |
| enabled | BOOLEAN | 是否启用 |

### 6. games 表（游戏）

| 字段 | 类型 | 说明 |
|------|------|------|
| game_id | UUID | 主键 |
| board_id | UUID | 外键到boards |
| status | VARCHAR(20) | 状态（setup/playing/ended） |
| winner | VARCHAR(20) | 胜利方 |
| created_at | TIMESTAMP | 创建时间 |
| ended_at | TIMESTAMP | 结束时间 |

### 7. game_players 表（游戏玩家）

| 字段 | 类型 | 说明 |
|------|------|------|
| game_id | UUID | 外键到games |
| player_id | UUID | 外键到players |
| seat | INT | 座位号 |
| role_key | VARCHAR(50) | 分配的角色 |
| alive | BOOLEAN | 是否存活 |
| sheriff | BOOLEAN | 是否警长 |

## API 设计

### 认证

- `POST /admin/login` - 登录（admin/admin）

### 玩家管理

- `GET /admin/players` - 列出所有玩家
- `POST /admin/players` - 添加玩家（AI或真人）
- `GET /admin/players/{id}` - 查看玩家详情
- `PUT /admin/players/{id}` - 更新玩家
- `DELETE /admin/players/{id}` - 删除玩家

### 角色管理（只读）

- `GET /admin/roles` - 列出所有角色

### 板子管理

- `GET /admin/boards` - 列出所有板子
- `POST /admin/boards` - 添加板子
- `GET /admin/boards/{id}` - 查看板子详情
- `PUT /admin/boards/{id}` - 更新板子
- `DELETE /admin/boards/{id}` - 删除板子
- `POST /admin/boards/{id}/roles` - 添加角色到板子
- `DELETE /admin/boards/{id}/roles/{role_key}` - 从板子移除角色

### AI管理

- `GET /admin/agents` - 列出所有AI
- `POST /admin/agents` - 添加AI
- `GET /admin/agents/{id}` - 查看AI详情
- `PUT /admin/agents/{id}` - 更新AI
- `DELETE /admin/agents/{id}` - 删除AI

### 游戏记录

- `GET /admin/games` - 列出游戏记录
- `GET /admin/games/{id}` - 查看游戏详情

## 技术架构

- FastAPI 后台管理 API
- 与主游戏 API 分离（共用数据库）
- SQLModel/ORM 操作数据库
- 简单 Session-based 认证