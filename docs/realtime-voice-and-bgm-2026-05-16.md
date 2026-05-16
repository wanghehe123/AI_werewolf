# 实时语音与昼夜 BGM 实施记录（2026-05-16）

## 背景

本次基于飞书《AI Werewolf 系统现状报告》继续推进 Phase 2 游戏体验增强。现状中已经存在前端音频播放队列和 `/games/{game_id}/tts` 接口，但语音链路只覆盖部分 AI 发言，BGM 尚未接入。

目标有两项：

- 对局时前端把系统播报和玩家发言以语音形式播报。
- 根据当前白天或夜晚阶段，前端自动循环播放 `frontend/src/music` 下的 BGM。

## 实现内容

### MiniMax TTS 后端代理

- 新增 `ai_werewolf/tts/minimax.py`，封装 MiniMax 同步 HTTP TTS；WebSocket 实现保留为备用实现。
- `/games/{game_id}/tts` 保持原接口不变，内部改为调用 MiniMax，返回 `audio/mpeg`。
- API Key 只在后端读取，前端不会接触密钥。读取顺序：
  - `MINIMAX_API_KEY`
  - `ai_werewolf/config/llm.yaml` 中 MiniMax provider 的 `api_key`
- 默认配置：
  - `MINIMAX_TTS_MODEL=speech-2.8-turbo`
  - `MINIMAX_TTS_VOICE_ID=male-qn-qingse`
  - `MINIMAX_TTS_HTTP_ENDPOINT=https://api.minimaxi.com/v1/t2a_v2`
- 新增 `websockets` 依赖，用于保留 MiniMax TTS WebSocket 客户端。
- MiniMax 返回额度、限流或其他生成错误时，后端会降级到 `edge-tts`。
- TTS 生成使用后端串行锁，避免同时触发多条 edge-tts fallback 导致 `NoAudioReceived`。
- 当 MiniMax 和 edge-tts 都不可用时，接口返回 503，不再冒出 500。

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
- 前端音频队列会等待当前语音真正播放结束后再进入下一条，避免连续播报互相截断。
- 前端会在用户点击或键盘操作时解锁 WebAudio，规避浏览器自动播放限制。
- 如果后端 TTS 返回失败或音频解码失败，前端会用浏览器内置 `speechSynthesis` 中文语音作为最终兜底。

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

- MiniMax TTS HTTP 音频解析、配置文件 API Key 解析，以及 WebSocket chunk 聚合。
- `/games/{game_id}/tts` 的成功、空文本拒绝、MiniMax fallback、双 provider 失败返回 503。
- `gameStore` 将公开系统事件和玩家发言转换为语音播报。
- `private_info` 不进入公开语音队列。
- `AudioQueue` 等待当前音频播放结束后再播放下一条。
- `StreamPlayer` 在无服务端音频时调用浏览器语音兜底。
- 游戏阶段到 BGM 类型的映射。

建议运行：

```bash
ai_werewolf/.venv/bin/pytest tests/api/test_tts_api.py tests/api/test_games_api.py tests/tts/test_minimax_tts.py -q
cd frontend && npm test -- --run src/audio/AudioQueue.test.ts src/audio/StreamPlayer.test.ts src/stores/gameStore.test.ts src/audio/bgm.test.ts
cd frontend && npm run build
```

## 2026-05-16 调试记录

用户测试时出现“无任何语音播报”。日志定位到：

- MiniMax 接口已被调用，但当前账号返回 `usage limit exceeded`，截至 `2026-05-16T20:00:00+08:00` 前不可用。
- edge-tts fallback 在多条播报并发请求时偶发 `NoAudioReceived`，此前会导致 500。
- 前端 `AudioQueue` 将 `StreamPlayer.play()` 的“开始播放成功”误当作“播放结束”，后续播报会立刻打断前一条。
- WebAudio `AudioContext.resume()` 未等待，也缺少显式用户交互解锁，容易被浏览器自动播放策略静默拦截。

修复后：

- 后端 TTS 请求串行生成，并把 provider 全部失败转换为 503。
- 前端队列等待播放完成，失败时进入浏览器原生语音兜底。
- 服务已重启，验证接口 `POST /games/game_smoke/tts` 可返回有效 `audio/mpeg`。
