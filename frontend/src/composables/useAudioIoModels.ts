import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { listModels, listPlatforms, type ModelVO } from '@/api/modelController'
import {
  getModelPlatforms,
  modelSelectLabel,
  platformLabel,
  resolveModelId,
} from '@/utils/modelPlatform'

export function useAudioIoModels() {
  const filterPlatform = ref<string | undefined>()
  const platformOptions = ref<string[]>(['openrouter', 'aihubmix'])
  const models = ref<ModelVO[]>([])
  const modelsLoading = ref(false)
  const selectedModelId = ref<string | undefined>()
  const selectedProviderPlatform = ref('openrouter')

  const selectedModelRecord = computed(() => {
    const list = models.value
    if (!Array.isArray(list)) return undefined
    return list.find((m) => m.id === selectedModelId.value)
  })

  const providerPlatforms = computed(() => getModelPlatforms(selectedModelRecord.value))

  const showProviderSelect = computed(() => providerPlatforms.value.length > 1)

  const effectiveModelId = computed(() => {
    if (!selectedModelRecord.value) return ''
    return resolveModelId(selectedModelRecord.value, selectedProviderPlatform.value)
  })

  function modelHasAudioOutput(m: ModelVO): boolean {
    const outs = m.outputModalities || []
    if (outs.some((x) => x.toLowerCase().includes('audio'))) return true
    const mod = (m.modality || '').toLowerCase()
    if (!mod.includes('audio')) return false
    if (!mod.includes('->')) return false
    const out = mod.split('->')[1]
    return out ? out.includes('audio') : false
  }

  const audioIoModelOptions = computed(() => {
    const list = models.value
    if (!Array.isArray(list)) return []
    return list
      .filter((m) => {
        const ins = m.inputModalities || []
        const hasAudioIn =
          ins.some((x) => x.toLowerCase() === 'audio') ||
          (m.modality || '').toLowerCase().includes('audio')
        return hasAudioIn && modelHasAudioOutput(m)
      })
      .map((m) => ({ value: m.id, label: modelSelectLabel(m) }))
  })

  async function loadPlatforms() {
    try {
      const res = await listPlatforms()
      if (res.data.code === 0 && res.data.data?.length) {
        platformOptions.value = res.data.data
      }
    } catch {
      /* keep defaults */
    }
  }

  async function loadModels() {
    modelsLoading.value = true
    try {
      const res = await listModels({
        inputModality: 'audio',
        platform: filterPlatform.value,
      })
      models.value = res.data.code === 0 ? res.data.data || [] : []
      if (
        selectedModelId.value &&
        !audioIoModelOptions.value.some((o) => o.value === selectedModelId.value)
      ) {
        selectedModelId.value = undefined
      }
      if (!selectedModelId.value && audioIoModelOptions.value.length) {
        selectedModelId.value = audioIoModelOptions.value[0].value
      }
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '无法加载模型')
      models.value = []
    } finally {
      modelsLoading.value = false
    }
  }

  function onFilterPlatformChange() {
    void loadModels()
  }

  function onModelChange() {
    const platforms = providerPlatforms.value
    if (platforms.length && !platforms.includes(selectedProviderPlatform.value)) {
      selectedProviderPlatform.value = platforms[0]
    }
  }

  onMounted(() => {
    void loadPlatforms()
    void loadModels()
  })

  return {
    filterPlatform,
    platformOptions,
    platformLabel,
    models,
    modelsLoading,
    selectedModelId,
    selectedProviderPlatform,
    providerPlatforms,
    showProviderSelect,
    effectiveModelId,
    audioIoModelOptions,
    loadModels,
    onFilterPlatformChange,
    onModelChange,
  }
}
