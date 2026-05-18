# Player Decision RAG Strategy Hook

## Purpose

当前版本只预留策略提示入口，不实现 RAG 检索。未来可以根据 `role_key`、`decision_kind`、`phase`、`day`、`board_roles` 和局势摘要检索身份策略，并通过 `strategy_hint_provider` 注入玩家决策图。

## Existing Hook

`run_player_decision_graph(..., strategy_hint_provider=None)` 接收一个可选 provider。

Provider 输入是当前初始 state 的浅拷贝，至少包含：

- `game_id`
- `player_id`
- `role_key`
- `decision_kind`
- `memory_context`
- `alive_player_ids`

Provider 输出是最多 5 条策略 hint：

```json
[
  {
    "source": "rag:werewolf_day_speech_v1",
    "title": "狼人白天悍跳预言家",
    "content": "当局势需要抢轮次时，可以选择悍跳预言家，但必须维护连续查验链。",
    "weight": 0.86
  }
]
```

## Rules

- RAG hint 只能影响 `n1/n2/n3` 的语义判断和战术选择。
- RAG hint 不能覆盖真实身份、真实游戏事实、合法行动规则。
- `n4_decide_action` 和 `n6_validate_and_repair` 必须继续保持规则主导。
- 默认 provider 是 `None`，系统不能因为没有 RAG 而报错。

## Recommended Retrieval Keys

- `role_key=werewolf, decision_kind=day_speech`: 狼人白天发言策略，如悍跳、倒钩、切割、冲票、垫飞。
- `role_key=werewolf, decision_kind=exile_vote`: 狼人投票策略，如冲票、分票、保护队友、放弃队友。
- `role_key=seer, decision_kind=day_speech`: 预言家公开报验人、警徽流、隐藏身份时机。
- `role_key=seer, decision_kind=night_action`: 预言家查验优先级。
- `role_key=villager, decision_kind=day_speech`: 平民找狼、压榨身份、避免假装强神。
