# AI狼人杀 Frontend MVP

第一版前端以“玩家闭环优先”为目标：选择后端默认板子和 AI 玩家，创建游戏，进入游戏桌，并根据后端阶段切换场景。

## 本地运行

先启动后端：

```bash
python -m uvicorn ai_werewolf.main:app --reload --port 8000
```

再启动前端：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：

```text
http://localhost:5173
```

> **注意：** 请使用 `http://localhost:5173` 访问前端。API 请求指向 `http://localhost:8000`，与前端页面同站（均为 `localhost`），Cookie 可正常发送，无需跨站登录问题。

如需指向不同后端地址：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## 验证命令

```bash
npm test -- --run
npm run build
```
