# PostgreSQL 与多模型配置

## PostgreSQL

后端默认通过 `ai_werewolf/config/application.yaml` 连接本地 PostgreSQL，配置结构接近 Spring Boot：

```yaml
app:
  database:
    enabled: true
    username: postgres
    password: postgres
    url: jdbc:postgresql://127.0.0.1:5432/
    database: ai_werewolf
    schema: public
```

应用会组装为 SQLAlchemy 连接串：

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf
```

也可以通过环境变量覆盖，推荐使用 SQLAlchemy URL：

```bash
export AI_WEREWOLF_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf"
```

也支持 JDBC URL 自动转换：

```bash
export AI_WEREWOLF_JDBC_URL="jdbc:postgresql://127.0.0.1:5432/ai_werewolf"
```

注意：`jdbc:postgresql://127.0.0.1:5432` 只包含 host 和 port，实际连接 PostgreSQL 仍需要数据库名；如果需要账号密码，请使用 `AI_WEREWOLF_DATABASE_URL`。

启用后，创建每一局游戏时会保存：

- `game_record`：游戏主状态
- `game_player_record`：本局每个玩家的座位、身份、存活状态和绑定的大模型 provider

## 多模型策略

后台 API：

- `POST /admin/llm/providers`：新增一个模型 provider
- `GET /admin/llm/providers`：查看 provider
- `POST /admin/llm/role-bindings`：配置 `role_key -> provider_id`
- `GET /admin/llm/role-bindings`：查看角色绑定

示例：

```json
{
  "provider_id": "deepseek",
  "provider_type": "openai_compatible",
  "model_name": "deepseek-chat",
  "base_url": "https://api.deepseek.com/v1",
  "api_key_env": "DEEPSEEK_API_KEY"
}
```

```json
{
  "role_key": "werewolf",
  "provider_id": "deepseek"
}
```
