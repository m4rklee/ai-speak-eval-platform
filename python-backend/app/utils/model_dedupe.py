"""跨平台模型去重：OpenRouter 与 AiHubMix 同一模型合并展示"""
from __future__ import annotations

from typing import Any

from app.schemas.model import ModelVO
from app.utils.model_id import split_model_id

_AIHUB_PREFIXES = ("aihubmix-", "aihub-", "ahm-")


def _strip_aihub_vendor_prefix(vendor_id: str) -> str:
    v = vendor_id.lower().strip()
    for prefix in _AIHUB_PREFIXES:
        if v.startswith(prefix):
            return v[len(prefix) :]
    return v


def match_keys(platform: str, composite_id: str) -> set[str]:
    """生成用于跨平台匹配的一组等价键"""
    _, vendor = split_model_id(composite_id, platform)
    v = vendor.lower().strip()
    keys: set[str] = {v, _strip_aihub_vendor_prefix(v)}
    if "/" in v:
        keys.add(v.split("/")[-1])
        keys.add(_strip_aihub_vendor_prefix(v.split("/")[-1]))
    return {k for k in keys if k}


def _platform_rank(platform: str) -> int:
    return 0 if platform == "openrouter" else 1


def _display_name(vo: ModelVO) -> str:
    """AiHubMix 独有且名称带渠道前缀时，用规范化 vendor id 作为展示名"""
    _, vendor = split_model_id(vo.id, vo.platform)
    stripped = _strip_aihub_vendor_prefix(vendor)
    if vo.platform != "aihubmix":
        return vo.name
    name_l = vo.name.lower()
    if any(name_l.startswith(p.rstrip("-")) for p in _AIHUB_PREFIXES) or name_l.startswith("ahm "):
        return stripped.replace("/", " ").replace("-", " ").title()
    return vo.name


def merge_model_vos(vos: list[ModelVO]) -> list[ModelVO]:
    """合并多平台重复模型，保留 OpenRouter 为主记录，平台列展示全部来源"""
    key_to_group: dict[str, int] = {}
    groups: list[list[ModelVO]] = []

    sorted_vos = sorted(vos, key=lambda m: (_platform_rank(m.platform), m.name))

    for vo in sorted_vos:
        keys = match_keys(vo.platform, vo.id)
        group_idx = None
        for k in keys:
            if k in key_to_group:
                group_idx = key_to_group[k]
                break
        if group_idx is None:
            group_idx = len(groups)
            groups.append([])
        groups[group_idx].append(vo)
        for k in keys:
            key_to_group[k] = group_idx

    merged: list[ModelVO] = []
    for members in groups:
        members.sort(key=lambda m: (_platform_rank(m.platform), m.name))
        primary = members[0]
        platforms = sorted({m.platform for m in members})
        alternate_ids = {m.platform: m.id for m in members}

        merged.append(
            ModelVO(
                id=primary.id,
                platform=", ".join(platforms),
                platforms=platforms,
                alternateIds=alternate_ids,
                name=_display_name(primary),
                description=primary.description or next(
                    (m.description for m in members if m.description), None
                ),
                provider=primary.provider,
                contextLength=max((m.context_length or 0) for m in members) or None,
                modality=primary.modality,
                inputModalities=primary.input_modalities,
                outputModalities=primary.output_modalities,
                inputPrice=_min_price(m.input_price for m in members),
                outputPrice=_min_price(m.output_price for m in members),
                releasedAt=primary.released_at
                or next((m.released_at for m in members if m.released_at), None),
                modelType=primary.model_type,
                recommended=max(m.recommended for m in members),
                isChina=max(m.is_china for m in members),
                totalTokens=sum(m.total_tokens or 0 for m in members),
                batchCallCount=sum(m.batch_call_count or 0 for m in members),
            )
        )
    return merged


def _min_price(values: Any) -> Any:
    nums = []
    for v in values:
        if v is None:
            continue
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return None
    from decimal import Decimal

    return Decimal(str(min(nums)))


def model_matches_platform_filter(vo: ModelVO, platform: str) -> bool:
    if not platform:
        return True
    if vo.platforms:
        return platform in vo.platforms
    return platform in [p.strip() for p in vo.platform.split(",")]
