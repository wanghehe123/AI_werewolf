你必须输出一段合法 JSON 文本，不能输出 Markdown 或解释。

JSON 字段说明：
- speech: 发言内容或行动描述（中文）。发言阶段必须非空，投票/夜晚阶段可为空字符串
- action_type: 行动类型，参见下方枚举
- target_id: 目标玩家ID，无目标时填 null
- public_reason: 公开可见的游戏内理由（中文，可为null）
- private_memory_update: 仅写给自己的记忆更新（中文，可为null）

【action_type 枚举说明】：
$action_enum_lines

【输出示例（few-shot）】
$fewshot_lines
