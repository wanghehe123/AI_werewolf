## 一句话结论

当前前端已经具备“能玩”的闭环，但主游戏页视觉上更像多人连麦直播间：玩家是等分大卡片，事件是右侧流水账，操作区和牌桌割裂。建议把主体验升级为“桌游桌面”：玩家围坐在桌边，中央有阶段、行动、投票和发言焦点，事件以可理解的游戏叙事呈现，关键行为用适量特效强化反馈。

推荐方案是：**不重写业务流，不引入 3D 引擎，先基于现有 React + Framer Motion + Tailwind v4 做桌面化组件重构和事件特效层**。

---

## 当前现状判断

### 从截图看到的问题

| 问题 | 表现 | 对玩家的影响 |
| --- | --- | --- |
| 缺少桌游桌面感 | 6 个玩家卡片被排成 3x2 网格，每张卡片很大但内容很少 | 玩家感受不到“围桌对局”，更像直播间麦位 |
| 中央信息缺失 | 页面中央没有牌桌核心区域，阶段、行动、发言焦点分散 | 不知道现在游戏的主事件是什么 |
| 事件流太像日志 | 右侧直接显示 `phase_changed`、`night_step_started` 等技术事件名 | 普通玩家读起来像后台日志，不像游戏播报 |
| 玩家状态弱 | 出局、说话、被查验、投票等状态只靠小标签 | 关键游戏信息不够显眼 |
| 操作区割裂 | 阶段操作面板在下方，和玩家座位没有直接关系 | 投票、查验、毒人等行为不像在桌上点目标 |
| 缺少阶段仪式感 | 夜晚、天亮、投票、遗言、复盘之间主要是文字变化 | 狼人杀的紧张感和节奏感不足 |
| 空间利用不均 | 玩家卡片大量空白，右侧事件区过密 | 看起来“空”和“挤”同时存在 |

### 从代码看到的现状

| 文件 | 当前职责 | 主要问题 |
| --- | --- | --- |
| `frontend/src/GameTable.tsx` | 页面头部、玩家卡片、事件时间线、查验结果 overlay、阶段路由入口 | 职责集中，难以继续加复杂交互 |
| `frontend/src/PhaseSceneRouter.tsx` | 不同阶段的操作面板 | 操作以表单/radio 为主，没有和座位交互联动 |
| `frontend/src/stores/gameStore.ts` | SSE 状态、流式发言、查验结果、TTS 播报 | 事件数据足够做视觉反馈，但还没有派生成前端视觉事件 |
| `frontend/src/index.css` | 全局主题变量和管理后台样式 | 主题已有暗色狼人杀气质，但缺少牌桌、座位、动效 token |
| `frontend/src/hooks/usePhaseBgm.ts` / `useTtsPlayback.ts` | BGM 和语音播放 | 已经有声音基础，可以和视觉动效联动 |

---

## 设计目标

### 核心目标

1. **第一眼像桌游**：玩家围绕一个中央牌桌，而不是整齐卡片矩阵。
2. **行动更像点桌面目标**：投票、查验、毒药、守护等目标选择优先点玩家座位，表单作为辅助。
3. **事件更像主持人播报**：隐藏技术事件名，改成“天黑请闭眼”“狼人行动结束”“昨夜 6 号倒牌”这类玩家语言。
4. **特效服务信息，不做空装饰**：说话、投票、夜晚、查验、出局、胜利都要有明确反馈。
5. **保留现有后端协议**：第一版尽量只用现有 `GameStateDto` 和 SSE 事件完成。
6. **移动端也能玩**：桌面端做围桌，移动端做上下布局和横向座位带。

### 非目标

1. 第一版不做 Three.js 或复杂 3D。
2. 第一版不重写后端游戏状态机。
3. 第一版不把所有 UI 做成大动画，避免低端设备卡顿。
4. 第一版不改管理后台。

---

## 方案对比

| 方案 | 做法 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- | --- |
| A. 轻量换皮 | 保留 3x2 卡片，只加背景、阴影和少量动画 | 最快，风险最低 | 桌游感提升有限，本质仍是直播间布局 | 不推荐作为最终方案 |
| B. 桌面化组件重构 | 拆出玩家环、中央牌桌、事件轨、操作坞、特效层 | 体验提升明显，复用现有数据，风险可控 | 需要拆组件和补测试 | 推荐 |
| C. Canvas/3D 牌桌 | 用 Canvas 或 Three.js 做完整桌面 | 视觉冲击强 | 成本高，交互和可访问性复杂，和 React 状态结合难 | 后续再考虑 |

**推荐走 B。**

---

## 目标页面结构

### 桌面端布局

```text
┌──────────────────────────────────────────────────────────────┐
│ 顶部状态条：第 N 天 / 当前阶段 / 胜利状态 / 音频状态           │
├───────────────────────────────────────────────┬──────────────┤
│                                               │              │
│              玩家围坐牌桌区                    │  事件叙事轨   │
│                                               │              │
│       seat 2       seat 3       seat 4         │  关键事件     │
│                                               │  发言摘要     │
│  seat 1        中央桌面        seat 5          │  投票记录     │
│                                               │              │
│       seat 8       seat 7       seat 6         │              │
│                                               │              │
├───────────────────────────────────────────────┴──────────────┤
│ 底部行动坞：当前可执行动作 / 目标确认 / 发言输入 / 提交按钮      │
└──────────────────────────────────────────────────────────────┘
```

### 移动端布局

```text
┌──────────────────────┐
│ 顶部状态条             │
├──────────────────────┤
│ 中央桌面摘要           │
├──────────────────────┤
│ 横向/双列玩家座位       │
├──────────────────────┤
│ 可折叠事件叙事轨        │
├──────────────────────┤
│ sticky 底部行动坞       │
└──────────────────────┘
```

---

## 组件拆分方案

### 新增目录

建议新增：

```text
frontend/src/game-ui/
```

不要放到 `admin` 下，避免和后台页面混在一起。

### 组件清单

| 组件 | 文件 | 只负责什么 |
| --- | --- | --- |
| `GameTableShell` | `frontend/src/game-ui/GameTableShell.tsx` | 主游戏页布局骨架，组合其他组件 |
| `PhaseStatusBar` | `frontend/src/game-ui/PhaseStatusBar.tsx` | 顶部阶段、天数、胜负、音频状态 |
| `PlayerRing` | `frontend/src/game-ui/PlayerRing.tsx` | 把玩家按座位摆到桌边 |
| `PlayerSeatCard` | `frontend/src/game-ui/PlayerSeatCard.tsx` | 单个玩家座位展示和点击状态 |
| `TableCenter` | `frontend/src/game-ui/TableCenter.tsx` | 中央牌桌、当前阶段、当前行动、最新关键事件 |
| `ActionDock` | `frontend/src/game-ui/ActionDock.tsx` | 底部操作区，替代大部分 `PhaseSceneRouter` 表单样式 |
| `EventRail` | `frontend/src/game-ui/EventRail.tsx` | 右侧事件叙事轨，把技术事件转成人话 |
| `SpeechBubbleLayer` | `frontend/src/game-ui/SpeechBubbleLayer.tsx` | 玩家发言气泡和流式输出 |
| `EffectsLayer` | `frontend/src/game-ui/EffectsLayer.tsx` | 阶段切换、查验、出局、投票等特效 |
| `PlayerDetailDrawer` | `frontend/src/game-ui/PlayerDetailDrawer.tsx` | 点击玩家后弹出的玩家详情 |
| `gameVisuals.ts` | `frontend/src/game-ui/gameVisuals.ts` | 纯函数：派生视觉状态、事件文案、座位位置 |
| `gameVisualTypes.ts` | `frontend/src/game-ui/gameVisualTypes.ts` | 前端视觉状态类型 |

### 保留和调整

| 文件 | 调整方式 |
| --- | --- |
| `frontend/src/GameTable.tsx` | 缩小为容器：接收 props，调用 `GameTableShell` |
| `frontend/src/PhaseSceneRouter.tsx` | 逐步瘦身，第一阶段可以保留逻辑，第二阶段把 UI 移入 `ActionDock` |
| `frontend/src/stores/gameStore.ts` | 不改游戏核心状态，只新增最近视觉事件队列 |
| `frontend/src/index.css` | 增加游戏桌面相关 CSS 变量、动画和 reduced-motion 处理 |

---

## 视觉状态设计

### 玩家座位应该展示的信息

每个座位固定展示：

1. 座位号，例如 `3`
2. 头像或名字首字
3. 玩家名
4. 存活状态
5. 当前是否发言
6. 是否是你
7. 是否警长
8. 是否已投票
9. 只有自己视角可见的身份标签
10. 查验结果标记，如果已有

### 玩家座位状态优先级

同一个玩家可能同时有多个状态，视觉优先级建议如下：

1. `speaking`：当前发言，最高优先级，金色脉冲边框和语音波纹。
2. `selectable`：当前行动可选目标，显示可点击高亮。
3. `selected`：玩家已选择该目标，显示目标环或投票筹码。
4. `eliminated`：出局，头像变灰，座位上放“出局”印章。
5. `checked_good` / `checked_wolf`：查验结果，仅自己可见时用私密标识。
6. `voted`：已投票，小筹码标记。
7. `self`：自己，使用稳定的绿色/青色小标识，不要抢过行动焦点。

### 建议类型

```ts
export interface PlayerVisualState {
  playerId: string;
  seat: number;
  displayName: string;
  roleLabel?: string;
  alive: boolean;
  isSelf: boolean;
  isSheriff: boolean;
  speaking: boolean;
  voted: boolean;
  selectable: boolean;
  selected: boolean;
  checkedCamp?: "good" | "wolf";
  visualTone: "normal" | "self" | "speaking" | "selectable" | "selected" | "dead";
}
```

---

## 事件叙事轨设计

### 现在的问题

现在右侧事件类似：

```text
phase_changed 遗言结束，进入下一阶段。
night_step_started 狼人开始行动。
night_step_finished 狼人行动完成。
```

玩家看到的是系统日志，不是游戏过程。

### 改造目标

展示为：

```text
阶段推进
遗言结束，游戏进入第二夜。

夜晚行动
狼人睁眼，正在选择袭击目标。

夜晚行动
狼人行动结束。
```

### 事件文案映射

在 `gameVisuals.ts` 新增：

```ts
export function eventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    phase_changed: "阶段推进",
    night_step_started: "夜晚行动",
    night_step_finished: "夜晚行动",
    speech_completed: "玩家发言",
    speech_delta: "实时发言",
    current_speaker_changed: "轮到发言",
    night_result: "昨夜结果",
    private_info: "私密信息",
    game_created: "房间创建",
    game_end: "游戏结束",
    role_reveal: "身份揭晓",
    last_words: "遗言",
    exile: "放逐结果",
  };
  return labels[eventType] ?? "游戏事件";
}
```

### 事件分组

事件轨不要永远显示全量流水。建议分三层：

1. **最新关键事件**：置顶显示 1 条，字体更大。
2. **当前阶段事件**：默认展开。
3. **历史事件**：折叠，可点击展开。

### 事件筛选

提供三个小切换按钮：

| 筛选 | 显示 |
| --- | --- |
| 全部 | 所有公开事件 |
| 发言 | `speech_completed`、`last_words`、流式发言 |
| 行动 | 投票、夜晚、查验、死亡、阶段切换 |

第一版可以只做按钮 UI 和本地过滤，不需要后端支持。

---

## 关键特效清单

### 1. 当前发言特效

触发条件：

```ts
player.speaking === true
```

表现：

1. 玩家座位边框金色呼吸。
2. 头像外有 2 层语音波纹。
3. 桌面中央显示“正在发言：X 号 玩家名”。
4. 如果有 `streamingSpeeches[playerId]`，在座位旁显示发言气泡，文字流式增长。

验收：

1. 当前发言者不用看日志也能一眼找到。
2. 发言结束后气泡淡出，不保留残影。
3. 多个流式数据到来时不抖动布局。

### 2. 夜晚幕布特效

触发条件：

```ts
game.phase === "night"
```

表现：

1. 页面整体进入低亮度蓝黑色。
2. 中央桌面出现“天黑请闭眼”。
3. 非当前操作者座位降低透明度。
4. 如果玩家有夜间行动，合法目标座位出现冷色可选环。

验收：

1. 夜晚和白天视觉差异明显。
2. 仍能看清按钮和目标，不牺牲可用性。
3. `prefers-reduced-motion` 下不做大面积闪动。

### 3. 天亮揭晓特效

触发条件：

```ts
game.phase === "day_announcement"
```

表现：

1. 顶部或中央出现晨光扫过。
2. 最新 `night_result` 在桌面中央翻牌式展示。
3. 被击杀玩家座位出现倒牌标记。

验收：

1. 玩家能立刻知道昨夜谁倒牌。
2. 如果平安夜，展示“昨夜平安夜”而不是空状态。

### 4. 投票筹码特效

触发条件：

1. 玩家进入 `exile_vote`。
2. 本人选择投票目标。
3. 某个玩家 `voted === true`。

表现：

1. 当前可投目标座位浮现小筹码。
2. 选择目标后，一个筹码从底部行动坞飞到目标座位。
3. 已投票玩家座位显示“已投”小印章。
4. 投票结束时中央桌面展示最高票玩家。

验收：

1. 投票目标选择不再只依赖 radio。
2. 误点后可以改选，提交前目标清晰。
3. 弃票按钮仍明确可用。

### 5. 查验结果特效

当前已经有 `overlayResult`，建议升级：

1. Overlay 保留，但改为“卡牌翻开”。
2. 查验目标座位同步高亮。
3. 查验结果在自己视角持续显示小标记。

验收：

1. 查验结果出现 3 秒后消失，但座位标记仍保留。
2. 好人/狼人颜色区分明显，不只靠颜色，文字也要明确。

### 6. 女巫药水特效

触发条件：

1. `primaryAction.night_kill_info` 存在。
2. 选择解药、毒药或不行动。

表现：

1. 被刀玩家座位出现红色危险环。
2. 解药按钮使用绿色药瓶视觉。
3. 毒药按钮使用紫色药瓶视觉。
4. 选择毒药后，可毒目标座位出现紫色可选环。

验收：

1. 女巫能一眼知道今晚刀口。
2. 毒药目标不会和解药目标混淆。

### 7. 出局和遗言特效

触发条件：

1. `player.alive` 从 true 变 false。
2. `game.phase === "last_words"`。

表现：

1. 出局玩家座位翻暗，盖上“出局”印章。
2. 遗言阶段中央桌面变成烛光/最后陈述样式。
3. 遗言文字显示成独立引用块，不混在普通事件里。

验收：

1. 出局状态强，但不要完全看不清玩家名。
2. 遗言阶段有明显仪式感。

### 8. 复盘翻牌特效

触发条件：

```ts
game.phase === "game_over"
```

表现：

1. 中央展示胜利阵营。
2. 玩家座位逐个翻牌，显示真实身份。
3. 狼人阵营和好人阵营用阵营框分组。
4. 事件轨切换为“复盘时间线”。

验收：

1. 复盘不是简单文本列表。
2. 所有身份能完整显示，不遮挡。

---

## 操作交互设计

### 投票阶段

当前：

1. 下方面板 radio 选人。
2. 点投票按钮。

目标：

1. 座位可直接点击选择目标。
2. 底部行动坞显示“你将投给：5 号 彭牢 y”。
3. 玩家仍可在行动坞中使用下拉/列表改选，保证可访问性。
4. 点击投票后按钮进入 pending 状态，显示“正在提交”。

实现步骤：

1. `ActionDock` 根据 `game.phase` 和 `allowed_actions` 计算当前动作。
2. `GameTableShell` 维护 `selectedTargetId`。
3. `PlayerRing` 接收 `selectablePlayerIds` 和 `selectedTargetId`。
4. `PlayerSeatCard` 点击时调用 `onSelectTarget(playerId)`。
5. `ActionDock` 提交时调用 `onSubmitAction({ action_type: "vote", target_player_id: selectedTargetId })`。

### 夜间目标阶段

当前：

1. 夜间技能目标在下方面板 radio 中选择。

目标：

1. 可选目标座位有冷色光环。
2. 点击目标座位选择。
3. 中央桌面显示当前技能，例如“预言家正在查验”。
4. 提交按钮文案使用后端 `primaryAction.label`。

### 发言阶段

当前：

1. 文本框在下方面板。
2. 提交后等待。

目标：

1. 当轮到人类发言时，行动坞变成发言台。
2. 文本框上方显示“你正在发言”。
3. 提供 3 个快速模板按钮：
   - “我先报信息”
   - “我怀疑 X”
   - “我先听后置位”
4. 模板只填充文本，不自动提交。
5. 提交后当前座位短暂出现自己的发言气泡。

### 点击玩家详情

点击任意玩家座位打开 `PlayerDetailDrawer`。

第一版详情内容：

1. 座位号和玩家名。
2. 存活状态。
3. 是否警长。
4. 是否当前发言。
5. 最近一条公开发言或事件。
6. 如果该玩家是当前合法目标，显示“选择为目标”按钮。

注意：

1. 不要泄露其他玩家隐藏身份。
2. 只有自己的 `role_key` 或游戏结束后的身份才显示。

---

## 阶段体验设计

| 阶段 | 中央桌面文案 | 主视觉 | 操作方式 |
| --- | --- | --- | --- |
| `setup` | 准备开局 | 玩家座位逐个入座 | 开始游戏按钮 |
| `night` | 天黑请闭眼 | 暗色幕布、冷色目标环 | 点座位选择夜间目标 |
| `day_announcement` | 天亮了 | 晨光、昨夜结果卡牌 | 继续按钮 |
| `sheriff_election` | 警长竞选 | 警徽在中央 | 参选/退选按钮，若后端支持 |
| `sheriff_speech` | 警上发言 | 发言聚光灯 | 发言/旁听 |
| `day_speech` | 白天发言 | 当前发言座位聚光 | 发言文本框或旁听 |
| `exile_vote` | 放逐投票 | 投票筹码 | 点座位投票 |
| `last_words` | 遗言 | 烛光、出局座位突出 | 继续按钮 |
| `game_over` | 游戏复盘 | 身份翻牌 | 返回大厅 |

注意：当前 `PhaseSceneRouter.tsx` 对 `sheriff_election` 和 `sheriff_speech` 没有明确分支，容易落到复盘 UI。改造时必须补上这两个阶段的 observer/action UI。

---

## 样式方向

### 整体气质

关键词：

1. 暗色木桌
2. 羊皮纸事件卡
3. 金色烛光
4. 夜晚冷蓝
5. 狼人红色危险反馈
6. 预言家绿色/青色私密信息

### CSS Token 建议

在 `frontend/src/index.css` 增加：

```css
@theme {
  --color-table-felt: #211d17;
  --color-table-wood: #3a261b;
  --color-table-edge: #6f4a2d;
  --color-candle: #ffcf7a;
  --color-night-fog: #121a2a;
  --color-vote-chip: #e7c06b;
  --color-dead-ink: #12100e;
}
```

### 动效原则

1. 所有动画都控制在 150ms 到 700ms。
2. 阶段切换可以用 900ms，但不能阻塞操作。
3. 循环动画只用于当前发言者和夜晚氛围。
4. 支持：

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 数据和状态改造

### 第一版不要求后端新增字段

现有字段已经够用：

| 体验 | 可用字段 |
| --- | --- |
| 当前发言 | `player.speaking`、`current_turn_player_id`、`streamingSpeeches` |
| 出局 | `player.alive` |
| 已投票 | `player.voted` |
| 当前阶段 | `game.phase` |
| 天数 | `game.day_count` |
| 查验结果 | `seerResults` |
| 事件轨 | `game.public_events`、SSE event |
| 可选行动 | `game.allowed_actions` |
| 夜间刀口 | `primaryAction.night_kill_info` |

### 建议新增前端派生状态

在 `gameVisuals.ts` 中放纯函数：

```ts
export function selectablePlayerIds(game: GameStateDto): string[] {
  return game.allowed_actions.flatMap((action) =>
    action.target_options?.map((target) => target.player_id) ?? []
  );
}

export function currentActionKind(game: GameStateDto): "none" | "speech" | "vote" | "night_target" | "continue" {
  const action = game.allowed_actions[0];
  if (!action) return "none";
  if (action.action_type === "speech") return "speech";
  if (action.action_type === "vote") return "vote";
  if (action.requires_target) return "night_target";
  return "continue";
}
```

### 可选后端增强字段

如果后端愿意配合，后续可以加：

| 字段 | 用途 | 优先级 |
| --- | --- | --- |
| `event.severity` | 区分普通/关键/私密事件 | 中 |
| `event.display_type` | 指定事件视觉类型，如 `kill`、`vote`、`reveal` | 中 |
| `vote_records` | 展示投票箭头和票型 | 高 |
| `speech_order` | 展示发言顺序队列 | 中 |
| `player.last_speech_summary` | 玩家详情里展示摘要 | 低 |

第一版不要依赖这些字段。

---

## 详细执行计划

### 阶段 0：基线确认

- [ ] 运行 `cd frontend && npm test -- --run`，确认现有测试状态。
- [ ] 运行 `cd frontend && npm run build`，确认当前构建状态。
- [ ] 截图保存当前游戏页，作为改造前对比。
- [ ] 确认 `GameTablePage.test.tsx` 覆盖基本渲染、pending、streaming speech。

验收：

- [ ] 测试和构建结果记录在 PR 描述或开发记录中。
- [ ] 有改造前截图。

### 阶段 1：纯函数和类型先行

- [ ] 新建 `frontend/src/game-ui/gameVisualTypes.ts`。
- [ ] 定义 `PlayerVisualState`。
- [ ] 定义 `VisualEventItem`。
- [ ] 定义 `ActionDockState`。
- [ ] 新建 `frontend/src/game-ui/gameVisuals.ts`。
- [ ] 实现 `roleLabel(roleKey)`，迁移现有重复函数。
- [ ] 实现 `phaseLabel(phase)`，迁移 `GameTable.tsx` 的 `phaseLabels`。
- [ ] 实现 `eventLabel(eventType)`。
- [ ] 实现 `eventMessage(event)`，优先返回 `event.payload.message`。
- [ ] 实现 `selectablePlayerIds(game)`。
- [ ] 实现 `derivePlayerVisualStates(game, selectedTargetId, seerResults)`。
- [ ] 为 `gameVisuals.ts` 写单元测试。

验收：

- [ ] 不改 UI 也能通过测试。
- [ ] `eventLabel("phase_changed")` 返回“阶段推进”。
- [ ] 出局、发言、已投票、自身玩家都能派生正确视觉状态。

### 阶段 2：拆出布局骨架

- [ ] 新建 `GameTableShell.tsx`。
- [ ] 把 `GameTable.tsx` 的主 JSX 移到 `GameTableShell`。
- [ ] `GameTable.tsx` 只保留 props 转发。
- [ ] 新建 `PhaseStatusBar.tsx`。
- [ ] 把顶部 header 改成 `PhaseStatusBar`。
- [ ] 新建 `EventRail.tsx`。
- [ ] 把右侧事件时间线移入 `EventRail`。
- [ ] 保持视觉基本不变，先确保无行为回归。

验收：

- [ ] 原有 `GameTablePage.test.tsx` 通过。
- [ ] 页面仍显示阶段、座位、事件、操作按钮。
- [ ] 没有引入新业务行为。

### 阶段 3：玩家环和中央桌面

- [ ] 新建 `PlayerRing.tsx`。
- [ ] 新建 `PlayerSeatCard.tsx`。
- [ ] 新建 `TableCenter.tsx`。
- [ ] 桌面端用 CSS grid/absolute 摆位，6 人局固定如下：

```ts
const sixSeatLayout = [
  { gridArea: "bottom-left" },
  { gridArea: "top-left" },
  { gridArea: "top" },
  { gridArea: "left" },
  { gridArea: "right" },
  { gridArea: "bottom" },
];
```

- [ ] 第一版可以不用真的圆形数学布局，先做“围绕中央桌面”的稳定布局。
- [ ] 中央桌面展示当前阶段、天数、最新关键事件。
- [ ] 玩家卡片缩小，降低空白面积。
- [ ] 自己的座位增加“你”标记。
- [ ] 当前发言玩家增加金色边框和波纹。

验收：

- [ ] 1366px 宽度下第一屏能看到完整牌桌、事件轨和行动坞。
- [ ] 玩家座位不再是 3x2 大空卡片。
- [ ] 当前发言玩家一眼可见。
- [ ] 文字不溢出、不重叠。

### 阶段 4：行动坞接管目标选择

- [ ] 新建 `ActionDock.tsx`。
- [ ] 在 `GameTableShell` 中维护 `selectedTargetId`。
- [ ] `ActionDock` 接收 `selectedTargetId`、`onSelectTarget`、`onSubmitAction`。
- [ ] `PlayerSeatCard` 接收 `selectable`、`selected`、`onSelect`。
- [ ] 投票阶段允许点击座位选目标。
- [ ] 夜间需要目标的行动允许点击座位选目标。
- [ ] radio 列表保留为行动坞内的辅助目标列表。
- [ ] 提交按钮始终显示将要提交的目标。

验收：

- [ ] 投票可以通过点座位完成目标选择。
- [ ] 夜间查验/毒药/守护可以通过点座位完成目标选择。
- [ ] 不能选择非法目标。
- [ ] pending 时按钮禁用，座位点击不提交重复请求。

### 阶段 5：事件叙事轨升级

- [ ] `EventRail` 使用 `eventLabel()` 隐藏技术事件名。
- [ ] 最新关键事件置顶。
- [ ] 历史事件默认折叠到最近 12 条。
- [ ] 增加“全部 / 发言 / 行动”本地筛选。
- [ ] 流式发言从普通事件列表中移出，交给 `SpeechBubbleLayer` 展示，同时在事件轨显示简短状态。

验收：

- [ ] 右侧不再直接显示 `night_step_started` 这类技术名。
- [ ] 玩家能读懂事件。
- [ ] 长日志不会把右侧挤成一整条流水账。

### 阶段 6：发言气泡层

- [ ] 新建 `SpeechBubbleLayer.tsx`。
- [ ] 根据 `streamingSpeeches` 找到对应玩家座位。
- [ ] 桌面端气泡显示在座位附近。
- [ ] 移动端气泡显示在中央桌面下方。
- [ ] 发言结束后气泡淡出。
- [ ] 人类提交发言后，自己的发言也短暂显示一次。

验收：

- [ ] AI 流式发言不只出现在事件轨。
- [ ] 气泡不会遮挡行动按钮。
- [ ] 长发言最多显示固定高度，内部滚动或折叠。

### 阶段 7：阶段特效层

- [ ] 新建 `EffectsLayer.tsx`。
- [ ] 夜晚阶段增加全局暗幕。
- [ ] 天亮阶段增加短暂晨光扫过。
- [ ] `day_announcement` 显示昨夜结果卡。
- [ ] `seerResults` 新增时触发翻牌 overlay。
- [ ] 玩家出局时触发座位出局动画。
- [ ] 投票提交时触发筹码飞行动画。
- [ ] 增加 `prefers-reduced-motion` 降级。

验收：

- [ ] 阶段变化有明显感知。
- [ ] 动画不阻塞点击。
- [ ] reduced-motion 环境下仍可用。

### 阶段 8：补齐警长阶段 UI

- [ ] 在 `PhaseSceneRouter.tsx` 或新 `ActionDock` 中明确处理 `sheriff_election`。
- [ ] 明确处理 `sheriff_speech`。
- [ ] 如果当前后端没有参选动作，就显示 observer 状态。
- [ ] 警长玩家座位显示警徽。
- [ ] 中央桌面展示警徽状态。

验收：

- [ ] `sheriff_election` 不会误显示复盘。
- [ ] `sheriff_speech` 不会误显示复盘。
- [ ] 警长标识清楚。

### 阶段 9：复盘体验

- [ ] `game_over` 时 `TableCenter` 展示胜利阵营。
- [ ] 所有玩家座位逐个显示真实身份。
- [ ] 阵营颜色区分但不只靠颜色。
- [ ] 右侧事件轨切换为复盘时间线。
- [ ] 返回大厅按钮放入行动坞。

验收：

- [ ] 游戏结束截图有仪式感。
- [ ] 身份完整可读。
- [ ] 用户知道下一步可以返回大厅。

### 阶段 10：移动端和可访问性

- [ ] 375px 宽度下检查所有文本。
- [ ] 768px 宽度下检查平板布局。
- [ ] 行动坞在移动端 sticky bottom。
- [ ] 事件轨移动端默认折叠。
- [ ] 所有可点击座位支持键盘 focus。
- [ ] 玩家座位按钮提供 `aria-label`，例如“选择 5 号 彭牢 y 为投票目标”。
- [ ] 颜色状态都配文字或图标。

验收：

- [ ] 手机上能完成开局、发言、投票、夜间目标选择。
- [ ] 键盘可以选择目标并提交。
- [ ] 无明显文本重叠。

---

## 测试计划

### 单元测试

新增：

```text
frontend/src/game-ui/gameVisuals.test.ts
```

覆盖：

1. 阶段标签。
2. 角色标签。
3. 事件标签。
4. 可选目标提取。
5. 玩家视觉状态派生。
6. 当前行动类型判断。

### 组件测试

更新或新增：

```text
frontend/src/GameTablePage.test.tsx
frontend/src/game-ui/ActionDock.test.tsx
frontend/src/game-ui/EventRail.test.tsx
frontend/src/game-ui/PlayerRing.test.tsx
```

覆盖：

1. 渲染桌面中央区域。
2. 当前发言玩家高亮。
3. 流式发言显示。
4. 投票阶段点击玩家座位选择目标。
5. 夜间阶段点击合法目标。
6. 非法目标不可点击。
7. pending 时不能重复提交。
8. 事件技术名被转义成人话。
9. 警长阶段不会落到复盘。

### 手工验收

必须手工走一遍：

1. 普通村民白天发言。
2. 放逐投票。
3. 预言家查验。
4. 女巫看到刀口、选择救或毒。
5. 狼人夜间刀人。
6. 玩家出局遗言。
7. 游戏结束复盘。

每一步都截图，确认：

1. 当前阶段明确。
2. 当前行动明确。
3. 可点击目标明确。
4. 关键结果有反馈。
5. 页面没有重叠和溢出。

---

## 推荐实施顺序

最推荐按这个顺序做：

1. 先做 `gameVisuals.ts` 和测试。
2. 拆 `GameTableShell`、`PhaseStatusBar`、`EventRail`，保持视觉不大变。
3. 做 `PlayerRing` 和 `TableCenter`，把页面从卡片网格变成桌游桌面。
4. 做 `ActionDock`，让投票和夜间目标可以点座位。
5. 做 `SpeechBubbleLayer`，让实时发言出现在玩家旁边。
6. 做 `EffectsLayer`，加阶段、查验、投票、出局特效。
7. 补警长阶段。
8. 做移动端和可访问性收尾。
9. 最后做复盘翻牌。

这个顺序的好处是每一步都能单独验收，不需要一次性大重构。

---

## 给开发同学的傻瓜版任务列表

### 第 1 组：准备

- [ ] 打开 `frontend/src/GameTable.tsx`，确认现有玩家卡片和事件轨位置。
- [ ] 打开 `frontend/src/PhaseSceneRouter.tsx`，确认当前投票和夜间行动表单。
- [ ] 打开 `frontend/src/stores/gameStore.ts`，确认 `streamingSpeeches` 和 `seerResults`。
- [ ] 执行 `cd frontend && npm test -- --run`。
- [ ] 执行 `cd frontend && npm run build`。

### 第 2 组：纯函数

- [ ] 创建 `frontend/src/game-ui/` 文件夹。
- [ ] 创建 `gameVisualTypes.ts`。
- [ ] 创建 `gameVisuals.ts`。
- [ ] 把 `roleLabel` 从 `GameTable.tsx` 复制到 `gameVisuals.ts`。
- [ ] 把 `phaseLabels` 从 `GameTable.tsx` 复制到 `gameVisuals.ts`。
- [ ] 写 `eventLabel()`。
- [ ] 写 `selectablePlayerIds()`。
- [ ] 写 `derivePlayerVisualStates()`。
- [ ] 创建 `gameVisuals.test.ts`。
- [ ] 跑测试。

### 第 3 组：组件拆分

- [ ] 创建 `PhaseStatusBar.tsx`。
- [ ] 创建 `EventRail.tsx`。
- [ ] 创建 `GameTableShell.tsx`。
- [ ] 把 `GameTable.tsx` 的 header JSX 移到 `PhaseStatusBar`。
- [ ] 把事件 aside JSX 移到 `EventRail`。
- [ ] `GameTable.tsx` 改成只渲染 `GameTableShell`。
- [ ] 跑 `GameTablePage.test.tsx`。

### 第 4 组：牌桌布局

- [ ] 创建 `TableCenter.tsx`。
- [ ] 创建 `PlayerSeatCard.tsx`。
- [ ] 创建 `PlayerRing.tsx`。
- [ ] 在 `GameTableShell` 里用 `PlayerRing` 替换原来的 3 列玩家网格。
- [ ] 在 `PlayerRing` 中实现 6 人布局。
- [ ] 在 `TableCenter` 中显示当前阶段和最新关键事件。
- [ ] 在 `PlayerSeatCard` 中显示头像、座位号、姓名、状态标签。
- [ ] 给当前发言玩家加高亮样式。
- [ ] 浏览器检查 1366x768。

### 第 5 组：操作坞

- [ ] 创建 `ActionDock.tsx`。
- [ ] 把 `PhaseSceneRouter` 中投票 UI 的行为迁到 `ActionDock`。
- [ ] 在 `GameTableShell` 中增加 `selectedTargetId` state。
- [ ] 把 `selectedTargetId` 传给 `PlayerRing`。
- [ ] 点击玩家座位时更新 `selectedTargetId`。
- [ ] `ActionDock` 提交投票时使用 `selectedTargetId`。
- [ ] 夜间目标行动复用同一套目标选择。
- [ ] 保留弃票按钮。
- [ ] 写点击座位投票测试。

### 第 6 组：事件轨

- [ ] `EventRail` 中使用 `eventLabel()`。
- [ ] 最新关键事件置顶。
- [ ] 默认只显示最近 12 条历史事件。
- [ ] 增加“全部 / 发言 / 行动”筛选按钮。
- [ ] 写测试确认不显示原始 `phase_changed` 文案。

### 第 7 组：发言气泡

- [ ] 创建 `SpeechBubbleLayer.tsx`。
- [ ] 从 `streamingSpeeches` 读取实时发言。
- [ ] 根据玩家 id 找到座位。
- [ ] 桌面端气泡靠近玩家座位。
- [ ] 移动端气泡放在中央桌面下。
- [ ] 发言结束淡出。
- [ ] 写测试确认流式发言仍可见。

### 第 8 组：特效层

- [ ] 创建 `EffectsLayer.tsx`。
- [ ] 夜晚阶段加暗幕。
- [ ] 天亮阶段加晨光效果。
- [ ] 查验结果改成翻牌 overlay。
- [ ] 出局玩家座位加印章。
- [ ] 投票提交加筹码动画。
- [ ] 增加 reduced-motion CSS。

### 第 9 组：补阶段

- [ ] 在 `ActionDock` 或 `PhaseSceneRouter` 中补 `sheriff_election`。
- [ ] 在 `ActionDock` 或 `PhaseSceneRouter` 中补 `sheriff_speech`。
- [ ] 没有可操作动作时展示等待状态。
- [ ] 警长玩家显示警徽。

### 第 10 组：收尾

- [ ] 检查手机宽度。
- [ ] 检查平板宽度。
- [ ] 检查 1366x768。
- [ ] 检查 1440x900。
- [ ] 跑 `cd frontend && npm test -- --run`。
- [ ] 跑 `cd frontend && npm run build`。
- [ ] 录制或截图一局完整流程。

---

## 验收标准

### 体验验收

| 标准 | 通过条件 |
| --- | --- |
| 桌游感 | 第一眼能看出玩家围绕牌桌，而不是普通卡片列表 |
| 当前阶段明确 | 不看事件轨也知道现在是夜晚、白天、投票还是复盘 |
| 当前发言明确 | 当前说话玩家一眼可见 |
| 行动目标明确 | 投票、查验、毒药等目标可以通过座位选择 |
| 事件可读 | 右侧事件不出现裸露技术事件名 |
| 关键反馈明确 | 查验、死亡、投票、胜利都有视觉反馈 |
| 移动端可用 | 375px 宽度可完整完成一局关键操作 |

### 技术验收

| 标准 | 通过条件 |
| --- | --- |
| 不破坏现有 API | `GameStateDto`、`SubmitActionInput` 不需要后端同步改动 |
| 测试通过 | `cd frontend && npm test -- --run` 通过 |
| 构建通过 | `cd frontend && npm run build` 通过 |
| 组件边界清楚 | `GameTable.tsx` 不再堆所有 UI |
| 动效可降级 | `prefers-reduced-motion` 生效 |
| 无文本重叠 | 桌面和移动端主要状态无重叠 |

---

## 风险和规避

| 风险 | 可能后果 | 规避方式 |
| --- | --- | --- |
| 一次性重构太大 | 难测、难回滚 | 按阶段提交，每阶段保持可运行 |
| 特效太多 | 卡顿、喧宾夺主 | 特效只绑定关键状态，默认克制 |
| 座位点击和表单状态不同步 | 提交错误目标 | 目标选择统一放在 `GameTableShell` |
| 事件文案误导 | 玩家理解错误 | `eventLabel` 只改标签，不擅自改后端 message |
| 移动端空间不够 | 操作困难 | 行动坞 sticky，事件轨折叠 |
| 隐藏身份泄露 | 破坏游戏 | `PlayerSeatCard` 必须按当前视角决定是否显示身份 |

---

## 最终推荐版本定义

第一版完成后，玩家应该有这样的感受：

1. 进入游戏后看到的是一张“狼人杀桌”，不是一组直播卡片。
2. AI 发言时，能看到对应玩家座位发光和发言气泡。
3. 夜晚时页面明显变暗，自己知道该点谁行动。
4. 投票时像把筹码投给某个座位，而不是填表。
5. 查验、死亡、遗言、复盘都有仪式感。
6. 右侧事件像主持人记录，而不是程序日志。

这版不追求炫技，重点是把“我在操作一个网页”变成“我在玩一局桌游”。
