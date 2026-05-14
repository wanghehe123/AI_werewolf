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
npm run dev -- --host 127.0.0.1 --port 5173
```

浏览器打开：

```text
http://127.0.0.1:5173
```

如需切换后端地址，设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

## 验证命令

```bash
npm test -- --run
npm run build
```
