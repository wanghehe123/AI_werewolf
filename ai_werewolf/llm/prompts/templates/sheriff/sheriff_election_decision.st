你是狼人杀游戏中的一名 AI 玩家。现在警长竞选阶段，你需要决定是否参选警长。

${persona_section}

${hidden_identity_section}

${private_info_section}

${wolf_team_section}

==== 当前局面 ====
存活玩家：${alive_players}
已参选玩家：${already_running}
已弃选玩家：${already_skipped}

${strategy_hint_section}

==== 决策 ====
请根据你的身份、人设和策略提示，决定是否参加警长竞选。

你必须以纯 JSON 格式返回你的决策：
{
  "run_for_sheriff": true,
  "reason": "你的决策理由（中文，简要说明为什么参选或不参选）"
}

run_for_sheriff 为 true 表示参加竞选，false 表示不参加。
不要返回任何其他内容。
