import type { ModelVO } from '@/api/modelController'

const PLATFORM_LABELS: Record<string, string> = {
  openrouter: 'OpenRouter',
  aihubmix: 'AiHubMix',
}

export function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform] || platform
}

/** 模型可用的提供商平台列表（去重后已排序） */
export function getModelPlatforms(model: ModelVO | undefined): string[] {
  if (!model) return []
  if (model.platforms?.length) return [...model.platforms]
  if (model.platform.includes(',')) {
    return model.platform
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean)
  }
  return model.platform ? [model.platform] : []
}

/** 选定平台后用于 API 调用的复合模型 ID */
export function resolveModelId(model: ModelVO | undefined, platform: string): string {
  if (!model) return ''
  if (model.alternateIds && platform in model.alternateIds) {
    return model.alternateIds[platform]
  }
  return model.id
}

/** 多平台模型默认选用：优先列表筛选平台，否则 OpenRouter 优先 */
export function defaultProviderPlatform(
  model: ModelVO | undefined,
  prefer?: string,
): string {
  const platforms = getModelPlatforms(model)
  if (!platforms.length) return prefer || 'openrouter'
  if (prefer && platforms.includes(prefer)) return prefer
  if (platforms.includes('openrouter')) return 'openrouter'
  return platforms[0]
}

export function modelSelectLabel(model: ModelVO): string {
  const platforms = getModelPlatforms(model)
  if (platforms.length > 1) {
    return `${model.name} (${platforms.map(platformLabel).join(' / ')})`
  }
  return `${model.name} (${platformLabel(platforms[0] || model.platform)})`
}
