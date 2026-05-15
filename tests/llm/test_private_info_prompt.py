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


def test_private_info_can_render_player_ids_as_seat_labels():
    labels = {
        "agent_akai": "2号 阿凯",
        "agent_moyu": "3号 墨鱼",
        "agent_linye": "4号 林野",
    }

    wolf_text = format_private_info(
        PlayerPrivateInfo(
            wolf_teammates=["agent_akai", "agent_moyu"],
        ),
        role_key="werewolf",
        player_label=lambda player_id: labels[player_id],
    )
    seer_text = format_private_info(
        PlayerPrivateInfo(
            seer_results=[{"round": "night1", "target": "agent_linye", "result": "werewolf"}],
        ),
        role_key="seer",
        player_label=lambda player_id: labels[player_id],
    )

    assert "2号 阿凯" in wolf_text
    assert "3号 墨鱼" in wolf_text
    assert "4号 林野" in seer_text
    assert "agent_akai" not in wolf_text
    assert "agent_moyu" not in wolf_text
    assert "agent_linye" not in seer_text
