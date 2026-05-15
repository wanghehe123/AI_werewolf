# AI 狼人杀游戏 - 数据库建表语句

> 数据库: PostgreSQL
> 生成时间: 2026-05-14

---

## 一、数据库创建

```sql
-- 创建数据库（如果不存在）
CREATE DATABASE ai_werewolf;
```

---

## 二、表结构

### 1. board_records 表（板子配置 - 旧表，保留兼容）

```sql
CREATE TABLE IF NOT EXISTS board_records (
    board_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    config_json JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE
);
```

### 2. llm_providers 表（LLM供应商配置）

```sql
CREATE TABLE IF NOT EXISTS llm_providers (
    provider_id VARCHAR(255) PRIMARY KEY,
    provider_type VARCHAR(50) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    config_json JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE
);
```

### 3. role_model_bindings 表（角色模型绑定）

```sql
CREATE TABLE IF NOT EXISTS role_model_bindings (
    role_key VARCHAR(255) PRIMARY KEY,
    provider_id VARCHAR(255) NOT NULL
);
```

### 4. games 表（游戏记录）

```sql
CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR(255) PRIMARY KEY,
    board_id VARCHAR(255) NOT NULL,
    human_player_id VARCHAR(255) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    day_count INTEGER NOT NULL DEFAULT 1,
    winner VARCHAR(50),
    state_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. game_players 表（游戏玩家关联）

```sql
CREATE TABLE IF NOT EXISTS game_players (
    game_id VARCHAR(255) NOT NULL,
    player_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255),
    seat INTEGER NOT NULL,
    role_key VARCHAR(50) NOT NULL,
    alive BOOLEAN DEFAULT TRUE,
    is_human BOOLEAN DEFAULT FALSE,
    sheriff BOOLEAN DEFAULT FALSE,
    model_provider_id VARCHAR(255) NOT NULL,
    PRIMARY KEY (game_id, player_id)
);
```

### 6. players 表（玩家表 - 新增，支持真人和AI）

```sql
CREATE TABLE IF NOT EXISTS players (
    player_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(50) NOT NULL UNIQUE,
    is_ai BOOLEAN DEFAULT FALSE,
    agent_id VARCHAR(255) REFERENCES agent_profiles(agent_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_players_name ON players(name);
```

### 7. agent_profiles 表（AI配置表 - 扩展）

```sql
CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(50) NOT NULL,
    avatar_url VARCHAR(500),
    avatar_prompt TEXT,
    profile_json JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    persona TEXT DEFAULT '',
    speech_style VARCHAR(100) DEFAULT '',
    reasoning_level INTEGER DEFAULT 3 CHECK (reasoning_level BETWEEN 1 AND 5),
    deception_level INTEGER DEFAULT 3 CHECK (deception_level BETWEEN 1 AND 5),
    aggression_level INTEGER DEFAULT 3 CHECK (aggression_level BETWEEN 1 AND 5),
    cooperation_level INTEGER DEFAULT 3 CHECK (cooperation_level BETWEEN 1 AND 5),
    risk_preference VARCHAR(20) DEFAULT 'balanced',
    memory_style VARCHAR(50) DEFAULT 'focus_on_votes',
    default_model_provider_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_profiles_name ON agent_profiles(name);
```

### 8. boards 表（板子配置 - 新表）

```sql
CREATE TABLE IF NOT EXISTS boards (
    board_id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    min_players INTEGER DEFAULT 6,
    max_players INTEGER DEFAULT 12,
    sheriff_enabled BOOLEAN DEFAULT TRUE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_boards_name ON boards(name);
```

### 9. board_roles 表（板子角色关联）

```sql
CREATE TABLE IF NOT EXISTS board_roles (
    board_id VARCHAR(255) NOT NULL REFERENCES boards(board_id) ON DELETE CASCADE,
    role_key VARCHAR(50) NOT NULL,
    count INTEGER DEFAULT 1 CHECK (count > 0),
    PRIMARY KEY (board_id, role_key)
);
```

### 10. role_metadata 表（角色元数据）

```sql
CREATE TABLE IF NOT EXISTS role_metadata (
    role_key VARCHAR(50) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    faction VARCHAR(20) NOT NULL CHECK (faction IN ('good', 'wolf', 'third')),
    description TEXT,
    night_action BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE
);
```

---

## 三、初始化数据

### 1. 插入预置角色数据

```sql
INSERT INTO role_metadata (role_key, name, faction, description, night_action) VALUES
    ('werewolf', '狼人', 'wolf', '每晚可以击杀一名玩家', TRUE),
    ('seer', '预言家', 'good', '每晚可以查验一名玩家身份', TRUE),
    ('witch', '女巫', 'good', '有一瓶解药和一瓶毒药', TRUE),
    ('hunter', '猎人', 'good', '死后可以开枪带走一人', TRUE),
    ('villager', '村民', 'good', '没有任何特殊能力', FALSE),
    ('guardian', '守卫', 'good', '每晚可以守护一名玩家', TRUE),
    ('idiot', '白痴', 'good', '被投票出局不会死亡', FALSE),
    ('wolf_king', '白狼王', 'wolf', '可以自爆带走一名玩家', TRUE),
    ('knight', '骑士', 'good', '可以决斗一名玩家', TRUE),
    ('wolf_beauty', '狼美人', 'wolf', '魅惑一名玩家，死亡时带走', TRUE)
ON CONFLICT (role_key) DO NOTHING;
```

### 2. 插入预置板子数据（示例）

```sql
-- 插入板子
INSERT INTO boards (board_id, name, description, min_players, max_players, sheriff_enabled) VALUES
    ('board_6_beginner', '6人新手局', '适合新手的6人局', 6, 6, FALSE),
    ('board_8_standard', '8人预女猎', '标准8人局', 8, 8, TRUE),
    ('board_9_advanced', '9人进阶局', '9人进阶配置', 9, 9, TRUE)
ON CONFLICT (board_id) DO NOTHING;

-- 板子角色配置
INSERT INTO board_roles (board_id, role_key, count) VALUES
    -- 6人新手局: 狼人x2, 预言家x1, 村民x3
    ('board_6_beginner', 'werewolf', 2),
    ('board_6_beginner', 'seer', 1),
    ('board_6_beginner', 'villager', 3),
    -- 8人标准局: 狼人x2, 预言家x1, 女巫x1, 猎人x1, 村民x3
    ('board_8_standard', 'werewolf', 2),
    ('board_8_standard', 'seer', 1),
    ('board_8_standard', 'witch', 1),
    ('board_8_standard', 'hunter', 1),
    ('board_8_standard', 'villager', 3),
    -- 9人进阶局: 狼人x3, 预言家x1, 女巫x1, 猎人x1, 村民x3
    ('board_9_advanced', 'werewolf', 3),
    ('board_9_advanced', 'seer', 1),
    ('board_9_advanced', 'witch', 1),
    ('board_9_advanced', 'hunter', 1),
    ('board_9_advanced', 'villager', 3)
ON CONFLICT (board_id, role_key) DO NOTHING;
```

### 3. 插入预置AI玩家（示例）

```sql
INSERT INTO agent_profiles (agent_id, name, persona, speech_style, reasoning_level, deception_level, aggression_level, cooperation_level) VALUES
    ('agent_lin_ye', '林野', '理性冷静，善于分析局势', '简洁有力', 5, 3, 2, 4),
    ('agent_xiao_man', '小满', '温和友善，喜欢配合', '亲切温和', 3, 2, 1, 5),
    ('agent_qing_shan', '青山', '沉稳老练，逻辑清晰', '稳重有条理', 5, 4, 3, 3),
    ('agent_a_kai', '阿凯', '活跃外向，喜欢发言', '活泼直接', 3, 3, 4, 3),
    ('agent_mo_yu', '墨雨', '神秘深沉，话不多但精准', '简洁犀利', 4, 5, 2, 2),
    ('agent_duo_duo', '多多', '新手AI，热情好客', '热情洋溢', 2, 2, 3, 4)
ON CONFLICT (agent_id) DO NOTHING;
```

---

## 四、表结构汇总

| 表名 | 说明 | 主键 | 外键 |
|------|------|------|------|
| `players` | 玩家（真人和AI） | player_id | agent_id → agent_profiles |
| `agent_profiles` | AI配置 | agent_id | - |
| `boards` | 板子配置 | board_id | - |
| `board_roles` | 板子角色关联 | board_id + role_key | board_id → boards |
| `role_metadata` | 角色元数据 | role_key | - |
| `games` | 游戏记录 | game_id | board_id |
| `game_players` | 游戏玩家 | game_id + player_id | game_id → games, player_id → players |
| `board_records` | 旧板子配置（兼容） | board_id | - |
| `llm_providers` | LLM供应商配置 | provider_id | - |
| `role_model_bindings` | 角色模型绑定 | role_key | provider_id → llm_providers |

---

## 五、ER 关系图

```
┌─────────────────┐     ┌─────────────────┐
│  agent_profiles │─────┤     players      │
│     (AI配置)     │     │    (玩家)        │
└─────────────────┘     └─────────────────┘
                              │
                              │ game_players
                              │
┌─────────────────┐     ┌─────┴─────┐     ┌─────────────────┐
│     boards      │─────┤   games   │◀────│  game_players   │
│    (板子)        │     │  (游戏)   │     │   (游戏玩家)     │
└────────┬────────┘     └───────────┘     └─────────────────┘
         │
         │ board_roles
         │
┌────────┴────────┐
│  role_metadata   │
│   (角色元数据)    │
└──────────────────┘
```