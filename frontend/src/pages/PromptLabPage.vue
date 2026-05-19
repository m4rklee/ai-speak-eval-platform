<template>
  <div class="prompt-lab-page">
    <div class="page-container">
    <!-- 页面头部 -->
    <div class="page-header page-header--toolbar">
      <div class="page-header-main">
        <PageTitle
          icon-key="prompt-lab"
          title="Prompt Lab"
          subtitle="单模型多提示词对比"
        />
      </div>
      <a-select
        v-model:value="selectedModel"
        placeholder="选择模型"
        :loading="modelsLoading"
        style="width: 280px"
      >
        <a-select-option
          v-for="model in modelOptions"
          :key="model.value"
          :value="model.value"
        >
          <div class="model-option">
            <span>{{ model.label }}</span>
            <span class="modality-tags">
              <span
                v-for="modality in getInputModalityLabels(model.value)"
                :key="`${model.value}-${modality}`"
                class="modality-tag"
              >
                {{ modality }}
              </span>
            </span>
          </div>
        </a-select-option>
      </a-select>
    </div>

    <!-- 历史记录 -->
    <div v-if="messages.length > 0" class="history-section">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message-round"
        :class="msg.type"
      >
        <!-- 用户输入展示 -->
        <template v-if="msg.type === 'user'">
          <div class="variants-grid">
            <div
              v-for="(text, vIdx) in msg.variantTexts"
              :key="vIdx"
              class="variant-display-card"
            >
              <div class="variant-display-header">变体 {{ vIdx + 1 }}:</div>
              <div class="variant-display-body">{{ text }}</div>
            </div>
          </div>
          <div v-if="msg.attachments?.length" class="user-attachments-bar">
            <span v-for="att in msg.attachments" :key="att" class="att-tag">{{ att }}</span>
          </div>
        </template>

        <!-- 评分区 -->
        <div
          v-if="msg.type === 'assistant' && msg.responses.every((r) => r.done)"
          class="rating-bar"
        >
          <span class="rating-label">选择最佳变体：</span>
          <a-space>
            <a-button
              v-for="(_, rIdx) in msg.responses"
              :key="`rate-${rIdx}`"
              size="small"
              :type="isVariantSelected(msg, rIdx) ? 'primary' : 'default'"
              @click="handleRating(idx, 'model_better', rIdx)"
            >
              变体 {{ rIdx + 1 }}
            </a-button>
            <a-button
              size="small"
              :type="msg.rating?.ratingType === 'both_bad' ? 'primary' : 'default'"
              @click="handleRating(idx, 'both_bad')"
            >
              都不好 👎
            </a-button>
          </a-space>
        </div>

        <!-- 结果展示 -->
        <div v-if="msg.type === 'assistant'" class="results-grid">
          <div
            v-for="(resp, rIdx) in msg.responses"
            :key="`result-${rIdx}`"
            class="result-card"
          >
            <div class="result-header">
              <span class="variant-badge">变体 {{ rIdx + 1 }}</span>
              <div class="result-metrics">
                <span v-if="resp.elapsedMs" class="metric">
                  ⏱ {{ (resp.elapsedMs / 1000).toFixed(2) }}s
                </span>
                <span v-if="resp.inputTokens || resp.outputTokens" class="metric">
                  📊 {{ (resp.inputTokens || 0) + (resp.outputTokens || 0) }}t
                </span>
                <span v-if="resp.cost" class="metric">
                  💰 ${{ resp.cost.toFixed(4) }}
                </span>
              </div>
            </div>

            <a-alert
              v-if="resp.hasError"
              type="error"
              show-icon
              :message="resp.error || '模型调用失败'"
              class="result-alert"
            />

            <details
              v-if="resp.hasReasoning && resp.reasoning"
              class="reasoning"
              open
            >
              <summary>思考了 {{ Math.floor((resp.elapsedMs || 0) / 1000) }} 秒</summary>
              <div class="markdown-body" v-html="renderMarkdown(resp.reasoning)" />
            </details>

            <div class="markdown-body" v-html="renderMarkdown(resp.fullContent || '')" />

            <div v-if="!resp.done && !resp.hasError" class="dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-section">
      <!-- 基础提示词 + 自动生成 -->
      <div class="base-prompt-row">
        <a-textarea
          v-model:value="basePrompt"
          placeholder="输入基础提示词，AI 将自动生成不同风格的变体表达..."
          :rows="3"
          class="base-prompt-textarea"
        />
        <a-button
          type="primary"
          :loading="isGenerating"
          :disabled="!basePrompt.trim()"
          @click="generateVariants"
        >
          <ThunderboltOutlined />
          自动生成变体
        </a-button>
      </div>

      <div class="input-section-header">
        <span class="section-title">提示词变体 ({{ variants.length }}/5)</span>
        <a-space>
          <a-button v-if="variants.length < 5" size="small" @click="addVariant">
            <PlusOutlined />
            添加变体
          </a-button>
        </a-space>
      </div>

      <div class="variants-grid">
        <div
          v-for="(variant, idx) in variants"
          :key="variant.id"
          class="variant-input-card"
        >
          <div class="variant-input-header">
            <span class="variant-name">变体 {{ idx + 1 }}</span>
            <a-button
              v-if="variants.length > 2"
              type="text"
              size="small"
              danger
              class="variant-remove-btn"
              @click="removeVariant(idx)"
            >
              <CloseOutlined />
            </a-button>
          </div>
          <a-textarea
            v-model:value="variant.content"
            placeholder="输入提示词变体..."
            :rows="4"
            @paste="handlePaste"
          />
        </div>
      </div>

      <div class="attachments-row">
        <a-space>
          <label
            class="attachment-btn"
            :class="{ disabled: !canUseImageInput }"
            :title="canUseImageInput ? '添加图片' : '模型不支持图片'"
          >
            <PictureOutlined />
            图片
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              :disabled="!canUseImageInput"
              @change="handleFileSelect"
            />
          </label>
          <label
            class="attachment-btn"
            :class="{ disabled: !canUseAudioInput }"
            :title="canUseAudioInput ? '添加音频' : '模型不支持音频'"
          >
            <AudioOutlined />
            音频
            <input
              type="file"
              accept="audio/wav,audio/mpeg,audio/mp3,audio/aac,audio/ogg,audio/flac,audio/mp4,audio/x-m4a"
              multiple
              :disabled="!canUseAudioInput"
              @change="handleFileSelect"
            />
          </label>
          <label
            class="attachment-btn"
            :class="{ disabled: !canUseFileInput }"
            :title="canUseFileInput ? '添加文件' : '模型不支持文件'"
          >
            <FileTextOutlined />
            文件
            <input
              type="file"
              accept=".pdf,.txt,.md,.json,.csv,.html,.css,.js,.ts,.py,.java,.cpp,.c,.go,.xml,.yaml,.yml"
              multiple
              :disabled="!canUseFileInput"
              @change="handleFileSelect"
            />
          </label>
          <a-button v-if="attachments.length" type="text" size="small" danger @click="clearAttachments">
            <DeleteOutlined />
            清除附件
          </a-button>
        </a-space>
      </div>

      <div v-if="attachments.length" class="attachments-preview">
        <div
          v-for="(att, idx) in attachments"
          :key="`${att.kind}-${att.name}-${idx}`"
          class="att-preview-item"
        >
          <img v-if="att.kind === 'image'" :src="att.url" class="att-preview-img" @click="openPreview(att.url)" />
          <span v-else-if="att.kind === 'audio'" class="att-preview-badge audio">音频</span>
          <span v-else class="att-preview-badge file">{{ att.format.toUpperCase() }}</span>
          <span class="att-preview-name">{{ att.name }}</span>
          <a-button type="text" size="small" danger @click="removeAttachment(idx)">
            <CloseOutlined />
          </a-button>
        </div>
      </div>

      <a-alert
        v-if="attachmentWarning"
        type="warning"
        show-icon
        :message="attachmentWarning"
        class="attachment-warning"
      />

      <a-button
        type="primary"
        block
        size="large"
        class="start-btn"
        :loading="isLoading"
        :disabled="!canSend"
        @click="sendMessage"
      >
        {{ isLoading ? '生成中' : '开始实验' }}
      </a-button>
    </div>
    </div>

    <a-modal v-model:open="showPreview" :footer="null" width="800px" @cancel="showPreview = false">
      <img :src="previewImage" style="width: 100%; border-radius: 8px" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import PageTitle from '@/components/PageTitle.vue'
import { message } from 'ant-design-vue'
import {
  PictureOutlined,
  AudioOutlined,
  FileTextOutlined,
  DeleteOutlined,
  CloseOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { listModels, type ModelVO } from '@/api/modelController'
import { addRating, type RatingRequest } from '@/api/ratingController'
import { createPostSSE } from '@/utils/sseClient'
import request from '@/request'

type StreamChunkVO = {
  conversationId?: string
  variantIndex?: number
  content?: string
  fullContent?: string
  inputTokens?: number
  outputTokens?: number
  elapsedMs?: number
  cost?: number
  done?: boolean
  hasError?: boolean
  error?: string
  reasoning?: string
  hasReasoning?: boolean
}

type VariantResponse = {
  variantIndex: number
  fullContent: string
  done: boolean
  hasError: boolean
  hasReasoning?: boolean
  reasoning?: string
  inputTokens?: number
  outputTokens?: number
  elapsedMs?: number
  cost?: number
  error?: string
}

type UserMessage = {
  type: 'user'
  content: string
  variantTexts: string[]
  attachments?: string[]
}

type AssistantMessage = {
  type: 'assistant'
  messageIndex: number
  responses: VariantResponse[]
  rating?: RatingRequest
}

type ChatMessage = UserMessage | AssistantMessage

type ImageAttachment = { kind: 'image'; name: string; url: string }
type AudioAttachment = { kind: 'audio'; name: string; data: string; format: string }
type FileAttachment = { kind: 'file'; name: string; data: string; format: string; mimeType: string }
type Attachment = ImageAttachment | AudioAttachment | FileAttachment

type VariantInput = { id: number; content: string }

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const fallbackModels = [
  { label: 'DeepSeek Chat', value: 'deepseek/deepseek-chat' },
  { label: 'Qwen 2.5 72B', value: 'qwen/qwen-2.5-72b-instruct' },
  { label: 'GPT-4o Mini', value: 'openai/gpt-4o-mini' },
]

const selectedModel = ref<string>('')
const basePrompt = ref('')
const isGenerating = ref(false)
const models = ref<ModelVO[]>([])
const modelsLoading = ref(false)
const variants = ref<VariantInput[]>([
  { id: 1, content: '' },
  { id: 2, content: '' },
  { id: 3, content: '' },
])
const nextVariantId = ref(4)
const messages = ref<ChatMessage[]>([])
const attachments = ref<Attachment[]>([])
const isLoading = ref(false)
const sse = ref<{ close: () => void } | null>(null)
const currentConversationId = ref<string | null>(null)
const nextAssistantMessageIndex = ref(1)
const showPreview = ref(false)
const previewImage = ref('')

const modelOptions = computed(() => {
  if (!models.value.length) return fallbackModels
  return models.value.map((model) => ({
    label: model.name || model.id,
    value: model.id,
  }))
})

const getInputModalities = (modelName?: string) => {
  if (!modelName) return []
  const model = models.value.find((item) => item.id === modelName)
  if (!model) return ['text']
  try {
    const parsed = JSON.parse(model.inputModalities || '[]')
    if (Array.isArray(parsed)) return parsed.filter((item: unknown) => typeof item === 'string')
  } catch {
    // ignore
  }
  const modality = model.modality
  if (modality) return (modality.split('->')[0] || 'text').split('+').filter(Boolean)
  return ['text']
}

const selectedModelsSupport = (modality: string) => {
  if (!selectedModel.value) return false
  return getInputModalities(selectedModel.value).includes(modality)
}

const canUseImageInput = computed(() => selectedModelsSupport('image'))
const canUseAudioInput = computed(() => selectedModelsSupport('audio'))
const canUseFileInput = computed(() => selectedModelsSupport('file'))

const attachmentWarning = computed(() => {
  if (!selectedModel.value) return ''
  const modalities = getInputModalities(selectedModel.value)
  const hasUnsupported = attachments.value.some((att) => {
    if (att.kind === 'image' && !modalities.includes('image')) return true
    if (att.kind === 'audio' && !modalities.includes('audio')) return true
    if (att.kind === 'file' && !modalities.includes('file')) return true
    return false
  })
  if (!hasUnsupported) return ''
  return `当前附件与模型 ${getModelName(selectedModel.value)} 不兼容`
})

const canSend = computed(() => {
  const hasValidPrompts = variants.value.filter((v) => v.content.trim().length > 0).length >= 2
  return (
    !isLoading.value &&
    selectedModel.value &&
    hasValidPrompts &&
    !attachmentWarning.value
  )
})

const renderMarkdown = (content: string) => {
  return DOMPurify.sanitize(marked.parse(content || '', { async: false }))
}

const loadModels = async () => {
  modelsLoading.value = true
  try {
    const res = await listModels()
    if (res.data.code === 0 && res.data.data?.length) {
      models.value = res.data.data
    }
  } catch (error) {
    console.warn('模型列表加载失败，使用默认模型', error)
  } finally {
    modelsLoading.value = false
  }
}

const addVariant = () => {
  if (variants.value.length >= 5) return
  variants.value.push({ id: nextVariantId.value++, content: '' })
}

const removeVariant = (index: number) => {
  if (variants.value.length <= 2) return
  variants.value.splice(index, 1)
}

const generateVariants = async () => {
  const prompt = basePrompt.value.trim()
  if (!prompt) return
  isGenerating.value = true
  try {
    const res = await request.post('/conversation/generate-variants', {
      prompt,
      count: Math.min(variants.value.length, 5),
      model: selectedModel.value || undefined,
    })
    if (res.data.code === 0 && res.data.data?.length) {
      const generated = res.data.data as string[]
      // 确保有足够的变体输入框
      while (variants.value.length < generated.length && variants.value.length < 5) {
        variants.value.push({ id: nextVariantId.value++, content: '' })
      }
      // 填充生成的变体
      generated.forEach((text, idx) => {
        if (variants.value[idx]) {
          variants.value[idx].content = text
        }
      })
      message.success(`已生成 ${generated.length} 个变体`)
    } else {
      message.error(res.data.message || '生成失败')
    }
  } catch (error: any) {
    message.error(error.response?.data?.message || '生成变体失败，请重试')
  } finally {
    isGenerating.value = false
  }
}

const sendMessage = async () => {
  if (!canSend.value) return

  const validVariants = variants.value.map((v) => ({ content: v.content.trim() })).filter((v) => v.content)
  if (validVariants.length < 2) {
    message.warning('至少需要 2 个非空提示词变体')
    return
  }
  const validPrompts = validVariants.map((v) => v.content)

  const currentAttachments = attachments.value
  attachments.value = []
  isLoading.value = true

  const images = currentAttachments
    .filter((a): a is ImageAttachment => a.kind === 'image')
    .map((a) => a.url)
  const audios = currentAttachments
    .filter((a): a is AudioAttachment => a.kind === 'audio')
    .map((a) => ({ name: a.name, data: a.data, format: a.format }))
  const files = currentAttachments
    .filter((a): a is FileAttachment => a.kind === 'file')
    .map((a) => ({ name: a.name, data: a.data, format: a.format, mimeType: a.mimeType }))

  const attachmentLabels = currentAttachments.map((att) => {
    if (att.kind === 'image') return `图片：${att.name}`
    if (att.kind === 'audio') return `音频：${att.name}`
    return `文件：${att.name}`
  })

  messages.value.push({
    type: 'user',
    content: validPrompts.join('\n\n---\n\n'),
    variantTexts: validPrompts,
    attachments: attachmentLabels,
  })

  const assistantMsgIndex = messages.value.length
  const messageIndex = nextAssistantMessageIndex.value
  messages.value.push({
    type: 'assistant',
    messageIndex,
    responses: validPrompts.map((_, idx) => ({
      variantIndex: idx,
      fullContent: '',
      done: false,
      hasError: false,
    })),
  })
  nextAssistantMessageIndex.value += 2

  const url = `${API_BASE_URL}/conversation/prompt-lab/stream`
  const body = {
    conversationId: currentConversationId.value,
    model: selectedModel.value,
    prompts: validPrompts,
    imageUrls: images,
    audioInputs: audios,
    fileInputs: files,
    stream: true,
  }

  try {
    sse.value?.close()
    sse.value = await createPostSSE(url, body, {
      onMessage: (chunk: StreamChunkVO) => {
        const msg = messages.value[assistantMsgIndex]
        if (!msg || msg.type !== 'assistant') return

        if (chunk.conversationId) {
          currentConversationId.value = chunk.conversationId
        }

        const variantIdx = chunk.variantIndex ?? 0
        const resp = msg.responses[variantIdx]
        if (!resp) return

        resp.fullContent = chunk.fullContent ?? resp.fullContent
        resp.done = chunk.done ?? resp.done
        resp.hasError = chunk.hasError ?? resp.hasError
        resp.hasReasoning = chunk.hasReasoning ?? resp.hasReasoning
        resp.reasoning = chunk.reasoning ?? resp.reasoning
        resp.inputTokens = chunk.inputTokens ?? resp.inputTokens
        resp.outputTokens = chunk.outputTokens ?? resp.outputTokens
        resp.elapsedMs = chunk.elapsedMs ?? resp.elapsedMs
        resp.cost = chunk.cost ?? resp.cost
        resp.error = chunk.error ?? resp.error

        messages.value = [...messages.value]

        if (chunk.done && msg.responses.every((r) => r.done)) {
          isLoading.value = false
        }
      },
      onError: (error) => {
        isLoading.value = false
        message.error(error.message || '请求失败')
      },
      onComplete: () => {
        isLoading.value = false
      },
    })
  } catch {
    isLoading.value = false
  }
}

const handleRating = async (
  messageListIndex: number,
  ratingType: RatingRequest['ratingType'],
  winnerVariantIndex?: number,
) => {
  const msg = messages.value[messageListIndex]
  if (!msg || msg.type !== 'assistant') return
  if (!currentConversationId.value) {
    message.warning('对话尚未创建完成')
    return
  }

  const rating: RatingRequest = {
    conversationId: currentConversationId.value,
    messageIndex: msg.messageIndex,
    ratingType,
    winnerModel:
      winnerVariantIndex !== undefined
        ? `${selectedModel.value}#variant-${winnerVariantIndex}`
        : undefined,
  }

  const res = await addRating(rating)
  if (res.data.code === 0) {
    msg.rating = rating
    messages.value = [...messages.value]
    message.success('评分已保存')
  } else {
    message.error(res.data.message || '评分失败')
  }
}

const isVariantSelected = (msg: AssistantMessage, variantIndex: number) => {
  return (
    msg.rating?.ratingType === 'model_better' &&
    msg.rating.winnerModel === `${selectedModel.value}#variant-${variantIndex}`
  )
}

const getModelById = (modelName?: string) => {
  if (!modelName) return undefined
  return models.value.find((item) => item.id === modelName)
}

const getModelName = (modelName?: string) => {
  if (!modelName) return '未知模型'
  const model = getModelById(modelName)
  return model?.name || modelName.split('/').pop() || modelName
}

const parseModalities = (value?: string) => {
  if (!value) return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

const modalityLabelMap: Record<string, string> = {
  text: '文本',
  image: '图像',
  file: '文件',
  audio: '音频',
  video: '视频',
}

const getInputModalityLabels = (modelName?: string) => {
  return getInputModalities(modelName).map((item) => modalityLabelMap[item] || item)
}

const readAsDataUrl = (file: File) => {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const getBase64FromDataUrl = (dataUrl: string) => dataUrl.split(',')[1] || ''

const getAudioFormat = (file: File) => {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext === 'mp3') return 'mp3'
  if (ext === 'wav') return 'wav'
  if (ext === 'm4a') return 'm4a'
  if (ext === 'aac') return 'aac'
  if (ext === 'ogg') return 'ogg'
  if (ext === 'flac') return 'flac'
  if (ext === 'aiff') return 'aiff'
  return ext || 'mp3'
}

const getFileFormat = (file: File) => {
  return file.name.split('.').pop()?.toLowerCase() || ''
}

const processFiles = async (files: File[]) => {
  for (const file of files) {
    if (file.type.startsWith('image/')) {
      if (!canUseImageInput.value) {
        message.warning('当前选择的模型不支持图片输入')
        continue
      }
      if (attachments.value.filter((a) => a.kind === 'image').length >= 4) {
        message.warning('最多上传 4 张图片')
        break
      }
      if (file.size > 4 * 1024 * 1024) {
        message.warning(`${file.name} 超过 4MB，已跳过`)
        continue
      }
      const url = await readAsDataUrl(file)
      attachments.value.push({ kind: 'image', name: file.name, url })
    } else if (file.type.startsWith('audio/')) {
      if (!canUseAudioInput.value) {
        message.warning('当前选择的模型不支持音频输入')
        continue
      }
      if (attachments.value.filter((a) => a.kind === 'audio').length >= 2) {
        message.warning('最多上传 2 个音频')
        break
      }
      if (file.size > 8 * 1024 * 1024) {
        message.warning(`${file.name} 超过 8MB，已跳过`)
        continue
      }
      const dataUrl = await readAsDataUrl(file)
      const format = getAudioFormat(file)
      attachments.value.push({
        kind: 'audio',
        name: file.name,
        data: getBase64FromDataUrl(dataUrl),
        format,
      })
    } else {
      if (!canUseFileInput.value) {
        message.warning('当前选择的模型不支持文件输入')
        continue
      }
      if (attachments.value.filter((a) => a.kind === 'file').length >= 3) {
        message.warning('最多上传 3 个文件')
        break
      }
      if (file.size > 10 * 1024 * 1024) {
        message.warning(`${file.name} 超过 10MB，已跳过`)
        continue
      }
      const format = getFileFormat(file)
      const dataUrl = await readAsDataUrl(file)
      attachments.value.push({
        kind: 'file',
        name: file.name,
        data: getBase64FromDataUrl(dataUrl),
        format,
        mimeType: file.type || 'application/octet-stream',
      })
    }
  }
}

const handleFileSelect = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (files.length) await processFiles(files)
}

const handlePaste = async (e: ClipboardEvent) => {
  const items = Array.from(e.clipboardData?.items || [])
  const files = items
    .filter((item) => item.kind === 'file')
    .map((item) => item.getAsFile())
    .filter((f): f is File => f !== null)
  if (files.length) {
    e.preventDefault()
    await processFiles(files)
  }
}

const removeAttachment = (index: number) => {
  attachments.value.splice(index, 1)
}

const clearAttachments = () => {
  attachments.value = []
}

const openPreview = (url: string) => {
  previewImage.value = url
  showPreview.value = true
}

onMounted(() => {
  loadModels()
})

onBeforeUnmount(() => {
  if (sse.value) {
    sse.value.close()
  }
})
</script>

<style scoped>
.prompt-lab-page {
  min-height: 100%;
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.modality-tags {
  display: inline-flex;
  gap: 4px;
  flex-wrap: wrap;
}

.modality-tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 5px;
  color: #175cd3;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 11px;
}

/* 历史记录区 */
.history-section {
  padding: 0;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message-round {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-round.assistant {
  margin-top: 8px;
}

/* 变体网格 */
.variants-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 768px) {
  .variants-grid {
    grid-template-columns: 1fr;
  }
}

/* 变体展示卡片（历史中的输入） */
.variant-display-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
}

.variant-display-header {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
  font-weight: 500;
}

.variant-display-body {
  font-size: 14px;
  color: #1f2937;
  line-height: 1.6;
  white-space: pre-wrap;
}

.user-attachments-bar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.att-tag {
  padding: 2px 8px;
  color: #175cd3;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 12px;
}

/* 评分区 */
.rating-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}

.rating-label {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

/* 结果网格 */
.results-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 768px) {
  .results-grid {
    grid-template-columns: 1fr;
  }
}

/* 结果卡片 */
.result-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  min-height: 120px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f3f4f6;
}

.variant-badge {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  color: #fff;
  background: #1677ff;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
}

.result-metrics {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #6b7280;
}

.metric {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.result-alert {
  margin-bottom: 10px;
}

/* 输入区 */
.input-section {
  margin: 0;
  padding: 20px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.base-prompt-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.base-prompt-textarea {
  flex: 1;
}

.input-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

/* 变体输入卡片 */
.variant-input-card {
  background: #fafbfc;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.variant-input-card:focus-within {
  border-color: #1677ff;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.08);
}

.variant-input-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.variant-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.variant-remove-btn {
  padding: 0 4px !important;
  height: auto !important;
}

/* 附件行 */
.attachments-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.attachment-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 10px;
  color: #4b5563;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.attachment-btn:hover {
  background: #e5e7eb;
}

.attachment-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.attachment-btn.disabled {
  color: #9ca3af;
  background: #f9fafb;
  border-color: #e5e7eb;
  cursor: not-allowed;
}

.attachments-preview {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.att-preview-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
}

.att-preview-img {
  width: 28px;
  height: 28px;
  object-fit: cover;
  border-radius: 4px;
  cursor: zoom-in;
}

.att-preview-badge {
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.att-preview-badge.audio {
  color: #7c2d12;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.att-preview-badge.file {
  color: #1e3a8a;
  background: #dbeafe;
  border: 1px solid #bfdbfe;
}

.att-preview-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-warning {
  margin: 0;
}

/* 开始实验按钮 */
.start-btn {
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  height: 44px;
}

/* Markdown 内容 */
.markdown-body {
  color: #1f2937;
  line-height: 1.7;
  overflow-wrap: anywhere;
  font-size: 14px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  color: #111827;
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.markdown-body :deep(p) {
  margin-bottom: 8px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin-bottom: 8px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(a) {
  color: #1677ff;
  text-decoration: none;
}

.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 6px 12px;
  color: #4b5563;
  border-left: 4px solid #d1d5db;
  background: #f9fafb;
  border-radius: 0 6px 6px 0;
}

.markdown-body :deep(pre) {
  padding: 12px;
  overflow-x: auto;
  background: #111827;
  border-radius: 8px;
  color: #e5e7eb;
  margin-bottom: 10px;
  font-size: 13px;
}

.markdown-body :deep(pre code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #e5e7eb;
  background: transparent;
  padding: 0;
}

.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #c7254e;
  background: #f9f2f4;
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 0.9em;
}

/* 思考过程 */
.reasoning {
  margin-bottom: 10px;
  padding: 8px 12px;
  background: #f5f7fb;
  border: 1px solid #e8ecf3;
  border-radius: 8px;
}

.reasoning summary {
  cursor: pointer;
  color: #475467;
  font-size: 13px;
}

/* 加载动画 */
.dots {
  display: inline-flex;
  gap: 5px;
  margin-top: 8px;
}

.dots span {
  width: 6px;
  height: 6px;
  background: #9aa4b2;
  border-radius: 50%;
  animation: dotPulse 1s infinite ease-in-out;
}

.dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes dotPulse {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
</style>
