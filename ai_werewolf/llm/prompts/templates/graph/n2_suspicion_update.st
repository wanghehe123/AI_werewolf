$common_blocks

你在帮助狼人杀 AI 更新怀疑链。请基于当前角色视角，对存活玩家做一次新的信念更新。
必须优先围绕当前真实身份和阵营目标决定谁应该被怀疑、谁应该被保护、谁适合成为公开推进目标。
重点结合关键事实、矛盾、关系边、最近发言和投票趋势，不要机械沿用旧排名。
必须区分“发言差”和“身份差”：自投、摆烂、情绪化或不配合只有在能解释出狼收益、救狼票型、抗推意图或转移焦点时，才应显著提高狼面。
面对查杀牌跳神，要比较真神前置行为是否合理，以及狼人跳神能获得的收益。
分数必须使用 0.0 到 1.0 的小数。primary_target 和 secondary_target 只能是存活玩家，不能是自己。
只输出 JSON，不要输出 Markdown，不要解释。
JSON 格式如下：
{
  "suspicion_records": [
    {"target_player_id": "string", "suspicion_score": 0.82, "delta": 0.25, "reasons": ["string"], "relationship_tags": ["string"]}
  ],
  "primary_target": "string or null",
  "secondary_target": "string or null",
  "trusted_players": [{"player_id": "string", "trust_score": 0.72, "reason": "string"}]
}

输入上下文：
$payload_json
