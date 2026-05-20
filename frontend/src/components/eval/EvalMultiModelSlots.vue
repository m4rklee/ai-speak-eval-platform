<template>
  <div class="eval-multi-model-slots">
    <p class="hint">
      为每个模型单独上传 answer {{ fileLabel }}，按文件名对齐同一题目，提交后输出各模型得分对比。
    </p>
    <div v-for="(slot, idx) in modelSlots" :key="slot.id" class="model-slot">
      <div class="model-slot-header">
        <span class="model-slot-label">模型 {{ idx + 1 }}</span>
        <a-button
          v-if="modelSlots.length > 2"
          type="link"
          danger
          size="small"
          @click="removeModelSlot(slot.id)"
        >
          删除
        </a-button>
      </div>
      <a-input
        v-model:value="slot.modelName"
        placeholder="模型名称，如 GPT-4o"
        style="max-width: 360px; margin-bottom: 8px"
      />
      <a-space wrap>
        <a-upload
          :multiple="true"
          :file-list="slot.fileList"
          :accept="acceptMime"
          :before-upload="slotBeforeUpload(slot.id)"
          @remove="slotRemove(slot.id)"
        >
          <a-button size="small">
            <UploadOutlined />
            选择 {{ fileLabel }}
          </a-button>
        </a-upload>
        <input
          :ref="(el) => setSlotDirRef(slot.id, el as HTMLInputElement | null)"
          type="file"
          webkitdirectory
          directory
          multiple
          :accept="acceptMime"
          style="display: none"
          @change="(e) => onSlotDirChange(slot.id, e)"
        />
        <a-button size="small" @click="pickSlotDirectory(slot.id)">
          <FolderOpenOutlined />
          选文件夹
        </a-button>
        <a-upload
          :multiple="false"
          :show-upload-list="!!slot.zipFile"
          accept=".zip"
          :before-upload="slotZipUpload(slot.id)"
          @remove="slot.zipFile = null"
        >
          <a-button size="small">
            <FileZipOutlined />
            zip
          </a-button>
        </a-upload>
      </a-space>
      <p class="hint">
        <span v-if="slot.zipFile">已选 zip：{{ slot.zipFile.name }}</span>
        <span v-else-if="slot.dirFiles.length && slot.dirFolderName">
          已选文件夹「{{ slot.dirFolderName }}」· {{ slot.dirFiles.length }} 个 {{ fileLabel }}
        </span>
        <span v-else-if="slot.files.length">已选 {{ slot.files.length }} 个 {{ fileLabel }}</span>
        <span v-else-if="slot.dirFiles.length">已选 {{ slot.dirFiles.length }} 个 {{ fileLabel }}</span>
      </p>
    </div>
    <a-space style="margin-top: 12px">
      <a-button v-if="modelSlots.length < maxModels" @click="addModelSlot">+ 添加模型</a-button>
      <a-button
        type="primary"
        :loading="loading"
        :disabled="!canSubmit"
        @click="emitSubmit"
      >
        提交多模型评测（{{ modelSlots.length }} 模型，共 {{ totalFiles }} 个 {{ fileLabel }}）
      </a-button>
    </a-space>
    <p v-if="showLoginHint" class="hint">请先登录后再提交评测</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'
import { FileZipOutlined, FolderOpenOutlined, UploadOutlined } from '@ant-design/icons-vue'
import type { ModelEvalSlot } from '@/api/unifiedEvalController'
import type { EvalAcceptExt } from '@/composables/useEvalBatchUpload'

const props = withDefaults(
  defineProps<{
    acceptExt: EvalAcceptExt
    fileLabel: string
    maxModels?: number
    loading?: boolean
    submitDisabled?: boolean
    showLoginHint?: boolean
  }>(),
  {
    maxModels: 10,
    loading: false,
    submitDisabled: false,
    showLoginHint: false,
  },
)

const emit = defineEmits<{
  submit: [slots: ModelEvalSlot[]]
}>()

const ext = computed(() => (props.acceptExt === 'wav' ? '.wav' : '.txt'))
const acceptMime = computed(() =>
  props.acceptExt === 'wav' ? '.wav,audio/wav' : '.txt,text/plain',
)

let slotIdSeq = 0

function folderNameFromFileList(files: File[]): string {
  if (!files.length) return ''
  const rel = (files[0] as File & { webkitRelativePath?: string }).webkitRelativePath || ''
  const normalized = rel.replace(/\\/g, '/')
  const slash = normalized.indexOf('/')
  return slash > 0 ? normalized.slice(0, slash) : ''
}

function createEmptySlot(): ModelEvalSlot {
  return {
    id: `slot-${++slotIdSeq}`,
    modelName: '',
    files: [],
    fileList: [],
    dirFiles: [],
    dirFolderName: '',
    zipFile: null,
  }
}

const modelSlots = ref<ModelEvalSlot[]>([createEmptySlot(), createEmptySlot()])
const slotDirRefs = ref<Record<string, HTMLInputElement | null>>({})

function matchesExt(name: string) {
  return name.toLowerCase().endsWith(ext.value)
}

function slotFileCount(slot: ModelEvalSlot): number | 'zip' {
  if (slot.zipFile) return 'zip'
  return slot.files.length || slot.dirFiles.length
}

function findSlot(id: string) {
  return modelSlots.value.find((s) => s.id === id)
}

function setSlotDirRef(id: string, el: HTMLInputElement | null) {
  slotDirRefs.value[id] = el
}

function pickSlotDirectory(id: string) {
  slotDirRefs.value[id]?.click()
}

function onSlotMultiBeforeUpload(slotId: string, file: File) {
  const slot = findSlot(slotId)
  if (!slot) return false
  if (!matchesExt(file.name)) {
    message.warning(`仅支持 ${props.fileLabel}`)
    return false
  }
  slot.zipFile = null
  slot.dirFiles = []
  slot.dirFolderName = ''
  slot.files.push(file)
  slot.fileList = [
    ...(slot.fileList || []),
    { uid: `${Date.now()}-${file.name}`, name: file.name, status: 'done' },
  ]
  return false
}

function onSlotMultiRemove(slotId: string, file: { name?: string }) {
  const slot = findSlot(slotId)
  if (!slot) return
  const name = file.name
  slot.files = slot.files.filter((f) => f.name !== name)
  slot.fileList = (slot.fileList || []).filter((f) => f.name !== name)
}

function onSlotDirChange(slotId: string, e: Event) {
  const slot = findSlot(slotId)
  if (!slot) return
  const input = e.target as HTMLInputElement
  const list = input.files
  if (!list) return
  slot.zipFile = null
  slot.files = []
  slot.fileList = []
  slot.dirFiles = Array.from(list).filter((f) => matchesExt(f.name))
  slot.dirFolderName = folderNameFromFileList(slot.dirFiles)
  const folderLabel = slot.dirFolderName ? `文件夹「${slot.dirFolderName}」` : '文件夹'
  message.info(`已选择 ${folderLabel}，共 ${slot.dirFiles.length} 个 ${props.fileLabel}`)
  input.value = ''
}

function onSlotZipBeforeUpload(slotId: string, file: File) {
  const slot = findSlot(slotId)
  if (!slot) return false
  slot.zipFile = file
  slot.files = []
  slot.fileList = []
  slot.dirFiles = []
  slot.dirFolderName = ''
  return false
}

function slotBeforeUpload(slotId: string): UploadProps['beforeUpload'] {
  return (file) => onSlotMultiBeforeUpload(slotId, file as File)
}

function slotRemove(slotId: string): UploadProps['onRemove'] {
  return (file) => onSlotMultiRemove(slotId, file)
}

function slotZipUpload(slotId: string): UploadProps['beforeUpload'] {
  return (file) => onSlotZipBeforeUpload(slotId, file as File)
}

function addModelSlot() {
  if (modelSlots.value.length >= props.maxModels) return
  modelSlots.value.push(createEmptySlot())
}

function removeModelSlot(id: string) {
  if (modelSlots.value.length <= 2) return
  modelSlots.value = modelSlots.value.filter((s) => s.id !== id)
  delete slotDirRefs.value[id]
}

const totalFiles = computed(() =>
  modelSlots.value.reduce((sum, slot) => {
    const count = slotFileCount(slot)
    if (count === 'zip') return sum
    return sum + count
  }, 0),
)

const canSubmit = computed(() => {
  if (props.submitDisabled) return false
  if (modelSlots.value.length < 2) return false
  const names = modelSlots.value.map((s) => s.modelName.trim()).filter(Boolean)
  if (names.length !== modelSlots.value.length) return false
  if (new Set(names).size !== names.length) return false
  return modelSlots.value.every((slot) => {
    const count = slotFileCount(slot)
    return count === 'zip' || count > 0
  })
})

function emitSubmit() {
  if (!canSubmit.value) {
    message.warning(`请填写不重复的模型名，且每个模型至少上传 ${props.fileLabel} 或 zip`)
    return
  }
  emit('submit', modelSlots.value)
}
</script>

<style scoped>
.hint {
  color: #888;
  font-size: 13px;
  margin-top: 8px;
}

.model-slot {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 12px;
  background: #fafafa;
}

.model-slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.model-slot-label {
  font-weight: 500;
}
</style>
