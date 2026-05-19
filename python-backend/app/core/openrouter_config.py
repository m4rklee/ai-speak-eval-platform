"""
OpenRouter 配置与客户端（支持 HTTP 代理）
"""
from __future__ import annotations

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings

settings = get_settings()

_OPENROUTER_DEFAULT_HEADERS = {
    "HTTP-Referer": "https://codefather.cn",
    "X-Title": "AI Evaluation Platform",
}


def openrouter_http_proxy() -> str | None:
    proxy = settings.OPENROUTER_HTTP_PROXY.strip()
    return proxy or None


def create_openrouter_http_client(*, timeout: float = 120.0) -> httpx.AsyncClient | None:
    proxy = openrouter_http_proxy()
    if not proxy:
        return None
    return httpx.AsyncClient(proxy=proxy, timeout=timeout)


def get_openrouter_client() -> AsyncOpenAI:
    """获取 OpenRouter AsyncOpenAI 客户端（若配置了 OPENROUTER_HTTP_PROXY 则经代理访问）。"""
    http_client = create_openrouter_http_client()
    kwargs: dict = {
        "api_key": settings.OPENROUTER_API_KEY,
        "base_url": settings.OPENROUTER_BASE_URL,
        "default_headers": dict(_OPENROUTER_DEFAULT_HEADERS),
    }
    if http_client is not None:
        kwargs["http_client"] = http_client
    return AsyncOpenAI(**kwargs)


SUPPORTED_MODELS = [
    "deepseek/deepseek-chat",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
]
