# AI 狼人杀项目当前工作总结

更新时间：2026-05-15

## 一、已完成的核心工作

### 1. PostgreSQL 配置接入

- 新增类似 Spring Boot 的应用配置文件：`ai_werewolf/config/application.yaml`。
- 新增配置读取模块：`ai_werewolf/config/application.py`。
- 默认连接本地 PostgreSQL：

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf
```

- 已确认真实连接到：

```text
database=ai_werewolf, schema=public
```

### 2. 后台管理从 mock/seed 改为真实数据库链路

已将以下后台数据改为真实数据库查询和落库：

- 玩家管理：`/admin/players`
- AI 人设管理：`/admin/agents`
- 板子管理：`/admin/boards`
- 角色元数据：`/admin/roles`
- 游戏记录：`/admin/games`
- 模型 Provider：`/admin/llm/providers`
- 角色模型绑定：`/admin/llm/role-bindings`

同时修复了玩家前台与后台配置脱节的问题：

- `/boards` 现在优先读取数据库中的启用板子。
- `/agents` 现在优先读取数据库中的启用 AI 人设。
- `/games` 创建游戏时使用数据库中的板子和 AI 配置。

### 3. ORM 表名与 SQL 文档对齐

已将 SQLModel 表名和 `ai_werewolf/docs/database-schema.md` 中的表名对齐，包括：

- `board_records`
- `llm_providers`
- `role_model_bindings`
- `games`
- `game_players`
- `players`
- `agent_profiles`
- `boards`
- `board_roles`
- `role_metadata`

### 4. 后台前端能力补齐

已在前端后台管理系统中补齐：

- 玩家页面：新增、启停 AI 标识、删除。
- AI 人设页面：新增、启停、删除。
- 板子页面：新增、启停、删除、角色配置。
- 角色页面：初始化角色、刷新。
- 模型页面：新增 Provider、配置角色模型绑定。
- 游戏记录页面：查看已落库游戏。

后台入口：

```text
http://127.0.0.1:5173/admin/login
```

账号密码：

```text
admin / admin
```

## 二、验证结果

最近一次完整验证结果：

```text
后端：124 passed, 48 warnings
前端：20 passed
前端构建：成功
```

真实 PostgreSQL 烟测结果：

- 后台创建板子成功。
- 后台配置板子角色成功。
- 后台创建 AI 人设成功。
- `/boards` 能读取后台创建的板子。
- `/agents` 能读取后台创建的 AI。
- `/games` 能使用这些数据库配置成功创建游戏。

## 三、当前正在排查的问题

### 问题：后台新增按钮点击后看起来没有反应

用户反馈：

- 点击“新增玩家”
- 点击“新增板子”
- 点击“新增 AI”

页面没有明显反馈，Network 面板看起来也没有请求发出。

### 已定位的前端原因

目前表单在必填字段为空时直接 `return`，没有任何错误提示：

- 玩家名称为空时，不会请求。
- 板子名称为空时，不会请求。
- AI 名称、人格、发言风格未填完整时，不会请求。

这会导致用户感觉按钮“没有反应”。

### 已新增但尚未修复通过的回归测试

当前新增了针对该问题的前端测试，测试目前是失败状态，正好锁定了待修复行为：

```text
src/admin/AdminPages.test.tsx

失败项：
- submits player creation only after required fields are present
- submits board creation only after required fields are present
- submits agent creation only after all required fields are present
```

期望修复后的行为：

- 空表单点击新增时，页面显示明确提示。
- 字段填完整后，点击新增会发出真实请求。
- 请求成功后刷新列表。
- 请求失败时展示错误信息，而不是静默失败。

## 四、系统当前现状

### 后端

后端已经具备真实数据库链路，核心管理 API 已接入 PostgreSQL。

当前运行服务：

```text
http://127.0.0.1:8000
```

健康检查：

```text
GET /health
```

返回：

```json
{"code":0,"message":"ok","data":{"status":"ok"}}
```

### 前端

前端后台页面已经具备基础管理界面，但表单交互还需要继续打磨：

- 需要补充表单校验提示。
- 需要补充提交中状态。
- 需要补充 API 错误展示。
- 需要针对新增、删除、启停、角色配置做浏览器级回归测试。

当前运行服务：

```text
http://127.0.0.1:5173
```

## 五、建议下一步

优先修复后台表单交互：

1. 给玩家、板子、AI、模型页面增加表单级错误提示。
2. 点击新增时展示 pending 状态。
3. 请求失败时展示后端返回错误。
4. 请求成功后清空表单并刷新列表。
5. 用浏览器真实操作验证：
   - 新增玩家
   - 新增 AI
   - 新增板子
   - 配置板子角色
   - 新增模型 Provider
   - 保存角色模型绑定

## 六、关键文件索引

后端：

- `ai_werewolf/config/application.yaml`
- `ai_werewolf/config/application.py`
- `ai_werewolf/api/public.py`
- `ai_werewolf/api/games.py`
- `ai_werewolf/api/llm_config.py`
- `ai_werewolf/api/admin/`
- `ai_werewolf/storage/models.py`
- `ai_werewolf/storage/catalog.py`
- `ai_werewolf/storage/repositories.py`

前端：

- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/admin/AdminPlayersPage.tsx`
- `frontend/src/admin/AdminAgentsPage.tsx`
- `frontend/src/admin/AdminBoardsPage.tsx`
- `frontend/src/admin/AdminLlmPage.tsx`
- `frontend/src/styles.css`

测试：

- `tests/api/test_database_backed_admin_flow.py`
- `tests/api/test_llm_config_api.py`
- `ai_werewolf/tests/storage/test_models.py`
- `frontend/src/admin/AdminPages.test.tsx`
- `frontend/src/adminApi.test.ts`
