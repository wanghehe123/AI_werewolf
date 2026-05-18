# Player Decision Phase Prompt Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将玩家决策 LangGraph 中需要调用 LLM 的节点改造成“按阶段、按节点、按身份”选择 prompt 模板，并集中管理，同时显著提高 AI 对自己真实身份和阵营目标的敏感度。

**Architecture:** 新增一个玩家决策 prompt catalog，集中定义阶段目标、身份策略、节点职责、输出约束和未来 RAG 策略提示入口。现有 `build_situation_analysis_prompt`、`build_suspicion_update_prompt`、`build_strategy_prompt` 保持公开函数名不变，但内部改为从 catalog 渲染模板。传统 `prompt_builder.py` 的发言/投票/夜晚/遗言 prompt 复用同一套身份优先级文本，避免 LangGraph 与旧链路身份约束不一致。

**Tech Stack:** Python 3.12, LangGraph, Pydantic v2, pytest, existing `ai_werewolf.llm.graphs` and `ai_werewolf.llm.prompt_builder` modules.

---

## Current Context

当前相关文件：

- `ai_werewolf/llm/graphs/player_decision_prompts.py`
  - 目前集中放了 `n1/n2/n3` 三个语义节点的 prompt builder。
  - 问题是每个 builder 都是硬编码长字符串，只有少量 `decision_kind` 输入，没有真正按阶段拆模板。
- `ai_werewolf/llm/graphs/player_decision_graph.py`
  - `n1_analyze_situation`、`n2_update_suspicion`、`n3_decide_strategy` 会在 semantic node 开启时调用 LLM。
  - `n4_decide_action` 和 `n6_validate_and_repair` 是规则节点，不应改成自由 LLM。
  - `n5_generate_decision` 当前默认走 `_default_decision_from_state`，也可由外部 `decision_generator` 提供语言生成。
- `ai_werewolf/llm/prompt_builder.py`
  - 旧链路和 fallback 使用这里生成完整玩家 prompt。
  - 已有 `【隐藏身份】`、`【角色约束】`、`【你必须严格遵守的人格守则】`，但身份权重不够靠前、不够强，且与 LangGraph 语义节点 prompt 不共享。
- `tests/llm/test_player_decision_graph.py`
  - 已有语义节点 prompt builder 约束测试和 LangGraph 行为测试。
- `tests/llm/test_prompt_builder.py`、`ai_werewolf/tests/test_m2_prompt_constraints.py`
  - 覆盖旧 prompt builder 的基础约束。

最终链路仍保持：

```text
n1_analyze_situation        LLM: 按阶段/身份提取局势事实
        ↓
n2_update_suspicion         LLM + Rule: 按阶段/身份更新怀疑
        ↓
n3_decide_strategy          LLM: 按阶段/身份选择战术
        ↓
n4_decide_action            Rule: 确定合法动作
        ↓
n5_generate_decision        LLM or default: 只包装语言，不改结构化决策
        ↓
n6_validate_and_repair      Rule: 校验修复
```

## Design Decisions

1. 不把 prompt 模板散落在节点函数里。
   - 新增 `ai_werewolf/llm/graphs/player_decision_prompt_catalog.py`。
   - 所有阶段目标、身份策略和节点职责都在这个文件里集中管理。

2. 保持现有公开 builder 名称。
   - `build_situation_analysis_prompt(state)`、`build_suspicion_update_prompt(state)`、`build_strategy_prompt(state)` 的调用方不需要改名。
   - 内部改为调用 catalog 渲染器。

3. 身份信息在每个 LLM prompt 中都放高优先级。
   - 每个语义节点 prompt 都必须包含 `【身份优先级】`。
   - 旧 `prompt_builder.py` 的完整玩家 prompt 也必须包含同一套身份优先级文本。
   - 身份约束不是“背景信息”，而是“所有推理和策略必须服务的第一目标”。

4. RAG 只预留接口，不实现检索。
   - 新增 `strategy_hints` 字段，允许未来把 RAG 检索出的角色策略注入 prompt。
   - 默认值为空列表，不访问向量库、不新增数据库、不引入 embedding。
   - 示例策略如“狼人白天可选择悍跳预言家”只作为可注入 hint 的渲染格式测试，不作为默认强制策略。

5. 阶段模板必须覆盖至少三类 `decision_kind`。
   - `day_speech`
   - `exile_vote`
   - `night_action`
   - 旧链路还要继续覆盖 `last_words`。

## Target File Structure

### Create

- `ai_werewolf/llm/graphs/player_decision_prompt_catalog.py`
  - 负责集中定义和渲染玩家决策图 prompt 片段。

- `tests/llm/test_player_decision_prompt_catalog.py`
  - 负责测试阶段模板、身份优先级和 RAG hook 渲染。

### Modify

- `ai_werewolf/llm/graphs/player_decision_prompts.py`
  - 保留原有 public builder。
  - 用 catalog 生成阶段化 prompt。

- `ai_werewolf/llm/graphs/player_decision_state.py`
  - 增加 `strategy_hints` 可选字段。

- `ai_werewolf/llm/graphs/player_decision_graph.py`
  - 增加 `StrategyHintProvider` 类型。
  - `run_player_decision_graph` 增加可选参数 `strategy_hint_provider`，默认不做任何事。
  - 初始 state 写入 `strategy_hints`。

- `ai_werewolf/llm/prompt_builder.py`
  - 复用 catalog 中的身份优先级 block。
  - 加强旧链路完整 prompt 的身份敏感度。

- `tests/llm/test_player_decision_graph.py`
  - 补充 LangGraph prompt 能收到 `strategy_hints` 的测试。

- `tests/llm/test_prompt_builder.py`
  - 补充旧链路 prompt 包含身份优先级 block 的测试。

- `ai_werewolf/tests/test_m2_prompt_constraints.py`
  - 如果原有断言因为新增身份文本需要更新，只增量补充断言，不删除旧约束。

---

## Task 1: Add Prompt Catalog Tests First

**Files:**

- Create: `tests/llm/test_player_decision_prompt_catalog.py`
- No production code in this task.

- [ ] **Step 1: Create failing catalog tests**

Create `tests/llm/test_player_decision_prompt_catalog.py` with this content:

```python
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import (
    build_identity_priority_block,
    build_phase_focus_block,
    build_strategy_hint_block,
)


def test_identity_priority_block_emphasizes_werewolf_camp_and_public_disguise():
    block = build_identity_priority_block(role_key="werewolf", decision_kind="day_speech")

    assert "【身份优先级】" in block
    assert "你的真实身份：狼人" in block
    assert "你的阵营目标：狼人阵营获胜" in block
    assert "公开发言不能暴露狼队友" in block
    assert "可以伪装成好人视角" in block


def test_identity_priority_block_emphasizes_seer_private_information():
    block = build_identity_priority_block(role_key="seer", decision_kind="night_action")

    assert "【身份优先级】" in block
    assert "你的真实身份：预言家" in block
    assert "你的阵营目标：好人阵营获胜" in block
    assert "查验信息是你的核心资产" in block
    assert "不能编造不存在的查验结果" in block


def test_identity_priority_block_emphasizes_villager_no_fake_skill():
    block = build_identity_priority_block(role_key="villager", decision_kind="day_speech")

    assert "你的真实身份：平民" in block
    assert "没有夜晚技能信息" in block
    assert "不能假装自己拥有真实查验或用药信息" in block


def test_phase_focus_block_is_phase_specific():
    day = build_phase_focus_block("day_speech")
    vote = build_phase_focus_block("exile_vote")
    night = build_phase_focus_block("night_action")
    last_words = build_phase_focus_block("last_words")

    assert "白天发言阶段" in day
    assert "投票放逐阶段" in vote
    assert "夜晚行动阶段" in night
    assert "遗言阶段" in last_words
    assert "夜晚行动阶段" not in day
    assert "投票放逐阶段" not in night


def test_strategy_hint_block_renders_future_rag_hints_without_requiring_rag():
    block = build_strategy_hint_block(
        [
            {
                "source": "rag:werewolf_day_speech_v1",
                "title": "狼人白天悍跳预言家",
                "content": "当局势需要抢轮次时，可以选择悍跳预言家，但必须维护连续查验链。",
                "weight": 0.86,
            }
        ]
    )

    assert "【可选策略参考】" in block
    assert "狼人白天悍跳预言家" in block
    assert "悍跳预言家" in block
    assert "0.86" in block


def test_strategy_hint_block_is_explicitly_empty_when_no_hints():
    block = build_strategy_hint_block([])

    assert "【可选策略参考】" in block
    assert "当前没有外部策略提示" in block
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_prompt_catalog.py -q
```

Expected:

```text
ERROR tests/llm/test_player_decision_prompt_catalog.py
ModuleNotFoundError: No module named 'ai_werewolf.llm.graphs.player_decision_prompt_catalog'
```

---

## Task 2: Implement Prompt Catalog

**Files:**

- Create: `ai_werewolf/llm/graphs/player_decision_prompt_catalog.py`
- Test: `tests/llm/test_player_decision_prompt_catalog.py`

- [ ] **Step 1: Add the catalog module**

Create `ai_werewolf/llm/graphs/player_decision_prompt_catalog.py` with this content:

```python
"""Central prompt catalog for player decision graph semantic nodes."""

from __future__ import annotations

from typing import Any


ROLE_DISPLAY_NAMES: dict[str, str] = {
    "werewolf": "狼人",
    "wolf_king": "狼人",
    "wolf_beauty": "狼人",
    "seer": "预言家",
    "witch": "女巫",
    "hunter": "猎人",
    "guard": "守卫",
    "guardian": "守卫",
    "villager": "平民",
    "idiot": "白痴",
    "grave_keeper": "守墓人",
}


GOOD_ROLES = {"seer", "witch", "hunter", "guard", "guardian", "villager", "idiot", "grave_keeper"}
WOLF_ROLES = {"werewolf", "wolf_king", "wolf_beauty"}


PHASE_FOCUS: dict[str, list[str]] = {
    "day_speech": [
        "当前是白天发言阶段。",
        "目标是通过发言影响场上站边、制造或缓解压力、推动下一轮投票方向。",
        "输出必须服务于后续自然发言，重点关注可公开表达的逻辑链。",
    ],
    "exile_vote": [
        "当前是投票放逐阶段。",
        "目标是选择最符合当前身份胜利条件的放逐目标，并给出可公开解释的理由。",
        "输出必须服务于合法投票，不能选择自己，不能选择已出局玩家。",
    ],
    "night_action": [
        "当前是夜晚行动阶段。",
        "目标是根据身份技能和私有信息选择收益最高、风险最低的夜晚目标。",
        "输出必须服务于合法夜晚行动，不能泄露夜晚私有视角到公开发言。",
    ],
    "last_words": [
        "当前是遗言阶段。",
        "目标是在出局后留下对自己阵营有利的公开判断。",
        "遗言只影响公开发言，不直接改变游戏状态。",
    ],
}


ROLE_PRIORITIES: dict[str, list[str]] = {
    "werewolf": [
        "你的阵营目标：狼人阵营获胜。",
        "公开发言不能暴露狼队友，不能说出只有狼人阵营才知道的信息。",
        "可以伪装成好人视角，可以通过站边、倒钩、冲票、切割、悍跳等方式争取轮次。",
        "所有分析都要同时考虑：保护自己、保护关键狼队友、误导好人阵营、推动有利票型。",
    ],
    "wolf_king": [
        "你的阵营目标：狼人阵营获胜。",
        "公开发言不能暴露狼队友，且要为自己可能出局后的收益做准备。",
        "可以伪装成好人视角，也可以在必要时强势带节奏。",
        "所有分析都要同时考虑：保护自己、制造好人错误归因、为狼人阵营争取轮次。",
    ],
    "wolf_beauty": [
        "你的阵营目标：狼人阵营获胜。",
        "公开发言不能暴露狼队友，且要隐藏魅惑相关私有信息。",
        "可以伪装成好人视角，通过关系绑定、误导和节奏控制争取胜率。",
        "所有分析都要同时考虑：保护自己、保护狼队友、利用关系链扰乱好人判断。",
    ],
    "seer": [
        "你的阵营目标：好人阵营获胜。",
        "查验信息是你的核心资产，必须围绕真实查验结果建立视角。",
        "不能编造不存在的查验结果，不能查验自己，不能重复查验已经确认的人。",
        "所有分析都要同时考虑：保护查验链可信度、找出狼人、避免过早暴露导致夜晚被击杀。",
    ],
    "witch": [
        "你的阵营目标：好人阵营获胜。",
        "解药和毒药是你的核心资源，用药收益必须高于暴露风险。",
        "不能编造未发生的救人或毒人信息，不能把私有夜晚信息当成公开事实。",
        "所有分析都要同时考虑：保护关键好人、避免毒错强神或高可信好人、控制暴露时机。",
    ],
    "hunter": [
        "你的阵营目标：好人阵营获胜。",
        "开枪能力是威慑资源，发言要为可能的带人目标建立逻辑。",
        "不能编造查验、用药或守护信息。",
        "所有分析都要同时考虑：找狼、保持可信度、避免被狼人利用枪口方向。",
    ],
    "guard": [
        "你的阵营目标：好人阵营获胜。",
        "守护选择要基于狼刀收益和关键身份保护价值。",
        "不能编造查验或用药信息，不能公开泄露会让狼人轻易绕刀的守护计划。",
        "所有分析都要同时考虑：保护关键好人、避免连续守护非法目标、降低狼人预测成功率。",
    ],
    "guardian": [
        "你的阵营目标：好人阵营获胜。",
        "守护选择要基于狼刀收益和关键身份保护价值。",
        "不能编造查验或用药信息，不能公开泄露会让狼人轻易绕刀的守护计划。",
        "所有分析都要同时考虑：保护关键好人、避免连续守护非法目标、降低狼人预测成功率。",
    ],
    "villager": [
        "你的阵营目标：好人阵营获胜。",
        "你没有夜晚技能信息，只能依靠公开发言、投票、站边变化和死亡信息推理。",
        "不能假装自己拥有真实查验或用药信息，不能编造强神视角。",
        "所有分析都要同时考虑：找出狼人、保护可信强神、用清晰逻辑提高自己的好人可信度。",
    ],
    "idiot": [
        "你的阵营目标：好人阵营获胜。",
        "你需要用发言和投票帮助好人找狼，同时避免无意义暴露身份。",
        "不能编造查验、用药或守护信息。",
        "所有分析都要同时考虑：找出狼人、保持自己的可解释性、避免被狼人抗推。",
    ],
    "grave_keeper": [
        "你的阵营目标：好人阵营获胜。",
        "墓地信息是你的核心资产，公开使用时要注意时机和可信度。",
        "不能编造未获得的墓地信息，不能把猜测说成确定事实。",
        "所有分析都要同时考虑：找出狼人、保护真实信息来源、避免过早暴露。",
    ],
}


NODE_RESPONSIBILITIES: dict[str, list[str]] = {
    "n1": [
        "节点职责：只做局势提炼。",
        "只提取最关键、最矛盾、最影响身份判断的信息。",
        "不要制定最终策略，不要生成自然发言，不要决定投票或夜晚目标。",
    ],
    "n2": [
        "节点职责：只做怀疑与信任更新。",
        "基于 n1 结果、历史怀疑、最近事件和身份视角更新信念。",
        "不要生成自然发言，不要越过规则选择非法目标。",
    ],
    "n3": [
        "节点职责：只做战术选择。",
        "基于 n1 和 n2 的结果选择当前阶段最适合的策略。",
        "不要直接执行动作，不要改变规则节点将要校验的动作类型。",
    ],
    "n5": [
        "节点职责：只做语言包装。",
        "必须服从 n4 已经确定的 action_type 和 target_id。",
        "不能重新判断目标，不能把发言目标改成另一个玩家。",
    ],
}


def role_display_name(role_key: str) -> str:
    return ROLE_DISPLAY_NAMES.get(role_key, role_key)


def role_camp_goal(role_key: str) -> str:
    if role_key in WOLF_ROLES:
        return "狼人阵营获胜"
    if role_key in GOOD_ROLES:
        return "好人阵营获胜"
    return "当前身份所属阵营获胜"


def build_identity_priority_block(role_key: str, decision_kind: str) -> str:
    role_name = role_display_name(role_key)
    priorities = ROLE_PRIORITIES.get(
        role_key,
        [
            f"你的阵营目标：{role_camp_goal(role_key)}。",
            "所有分析和行动都必须服务于你的真实身份和阵营胜利条件。",
            "不能编造没有发生的身份信息、夜晚信息或技能结果。",
        ],
    )
    lines = [
        "【身份优先级】",
        f"你的真实身份：{role_name}",
        f"你的阵营目标：{role_camp_goal(role_key)}。",
        f"当前决策阶段：{decision_kind}",
        "这部分优先级高于通用推理：你不是旁观者，不能以上帝视角判断，必须以自己的真实身份和私有信息做决策。",
        *priorities,
    ]
    return "\n".join(lines)


def build_phase_focus_block(decision_kind: str) -> str:
    lines = PHASE_FOCUS.get(
        decision_kind,
        [
            f"当前阶段：{decision_kind}",
            "目标是根据当前阶段规则做出符合身份胜利条件的判断。",
        ],
    )
    return "\n".join(["【阶段目标】", *lines])


def build_node_responsibility_block(node_name: str) -> str:
    lines = NODE_RESPONSIBILITIES.get(node_name, [f"节点职责：{node_name}。"])
    return "\n".join(["【节点职责】", *lines])


def build_strategy_hint_block(strategy_hints: list[dict[str, Any]] | None) -> str:
    hints = strategy_hints or []
    lines = ["【可选策略参考】"]
    if not hints:
        lines.append("当前没有外部策略提示。不要凭空假设 RAG 策略存在。")
        return "\n".join(lines)
    lines.append("以下内容来自外部策略检索，只能作为战术参考，不能覆盖真实游戏事实和规则校验：")
    for index, hint in enumerate(hints[:5], start=1):
        title = str(hint.get("title") or "未命名策略")
        content = str(hint.get("content") or "").strip()
        source = str(hint.get("source") or "unknown")
        weight = hint.get("weight")
        weight_text = f"，weight={weight}" if weight is not None else ""
        lines.append(f"{index}. {title}（source={source}{weight_text}）：{content}")
    return "\n".join(lines)
```

- [ ] **Step 2: Run catalog tests**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_prompt_catalog.py -q
```

Expected:

```text
6 passed
```

---

## Task 3: Refactor Semantic Node Prompt Builders to Use Catalog

**Files:**

- Modify: `ai_werewolf/llm/graphs/player_decision_prompts.py`
- Test: `tests/llm/test_player_decision_graph.py`
- Test: `tests/llm/test_player_decision_prompt_catalog.py`

- [ ] **Step 1: Add focused prompt builder tests**

Append these tests to `tests/llm/test_player_decision_graph.py`:

```python
def test_semantic_prompts_are_phase_and_role_aware():
    state = {
        "game_id": "game_1",
        "player_id": "ai_3",
        "role_key": "werewolf",
        "agent_name": "小明",
        "speech_style": "冷静、压迫",
        "decision_kind": "day_speech",
        "alive_player_ids": ["human", "ai_2", "ai_3"],
        "memory_context": _memory_context().model_dump(mode="json"),
        "analysis": {"key_facts": ["1号被多人攻击"]},
        "suspicion_update": {"primary_target": "human"},
        "strategy_hints": [
            {
                "source": "rag:werewolf_day_speech_v1",
                "title": "狼人白天悍跳预言家",
                "content": "局势需要抢轮次时，可以悍跳预言家，但必须维护连续查验链。",
                "weight": 0.86,
            }
        ],
    }

    n1_prompt = build_situation_analysis_prompt(state)
    n2_prompt = build_suspicion_update_prompt(state)
    n3_prompt = build_strategy_prompt(state)

    for prompt in (n1_prompt, n2_prompt, n3_prompt):
        assert "【身份优先级】" in prompt
        assert "你的真实身份：狼人" in prompt
        assert "你的阵营目标：狼人阵营获胜" in prompt
        assert "【阶段目标】" in prompt
        assert "白天发言阶段" in prompt
        assert "【可选策略参考】" in prompt
        assert "狼人白天悍跳预言家" in prompt

    assert "节点职责：只做局势提炼" in n1_prompt
    assert "节点职责：只做怀疑与信任更新" in n2_prompt
    assert "节点职责：只做战术选择" in n3_prompt


def test_semantic_prompts_change_phase_focus_for_night_action():
    state = {
        "game_id": "game_1",
        "player_id": "ai_2",
        "role_key": "seer",
        "agent_name": "林野",
        "speech_style": "短句、克制",
        "decision_kind": "night_action",
        "alive_player_ids": ["human", "ai_2", "p5"],
        "memory_context": _memory_context().model_dump(mode="json"),
        "analysis": {"key_facts": ["5号持续攻击1号"]},
        "suspicion_update": {"primary_target": "p5"},
        "strategy_hints": [],
    }

    prompt = build_strategy_prompt(state)

    assert "你的真实身份：预言家" in prompt
    assert "查验信息是你的核心资产" in prompt
    assert "夜晚行动阶段" in prompt
    assert "白天发言阶段" not in prompt
```

- [ ] **Step 2: Run prompt tests and verify they fail**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_graph.py::test_semantic_prompts_are_phase_and_role_aware tests/llm/test_player_decision_graph.py::test_semantic_prompts_change_phase_focus_for_night_action -q
```

Expected:

```text
2 failed
```

The failure should be missing `【身份优先级】` or missing strategy hint text.

- [ ] **Step 3: Refactor `player_decision_prompts.py`**

Modify imports at the top of `ai_werewolf/llm/graphs/player_decision_prompts.py`:

```python
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import (
    build_identity_priority_block,
    build_node_responsibility_block,
    build_phase_focus_block,
    build_strategy_hint_block,
)
```

Add this helper below `_json_block`:

```python
def _common_blocks(state: dict[str, Any], node_name: str) -> str:
    return "\n\n".join(
        [
            build_identity_priority_block(
                role_key=state["role_key"],
                decision_kind=state["decision_kind"],
            ),
            build_phase_focus_block(state["decision_kind"]),
            build_node_responsibility_block(node_name),
            build_strategy_hint_block(state.get("strategy_hints", [])),
        ]
    )
```

In `build_situation_analysis_prompt`, replace the beginning of the returned string with:

```python
    return (
        f"{_common_blocks(state, 'n1')}\n\n"
        "你在帮助狼人杀 AI 做局势提炼。请从当前玩家视角提取最关键、最矛盾、最影响身份判断的信息。\n"
        "必须优先围绕当前真实身份和阵营目标判断哪些信息最重要。\n"
        "不要总结流水账，不要平均分配注意力，优先提取立场反复、发言与投票冲突、异常保护、异常跟票、查杀/金水后的反应。\n"
        "relationship_edges[].relation 必须使用英文枚举：support, attack, protect, follow, distance, conflict, unknown。\n"
        "只输出 JSON，不要输出 Markdown，不要解释。\n"
```

Keep the existing JSON schema and payload block unchanged.

In `build_suspicion_update_prompt`, replace the beginning of the returned string with:

```python
    return (
        f"{_common_blocks(state, 'n2')}\n\n"
        "你在帮助狼人杀 AI 更新怀疑链。请基于当前角色视角，对存活玩家做一次新的信念更新。\n"
        "必须优先围绕当前真实身份和阵营目标决定谁应该被怀疑、谁应该被保护、谁适合成为公开推进目标。\n"
        "重点结合关键事实、矛盾、关系边、最近发言和投票趋势，不要机械沿用旧排名。\n"
        "分数必须使用 0.0 到 1.0 的小数。primary_target 和 secondary_target 只能是存活玩家，不能是自己。\n"
        "只输出 JSON，不要输出 Markdown，不要解释。\n"
```

Keep the existing JSON schema and payload block unchanged.

In `build_strategy_prompt`, replace the beginning of the returned string with:

```python
    return (
        f"{_common_blocks(state, 'n3')}\n\n"
        "你在帮助狼人杀 AI 选择战术，而不是直接执行动作。\n"
        "必须优先围绕当前真实身份和阵营目标选择战术：好人要提高找狼效率，狼人要提高隐藏、误导和控轮次收益。\n"
        "请根据角色视角、当前局势分析、怀疑链和决策场景，选择最合适的 strategy_type。\n"
        "不要决定非法目标，不要选择自己，不要输出动作执行结果。\n"
        "只输出 JSON，不要输出 Markdown，不要解释。\n"
```

Keep the existing JSON schema and payload block unchanged.

- [ ] **Step 4: Run prompt tests**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_prompt_catalog.py tests/llm/test_player_decision_graph.py::test_prompt_builders_include_expected_constraints tests/llm/test_player_decision_graph.py::test_semantic_prompts_are_phase_and_role_aware tests/llm/test_player_decision_graph.py::test_semantic_prompts_change_phase_focus_for_night_action -q
```

Expected:

```text
9 passed
```

---

## Task 4: Add Strategy Hint Hook to Graph State

**Files:**

- Modify: `ai_werewolf/llm/graphs/player_decision_state.py`
- Modify: `ai_werewolf/llm/graphs/player_decision_graph.py`
- Modify: `tests/llm/test_player_decision_graph.py`

- [ ] **Step 1: Add failing graph hook test**

Append this test to `tests/llm/test_player_decision_graph.py`:

```python
def test_strategy_hint_provider_injects_hints_into_semantic_prompts():
    decider = FakeRawDecider(
        [
            {
                "key_facts": ["狼人需要抢轮次"],
                "contradictions": [],
                "relationship_edges": [],
                "turning_points": [],
            }
        ]
    )

    def strategy_hint_provider(state: dict):
        assert state["role_key"] == "werewolf"
        assert state["decision_kind"] == "day_speech"
        return [
            {
                "source": "rag:werewolf_day_speech_v1",
                "title": "狼人白天悍跳预言家",
                "content": "可以悍跳预言家，但必须维护连续查验链。",
                "weight": 0.86,
            }
        ]

    wolf = _player().model_copy(update={"role_key": "werewolf", "player_id": "ai_3"})
    context = _memory_context().model_copy(update={"player_id": "ai_3"})

    result = run_player_decision_graph(
        agent=_agent(),
        player=wolf,
        memory_context=context,
        decision_kind="day_speech",
        semantic_decider=decider,
        semantic_nodes={"n1"},
        strategy_hint_provider=strategy_hint_provider,
    )

    assert result["semantic_node_sources"]["n1"] == "llm"
    assert "狼人白天悍跳预言家" in decider.prompts[0]
```

- [ ] **Step 2: Run hook test and verify it fails**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_graph.py::test_strategy_hint_provider_injects_hints_into_semantic_prompts -q
```

Expected:

```text
FAILED ... TypeError: run_player_decision_graph() got an unexpected keyword argument 'strategy_hint_provider'
```

- [ ] **Step 3: Extend state type**

Modify `ai_werewolf/llm/graphs/player_decision_state.py`:

```python
    strategy_hints: NotRequired[list[dict[str, Any]]]
```

Place it after `alive_player_ids`.

- [ ] **Step 4: Add provider type and parameter**

In `ai_werewolf/llm/graphs/player_decision_graph.py`, add near `DecisionGenerator`:

```python
StrategyHintProvider = Callable[[dict[str, Any]], list[dict[str, Any]]]
```

Update `run_player_decision_graph` signature:

```python
def run_player_decision_graph(
    *,
    agent: AgentProfile,
    player: PlayerState,
    memory_context: MemoryContext,
    decision_kind: str,
    decision_generator: DecisionGenerator | None = None,
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
    strategy_hint_provider: StrategyHintProvider | None = None,
) -> dict[str, Any]:
```

- [ ] **Step 5: Inject hints into initial state**

In `run_player_decision_graph`, build the base initial state first:

```python
    initial: PlayerDecisionGraphState = {
        "game_id": memory_context.game_id,
        "player_id": player.player_id,
        "role_key": player.role_key,
        "agent_name": agent.name,
        "speech_style": agent.speech_style,
        "decision_kind": decision_kind,
        "memory_context": memory_context.model_dump(mode="json"),
        "alive_player_ids": _alive_player_ids(memory_context),
        "strategy_hints": [],
        "semantic_node_errors": {},
        "semantic_node_sources": {},
        "error": None,
    }
    if strategy_hint_provider is not None:
        try:
            initial["strategy_hints"] = strategy_hint_provider(dict(initial))[:5]
        except Exception as exc:
            logger.warning("[PLAYER_GRAPH_STRATEGY_HINTS_FALLBACK] %s", exc)
            initial["strategy_hints"] = []
```

This is the future RAG口子. It must not call RAG by default.

- [ ] **Step 6: Thread provider through speech helper**

Update `run_player_speech_graph` signature:

```python
def run_player_speech_graph(
    *,
    agent: AgentProfile,
    player: PlayerState,
    memory_context: MemoryContext,
    speech_generator: Callable[[dict[str, Any]], str] | None = None,
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
    strategy_hint_provider: StrategyHintProvider | None = None,
) -> dict[str, Any]:
```

Pass it into `run_player_decision_graph`:

```python
        strategy_hint_provider=strategy_hint_provider,
```

- [ ] **Step 7: Run hook test**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_graph.py::test_strategy_hint_provider_injects_hints_into_semantic_prompts -q
```

Expected:

```text
1 passed
```

---

## Task 5: Strengthen Legacy Player Prompt Identity Weight

**Files:**

- Modify: `ai_werewolf/llm/prompt_builder.py`
- Modify: `tests/llm/test_prompt_builder.py`
- Possibly modify: `ai_werewolf/tests/test_m2_prompt_constraints.py`

- [ ] **Step 1: Add failing prompt builder test**

Append this test to `tests/llm/test_prompt_builder.py`:

```python
def test_player_prompt_reuses_identity_priority_block_for_role_sensitivity():
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        persona="理性、谨慎",
        speech_style="短句、克制",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes_and_claims",
    )

    prompt = build_player_prompt(agent, role_key="werewolf", phase="day_speech")

    assert "【身份优先级】" in prompt
    assert "你的真实身份：狼人" in prompt
    assert "你的阵营目标：狼人阵营获胜" in prompt
    assert "公开发言不能暴露狼队友" in prompt
    assert prompt.index("【身份优先级】") < prompt.index("【当前状态】")
```

If `AgentProfile` and `RiskPreference` are already imported in this file, reuse existing imports instead of duplicating.

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
./.venv/bin/pytest tests/llm/test_prompt_builder.py::test_player_prompt_reuses_identity_priority_block_for_role_sensitivity -q
```

Expected:

```text
1 failed
```

- [ ] **Step 3: Import identity block in `prompt_builder.py`**

Add this import near the top:

```python
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import build_identity_priority_block
```

- [ ] **Step 4: Insert identity priority after hidden identity**

In `build_player_prompt`, after the existing hidden identity block:

```python
    parts.extend([
        "=" * 40,
        "【隐藏身份】",
        "=" * 40,
        f"你的真实身份：{role_name}",
        f"你的阵营：{camp_name}",
        "",
    ])
```

add:

```python
    parts.extend([
        "=" * 40,
        build_identity_priority_block(role_key, phase),
        "",
    ])
```

Do not remove `【隐藏身份】`; many existing tests depend on it.

- [ ] **Step 5: Run prompt builder tests**

Run:

```bash
./.venv/bin/pytest tests/llm/test_prompt_builder.py ai_werewolf/tests/test_m2_prompt_constraints.py -q
```

Expected:

```text
all tests pass
```

If a snapshot-like assertion fails because prompt text changed, update the assertion to include `【身份优先级】` while preserving all previous hard constraints.

---

## Task 6: Add Phase-Specific Node Prompt Smoke Tests

**Files:**

- Modify: `tests/llm/test_player_decision_graph.py`

- [ ] **Step 1: Add tests for vote and night phase wording**

Append:

```python
def test_suspicion_prompt_for_vote_phase_emphasizes_exile_target():
    state = {
        "game_id": "game_1",
        "player_id": "ai_2",
        "role_key": "villager",
        "agent_name": "林野",
        "speech_style": "短句、克制",
        "decision_kind": "exile_vote",
        "alive_player_ids": ["human", "ai_2", "p5"],
        "memory_context": _memory_context().model_dump(mode="json"),
        "analysis": {"key_facts": ["5号发言和投票不一致"]},
        "strategy_hints": [],
    }

    prompt = build_suspicion_update_prompt(state)

    assert "投票放逐阶段" in prompt
    assert "你的真实身份：平民" in prompt
    assert "没有夜晚技能信息" in prompt
    assert "primary_target 和 secondary_target 只能是存活玩家" in prompt


def test_strategy_prompt_for_wolf_night_emphasizes_private_night_action():
    state = {
        "game_id": "game_1",
        "player_id": "ai_3",
        "role_key": "werewolf",
        "agent_name": "小明",
        "speech_style": "冷静、压迫",
        "decision_kind": "night_action",
        "alive_player_ids": ["human", "ai_2", "ai_3"],
        "memory_context": _memory_context().model_dump(mode="json"),
        "analysis": {"key_facts": ["2号像预言家"]},
        "suspicion_update": {"primary_target": "ai_2"},
        "strategy_hints": [],
    }

    prompt = build_strategy_prompt(state)

    assert "夜晚行动阶段" in prompt
    assert "你的真实身份：狼人" in prompt
    assert "狼人阵营获胜" in prompt
    assert "不能泄露夜晚私有视角到公开发言" in prompt
```

- [ ] **Step 2: Run smoke tests**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_graph.py::test_suspicion_prompt_for_vote_phase_emphasizes_exile_target tests/llm/test_player_decision_graph.py::test_strategy_prompt_for_wolf_night_emphasizes_private_night_action -q
```

Expected:

```text
2 passed
```

---

## Task 7: Preserve Existing Behavior and Fallbacks

**Files:**

- No new production files.
- Test: `tests/llm/test_player_decision_graph.py`
- Test: `tests/llm/test_prompt_builder.py`
- Test: `ai_werewolf/tests/test_m2_prompt_constraints.py`

- [ ] **Step 1: Run current focused player decision tests**

Run:

```bash
./.venv/bin/pytest tests/llm/test_player_decision_graph.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run prompt constraints tests**

Run:

```bash
./.venv/bin/pytest tests/llm/test_prompt_builder.py ai_werewolf/tests/test_m2_prompt_constraints.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 3: Manually inspect generated prompt snippets**

Run:

```bash
./.venv/bin/python - <<'PY'
from tests.llm.test_player_decision_graph import _memory_context
from ai_werewolf.llm.graphs.player_decision_prompts import build_strategy_prompt

state = {
    "game_id": "game_1",
    "player_id": "ai_3",
    "role_key": "werewolf",
    "agent_name": "小明",
    "speech_style": "冷静",
    "decision_kind": "day_speech",
    "alive_player_ids": ["human", "ai_2", "ai_3"],
    "memory_context": _memory_context().model_dump(mode="json"),
    "analysis": {"key_facts": ["5号站边反复"]},
    "suspicion_update": {"primary_target": "human"},
    "strategy_hints": [
        {
            "source": "rag:werewolf_day_speech_v1",
            "title": "狼人白天悍跳预言家",
            "content": "可以悍跳预言家，但必须维护连续查验链。",
            "weight": 0.86,
        }
    ],
}
prompt = build_strategy_prompt(state)
for marker in ["【身份优先级】", "【阶段目标】", "【节点职责】", "【可选策略参考】"]:
    print(marker, prompt.index(marker))
print(prompt[:1200])
PY
```

Expected:

```text
【身份优先级】 <number>
【阶段目标】 <number>
【节点职责】 <number>
【可选策略参考】 <number>
```

The printed prompt must show identity before phase, phase before node responsibility, and node responsibility before strategy hints.

---

## Task 8: Documentation for Future RAG Integration

**Files:**

- Create: `docs/superpowers/specs/2026-05-18-player-decision-rag-strategy-hook.md`

- [ ] **Step 1: Create RAG hook note**

Create `docs/superpowers/specs/2026-05-18-player-decision-rag-strategy-hook.md`:

```markdown
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
```

- [ ] **Step 2: Verify doc exists**

Run:

```bash
test -f docs/superpowers/specs/2026-05-18-player-decision-rag-strategy-hook.md && echo ok
```

Expected:

```text
ok
```

---

## Task 9: Full Regression

**Files:**

- All files modified above.

- [ ] **Step 1: Run LLM test suite**

Run:

```bash
./.venv/bin/pytest tests/llm -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run engine tests that exercise player prompts**

Run:

```bash
./.venv/bin/pytest ai_werewolf/tests/test_engine_orchestrator.py ai_werewolf/tests/test_engine_night.py ai_werewolf/tests/test_engine_vote.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 3: Run full project tests if time allows**

Run:

```bash
./.venv/bin/pytest tests -q
./.venv/bin/pytest ai_werewolf/tests -q
```

Expected:

```text
all tests pass
```

Existing deprecation warnings are acceptable if they match the current suite warnings and are unrelated to prompt changes.

---

## Acceptance Criteria

The implementation is complete only when all of these are true:

- `player_decision_prompts.py` no longer owns hardcoded identity/phase/node policy text by itself.
- `player_decision_prompt_catalog.py` centrally defines:
  - role display names
  - role camp goals
  - role-specific identity priorities
  - phase focus blocks
  - node responsibility blocks
  - strategy hint rendering
- Every semantic LLM prompt for `n1/n2/n3` includes:
  - `【身份优先级】`
  - `【阶段目标】`
  - `【节点职责】`
  - `【可选策略参考】`
- `day_speech`、`exile_vote`、`night_action` 生成的 prompt 内容不同，且阶段目标明确。
- 狼人 prompt 明确强调：
  - 狼人阵营获胜
  - 公开发言不能暴露狼队友
  - 可以伪装成好人视角
  - 可通过站边、倒钩、冲票、切割、悍跳等方式争取轮次
- 好人 prompt 明确强调：
  - 好人阵营获胜
  - 不能编造未发生的技能信息
  - 根据真实身份使用信息
- `prompt_builder.py` 的旧链路完整 prompt 也包含 `【身份优先级】`。
- `strategy_hint_provider` 是可选参数，默认不调用任何 RAG。
- 当 provider 返回“狼人白天悍跳预言家”策略 hint 时，该 hint 能出现在语义节点 prompt 中。
- `n4_decide_action` 和 `n6_validate_and_repair` 没有被改成 LLM 节点。
- `tests/llm/test_player_decision_prompt_catalog.py`、`tests/llm/test_player_decision_graph.py`、`tests/llm/test_prompt_builder.py`、`ai_werewolf/tests/test_m2_prompt_constraints.py` 全部通过。

## Non-Goals

- 不实现向量库。
- 不实现 embedding。
- 不实现真实 RAG 检索。
- 不让 LLM 直接决定最终合法动作。
- 不移除旧 `build_player_prompt`、`build_speech_prompt`、`build_vote_prompt`、`build_night_action_prompt`。
- 不改变 `PlayerDecision` 输出 schema。

## Suggested Commit Sequence

1. `test: cover player decision prompt catalog`
2. `feat: add centralized player decision prompt catalog`
3. `feat: render phase-aware semantic prompts`
4. `feat: add strategy hint hook for player decision graph`
5. `feat: strengthen role identity prompts`
6. `docs: document player decision rag strategy hook`

Each commit should pass the focused tests for its task before moving on.

## Self-Review Checklist

- Search for accidental placeholders:

```bash
rg -n "TBD|TODO|implement later|fill in details" ai_werewolf/llm/graphs/player_decision_prompt_catalog.py docs/superpowers/specs/2026-05-18-player-decision-rag-strategy-hook.md tests/llm/test_player_decision_prompt_catalog.py
```

Expected: no matches except pre-existing comments outside touched files.

- Search for prompt drift:

```bash
rg -n "【身份优先级】|【阶段目标】|【可选策略参考】" ai_werewolf/llm tests/llm ai_werewolf/tests
```

Expected: matches in catalog, semantic prompt tests, and prompt builder tests.

- Check that `n4` and `n6` remain deterministic:

```bash
rg -n "def n4_decide_action|def n6_validate_and_repair|decide_raw\\(|build_strategy_prompt" ai_werewolf/llm/graphs/player_decision_graph.py
```

Expected: `decide_raw` appears only in semantic node makers for `n1/n2/n3`; `n4_decide_action` and `n6_validate_and_repair` do not call LLM.
