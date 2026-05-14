from typing import Protocol


class AvatarProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class FakeAvatarProvider:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str) -> str:
        return f"{self.base_url}/generated-avatar.png"
