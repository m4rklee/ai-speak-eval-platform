from app.providers.aihubmix import AiHubMixProvider
from app.providers.base import ModelProvider
from app.providers.openrouter import OpenRouterProvider

_PROVIDERS: dict[str, ModelProvider] = {
    "openrouter": OpenRouterProvider(),
    "aihubmix": AiHubMixProvider(),
}


def get_provider(platform: str) -> ModelProvider:
    key = platform.lower()
    if key not in _PROVIDERS:
        raise ValueError(f"Unsupported platform: {platform}")
    return _PROVIDERS[key]


def list_platforms() -> list[str]:
    return list(_PROVIDERS.keys())
