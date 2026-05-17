"""Tests for the speech post-validator.

Tests cover:
- Role existence violations (Chinese and English role names)
- Unspoken player reference violations
- build_rejection_prompt formatting
- Edge cases (empty speech, no board roles, no player references)
"""
from __future__ import annotations

import pytest

from ai_werewolf.llm.validators import build_rejection_prompt, validate_speech


# =====================================================================
# Tests: Role existence validation
# =====================================================================


class TestRoleExistenceValidation:
    """Tests for detecting mentions of non-existent roles."""

    def test_no_violation_when_role_exists(self):
        """Speech mentions a role that IS in the board -> no violation."""
        speech = "我觉得女巫这局应该已经用药了。"
        board_roles = {"werewolf": 2, "seer": 1, "witch": 1, "villager": 3}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 0

    def test_violation_when_witch_not_in_board(self):
        """Speech mentions witch but board has no witch -> violation."""
        speech = "我觉得女巫这局应该已经用药了。"
        board_roles = {"werewolf": 2, "seer": 1, "villager": 5}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 1
        assert "女巫" in violations[0]

    def test_violation_when_seer_not_in_board(self):
        """Speech mentions seer but board has no seer -> violation."""
        speech = "预言家应该跳出来了。"
        board_roles = {"werewolf": 2, "witch": 1, "villager": 5}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 1
        assert "预言家" in violations[0]

    def test_violation_when_guard_not_in_board(self):
        """Speech mentions guard but board has no guard -> violation."""
        speech = "守卫昨晚保护了他。"
        board_roles = {"werewolf": 2, "seer": 1, "witch": 1, "villager": 4}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 1
        assert "守卫" in violations[0]

    def test_violation_when_hunter_not_in_board(self):
        """Speech mentions hunter but board has no hunter -> violation."""
        speech = "猎人可以开枪带人。"
        board_roles = {"werewolf": 2, "seer": 1, "witch": 1, "villager": 4}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 1
        assert "猎人" in violations[0]

    def test_multiple_role_violations(self):
        """Speech mentions multiple non-existent roles."""
        speech = "女巫和守卫都应该跳身份了。"
        board_roles = {"werewolf": 2, "seer": 1, "villager": 5}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 2

    def test_no_role_mentions_no_violation(self):
        """Speech with no role mentions -> no violation."""
        speech = "我觉得3号和5号都很可疑。"
        board_roles = {"werewolf": 2, "seer": 1, "villager": 5}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 0

    def test_english_role_name_violation(self):
        """Speech mentions English role name not in board -> violation."""
        speech = "The witch should use her potion."
        board_roles = {"werewolf": 2, "seer": 1, "villager": 5}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 1
        assert "witch" in violations[0]

    def test_werewolf_mention_no_violation(self):
        """Speech mentions werewolf which is always in board -> no violation."""
        speech = "我觉得场上还有狼人没找到。"
        board_roles = {"werewolf": 2, "seer": 1, "villager": 5}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 0

    def test_villager_mention_no_violation(self):
        """Speech mentions villager which is in board -> no violation."""
        speech = "我就是一个平民。"
        board_roles = {"werewolf": 2, "seer": 1, "witch": 1, "villager": 3}
        violations = validate_speech(speech, board_roles, set())
        assert len(violations) == 0


# =====================================================================
# Tests: Unspoken player reference validation
# =====================================================================


class TestUnspokenPlayerValidation:
    """Tests for detecting references to unspoken players."""

    def test_no_violation_when_player_spoke(self):
        """Speech quotes a player who HAS spoken -> no violation."""
        speech = "3号刚才说他觉得4号可疑。"
        board_roles = {"werewolf": 2, "villager": 5}
        player_references = {"p3": "3号 Alice", "p4": "4号 Bob"}
        violations = validate_speech(speech, board_roles, {"p3"}, player_references)
        assert len(violations) == 0

    def test_violation_when_player_not_spoken(self):
        """Speech quotes a player who HAS NOT spoken -> violation."""
        speech = "3号刚才说他觉得4号可疑。"
        board_roles = {"werewolf": 2, "villager": 5}
        player_references = {"p3": "3号 Alice", "p4": "4号 Bob"}
        violations = validate_speech(speech, board_roles, {"p4"}, player_references)
        assert len(violations) == 1
        assert "3号" in violations[0]
        assert "未发言" in violations[0]

    def test_no_violation_without_player_references(self):
        """Without player_references, seat numbers cannot be mapped -> no violation."""
        speech = "3号刚才说他觉得4号可疑。"
        board_roles = {"werewolf": 2, "villager": 5}
        violations = validate_speech(speech, board_roles, set(), None)
        # Cannot determine player ID from seat number without references
        assert len(violations) == 0

    def test_no_quote_pattern_no_violation(self):
        """Speech doesn't quote any player -> no violation."""
        speech = "我觉得大家都有点可疑。"
        board_roles = {"werewolf": 2, "villager": 5}
        violations = validate_speech(speech, board_roles, set(), {"p1": "1号 A"})
        assert len(violations) == 0

    def test_multiple_unspoken_players(self):
        """Speech quotes multiple unspoken players -> multiple violations."""
        speech = "3号说了他是好人，5号刚才说也是好人。"
        board_roles = {"werewolf": 2, "villager": 5}
        player_references = {
            "p3": "3号 Alice",
            "p5": "5号 Carol",
        }
        violations = validate_speech(speech, board_roles, set(), player_references)
        assert len(violations) == 2


# =====================================================================
# Tests: Combined validation
# =====================================================================


class TestCombinedValidation:
    """Tests for combined role + player reference violations."""

    def test_both_types_of_violation(self):
        """Speech with both role and player reference violations."""
        speech = "女巫救了3号，3号刚才说自己是预言家。"
        board_roles = {"werewolf": 2, "seer": 1, "villager": 5}
        player_references = {"p3": "3号 Alice"}
        violations = validate_speech(speech, board_roles, set(), player_references)
        # Should have: 1 role violation (witch) + 1 player violation (3号 not spoken)
        assert len(violations) == 2
        role_violations = [v for v in violations if "角色" in v]
        player_violations = [v for v in violations if "未发言" in v]
        assert len(role_violations) == 1
        assert len(player_violations) == 1


# =====================================================================
# Tests: build_rejection_prompt
# =====================================================================


class TestBuildRejectionPrompt:
    """Tests for the rejection prompt builder."""

    def test_empty_violations_returns_empty_string(self):
        result = build_rejection_prompt([])
        assert result == ""

    def test_single_violation(self):
        violations = ["提到了不存在的角色：女巫"]
        result = build_rejection_prompt(violations)
        assert "女巫" in result
        assert "违规" in result

    def test_multiple_violations(self):
        violations = [
            "提到了不存在的角色：女巫",
            "引用了未发言玩家3号的观点",
        ]
        result = build_rejection_prompt(violations)
        assert "女巫" in result
        assert "3号" in result
        assert "违规" in result
        assert "板子约束" in result


# =====================================================================
# Tests: Edge cases
# =====================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_speech(self):
        violations = validate_speech("", {"werewolf": 2}, set())
        assert len(violations) == 0

    def test_empty_board_roles(self):
        """Empty board roles -> any role mention is a violation."""
        speech = "女巫可能用药了。"
        violations = validate_speech(speech, {}, set())
        assert len(violations) >= 1

    def test_empty_spoken_players_set(self):
        """Empty spoken set with player references -> all player quotes are violations."""
        speech = "3号说了他是好人。"
        player_references = {"p3": "3号 Alice"}
        violations = validate_speech(speech, {"werewolf": 2}, set(), player_references)
        assert len(violations) == 1
