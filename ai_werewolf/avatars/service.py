from ai_werewolf.avatars.provider import AvatarProvider


class AvatarService:
    def __init__(self, provider: AvatarProvider, default_avatar_url: str) -> None:
        self.provider = provider
        self.default_avatar_url = default_avatar_url

    def generate_or_default(self, prompt: str | None) -> str:
        if not prompt:
            return self.default_avatar_url
        try:
            return self.provider.generate(prompt)
        except Exception:
            return self.default_avatar_url
