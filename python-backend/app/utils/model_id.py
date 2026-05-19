"""模型复合 ID 工具：platform:vendorModelId"""


def normalize_model_id(model_id: str, default_platform: str = "openrouter") -> str:
    if not model_id:
        return model_id
    if ":" in model_id:
        return model_id
    return f"{default_platform}:{model_id}"


def split_model_id(model_id: str, default_platform: str = "openrouter") -> tuple[str, str]:
    normalized = normalize_model_id(model_id, default_platform)
    platform, _, vendor = normalized.partition(":")
    return platform or default_platform, vendor or normalized


def vendor_model_id(model_id: str, default_platform: str = "openrouter") -> str:
    return split_model_id(model_id, default_platform)[1]
