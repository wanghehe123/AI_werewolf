from ai_werewolf.seeds.agents import default_agents


def test_default_agents_have_distinct_speech_styles():
    agents = default_agents()
    styles = {agent.speech_style for agent in agents}

    assert len(agents) >= 6
    assert len(styles) >= 4


def test_default_agents_are_enabled():
    assert all(agent.enabled for agent in default_agents())
