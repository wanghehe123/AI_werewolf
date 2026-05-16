# 实时语音与昼夜 BGM 实施记录（2026-05-16）

## 背景

本次基于飞书《AI Werewolf 系统现状报告》继续推进 Phase 2 游戏体验增强。现状中已经存在前端音频播放队列和 `/games/{game_id}/tts` 接口，但语音链路只覆盖部分 AI 发言，BGM 尚未接入。

目标有两项：

- 对局时前端把系统播报和玩家发言以语音形式播报。
- 根据当前白天或夜晚阶段，前端自动循环播放 `frontend/src/music` 下的 BGM。

## 实现内容

### MiniMax TTS 后端代理

- 新增 `ai_werewolf/tts/minimax.py`，封装 MiniMax 同步 WebSocket TTS。
- `/games/{game_id}/tts` 保持原接口不变，内部改为调用 MiniMax，返回 `audio/mpeg`。
- API Key 只在后端读取，前端不会接触 `MINIMAX_API_KEY`。
- 默认配置：
  - `MINIMAX_TTS_MODEL=speech-2.8-turbo`
  - `MINIMAX_TTS_VOICE_ID=male-qn-qingse`
  - `MINIMAX_API_KEY` 必填
- 新增 `websockets` 依赖，用于运行时连接 MiniMax TTS WebSocket。

### 前端语音播报队列

- `gameStore` 新增 `audioAnnouncements`，把可播报事件转换为统一队列。
- 当前纳入播报的系统事件包括：
  - `phase_changed`
  - `night_step_started`
  - `night_step_finished`
  - `night_result`
  - `exile`
  - `game_end`
  - `last_words`
- 玩家发言通过 `speech_completed` 和新增公开事件差量进入语音队列。
- `private_info` 不会进入公开语音播报，避免泄露私密技能信息。
- `useTtsPlayback` 从统一队列消费文本，调用后端 TTS 后串行播放。

### 昼夜 BGM

- 新增 `frontend/src/audio/bgm.ts`，将游戏阶段映射为 `day`、`night` 或停止播放。
- 新增 `usePhaseBgm`：
  - `night` 播放 `werewolf_night.mp3`
  - 白天相关阶段播放 `werewolf_daytime.mp3`
  - `setup` 和 `game_over` 停止 BGM
- BGM 使用浏览器 `HTMLAudioElement` 循环播放。
- 受浏览器自动播放策略限制，BGM 会在首次用户交互后解锁播放。
- 语音播报开始时自动降低 BGM 音量，语音结束后恢复。

## 相关文件

- 后端 TTS：`ai_werewolf/tts/minimax.py`
- 游戏 API：`ai_werewolf/api/games.py`
- 前端音频队列：`frontend/src/audio/AudioQueue.ts`
- 前端 TTS Hook：`frontend/src/hooks/useTtsPlayback.ts`
- 前端 BGM Hook：`frontend/src/hooks/usePhaseBgm.ts`
- 前端状态：`frontend/src/stores/gameStore.ts`
- BGM 资源：`frontend/src/music/werewolf_daytime.mp3`、`frontend/src/music/werewolf_night.mp3`

## 验证

新增测试覆盖：

- MiniMax TTS WebSocket chunk 聚合。
- `/games/{game_id}/tts` 的成功与空文本拒绝。
- `gameStore` 将公开系统事件和玩家发言转换为语音播报。
- `private_info` 不进入公开语音队列。
- 游戏阶段到 BGM 类型的映射。

建议运行：

```bash
ai_werewolf/.venv/bin/pytest tests/tts/test_minimax_tts.py tests/api/test_tts_api.py -q
cd frontend && npm test -- --run src/stores/gameStore.test.ts src/audio/bgm.test.ts
cd frontend && npm run build
```
