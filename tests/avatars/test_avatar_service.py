from ai_werewolf.avatars.service import AvatarService


class BrokenProvider:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("image service unavailable")


def test_avatar_service_returns_default_when_provider_fails():
    service = AvatarService(provider=BrokenProvider(), default_avatar_url="/static/default/avatar.png")

    assert service.generate_or_default("侦探头像") == "/static/default/avatar.png"
