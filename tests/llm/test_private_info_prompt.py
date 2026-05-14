from ai_werewolf.domain.game_state import PlayerPrivateInfo
from ai_werewolf.llm.prompt_builder import format_private_info


def test_werewolf_private_info_includes_teammates():
    text = format_private_info(
        PlayerPrivateInfo(wolf_teammates=["agent_akai", "agent_moyu"]),
        role_key="werewolf",
    )

    assert "狼队友" in text
    assert "agent_akai" in text
    assert "agent_moyu" in text


def test_seer_private_info_includes_check_results():
    text = format_private_info(
        PlayerPrivateInfo(
            seer_results=[
                {"round": "night1", "target": "agent_linye", "result": "werewolf"},
                {"round": "night2", "target": "agent_xiaoman", "result": "good"},
            ]
        ),
        role_key="seer",
    )

    assert "查验结果" in text
    assert "night1 查验 agent_linye：狼人阵营" in text
    assert "night2 查验 agent_xiaoman：好人阵营" in text


def test_villager_private_info_omits_empty_sections():
    text = format_private_info(PlayerPrivateInfo(), role_key="villager")

    assert text == ""
