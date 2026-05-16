# 前端体验优化设计

## 问题清单

### P1: "你已出局"误显示
- 存活玩家在等待其他玩家发言/行动时，UI 显示"你已出局"
- 根因：`PhaseSceneRouter.tsx` 在 `allowed_actions` 为空时统一渲染 `ObserverScene`（"你已出局"），未区分"真的死了"和"等待中"

### P2: 预言家验人结果不可见
- 预言家查验后，结果不会显示在对应玩家卡片上
- 根因：后端已发送 `private_info` SSE 事件，但前端未监听和处理

### P3: 夜晚行动结果延迟
- 预言家验完人后必须等所有人行动完才知结果
- 根因：同 P2——后端已即时发送 `private_info`，前端未消费

## 设计方案

### 1. 修复"你已出局"误显示

**文件**: `frontend/src/PhaseSceneRouter.tsx`

**改动**: `ObserverScene` 消息根据玩家存活状态区分：
- `player.alive === false` → "你已出局，正在旁听/等待结算"
- `player.alive === true` → "等待其他玩家行动中..."

### 2. 消费 private_info SSE 事件

**文件**: `frontend/src/App.tsx`

**改动**: SSE 事件处理器新增 `private_info` 监听：
- 收到后存入状态 `seerResults: Map<playerId, {camp: 'good'|'wolf', label: string}>`
- 传递给 `GameTable` 组件

**文件**: `frontend/src/types.ts`

**改动**: 新增 `SeerCheckResult` 类型

### 3. 全屏弹出字幕 + 玩家卡片标记

**文件**: `frontend/src/GameTable.tsx`

**改动 A — 全屏弹出字幕**:
- 收到新 seer 结果时，渲染全屏 overlay
- 内容："X号 玩家名 是好人阵营/狼人阵营"
- 好人用绿色，狼人用红色
- CSS 动画：淡入 + 缩放，自动 3 秒后消失或点击关闭

**改动 B — 玩家卡片永久标记**:
- 在玩家卡片 `.seat-tags` 区域新增查验结果标签
- 好人 → 绿色徽标 "好"
- 狼人 → 红色徽标 "狼"
- 标记贯穿整局

**文件**: `frontend/src/styles.css`

**改动**: 新增 overlay 动画样式和 seer 标记样式

## 后端

无需改动。后端 `night.py` 已在预言家查验后立即发送 `private_info` 事件。

## 涉及文件汇总

| 文件 | 改动类型 |
|------|---------|
| `frontend/src/PhaseSceneRouter.tsx` | 修改 |
| `frontend/src/App.tsx` | 修改 |
| `frontend/src/GameTable.tsx` | 修改 |
| `frontend/src/types.ts` | 修改 |
| `frontend/src/styles.css` | 修改 |
