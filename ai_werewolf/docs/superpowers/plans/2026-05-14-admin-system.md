# 后台管理系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为AI狼人杀游戏实现后台管理系统，包含玩家管理、AI管理、板子管理、角色元数据、游戏记录查询功能。

**Architecture:**
- 在现有 `api/` 目录下创建 `admin/` 子目录，包含所有后台管理API
- 新增 `storage/models.py` 中扩展数据库模型（新增 Player、RoleMetadata 等表）
- 复用现有 `api/responses.py` 的统一响应格式
- 简单 Session-based 认证（登录后设置 session cookie）

**Tech Stack:** FastAPI, SQLModel, PostgreSQL, Session-based auth

---

## 文件结构

```
ai_werewolf/
├── storage/
│   ├── models.py              # 扩展：新增 Player, BoardRole, RoleMetadata 模型
│   └── repositories.py       # 新增：admin 相关的 repository
├── api/
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── router.py         # 创建：admin API router
│   │   ├── auth.py           # 认证相关：login, logout
│   │   ├── players.py        # 玩家管理 API
│   │   ├── agents.py         # AI管理 API
│   │   ├── boards.py         # 板子管理 API
│   │   ├── roles.py          # 角色元数据 API（只读）
│   │   └── games.py          # 游戏记录 API
│   ├── responses.py           # 已有：统一响应格式
│   └── main.py               # 注册 admin router
└── tests/
    └── api/
        └── admin/
            ├── test_auth.py
            ├── test_players.py
            ├── test_agents.py
            └── test_boards.py
```

---

## Task 1: 扩展数据库模型

**Files:**
- Modify: `ai_werewolf/storage/models.py:1-54`
- Test: `tests/storage/test_models.py` (new)

- [ ] **Step 1: 创建失败的测试**

```python
# tests/storage/test_models.py
from ai_werewolf.storage.models import Player, RoleMetadata, Board, BoardRole

def test_player_can_be_created():
    player = Player(name="测试玩家", is_ai=False)
    assert player.name == "测试玩家"
    assert player.is_ai == False
    assert player.player_id is not None

def test_role_metadata_fields():
    role = RoleMetadata(role_key="werewolf", name="狼人", faction="wolf", description="夜里杀人")
    assert role.role_key == "werewolf"
    assert role.faction == "wolf"

def test_board_has_roles():
    board = Board(name="测试板子", min_players=6, max_players=8)
    role = BoardRole(role_key="werewolf", count=2)
    board.roles.append(role)
    assert len(board.roles) == 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/storage/test_models.py -v`
Expected: FAIL - ImportError: cannot import 'Player' from 'ai_werewolf.storage.models'

- [ ] **Step 3: 扩展 models.py**

在 `storage/models.py` 末尾添加：

```python
# 玩家表（支持真人和AI）
class Player(SQLModel, table=True):
    player_id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(index=True, unique=True)
    is_ai: bool = Field(default=False)
    agent_id: str | None = Field(default=None, foreign_key="agent_profiles.agent_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# AI配置表（扩展现有 AgentProfileRecord）
class AgentProfileRecord(SQLModel, table=True):
    agent_id: str = Field(primary_key=True)
    name: str
    profile_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True
    # 新增字段
    persona: str | None = None
    speech_style: str | None = None
    reasoning_level: int = Field(default=3)
    deception_level: int = Field(default=3)
    aggression_level: int = Field(default=3)
    cooperation_level: int = Field(default=3)

# 板子表
class Board(SQLModel, table=True):
    board_id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(index=True)
    description: str | None = None
    min_players: int = Field(default=6)
    max_players: int = Field(default=12)
    sheriff_enabled: bool = Field(default=True)
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 板子角色关联表
class BoardRole(SQLModel, table=True):
    board_id: str = Field(primary_key=True, foreign_key="boards.board_id")
    role_key: str = Field(primary_key=True)
    count: int = Field(default=1)

# 角色元数据表（只读配置）
class RoleMetadata(SQLModel, table=True):
    role_key: str = Field(primary_key=True)
    name: str
    faction: str  # good/wolf/third
    description: str | None = None
    night_action: bool = Field(default=False)
    enabled: bool = Field(default=True)
```

- [ ] **Step 4: 添加必要的 import**

在 `models.py` 顶部添加：
```python
import uuid
from datetime import datetime
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/storage/test_models.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add storage/models.py tests/storage/test_models.py
git commit -m "feat: add Player, Board, BoardRole, RoleMetadata models"
```

---

## Task 2: 创建 Repository 层

**Files:**
- Create: `ai_werewolf/storage/admin_repository.py`
- Test: `tests/storage/test_admin_repository.py` (new)

- [ ] **Step 1: 创建失败的测试**

```python
# tests/storage/test_admin_repository.py
from ai_werewolf.storage.admin_repository import PlayerRepository, BoardRepository

def test_player_repository_crud():
    repo = PlayerRepository(session=mock_session)
    # 创建
    player = repo.create(name="测试", is_ai=False)
    assert player.name == "测试"
    # 查询
    found = repo.get_by_name("测试")
    assert found.name == "测试"
    # 列表
    all_players = repo.list_all()
    assert len(all_players) >= 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/storage/test_admin_repository.py -v`
Expected: FAIL - cannot import from 'ai_werewolf.storage.admin_repository'

- [ ] **Step 3: 创建 admin_repository.py**

```python
# ai_werewolf/storage/admin_repository.py
from typing import Optional
from sqlmodel import Session, select

from ai_werewolf.storage.models import Player, AgentProfileRecord, Board, BoardRole, RoleMetadata

class PlayerRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, is_ai: bool, agent_id: str | None = None) -> Player:
        player = Player(name=name, is_ai=is_ai, agent_id=agent_id)
        self.session.add(player)
        self.session.commit()
        self.session.refresh(player)
        return player

    def get_by_id(self, player_id: str) -> Player | None:
        return self.session.get(Player, player_id)

    def get_by_name(self, name: str) -> Player | None:
        return self.session.exec(select(Player).where(Player.name == name)).first()

    def list_all(self) -> list[Player]:
        return list(self.session.exec(select(Player)).all())

    def update(self, player_id: str, name: str | None = None, is_ai: bool | None = None, agent_id: str | None = None) -> Player | None:
        player = self.get_by_id(player_id)
        if not player:
            return None
        if name is not None:
            player.name = name
        if is_ai is not None:
            player.is_ai = is_ai
        if agent_id is not None:
            player.agent_id = agent_id
        self.session.commit()
        self.session.refresh(player)
        return player

    def delete(self, player_id: str) -> bool:
        player = self.get_by_id(player_id)
        if not player:
            return False
        self.session.delete(player)
        self.session.commit()
        return True


class AgentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, persona: str, speech_style: str, reasoning_level: int = 3,
               deception_level: int = 3, aggression_level: int = 3, cooperation_level: int = 3) -> AgentProfileRecord:
        agent = AgentProfileRecord(
            name=name,
            profile_json={},
            persona=persona,
            speech_style=speech_style,
            reasoning_level=reasoning_level,
            deception_level=deception_level,
            aggression_level=aggression_level,
            cooperation_level=cooperation_level,
            enabled=True
        )
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def get_by_id(self, agent_id: str) -> AgentProfileRecord | None:
        return self.session.get(AgentProfileRecord, agent_id)

    def list_all(self) -> list[AgentProfileRecord]:
        return list(self.session.exec(select(AgentProfileRecord)).all())

    def update(self, agent_id: str, **kwargs) -> AgentProfileRecord | None:
        agent = self.get_by_id(agent_id)
        if not agent:
            return None
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def delete(self, agent_id: str) -> bool:
        agent = self.get_by_id(agent_id)
        if not agent:
            return False
        self.session.delete(agent)
        self.session.commit()
        return True


class BoardRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, description: str | None = None, min_players: int = 6,
               max_players: int = 12, sheriff_enabled: bool = True) -> Board:
        board = Board(name=name, description=description, min_players=min_players,
                       max_players=max_players, sheriff_enabled=sheriff_enabled)
        self.session.add(board)
        self.session.commit()
        self.session.refresh(board)
        return board

    def get_by_id(self, board_id: str) -> Board | None:
        return self.session.get(Board, board_id)

    def list_all(self) -> list[Board]:
        return list(self.session.exec(select(Board)).all())

    def add_role(self, board_id: str, role_key: str, count: int) -> BoardRole:
        board_role = BoardRole(board_id=board_id, role_key=role_key, count=count)
        self.session.add(board_role)
        self.session.commit()
        return board_role

    def remove_role(self, board_id: str, role_key: str) -> bool:
        board_role = self.session.get(BoardRole, (board_id, role_key))
        if not board_role:
            return False
        self.session.delete(board_role)
        self.session.commit()
        return True

    def get_roles(self, board_id: str) -> list[BoardRole]:
        return list(self.session.exec(select(BoardRole).where(BoardRole.board_id == board_id)).all())

    def delete(self, board_id: str) -> bool:
        board = self.get_by_id(board_id)
        if not board:
            return False
        self.session.delete(board)
        self.session.commit()
        return True


class RoleMetadataRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[RoleMetadata]:
        return list(self.session.exec(select(RoleMetadata)).all())

    def get_by_key(self, role_key: str) -> RoleMetadata | None:
        return self.session.get(RoleMetadata, role_key)
```

- [ ] **Step 3: 运行测试验证失败**

Run: `pytest tests/storage/test_admin_repository.py -v`
Expected: FAIL - cannot import from 'ai_werewolf.storage.admin_repository'

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/storage/test_admin_repository.py -v`
Expected: PASS (mock 会 pass，但实际需要真实 DB 测试)

- [ ] **Step 5: 提交**

```bash
git add storage/admin_repository.py tests/storage/test_admin_repository.py
git commit -m "feat: add admin repository for Player, Agent, Board, RoleMetadata"
```

---

## Task 3: 创建认证 API

**Files:**
- Create: `ai_werewolf/api/admin/auth.py`
- Create: `ai_werewolf/api/admin/__init__.py`
- Test: `tests/api/admin/test_auth.py`

- [ ] **Step 1: 创建失败的测试**

```python
# tests/api/admin/test_auth.py
from fastapi.testclient import TestClient

def test_login_success(client: TestClient):
    response = client.post("/admin/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "session_id" in data["data"]

def test_login_failure(client: TestClient):
    response = client.post("/admin/login", json={"username": "wrong", "password": "wrong"})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1
    assert "error" in data["message"].lower()

def test_logout(client: TestClient):
    # 先登录
    login_response = client.post("/admin/login", json={"username": "admin", "password": "admin"})
    session_id = login_response.json()["data"]["session_id"]
    # 登出
    response = client.post("/admin/logout", headers={"Cookie": f"session_id={session_id}"})
    assert response.status_code == 200
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/api/admin/test_auth.py -v`
Expected: FAIL - cannot import from 'ai_werewolf.api.admin.auth'

- [ ] **Step 3: 创建 auth.py**

```python
# ai_werewolf/api/admin/auth.py
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Response, Cookie

from ai_werewolf.api.responses import success_response, error_response

router = APIRouter(prefix="/admin", tags=["admin"])

# 简单 session 存储（生产环境用 Redis）
_sessions: dict[str, dict] = {}

# 硬编码管理员账号（后续可存数据库）
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin".encode()).hexdigest()


def create_session() -> str:
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {"authenticated": True}
    return session_id


def verify_session(session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    return _sessions.get(session_id, {}).get("authenticated", False)


@router.post("/login")
def login(response: Response, username: str, password: str) -> dict:
    """管理员登录"""
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
        session_id = create_session()
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        return success_response(data={"session_id": session_id})

    return error_response(message="用户名或密码错误", code=1)


@router.post("/logout")
def logout(response: Response, session_id: Optional[str] = Cookie(None)) -> dict:
    """管理员登出"""
    if session_id and session_id in _sessions:
        del _sessions[session_id]

    response.delete_cookie(key="session_id")
    return success_response()


@router.get("/session")
def check_session(session_id: Optional[str] = Cookie(None)) -> dict:
    """检查 session 是否有效"""
    if verify_session(session_id):
        return success_response(data={"authenticated": True})
    return error_response(message="未登录", code=401)
```

- [ ] **Step 4: 创建 __init__.py**

```python
# ai_werewolf/api/admin/__init__.py
from .auth import router as auth_router

__all__ = ["auth_router"]
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/api/admin/test_auth.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add api/admin/auth.py api/admin/__init__.py tests/api/admin/test_auth.py
git commit -m "feat: add admin auth API with session-based login"
```

---

## Task 4: 创建玩家管理 API

**Files:**
- Create: `ai_werewolf/api/admin/players.py`
- Modify: `ai_werewolf/api/main.py` (注册 router)
- Test: `tests/api/admin/test_players.py`

- [ ] **Step 1: 创建失败的测试**

```python
# tests/api/admin/test_players.py
from fastapi.testclient import TestClient

def test_list_players(client: TestClient, authenticated_cookie: dict):
    response = client.get("/admin/players", cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)

def test_create_player(client: TestClient, authenticated_cookie: dict):
    response = client.post("/admin/players", json={"name": "测试玩家", "is_ai": False}, cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "测试玩家"

def test_create_ai_player(client: TestClient, authenticated_cookie: dict):
    response = client.post("/admin/players", json={"name": "AI玩家", "is_ai": True, "agent_id": None}, cookies=authenticated_cookie)
    assert response.status_code == 200

def test_create_duplicate_name(client: TestClient, authenticated_cookie: dict):
    # 先创建
    client.post("/admin/players", json={"name": "重复", "is_ai": False}, cookies=authenticated_cookie)
    # 再次创建同名
    response = client.post("/admin/players", json={"name": "重复", "is_ai": False}, cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1  # 应该失败
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/api/admin/test_players.py -v`
Expected: FAIL - cannot import from 'ai_werewolf.api.admin.players'

- [ ] **Step 3: 创建 players.py**

```python
# ai_werewolf/api/admin/players.py
from typing import Optional

from fastapi import APIRouter, Cookie, Depends

from ai_werewolf.api.responses import success_response, error_response
from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.storage.admin_repository import PlayerRepository
from ai_werewolf.storage.database import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


def get_player_repo(session=Depends(get_session)) -> PlayerRepository:
    return PlayerRepository(session)


@router.get("/players")
def list_players(session_id: Optional[str] = Cookie(None), repo: PlayerRepository = Depends(get_player_repo)) -> dict:
    """列出所有玩家"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    players = repo.list_all()
    return success_response(data=[
        {
            "player_id": p.player_id,
            "name": p.name,
            "is_ai": p.is_ai,
            "agent_id": p.agent_id,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in players
    ])


@router.post("/players")
def create_player(name: str, is_ai: bool = False, agent_id: Optional[str] = None,
                  session_id: Optional[str] = Cookie(None), repo: PlayerRepository = Depends(get_player_repo)) -> dict:
    """添加玩家"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    # 检查名称唯一
    existing = repo.get_by_name(name)
    if existing:
        return error_response(message=f"玩家 '{name}' 已存在", code=1)

    player = repo.create(name=name, is_ai=is_ai, agent_id=agent_id)
    return success_response(data={
        "player_id": player.player_id,
        "name": player.name,
        "is_ai": player.is_ai,
        "agent_id": player.agent_id,
        "created_at": player.created_at.isoformat() if player.created_at else None
    })


@router.get("/players/{player_id}")
def get_player(player_id: str, session_id: Optional[str] = Cookie(None),
               repo: PlayerRepository = Depends(get_player_repo)) -> dict:
    """查看玩家详情"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    player = repo.get_by_id(player_id)
    if not player:
        return error_response(message="玩家不存在", code=404)

    return success_response(data={
        "player_id": player.player_id,
        "name": player.name,
        "is_ai": player.is_ai,
        "agent_id": player.agent_id,
        "created_at": player.created_at.isoformat() if player.created_at else None
    })


@router.put("/players/{player_id}")
def update_player(player_id: str, name: Optional[str] = None, is_ai: Optional[bool] = None,
                  agent_id: Optional[str] = None, session_id: Optional[str] = Cookie(None),
                  repo: PlayerRepository = Depends(get_player_repo)) -> dict:
    """更新玩家"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    player = repo.update(player_id, name=name, is_ai=is_ai, agent_id=agent_id)
    if not player:
        return error_response(message="玩家不存在", code=404)

    return success_response(data={
        "player_id": player.player_id,
        "name": player.name,
        "is_ai": player.is_ai,
        "agent_id": player.agent_id,
        "created_at": player.created_at.isoformat() if player.created_at else None
    })


@router.delete("/players/{player_id}")
def delete_player(player_id: str, session_id: Optional[str] = Cookie(None),
                  repo: PlayerRepository = Depends(get_player_repo)) -> dict:
    """删除玩家"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    success = repo.delete(player_id)
    if not success:
        return error_response(message="玩家不存在", code=404)

    return success_response()
```

- [ ] **Step 4: 更新 main.py 注册 router**

在 `main.py` 中添加：
```python
from ai_werewolf.api.admin.auth import router as admin_router

app.include_router(admin_router)
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/api/admin/test_players.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add api/admin/players.py api/main.py tests/api/admin/test_players.py
git commit -m "feat: add admin players API"
```

---

## Task 5: 创建 AI 管理 API

**Files:**
- Create: `ai_werewolf/api/admin/agents.py`
- Modify: `ai_werewolf/api/main.py`
- Test: `tests/api/admin/test_agents.py`

- [ ] **Step 1: 创建失败的测试**

```python
# tests/api/admin/test_agents.py
from fastapi.testclient import TestClient

def test_list_agents(client: TestClient, authenticated_cookie: dict):
    response = client.get("/admin/agents", cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0

def test_create_agent(client: TestClient, authenticated_cookie: dict):
    response = client.post("/admin/agents", json={
        "name": "测试AI",
        "persona": "理性谨慎",
        "speech_style": "简洁",
        "reasoning_level": 4,
        "deception_level": 3
    }, cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "测试AI"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/api/admin/test_agents.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 agents.py**

```python
# ai_werewolf/api/admin/agents.py
from typing import Optional

from fastapi import APIRouter, Cookie, Depends

from ai_werewolf.api.responses import success_response, error_response
from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.storage.admin_repository import AgentRepository
from ai_werewolf.storage.database import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


def get_agent_repo(session=Depends(get_session)) -> AgentRepository:
    return AgentRepository(session)


@router.get("/agents")
def list_agents(session_id: Optional[str] = Cookie(None), repo: AgentRepository = Depends(get_agent_repo)) -> dict:
    """列出所有 AI 配置"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    agents = repo.list_all()
    return success_response(data=[
        {
            "agent_id": a.agent_id,
            "name": a.name,
            "persona": a.persona,
            "speech_style": a.speech_style,
            "reasoning_level": a.reasoning_level,
            "deception_level": a.deception_level,
            "aggression_level": a.aggression_level,
            "cooperation_level": a.cooperation_level,
            "enabled": a.enabled
        }
        for a in agents
    ])


@router.post("/agents")
def create_agent(name: str, persona: str, speech_style: str,
                 reasoning_level: int = 3, deception_level: int = 3,
                 aggression_level: int = 3, cooperation_level: int = 3,
                 session_id: Optional[str] = Cookie(None),
                 repo: AgentRepository = Depends(get_agent_repo)) -> dict:
    """添加 AI 配置"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    agent = repo.create(name=name, persona=persona, speech_style=speech_style,
                        reasoning_level=reasoning_level, deception_level=deception_level,
                        aggression_level=aggression_level, cooperation_level=cooperation_level)
    return success_response(data={
        "agent_id": agent.agent_id,
        "name": agent.name,
        "persona": agent.persona,
        "speech_style": agent.speech_style,
        "reasoning_level": agent.reasoning_level,
        "deception_level": agent.deception_level,
        "aggression_level": agent.aggression_level,
        "cooperation_level": agent.cooperation_level,
        "enabled": agent.enabled
    })


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, session_id: Optional[str] = Cookie(None),
              repo: AgentRepository = Depends(get_agent_repo)) -> dict:
    """查看 AI 详情"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    agent = repo.get_by_id(agent_id)
    if not agent:
        return error_response(message="AI 不存在", code=404)

    return success_response(data={
        "agent_id": agent.agent_id,
        "name": agent.name,
        "persona": agent.persona,
        "speech_style": agent.speech_style,
        "reasoning_level": agent.reasoning_level,
        "deception_level": agent.deception_level,
        "aggression_level": agent.aggression_level,
        "cooperation_level": agent.cooperation_level,
        "enabled": agent.enabled
    })


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, name: Optional[str] = None, persona: Optional[str] = None,
                 speech_style: Optional[str] = None, reasoning_level: Optional[int] = None,
                 deception_level: Optional[int] = None, aggression_level: Optional[int] = None,
                 cooperation_level: Optional[int] = None, enabled: Optional[bool] = None,
                 session_id: Optional[str] = Cookie(None),
                 repo: AgentRepository = Depends(get_agent_repo)) -> dict:
    """更新 AI 配置"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    update_data = {}
    if name is not None:
        update_data["name"] = name
    if persona is not None:
        update_data["persona"] = persona
    if speech_style is not None:
        update_data["speech_style"] = speech_style
    if reasoning_level is not None:
        update_data["reasoning_level"] = reasoning_level
    if deception_level is not None:
        update_data["deception_level"] = deception_level
    if aggression_level is not None:
        update_data["aggression_level"] = aggression_level
    if cooperation_level is not None:
        update_data["cooperation_level"] = cooperation_level
    if enabled is not None:
        update_data["enabled"] = enabled

    agent = repo.update(agent_id, **update_data)
    if not agent:
        return error_response(message="AI 不存在", code=404)

    return success_response(data={
        "agent_id": agent.agent_id,
        "name": agent.name,
        "persona": agent.persona,
        "speech_style": agent.speech_style,
        "reasoning_level": agent.reasoning_level,
        "deception_level": agent.deception_level,
        "aggression_level": agent.aggression_level,
        "cooperation_level": agent.cooperation_level,
        "enabled": agent.enabled
    })


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, session_id: Optional[str] = Cookie(None),
                 repo: AgentRepository = Depends(get_agent_repo)) -> dict:
    """删除 AI 配置"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    success = repo.delete(agent_id)
    if not success:
        return error_response(message="AI 不存在", code=404)

    return success_response()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/api/admin/test_agents.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add api/admin/agents.py tests/api/admin/test_agents.py
git commit -m "feat: add admin agents API"
```

---

## Task 6: 创建板子管理 API

**Files:**
- Create: `ai_werewolf/api/admin/boards.py`
- Modify: `ai_werewolf/api/main.py`
- Test: `tests/api/admin/test_boards.py`

- [ ] **Step 1: 创建失败的测试**

```python
# tests/api/admin/test_boards.py
from fastapi.testclient import TestClient

def test_list_boards(client: TestClient, authenticated_cookie: dict):
    response = client.get("/admin/boards", cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0

def test_create_board(client: TestClient, authenticated_cookie: dict):
    response = client.post("/admin/boards", json={
        "name": "测试板子",
        "description": "用于测试",
        "min_players": 6,
        "max_players": 8
    }, cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "测试板子"

def test_add_role_to_board(client: TestClient, authenticated_cookie: dict):
    # 先创建板子
    board_resp = client.post("/admin/boards", json={"name": "角色测试板", "min_players": 6, "max_players": 9}, cookies=authenticated_cookie)
    board_id = board_resp.json()["data"]["board_id"]
    # 添加角色
    response = client.post(f"/admin/boards/{board_id}/roles", json={"role_key": "werewolf", "count": 2}, cookies=authenticated_cookie)
    assert response.status_code == 200
    assert response.json()["code"] == 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/api/admin/test_boards.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 boards.py**

```python
# ai_werewolf/api/admin/boards.py
from typing import Optional

from fastapi import APIRouter, Cookie, Depends

from ai_werewolf.api.responses import success_response, error_response
from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.storage.admin_repository import BoardRepository
from ai_werewolf.storage.database import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


def get_board_repo(session=Depends(get_session)) -> BoardRepository:
    return BoardRepository(session)


@router.get("/boards")
def list_boards(session_id: Optional[str] = Cookie(None), repo: BoardRepository = Depends(get_board_repo)) -> dict:
    """列出所有板子"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    boards = repo.list_all()
    result = []
    for b in boards:
        roles = repo.get_roles(b.board_id)
        result.append({
            "board_id": b.board_id,
            "name": b.name,
            "description": b.description,
            "min_players": b.min_players,
            "max_players": b.max_players,
            "sheriff_enabled": b.sheriff_enabled,
            "enabled": b.enabled,
            "roles": [{"role_key": r.role_key, "count": r.count} for r in roles]
        })
    return success_response(data=result)


@router.post("/boards")
def create_board(name: str, description: Optional[str] = None,
                 min_players: int = 6, max_players: int = 12,
                 sheriff_enabled: bool = True,
                 session_id: Optional[str] = Cookie(None),
                 repo: BoardRepository = Depends(get_board_repo)) -> dict:
    """添加板子"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    board = repo.create(name=name, description=description, min_players=min_players,
                        max_players=max_players, sheriff_enabled=sheriff_enabled)
    return success_response(data={
        "board_id": board.board_id,
        "name": board.name,
        "description": board.description,
        "min_players": board.min_players,
        "max_players": board.max_players,
        "sheriff_enabled": board.sheriff_enabled,
        "enabled": board.enabled
    })


@router.get("/boards/{board_id}")
def get_board(board_id: str, session_id: Optional[str] = Cookie(None),
              repo: BoardRepository = Depends(get_board_repo)) -> dict:
    """查看板子详情"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    board = repo.get_by_id(board_id)
    if not board:
        return error_response(message="板子不存在", code=404)

    roles = repo.get_roles(board_id)
    return success_response(data={
        "board_id": board.board_id,
        "name": board.name,
        "description": board.description,
        "min_players": board.min_players,
        "max_players": board.max_players,
        "sheriff_enabled": board.sheriff_enabled,
        "enabled": board.enabled,
        "roles": [{"role_key": r.role_key, "count": r.count} for r in roles]
    })


@router.post("/boards/{board_id}/roles")
def add_role_to_board(board_id: str, role_key: str, count: int,
                      session_id: Optional[str] = Cookie(None),
                      repo: BoardRepository = Depends(get_board_repo)) -> dict:
    """添加角色到板子"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    board = repo.get_by_id(board_id)
    if not board:
        return error_response(message="板子不存在", code=404)

    board_role = repo.add_role(board_id=board_id, role_key=role_key, count=count)
    return success_response(data={
        "board_id": board_role.board_id,
        "role_key": board_role.role_key,
        "count": board_role.count
    })


@router.delete("/boards/{board_id}/roles/{role_key}")
def remove_role_from_board(board_id: str, role_key: str,
                           session_id: Optional[str] = Cookie(None),
                           repo: BoardRepository = Depends(get_board_repo)) -> dict:
    """从板子移除角色"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    success = repo.remove_role(board_id, role_key)
    if not success:
        return error_response(message="板子或角色不存在", code=404)

    return success_response()


@router.delete("/boards/{board_id}")
def delete_board(board_id: str, session_id: Optional[str] = Cookie(None),
                 repo: BoardRepository = Depends(get_board_repo)) -> dict:
    """删除板子"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    success = repo.delete(board_id)
    if not success:
        return error_response(message="板子不存在", code=404)

    return success_response()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/api/admin/test_boards.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add api/admin/boards.py tests/api/admin/test_boards.py
git commit -m "feat: add admin boards API"
```

---

## Task 7: 创建角色元数据 API（只读）

**Files:**
- Create: `ai_werewolf/api/admin/roles.py`
- Test: `tests/api/admin/test_roles.py`

- [ ] **Step 1: 创建失败的测试**

```python
# tests/api/admin/test_roles.py
from fastapi.testclient import TestClient

def test_list_roles(client: TestClient, authenticated_cookie: dict):
    response = client.get("/admin/roles", cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
    # 应该包含预定义角色
    role_keys = [r["role_key"] for r in data["data"]]
    assert "werewolf" in role_keys
    assert "seer" in role_keys
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/api/admin/test_roles.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 roles.py**

```python
# ai_werewolf/api/admin/roles.py
from typing import Optional

from fastapi import APIRouter, Cookie

from ai_werewolf.api.responses import success_response, error_response
from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.rules.role_registry import get_all_roles

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/roles")
def list_roles(session_id: Optional[str] = Cookie(None)) -> dict:
    """列出所有角色（只读）"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    all_roles = get_all_roles()
    return success_response(data=[
        {
            "role_key": r.key,
            "name": r.name,
            "faction": r.faction.value if hasattr(r.faction, 'value') else r.faction,
            "night_action": r.night_action,
            "can_speak": r.can_speak,
            "can_vote": r.can_vote
        }
        for r in all_roles
    ])
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/api/admin/test_roles.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add api/admin/roles.py tests/api/admin/test_roles.py
git commit -m "feat: add admin roles API (readonly)"
```

---

## Task 8: 创建游戏记录 API

**Files:**
- Create: `ai_werewolf/api/admin/games.py`
- Test: `tests/api/admin/test_games.py`

- [ ] **Step 1: 创建失败的测试**

```python
# tests/api/admin/test_games.py
from fastapi.testclient import TestClient

def test_list_games(client: TestClient, authenticated_cookie: dict):
    response = client.get("/admin/games", cookies=authenticated_cookie)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/api/admin/test_games.py -v`
Expected: FAIL

- [ ] **Step 3: 创建 games.py**

```python
# ai_werewolf/api/admin/games.py
from typing import Optional

from fastapi import APIRouter, Cookie, Depends
from sqlmodel import select

from ai_werewolf.api.responses import success_response, error_response
from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.storage.models import GameRecord, GamePlayerRecord
from ai_werewolf.storage.database import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/games")
def list_games(session_id: Optional[str] = Cookie(None), session=Depends(get_session)) -> dict:
    """列出游戏记录"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    games = session.exec(select(GameRecord)).all()
    result = []
    for g in games:
        result.append({
            "game_id": g.game_id,
            "board_id": g.board_id,
            "phase": g.phase,
            "day_count": g.day_count,
            "winner": g.winner,
            "created_at": g.created_at.isoformat() if hasattr(g, 'created_at') and g.created_at else None
        })
    return success_response(data=result)


@router.get("/games/{game_id}")
def get_game(game_id: str, session_id: Optional[str] = Cookie(None),
             session=Depends(get_session)) -> dict:
    """查看游戏详情"""
    if not verify_session(session_id):
        return error_response(message="未登录", code=401)

    game = session.get(GameRecord, game_id)
    if not game:
        return error_response(message="游戏不存在", code=404)

    # 获取玩家
    players = session.exec(select(GamePlayerRecord).where(GamePlayerRecord.game_id == game_id)).all()
    player_list = [
        {
            "player_id": p.player_id,
            "seat": p.seat,
            "role_key": p.role_key,
            "alive": p.alive,
            "is_human": p.is_human,
            "sheriff": p.sheriff
        }
        for p in players
    ]

    return success_response(data={
        "game_id": game.game_id,
        "board_id": game.board_id,
        "phase": game.phase,
        "day_count": game.day_count,
        "winner": game.winner,
        "players": player_list
    })
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/api/admin/test_games.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add api/admin/games.py tests/api/admin/test_games.py
git commit -m "feat: add admin games API"
```

---

## Task 9: 初始化角色数据

**Files:**
- Create: `ai_werewolf/seeds/admin_roles.py`
- Modify: `ai_werewolf/storage/database.py` (添加初始化逻辑)

- [ ] **Step 1: 创建角色初始化 seed**

```python
# ai_werewolf/seeds/admin_roles.py
from ai_werewolf.storage.admin_repository import RoleMetadataRepository
from ai_werewolf.storage.database import get_session

def seed_role_metadata():
    """初始化角色元数据"""
    session = next(get_session())
    repo = RoleMetadataRepository(session)

    roles_data = [
        {"role_key": "werewolf", "name": "狼人", "faction": "wolf", "description": "每晚可以击杀一名玩家", "night_action": True},
        {"role_key": "seer", "name": "预言家", "faction": "good", "description": "每晚可以查验一名玩家身份", "night_action": True},
        {"role_key": "witch", "name": "女巫", "faction": "good", "description": "有一瓶解药和一瓶毒药", "night_action": True},
        {"role_key": "hunter", "name": "猎人", "faction": "good", "description": "死后可以开枪带走一人", "night_action": True},
        {"role_key": "villager", "name": "村民", "faction": "good", "description": "没有任何特殊能力", "night_action": False},
        {"role_key": "guardian", "name": "守卫", "faction": "good", "description": "每晚可以守护一名玩家", "night_action": True},
        {"role_key": "idiot", "name": "白痴", "faction": "good", "description": "被投票出局不会死亡", "night_action": False},
        {"role_key": "wolf_king", "name": "白狼王", "faction": "wolf", "description": "可以自爆带走一名玩家", "night_action": True},
        {"role_key": "knight", "name": "骑士", "faction": "good", "description": "可以决斗一名玩家", "night_action": True},
        {"role_key": "wolf_beauty", "name": "狼美人", "faction": "wolf", "description": "魅惑一名玩家，死亡时带走", "night_action": True},
    ]

    for role_data in roles_data:
        existing = repo.get_by_key(role_data["role_key"])
        if not existing:
            session.add(RoleMetadata(**role_data))

    session.commit()
```

- [ ] **Step 2: 在 database.py 添加初始化调用**

在 `ensure_db_created()` 函数中调用 `seed_role_metadata()`

- [ ] **Step 3: 运行并验证**

Run: `python -c "from ai_werewolf.seeds.admin_roles import seed_role_metadata; seed_role_metadata()"`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add seeds/admin_roles.py storage/database.py
git commit -m "feat: add role metadata seeding"
```

---

## Task 10: 集成测试

**Files:**
- Create: `tests/api/admin/conftest.py`
- Modify: `tests/api/admin/test_*.py`

- [ ] **Step 1: 创建 conftest.py**

```python
# tests/api/admin/conftest.py
import pytest
from fastapi.testclient import TestClient
from ai_werewolf.api.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def authenticated_cookie(client: TestClient):
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}
```

- [ ] **Step 2: 运行完整测试**

Run: `pytest tests/api/admin/ -v`
Expected: 所有测试通过

- [ ] **Step 3: 提交**

```bash
git add tests/api/admin/conftest.py
git commit -m "test: add admin API integration tests"
```

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-admin-system.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**