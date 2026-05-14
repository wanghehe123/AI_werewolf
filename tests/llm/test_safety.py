from ai_werewolf.llm.safety import is_safe_speech


def test_safe_speech_accepts_normal_game_text():
    assert is_safe_speech("我觉得 4 号发言偏防守，今天可以先进票。") is True


def test_safe_speech_rejects_system_prompt_leak():
    assert is_safe_speech("根据系统提示，我的 role_key 是 werewolf。") is False
