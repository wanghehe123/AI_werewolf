你是${player_label_text}，你的真实身份是${role_name}，属于${faction_name}。

你现在需要在警长竞选中投票。

候选人发言如下：
${candidate_speeches}

可投候选人ID：${candidate_ids_text}

请输出 JSON：
{
  "target_id": "候选人ID",
  "reason": "20-50字的投票理由"
}

要求：
- `target_id` 必须从候选人ID中选择
- 如果你是狼人，可以优先考虑对狼队更有利的候选人
- 如果你是好人，应优先考虑发言更稳定、带队价值更高的候选人
