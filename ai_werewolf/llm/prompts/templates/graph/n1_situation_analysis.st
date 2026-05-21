$common_blocks

你在帮助狼人杀 AI 做局势提炼。请从当前玩家视角提取最关键、最矛盾、最影响身份判断的信息。
必须优先围绕当前真实身份和阵营目标判断哪些信息最重要。
不要总结流水账，不要平均分配注意力，优先提取立场反复、发言与投票冲突、异常保护、异常跟票、查杀/金水后的反应。
必须先维护身份账本和轮次账本：梳理预言家对跳、神职声明、查杀跳神、狼坑候选、关键票型、当前是否必须出狼。
看到发言差、自投、摆烂、不配合时，只能记录为风险点，不能直接当成狼人结论。
relationship_edges[].relation 必须使用英文枚举：support, attack, protect, follow, distance, conflict, unknown。
只输出 JSON，不要输出 Markdown，不要解释。
JSON 格式如下：
{
  "key_facts": ["string"],
  "contradictions": [{"player_id": "string", "type": "string", "evidence": "string"}],
  "relationship_edges": [{"from": "string", "to": "string", "relation": "support", "confidence": 0.7}],
  "turning_points": ["string"]
}

输入上下文：
$payload_json
