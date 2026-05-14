from ai_werewolf.avatars.provider import FakeAvatarProvider


def test_fake_avatar_provider_returns_deterministic_url():
    provider = FakeAvatarProvider(base_url="/static/default")

    url = provider.generate("冷静的年轻侦探")

    assert url == "/static/default/generated-avatar.png"
