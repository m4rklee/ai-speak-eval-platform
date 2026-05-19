<template>
  <div class="side-by-side-page">
    <div class="page-container">
      <div class="page-header">
        <PageTitle
          icon-key="side-by-side"
          title="模型对比"
          subtitle="同时调用多个模型，并排查看回复并评分"
        />
      </div>

      <a-card title="对比配置" class="page-section composer-card">
    <section
      class="composer"
      :class="{ 'drag-over': dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="handleDrop"
    >
      <div v-if="dragOver" class="drag-overlay">
        <span>释放以上传文件</span>
      </div>

      <a-form layout="vertical">
        <a-form-item label="选择模型">
          <a-select
            v-model:value="selectedModels"
            mode="multiple"
            :max-tag-count="4"
            placeholder="选择 1-8 个模型"
            :loading="modelsLoading"
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

          <div v-if="selectedModels.length" class="selected-capabilities">
            <div
              v-for="modelId in selectedModels.filter(Boolean)"
              :key="modelId"
              class="selected-capability"
            >
              <span class="selected-model-name">{{ getModelName(modelId) }}</span>
              <span class="selected-model-modality">{{ getModelCapabilityText(modelId) }}</span>
            </div>
          </div>
        </a-form-item>

        <a-form-item label="输入问题">
          <a-textarea
            v-model:value="userInput"
            placeholder="请输入要对比的问题，支持粘贴图片/文件"
            :rows="4"
            @keydown.ctrl.enter="sendMessage"
            @paste="handlePaste"
          />
        </a-form-item>

        <a-form-item label="附件输入">
          <div class="attachment-actions">
            <label
              class="attachment-button"
              :class="{ disabled: !canUseImageInput }"
              :title="canUseImageInput ? '添加图片输入' : '当前选择的模型不支持图片输入'"
            >
              <PictureOutlined />
              选择图片
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                multiple
                :disabled="!canUseImageInput"
                @change="handleFileSelect"
              />
            </label>
            <label
              class="attachment-button"
              :class="{ disabled: !canUseAudioInput }"
              :title="canUseAudioInput ? '添加音频输入' : '当前选择的模型不支持音频输入'"
            >
              <AudioOutlined />
              选择音频
              <input
                type="file"
                accept="audio/wav,audio/mpeg,audio/mp3,audio/aac,audio/ogg,audio/flac,audio/mp4,audio/x-m4a"
                multiple
                :disabled="!canUseAudioInput"
                @change="handleFileSelect"
              />
            </label>
            <label
              class="attachment-button"
              :class="{ disabled: !canUseFileInput }"
              :title="canUseFileInput ? '添加文件输入(PDF/文档)' : '当前选择的模型不支持文件输入'"
            >
              <FileTextOutlined />
              选择文件
              <input
                type="file"
                accept=".pdf,.txt,.md,.json,.csv,.html,.css,.js,.ts,.py,.java,.cpp,.c,.go,.xml,.yaml,.yml"
                multiple
                :disabled="!canUseFileInput"
                @change="handleFileSelect"
              />
            </label>
            <a-button
              v-if="attachments.length"
              size="small"
              danger
              @click="clearAttachments"
            >
              <DeleteOutlined />
              清除全部
            </a-button>
          </div>

          <div class="attachment-capability-hint">
            <span :class="{ available: canUseImageInput }">
              图片：{{ canUseImageInput ? '可用' : '不支持' }}
            </span>
            <span :class="{ available: canUseAudioInput }">
              音频：{{ canUseAudioInput ? '可用' : '不支持' }}
            </span>
            <span :class="{ available: canUseFileInput }">
              文件：{{ canUseFileInput ? '可用' : '不支持' }}
            </span>
          </div>

          <div v-if="attachments.length" class="attachment-list">
            <div
              v-for="(att, idx) in attachments"
              :key="`${att.kind}-${att.name}-${idx}`"
              class="attachment-item"
              :class="`attachment-item--${att.kind}`"
            >
              <template v-if="att.kind === 'image'">
                <img
                  :src="att.url"
                  :alt="att.name"
                  class="attachment-thumb"
                  @click="openPreview(att.url)"
                />
              </template>
              <template v-else-if="att.kind === 'audio'">
                <span class="audio-mark">音频</span>
              </template>
              <template v-else>
                <span class="file-mark">{{ att.format.toUpperCase() }}</span>
              </template>

              <span class="attachment-name" :title="att.name">{{ att.name }}</span>

              <template v-if="att.kind === 'audio'">
                <audio controls :src="`data:audio/${att.format};base64,${att.data}`" class="audio-player" />
              </template>

              <a-button
                type="text"
                size="small"
                danger
                class="attachment-delete"
                @click="removeAttachment(idx)"
              >
                <CloseOutlined />
              </a-button>
            </div>
          </div>

          <a-alert
            v-if="attachmentWarning"
            class="attachment-warning"
            type="warning"
            show-icon
            :message="attachmentWarning"
          />
        </a-form-item>

        <a-space>
          <a-button type="primary" :loading="isLoading" :disabled="!canSend" @click="sendMessage">
            {{ isLoading ? '生成中' : '发送对比' }}
          </a-button>
          <a-button :disabled="isLoading" @click="clearMessages">清空</a-button>
        </a-space>
      </a-form>
    </section>
      </a-card>

    <section class="messages page-section">
      <a-empty v-if="messages.length === 0" description="暂无对话" />

      <div v-for="(msg, idx) in messages" :key="idx" class="message-block" :class="msg.type">
        <div v-if="msg.type === 'user'" class="user-message">
          <div>{{ msg.content }}</div>
          <div v-if="msg.attachments?.length" class="user-attachments">
            <span v-for="attachment in msg.attachments" :key="attachment">
              {{ attachment }}
            </span>
          </div>
        </div>

        <template v-else>
          <div class="ai-responses">
            <div
              v-for="(resp, respIndex) in msg.responses"
              :key="`${resp.modelName}-${respIndex}`"
              class="response-card"
            >
              <div class="col-header">
                <span class="model-icon">{{ getProviderIcon(resp.modelName) }}</span>
                <span class="model-tag">{{ getModelName(resp.modelName) }}</span>
                <span
                  v-for="modality in getInputModalityLabels(resp.modelName)"
                  :key="`${resp.modelName}-${modality}`"
                  class="modality-tag"
                >
                  {{ modality }}
                </span>
                <span v-if="resp.elapsedMs">{{ (resp.elapsedMs / 1000).toFixed(1) }}s</span>
                <span v-if="resp.inputTokens || resp.outputTokens">
                  {{ (resp.inputTokens || 0) + (resp.outputTokens || 0) }}t
                </span>
                <span v-if="resp.cost">${{ resp.cost.toFixed(4) }}</span>
              </div>

              <a-alert
                v-if="resp.hasError"
                type="error"
                show-icon
                :message="resp.error || '模型调用失败'"
              />

              <details v-if="resp.hasReasoning && resp.reasoning" class="reasoning" open>
                <summary>
                  思考了 {{ resp.thinkingTime ?? Math.floor((resp.elapsedMs || 0) / 1000) }} 秒
                </summary>
                <div class="markdown-body" v-html="renderMarkdown(resp.reasoning)" />
              </details>

              <div class="markdown-body" v-html="renderMarkdown(resp.fullContent || '')" />

              <div v-if="!resp.done && !resp.hasError" class="dots">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>

          <div
            v-if="msg.responses.every((r) => r.done) && msg.responses.length >= 2"
            class="rating-section"
          >
            <a-button
              v-for="(resp, respIdx) in msg.responses"
              :key="`model-better-${respIdx}`"
              size="small"
              :type="isModelSelected(msg, resp.modelName) ? 'primary' : 'default'"
              @click="handleRating(idx, 'model_better', resp.modelName)"
            >
              {{ getModelName(resp.modelName) }} 更好
            </a-button>
            <a-button
              size="small"
              :type="msg.rating?.ratingType === 'tie' ? 'primary' : 'default'"
              @click="handleRating(idx, 'tie')"
            >
              平局
            </a-button>
            <a-button
              size="small"
              :type="msg.rating?.ratingType === 'both_bad' ? 'primary' : 'default'"
              @click="handleRating(idx, 'both_bad')"
            >
              都不好
            </a-button>
          </div>
        </template>
      </div>
    </section>
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
} from '@ant-design/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { listModels, type ModelVO } from '@/api/modelController'
import { addRating, type RatingRequest } from '@/api/ratingController'
import { createPostSSE } from '@/utils/sseClient'

type StreamChunkVO = {
  conversationId?: string
  modelName?: string
  content?: string
  fullContent?: string
  inputTokens?: number
  outputTokens?: number
  elapsedMs?: number
  responseTimeMs?: number
  cost?: number
  done?: boolean
  hasError?: boolean
  error?: string
  reasoning?: string
  hasReasoning?: boolean
  thinkingTime?: number
}

type AiResponse = StreamChunkVO & {
  modelName: string
  fullContent: string
  done: boolean
  hasError: boolean
}

type UserMessage = {
  type: 'user'
  content: string
  attachments?: string[]
}

type AssistantMessage = {
  type: 'assistant'
  messageIndex: number
  responses: AiResponse[]
  rating?: RatingRequest
}

type ChatMessage = UserMessage | AssistantMessage

type ImageAttachment = { kind: 'image'; name: string; url: string }
type AudioAttachment = { kind: 'audio'; name: string; data: string; format: string }
type FileAttachment = { kind: 'file'; name: string; data: string; format: string; mimeType: string }
type Attachment = ImageAttachment | AudioAttachment | FileAttachment

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const fallbackModels = [
  { label: 'DeepSeek Chat', value: 'deepseek/deepseek-chat' },
  { label: 'Qwen 2.5 72B', value: 'qwen/qwen-2.5-72b-instruct' },
  { label: 'GPT-4o Mini', value: 'openai/gpt-4o-mini' },
]

const userInput = ref('')
const selectedModels = ref<string[]>(['deepseek/deepseek-chat'])
const models = ref<ModelVO[]>([])
const modelsLoading = ref(false)
const messages = ref<ChatMessage[]>([])
const attachments = ref<Attachment[]>([])
const isLoading = ref(false)
const sse = ref<{ close: () => void } | null>(null)
const currentConversationId = ref<string | null>(null)
const nextAssistantMessageIndex = ref(1)
const dragOver = ref(false)
const showPreview = ref(false)
const previewImage = ref('')

const modelOptions = computed(() => {
  if (!models.value.length) return fallbackModels
  return models.value.map((model) => ({
    label: model.name || model.id,
    value: model.id,
  }))
})

const selectedModelIds = computed(() => selectedModels.value.filter(Boolean))

const selectedModelsSupport = (modality: string) => {
  const selected = selectedModelIds.value
  return selected.length > 0 && selected.every((modelId) => getInputModalities(modelId).includes(modality))
}

const canUseImageInput = computed(() => selectedModelsSupport('image'))
const canUseAudioInput = computed(() => selectedModelsSupport('audio'))
const canUseFileInput = computed(() => selectedModelsSupport('file'))

const attachmentWarning = computed(() => {
  const selected = selectedModelIds.value
  if (!selected.length) return ''

  const unsupported = selected.filter((modelId) => {
    const modalities = getInputModalities(modelId)
    return attachments.value.some((att) => {
      if (att.kind === 'image' && !modalities.includes('image')) return true
      if (att.kind === 'audio' && !modalities.includes('audio')) return true
      if (att.kind === 'file' && !modalities.includes('file')) return true
      return false
    })
  })

  if (!unsupported.length) return ''
  return `当前附件与部分模型不兼容：${unsupported.map(getModelName).join('、')}`
})

const canSend = computed(() => {
  return (
    !isLoading.value &&
    selectedModelIds.value.length > 0 &&
    (userInput.value.trim().length > 0 || attachments.value.length > 0) &&
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

const sendMessage = async () => {
  if (!canSend.value) return

  const text = userInput.value.trim()
  const currentAttachments = attachments.value
  attachments.value = []
  userInput.value = ''
  isLoading.value = true

  const validModels = selectedModels.value.filter(Boolean).slice(0, 8)

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

  messages.value.push({ type: 'user', content: text, attachments: attachmentLabels })

  const assistantMsgIndex = messages.value.length
  const messageIndex = nextAssistantMessageIndex.value
  messages.value.push({
    type: 'assistant',
    messageIndex,
    responses: validModels.map((model) => ({
      modelName: model,
      fullContent: '',
      done: false,
      hasError: false,
    })),
  })
  nextAssistantMessageIndex.value += 2

  const url = `${API_BASE_URL}/conversation/side-by-side/stream`
  const body = {
    conversationId: currentConversationId.value,
    models: validModels,
    prompt: text,
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

        const idx = msg.responses.findIndex((resp) => resp.modelName === chunk.modelName)
        if (idx >= 0) {
          const currentResp = msg.responses[idx]
          if (!currentResp) return
          msg.responses[idx] = {
            ...currentResp,
            ...chunk,
            modelName: currentResp.modelName,
            fullContent: chunk.fullContent ?? currentResp.fullContent,
            done: chunk.done ?? currentResp.done,
            hasError: chunk.hasError ?? currentResp.hasError,
          }
          messages.value = [...messages.value]
        }

        if (chunk.done && msg.responses.every((resp) => resp.done)) {
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
  winnerModel?: string,
) => {
  const msg = messages.value[messageListIndex]
  if (!msg || msg.type !== 'assistant') return
  if (!currentConversationId.value) {
    message.warning('对话尚未创建完成')
    return
  }

  const loserModel =
    ratingType === 'model_better'
      ? msg.responses.find((resp) => resp.modelName !== winnerModel)?.modelName
      : undefined

  const rating: RatingRequest = {
    conversationId: currentConversationId.value,
    messageIndex: msg.messageIndex,
    ratingType,
    winnerModel,
    loserModel,
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

const isModelSelected = (msg: AssistantMessage, modelName: string) => {
  return msg.rating?.ratingType === 'model_better' && msg.rating.winnerModel === modelName
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

const handleDrop = async (e: DragEvent) => {
  dragOver.value = false
  const files = Array.from(e.dataTransfer?.files || [])
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

const getInputModalities = (modelName?: string) => {
  const model = getModelById(modelName)
  const modalities = parseModalities(model?.inputModalities)
  if (modalities.length) return modalities
  const modality = model?.modality
  if (modality) return (modality.split('->')[0] || 'text').split('+').filter(Boolean)
  return ['text']
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

const getModelCapabilityText = (modelName?: string) => {
  const model = getModelById(modelName)
  const input = getInputModalityLabels(modelName).join('、')
  const outputModalities = parseModalities(model?.outputModalities)
  const output = outputModalities.length
    ? outputModalities.map((item) => modalityLabelMap[item] || item).join('、')
    : '文本'
  return `输入：${input} / 输出：${output}`
}

const getProviderIcon = (modelName?: string) => {
  return (modelName || '?').slice(0, 1).toUpperCase()
}

const clearMessages = () => {
  sse.value?.close()
  messages.value = []
  currentConversationId.value = null
  nextAssistantMessageIndex.value = 1
  clearAttachments()
  isLoading.value = false
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
.side-by-side-page {
  min-height: 100%;
}

.composer-card :deep(.ant-card-body) {
  padding-top: 16px;
}

.composer {
  position: relative;
  padding: 0;
  background: transparent;
  border: none;
  transition: box-shadow 0.2s;
}

.composer.drag-over {
  box-shadow: inset 0 0 0 2px #1677ff;
}

.drag-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(22, 119, 255, 0.08);
  pointer-events: none;
}

.drag-overlay span {
  padding: 10px 24px;
  color: #1677ff;
  background: #fff;
  border: 2px dashed #1677ff;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
}

.messages {
  padding: 0;
}

.message-block {
  margin-bottom: 20px;
}

.user-message {
  max-width: 720px;
  margin-left: auto;
  padding: 12px 16px;
  color: #1f2937;
  background: #e8f3ff;
  border: 1px solid #d4e7ff;
  border-radius: 8px;
  white-space: pre-wrap;
}

.user-attachments {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.user-attachments span {
  padding: 2px 7px;
  color: #175cd3;
  background: #fff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 12px;
}

.ai-responses {
  display: flex;
  gap: 20px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.response-card {
  flex: 1 1 0;
  min-width: 360px;
  min-height: 180px;
  padding: 18px;
  background: #fff;
  border: 1px solid #e7eaf0;
  border-radius: 8px;
}

.col-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  color: #667085;
  font-size: 12px;
  flex-wrap: wrap;
}

.model-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: #fff;
  background: #1677ff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
}

.model-tag {
  color: #1f2937;
  font-weight: 600;
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
  justify-content: flex-end;
}

.modality-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  color: #175cd3;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.selected-capabilities {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.selected-capability {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.selected-model-name {
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
}

.selected-model-modality {
  color: #667085;
  font-size: 12px;
  text-align: right;
}

.attachment-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.attachment-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  color: #1f2937;
  background: #fff;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.attachment-button:hover {
  border-color: #1677ff;
  color: #1677ff;
}

.attachment-button input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.attachment-button.disabled {
  color: #98a2b3;
  background: #f2f4f7;
  border-color: #e4e7ec;
  cursor: not-allowed;
}

.attachment-button.disabled input {
  cursor: not-allowed;
}

.attachment-capability-hint {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: #98a2b3;
  font-size: 12px;
}

.attachment-capability-hint .available {
  color: #067647;
}

.attachment-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.attachment-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 320px;
  padding: 6px 8px;
  color: #344054;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
}

.attachment-item--image {
  padding-right: 28px;
}

.attachment-item--audio {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding-bottom: 8px;
}

.attachment-item--file {
  padding-right: 28px;
}

.attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.attachment-thumb {
  width: 34px;
  height: 34px;
  object-fit: cover;
  border-radius: 4px;
  cursor: zoom-in;
}

.audio-mark {
  flex: none;
  padding: 2px 6px;
  color: #7c2d12;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 4px;
}

.file-mark {
  flex: none;
  padding: 2px 6px;
  color: #1e3a8a;
  background: #dbeafe;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.audio-player {
  height: 28px;
  width: 220px;
  max-width: 100%;
}

.attachment-delete {
  position: absolute;
  right: 2px;
  top: 2px;
  padding: 2px 4px !important;
  height: auto !important;
  line-height: 1;
}

.attachment-warning {
  margin-top: 10px;
}

.reasoning {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f5f7fb;
  border: 1px solid #e8ecf3;
  border-radius: 8px;
}

.reasoning summary {
  cursor: pointer;
  color: #475467;
  font-size: 13px;
}

.markdown-body {
  color: #1f2937;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  color: #111827;
  margin-top: 18px;
  margin-bottom: 10px;
  font-weight: 600;
}

.markdown-body :deep(p) {
  margin-bottom: 10px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 22px;
  margin-bottom: 10px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(a) {
  color: #1677ff;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  color: #4b5563;
  border-left: 4px solid #d1d5db;
  background: #f9fafb;
  border-radius: 0 6px 6px 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 12px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f9fafb;
  font-weight: 600;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}

.markdown-body :deep(pre) {
  padding: 14px;
  overflow-x: auto;
  background: #111827;
  border-radius: 8px;
  color: #e5e7eb;
  margin-bottom: 12px;
}

.markdown-body :deep(pre code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #e5e7eb;
  background: transparent;
  padding: 0;
  font-size: 13px;
}

.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #c7254e;
  background: #f9f2f4;
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 0.9em;
}

.markdown-body :deep(hr) {
  border: 0;
  border-top: 1px solid #e5e7eb;
  margin: 16px 0;
}

.dots {
  display: inline-flex;
  gap: 5px;
  margin-top: 10px;
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

.rating-section {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 14px;
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

@media (max-width: 768px) {
  .composer,
  .messages {
    padding-right: 14px;
    padding-left: 14px;
  }

  .response-card {
    min-width: 300px;
  }

  .attachment-item {
    max-width: 100%;
  }
}
</style>
