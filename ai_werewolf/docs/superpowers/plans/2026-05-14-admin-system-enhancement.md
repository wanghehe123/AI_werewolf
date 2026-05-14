# AI狼人杀后台管理系统增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 AI 狼人杀后端与 React 前端基础上，补齐一版可真实使用的后台管理系统：登录后可管理玩家、AI 人设、板子、角色元数据、LLM 角色绑定，并查看游戏记录。

**Architecture:** 后台系统采用“后端管理 API + 前端管理控制台”的双层结构。后端继续使用 FastAPI、SQLModel、PostgreSQL、统一响应格式 `{ code, message, data }`，管理端 API 放在 `ai_werewolf/api/admin/` 并通过 session cookie 保护；前端在现有 Vite React 工程中增加 `/admin/*` 路由，复用同一 API client，但开启 `credentials: "include"` 支持登录态。

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Pydantic v2, React, Vite, TypeScript, Vitest, Testing Library.

---

## 1. 当前状态

### 已有能力

- 已存在统一响应工具：`ai_werewolf/api/responses.py`
- 已存在后台认证 API：`ai_werewolf/api/admin/auth.py`
  - `POST /admin/login`
  - `POST /admin/logout`
  - `GET /admin/session`
- 已存在部分后台数据模型：`ai_werewolf/storage/models.py`
  - `Player`
  - `AgentProfileRecord`
  - `Board`
  - `BoardRole`
  - `RoleMetadata`
  - 游戏持久化相关 `GameRecord` / `GamePlayerRecord`
- 已存在 repository 雏形：`ai_werewolf/storage/admin_repository.py`
  - `PlayerRepository`
  - `AgentRepository`
  - `BoardRepository`
  - `RoleMetadataRepository`
- 已有测试：
  - `ai_werewolf/tests/api/admin/test_auth.py`
  - `ai_werewolf/tests/storage/test_admin_repository.py`
  - `ai_werewolf/tests/storage/test_models.py`

### 当前缺口

- `main.py` 尚未统一注册完整 admin router；当前只有 `auth.py` 文件，缺少聚合路由。
- 缺少受保护的后台 API：
  - 玩家管理
  - AI 人设管理
  - 板子管理
  - 角色元数据
  - 游戏记录
- 现有 `BoardRole` 模型主键设计需要修正为 `(board_id, role_key)` 复合主键，否则多个板子无法稳定复用同一个 `role_key`。
- `AgentProfileRecord` 与领域层 `AgentProfile` 字段尚未完全对齐，缺少头像、风险偏好、记忆风格等后台编辑字段。
- 现有前端只有玩家大厅与游戏桌，没有后台入口、登录页、表格页、编辑表单。
- 后台 API 与玩家侧 `/admin/agents`、`/admin/boards` 的旧临时接口存在职责重叠，需要统一归并到 `ai_werewolf/api/admin/*`。

---

## 2. 产品边界

### MVP 必做

- 管理员登录、登出、会话检查。
- 玩家管理：列表、新增、编辑、删除。
- AI 人设管理：列表、新增、编辑、启停、删除。
- 板子管理：列表、新增、编辑、启停、删除、配置角色数量。
- 角色元数据：列表只读，支持初始化默认角色数据。
- LLM 配置联动：AI 人设可选择默认模型 provider，角色可绑定模型 provider。
- 游戏记录：列表、详情、查看玩家座位/身份/模型绑定/胜负结果。

### MVP 不做

- 多管理员、RBAC、复杂权限。
- 操作审计日志。
- 后台实时监控大屏。
- 富文本头像提示词编辑器。
- 复杂迁移工具。MVP 使用 `SQLModel.metadata.create_all`，后续再接 Alembic。

---

## 3. 后端接口设计

所有接口返回统一格式：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

错误也使用同一结构：

```json
{
  "code": 401,
  "message": "未登录",
  "data": null
}
```

### 3.1 Auth

| Method | Path | 说明 |
| --- | --- | --- |
| POST | `/admin/login` | 登录，设置 `session_id` cookie |
| POST | `/admin/logout` | 登出，清除 cookie |
| GET | `/admin/session` | 检查当前登录态 |

### 3.2 Players

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/players` | 玩家列表 |
| POST | `/admin/players` | 新增玩家 |
| GET | `/admin/players/{player_id}` | 玩家详情 |
| PUT | `/admin/players/{player_id}` | 更新玩家 |
| DELETE | `/admin/players/{player_id}` | 删除玩家 |

### 3.3 Agents

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/agents` | AI 人设列表 |
| POST | `/admin/agents` | 新增 AI 人设 |
| GET | `/admin/agents/{agent_id}` | AI 人设详情 |
| PUT | `/admin/agents/{agent_id}` | 更新 AI 人设 |
| DELETE | `/admin/agents/{agent_id}` | 删除 AI 人设 |

### 3.4 Boards

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/boards` | 板子列表 |
| POST | `/admin/boards` | 新增板子 |
| GET | `/admin/boards/{board_id}` | 板子详情 |
| PUT | `/admin/boards/{board_id}` | 更新板子基础信息 |
| PUT | `/admin/boards/{board_id}/roles` | 整体替换板子角色配置 |
| DELETE | `/admin/boards/{board_id}` | 删除板子 |

说明：板子角色推荐用“整体替换”而不是逐条增删，便于前端编辑器保存和后端一次性校验人数。

### 3.5 Roles

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/roles` | 角色元数据列表 |
| POST | `/admin/roles/seed` | 初始化默认角色元数据，幂等 |

### 3.6 LLM

复用现有：

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/llm/providers` | 模型 provider 列表 |
| POST | `/admin/llm/providers` | 新增/更新 provider |
| GET | `/admin/llm/role-bindings` | 角色模型绑定列表 |
| POST | `/admin/llm/role-bindings` | 新增/更新角色模型绑定 |

### 3.7 Games

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/games` | 游戏记录列表 |
| GET | `/admin/games/{game_id}` | 游戏详情 |

---

## 4. 前端后台设计

### 路由

| Route | 页面 |
| --- | --- |
| `/admin/login` | 登录页 |
| `/admin` | 后台首页/概览 |
| `/admin/players` | 玩家管理 |
| `/admin/agents` | AI 人设管理 |
| `/admin/boards` | 板子管理 |
| `/admin/roles` | 角色元数据 |
| `/admin/llm` | 模型配置 |
| `/admin/games` | 游戏记录 |
| `/admin/games/:gameId` | 游戏详情 |

### 页面结构

- 左侧导航：概览、玩家、AI 人设、板子、角色、模型、游戏记录。
- 顶部栏：当前登录状态、登出按钮、API 状态。
- 内容区：表格 + 右侧抽屉/弹窗编辑表单。

### 交互原则

- 后台偏“配置工具”，不做营销式大屏。
- 表格优先显示可扫描字段：名称、启用状态、更新时间/创建时间、核心配置摘要。
- 编辑板子时，角色数量以 stepper/input 呈现，并实时显示“总人数”和“角色合法性”。
- AI 人设编辑要能配置：
  - 名称
  - 虚拟头像 URL / 头像提示词
  - 人格描述
  - 发言风格
  - 推理/伪装/攻击/合作数值
  - 风险偏好
  - 记忆风格
  - 默认模型 provider
  - 启用状态

---

## 5. 数据模型修正

### AgentProfileRecord 目标字段

`ai_werewolf/storage/models.py`

```python
class AgentProfileRecord(SQLModel, table=True):
    __tablename__ = "agent_profiles"

    agent_id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(index=True)
    avatar_url: str | None = None
    avatar_prompt: str | None = None
    persona: str
    speech_style: str
    reasoning_level: int = Field(default=3, ge=1, le=5)
    deception_level: int = Field(default=3, ge=1, le=5)
    aggression_level: int = Field(default=3, ge=1, le=5)
    cooperation_level: int = Field(default=3, ge=1, le=5)
    risk_preference: str = Field(default="balanced")
    memory_style: str = Field(default="focus_on_votes")
    default_model_provider_id: str | None = None
    profile_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### BoardRole 目标字段

```python
class BoardRole(SQLModel, table=True):
    __tablename__ = "board_roles"

    board_id: str = Field(primary_key=True, foreign_key="boards.board_id")
    role_key: str = Field(primary_key=True)
    count: int = Field(default=1, ge=1)
    board: Board | None = Relationship(back_populates="roles")
```

---

## 6. Implementation Tasks

### Task 1: 注册后台聚合路由与认证依赖

**Files:**
- Create: `ai_werewolf/api/admin/router.py`
- Create: `ai_werewolf/api/admin/dependencies.py`
- Modify: `ai_werewolf/main.py`
- Test: `ai_werewolf/tests/api/admin/test_router.py`

- [ ] **Step 1: Write failing test**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_session_route_is_registered():
    client = TestClient(create_app())

    response = client.get("/admin/session")

    assert response.status_code == 200
    assert response.json()["code"] == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_router.py -q`

Expected before implementation: FAIL because `/admin/session` is not registered from the aggregate admin router.

- [ ] **Step 3: Implement admin router**

```python
# ai_werewolf/api/admin/router.py
from fastapi import APIRouter

from ai_werewolf.api.admin.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
```

```python
# ai_werewolf/api/admin/dependencies.py
from typing import Optional

from fastapi import Cookie, HTTPException

from ai_werewolf.api.admin.auth import verify_session


def require_admin_session(session_id: Optional[str] = Cookie(None)) -> None:
    if not verify_session(session_id):
        raise HTTPException(status_code=401, detail="未登录")
```

In `ai_werewolf/main.py`:

```python
from ai_werewolf.api.admin.router import router as admin_router

app.include_router(admin_router)
```

- [ ] **Step 4: Run test**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_router.py ai_werewolf/tests/api/admin/test_auth.py -q`

Expected: PASS.

---

### Task 2: 修正后台数据模型

**Files:**
- Modify: `ai_werewolf/storage/models.py`
- Test: `ai_werewolf/tests/storage/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
from ai_werewolf.storage.models import AgentProfileRecord, BoardRole


def test_agent_profile_record_contains_admin_editable_fields():
    agent = AgentProfileRecord(
        name="林野",
        persona="理性谨慎",
        speech_style="短句克制",
        avatar_prompt="冷静的年轻侦探",
        risk_preference="balanced",
        memory_style="focus_on_votes",
        default_model_provider_id="deepseek",
    )

    assert agent.agent_id
    assert agent.avatar_prompt == "冷静的年轻侦探"
    assert agent.default_model_provider_id == "deepseek"


def test_board_role_uses_board_and_role_as_identity():
    role = BoardRole(board_id="board_a", role_key="werewolf", count=2)

    assert role.board_id == "board_a"
    assert role.role_key == "werewolf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/storage/test_models.py -q`

Expected: FAIL because `AgentProfileRecord` is missing several admin fields and `BoardRole.board_id` is not a primary key.

- [ ] **Step 3: Implement model fields**

Update `AgentProfileRecord` and `BoardRole` to match section 5.

- [ ] **Step 4: Run model tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/storage/test_models.py -q`

Expected: PASS.

---

### Task 3: 补齐后台 Repository

**Files:**
- Modify: `ai_werewolf/storage/admin_repository.py`
- Test: `ai_werewolf/tests/storage/test_admin_repository.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import MagicMock

from ai_werewolf.storage.admin_repository import AgentRepository, BoardRepository


def test_agent_repository_updates_enabled_and_model_provider():
    session = MagicMock()
    agent = MagicMock()
    session.get.return_value = agent
    repo = AgentRepository(session)

    updated = repo.update("agent_1", enabled=False, default_model_provider_id="glm")

    assert updated is agent
    assert agent.enabled is False
    assert agent.default_model_provider_id == "glm"
    session.commit.assert_called_once()


def test_board_repository_replaces_roles_atomically():
    session = MagicMock()
    session.exec.return_value.all.return_value = [MagicMock()]
    repo = BoardRepository(session)

    roles = repo.replace_roles("board_1", [{"role_key": "werewolf", "count": 2}])

    assert len(roles) == 1
    assert roles[0].role_key == "werewolf"
    assert roles[0].count == 2
    session.commit.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/storage/test_admin_repository.py -q`

Expected: FAIL because `replace_roles` does not exist.

- [ ] **Step 3: Implement repository methods**

Add:

```python
def replace_roles(self, board_id: str, roles: list[dict]) -> list[BoardRole]:
    existing = list(self.session.exec(select(BoardRole).where(BoardRole.board_id == board_id)).all())
    for role in existing:
        self.session.delete(role)
    new_roles = [BoardRole(board_id=board_id, role_key=item["role_key"], count=item["count"]) for item in roles]
    for role in new_roles:
        self.session.add(role)
    self.session.commit()
    return new_roles
```

- [ ] **Step 4: Run repository tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/storage/test_admin_repository.py -q`

Expected: PASS.

---

### Task 4: 玩家管理 API

**Files:**
- Create: `ai_werewolf/api/admin/players.py`
- Modify: `ai_werewolf/api/admin/router.py`
- Test: `ai_werewolf/tests/api/admin/test_players.py`

- [ ] **Step 1: Write failing API test**

```python
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_admin_player_crud():
    client = TestClient(create_app())
    cookies = login(client)

    created = client.post("/admin/players", json={"name": "测试玩家", "is_ai": False}, cookies=cookies)
    assert created.status_code == 201
    player = created.json()["data"]
    assert player["name"] == "测试玩家"

    listed = client.get("/admin/players", cookies=cookies)
    assert any(item["player_id"] == player["player_id"] for item in listed.json()["data"])

    updated = client.put(f"/admin/players/{player['player_id']}", json={"name": "新名字"}, cookies=cookies)
    assert updated.json()["data"]["name"] == "新名字"

    deleted = client.delete(f"/admin/players/{player['player_id']}", cookies=cookies)
    assert deleted.json()["code"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_players.py -q`

Expected: FAIL because `players.py` route does not exist.

- [ ] **Step 3: Implement API**

Implement request DTOs with Pydantic and endpoints using `PlayerRepository`. All endpoints depend on `require_admin_session` and return `success_response`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_players.py -q`

Expected: PASS.

---

### Task 5: AI 人设管理 API

**Files:**
- Create: `ai_werewolf/api/admin/agents.py`
- Modify: `ai_werewolf/api/admin/router.py`
- Test: `ai_werewolf/tests/api/admin/test_agents.py`

- [ ] **Step 1: Write failing API test**

```python
def test_admin_agent_crud(client):
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}

    payload = {
        "name": "冷静侦探",
        "avatar_url": None,
        "avatar_prompt": "冷静的年轻侦探，暗色背景",
        "persona": "理性、谨慎、会复盘票型",
        "speech_style": "短句克制",
        "reasoning_level": 5,
        "deception_level": 2,
        "aggression_level": 2,
        "cooperation_level": 4,
        "risk_preference": "balanced",
        "memory_style": "focus_on_votes",
        "default_model_provider_id": "deepseek",
        "enabled": True,
    }

    created = client.post("/admin/agents", json=payload, cookies=cookies)
    assert created.status_code == 201
    agent = created.json()["data"]
    assert agent["name"] == "冷静侦探"

    updated = client.put(f"/admin/agents/{agent['agent_id']}", json={"enabled": False}, cookies=cookies)
    assert updated.json()["data"]["enabled"] is False
```

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_agents.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement API**

Implement CRUD with explicit request models. Clamp numeric traits to 1-5 via Pydantic `Field(ge=1, le=5)`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_agents.py -q`

Expected: PASS.

---

### Task 6: 板子管理 API 与校验

**Files:**
- Create: `ai_werewolf/api/admin/boards.py`
- Modify: `ai_werewolf/api/admin/router.py`
- Test: `ai_werewolf/tests/api/admin/test_boards.py`

- [ ] **Step 1: Write failing API test**

```python
def test_admin_board_create_and_replace_roles(client):
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}

    created = client.post(
        "/admin/boards",
        json={
            "name": "6人新手局后台版",
            "description": "2狼1预3民",
            "min_players": 6,
            "max_players": 6,
            "sheriff_enabled": False,
            "enabled": True,
        },
        cookies=cookies,
    )
    board = created.json()["data"]

    roles = client.put(
        f"/admin/boards/{board['board_id']}/roles",
        json={"roles": [{"role_key": "werewolf", "count": 2}, {"role_key": "seer", "count": 1}, {"role_key": "villager", "count": 3}]},
        cookies=cookies,
    )

    assert roles.json()["code"] == 0
    assert sum(item["count"] for item in roles.json()["data"]) == 6
```

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_boards.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement API**

Implement board CRUD and `PUT /admin/boards/{board_id}/roles`. Validate:

- `min_players <= max_players`
- role `count >= 1`
- total role count between `min_players` and `max_players`
- `role_key` exists in `RoleMetadata` or built-in role registry

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_boards.py -q`

Expected: PASS.

---

### Task 7: 角色元数据初始化与 API

**Files:**
- Create: `ai_werewolf/seeds/admin_roles.py`
- Create: `ai_werewolf/api/admin/roles.py`
- Modify: `ai_werewolf/api/admin/router.py`
- Test: `ai_werewolf/tests/api/admin/test_roles.py`

- [ ] **Step 1: Write failing test**

```python
def test_admin_roles_seed_and_list(client):
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}

    seeded = client.post("/admin/roles/seed", cookies=cookies)
    assert seeded.json()["code"] == 0

    listed = client.get("/admin/roles", cookies=cookies)
    role_keys = {role["role_key"] for role in listed.json()["data"]}
    assert {"werewolf", "seer", "witch", "hunter", "villager"}.issubset(role_keys)
```

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_roles.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement seed data**

Seed roles:

- `werewolf`
- `seer`
- `witch`
- `hunter`
- `villager`
- `guard`
- `idiot`
- `wolf_king`
- `knight`
- `wolf_beauty`

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_roles.py -q`

Expected: PASS.

---

### Task 8: 游戏记录后台 API

**Files:**
- Create: `ai_werewolf/api/admin/games.py`
- Modify: `ai_werewolf/api/admin/router.py`
- Test: `ai_werewolf/tests/api/admin/test_games.py`

- [ ] **Step 1: Write failing test**

```python
def test_admin_games_list_requires_login(client):
    response = client.get("/admin/games")

    assert response.status_code == 401
    assert response.json()["code"] == 401
```

```python
def test_admin_games_list_after_login(client):
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}

    response = client.get("/admin/games", cookies=cookies)

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert isinstance(response.json()["data"], list)
```

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_games.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement API**

Use `GameRecord` and `GamePlayerRecord` to return:

- `game_id`
- `board_id`
- `phase`
- `day_count`
- `winner`
- `human_player_id`
- player count

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests/api/admin/test_games.py -q`

Expected: PASS.

---

### Task 9: 前端后台 API client

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Test: `frontend/src/adminApi.test.ts`

- [ ] **Step 1: Write failing frontend test**

```typescript
import { describe, expect, it, vi, afterEach } from "vitest";
import { adminLogin, fetchAdminPlayers } from "./api";

describe("admin api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends credentials for admin requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, message: "ok", data: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchAdminPlayers("http://api.local");

    expect(fetchMock).toHaveBeenCalledWith("http://api.local/admin/players", { credentials: "include" });
  });
});
```

- [ ] **Step 2: Run test**

Run: `cd frontend && npm test -- --run src/adminApi.test.ts`

Expected: FAIL.

- [ ] **Step 3: Implement admin client functions**

Add:

- `adminLogin(username, password)`
- `adminLogout()`
- `fetchAdminSession()`
- `fetchAdminPlayers()`
- `fetchAdminAgents()`
- `fetchAdminBoards()`
- `fetchAdminRoles()`
- `fetchAdminGames()`

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- --run src/adminApi.test.ts`

Expected: PASS.

---

### Task 10: 前端后台框架与登录页

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/admin/AdminLayout.tsx`
- Create: `frontend/src/admin/AdminLoginPage.tsx`
- Create: `frontend/src/admin/AdminDashboardPage.tsx`
- Test: `frontend/src/admin/AdminLoginPage.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AdminLoginPage } from "./AdminLoginPage";

it("submits admin credentials", async () => {
  const login = vi.fn().mockResolvedValue(undefined);
  render(<AdminLoginPage login={login} />);

  await userEvent.type(screen.getByLabelText("用户名"), "admin");
  await userEvent.type(screen.getByLabelText("密码"), "admin");
  await userEvent.click(screen.getByRole("button", { name: "登录" }));

  expect(login).toHaveBeenCalledWith("admin", "admin");
});
```

- [ ] **Step 2: Run test**

Run: `cd frontend && npm test -- --run src/admin/AdminLoginPage.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Implement pages**

Implement a quiet admin console style:

- compact dark sidebar
- dense table content
- no marketing hero
- no nested cards
- clear disabled/loading/error states

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- --run src/admin/AdminLoginPage.test.tsx`

Expected: PASS.

---

### Task 11: 前端管理页面 MVP

**Files:**
- Create: `frontend/src/admin/AdminPlayersPage.tsx`
- Create: `frontend/src/admin/AdminAgentsPage.tsx`
- Create: `frontend/src/admin/AdminBoardsPage.tsx`
- Create: `frontend/src/admin/AdminRolesPage.tsx`
- Create: `frontend/src/admin/AdminGamesPage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/admin/AdminPages.test.tsx`

- [ ] **Step 1: Write failing render test**

```tsx
import { render, screen } from "@testing-library/react";
import { AdminAgentsPage } from "./AdminAgentsPage";

it("renders agent management table", () => {
  render(
    <AdminAgentsPage
      agents={[{ agent_id: "agent_1", name: "林野", enabled: true, persona: "理性", speech_style: "短句" }]}
      onRefresh={() => undefined}
    />
  );

  expect(screen.getByText("林野")).toBeInTheDocument();
  expect(screen.getByText("理性")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test**

Run: `cd frontend && npm test -- --run src/admin/AdminPages.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Implement pages**

Each page should include:

- title
- primary action button
- table
- empty state
- loading state
- error state
- minimal edit form modal/drawer for players, agents, boards

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- --run src/admin/AdminPages.test.tsx`

Expected: PASS.

---

### Task 12: 集成验证

**Files:**
- Modify: `README.md` if present, otherwise create `docs/admin-system-runbook.md`

- [ ] **Step 1: Run backend tests**

Run: `.venv/bin/python -m pytest ai_werewolf/tests tests/api -q`

Expected: all tests pass.

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm test -- --run`

Expected: all tests pass.

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`

Expected: Vite build succeeds.

- [ ] **Step 4: Manual smoke test**

Run backend:

```bash
AI_WEREWOLF_JDBC_URL=jdbc:postgresql://127.0.0.1:5432/postgres .venv/bin/python -m uvicorn ai_werewolf.main:app --host 127.0.0.1 --port 8000
```

Run frontend:

```bash
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

Smoke path:

1. Open `http://127.0.0.1:5173/admin/login`
2. Login with `admin/admin`
3. Open players page
4. Create one player
5. Open agents page
6. Create or disable one AI persona
7. Open boards page
8. Create one board and configure roles
9. Open roles page
10. Seed roles and confirm role list appears
11. Open games page and confirm it renders an empty list or persisted games

---

## 7. Execution Order

Recommended order:

1. Task 1: Router and auth dependency
2. Task 2: Data model corrections
3. Task 3: Repository completeness
4. Task 4: Players API
5. Task 5: Agents API
6. Task 6: Boards API
7. Task 7: Roles API and seed
8. Task 8: Games API
9. Task 9: Frontend admin API client
10. Task 10: Admin layout and login
11. Task 11: Admin pages
12. Task 12: Integration verification

Backend tasks should complete before frontend pages except Task 9 can begin once API contracts are stable.

---

## 8. Self-Review

- Spec coverage: covers original spec modules: players, agents, boards, board roles, roles metadata, games, session auth.
- Current-state alignment: references actual existing files and notes that model/repository/auth are partially complete.
- Scope control: excludes RBAC, audit, dashboard, Alembic, rich editor from MVP.
- Response consistency: all API endpoints use `{ code, message, data }`.
- Frontend alignment: keeps player game UI untouched and adds `/admin/*` routes inside existing React app.
- TDD coverage: every implementation task starts with failing tests and has explicit verification commands.
