<template>
  <div class="oral-gen-panel">
    <a-card title="服务状态" class="page-section" size="small">
      <a-space wrap>
        <a-tag :color="health?.questionwavDirOk ? 'green' : 'default'">
          内置音频 {{ health?.wavCount ?? 0 }} 条
        </a-tag>
        <a-tag :color="health?.apiConfigured ? 'green' : 'red'">
          API {{ health?.apiConfigured ? '已配置' : '未配置' }}
        </a-tag>
      </a-space>
      <p v-if="health?.message && !health?.ready" class="hint">{{ health.message }}</p>
      <a-button size="small" style="margin-top: 8px" :loading="healthLoading" @click="loadHealth">
        刷新状态
      </a-button>
    </a-card>

    <a-card title="生成配置" class="page-section">
      <a-form layout="vertical">
        <a-form-item label="系统提示词（固定）">
          <a-textarea :value="systemPrompt" :rows="4" readonly class="system-prompt" />
        </a-form-item>

        <a-form-item label="平台筛选">
          <a-select
            v-model:value="filterPlatform"
            allow-clear
            placeholder="全部平台"
            style="width: 220px"
            @change="onFilterPlatformChange"
          >
            <a-select-option v-for="p in platformOptions" :key="p" :value="p">
              {{ platformLabel(p) }}
            </a-select-option>
          </a-select>
          <span class="hint" style="margin-left: 8px">需支持音频输入与音频输出</span>
        </a-form-item>

        <a-form-item label="模型" required>
          <a-select
            v-model:value="selectedModelId"
            show-search
            placeholder="选择模型"
            :loading="modelsLoading"
            :options="audioIoModelOptions"
            style="width: 100%; max-width: 520px"
            @change="onModelChange"
          />
        </a-form-item>

        <a-form-item v-if="showProviderSelect" label="调用平台" required>
          <a-radio-group v-model:value="selectedProviderPlatform">
            <a-radio v-for="p in providerPlatforms" :key="p" :value="p">
              {{ platformLabel(p) }}
            </a-radio>
          </a-radio-group>
          <p v-if="effectiveModelId" class="hint">将使用：{{ effectiveModelId }}</p>
        </a-form-item>

        <a-form-item label="输入来源">
          <a-radio-group v-model:value="inputSource">
            <a-radio value="builtin">内置数据集 (questionwav)</a-radio>
            <a-radio value="upload">上传音频</a-radio>
          </a-radio-group>
        </a-form-item>

        <template v-if="inputSource === 'builtin'">
          <a-form-item label="抽样方式">
            <a-radio-group v-model:value="sampleMode">
              <a-radio value="all">全量（最多 {{ health?.maxSamplesPerJob ?? 200 }}）</a-radio>
              <a-radio value="random">随机 N 条</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item v-if="sampleMode === 'random'" label="随机题数 N">
            <a-input-number
              v-model:value="sampleCount"
              :min="1"
              :max="health?.wavCount || health?.maxSamplesPerJob || 200"
              style="width: 160px"
            />
          </a-form-item>
          <a-form-item v-if="sampleMode === 'random'" label="随机种子（可选）">
            <a-input-number v-model:value="seed" style="width: 160px" />
          </a-form-item>
        </template>

        <template v-else>
          <a-form-item label="上传 wav">
            <a-upload-dragger
              :multiple="true"
              :file-list="uploadFileList"
              accept=".wav,audio/wav"
              :before-upload="onUploadBefore"
              @remove="onUploadRemove"
            >
              <p class="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p>拖拽或点击上传 .wav（已选 {{ uploadFiles.length }} 个）</p>
            </a-upload-dragger>
          </a-form-item>
        </template>

        <a-form-item label="请求间隔（秒）">
          <a-input-number
            v-model:value="requestInterval"
            :min="0"
            :max="30"
            :step="0.5"
            style="width: 120px"
          />
        </a-form-item>

        <a-button type="primary" :loading="jobLoading" :disabled="!canSubmit" @click="runJob">
          开始生成
        </a-button>
        <p v-if="!loginUserStore.loginUser?.id" class="hint">请先登录后再提交</p>
      </a-form>
    </a-card>

    <div v-if="jobId && jobStatus" ref="jobDetailRef" class="job-detail-section">
      <a-card v-if="showProgress" title="生成进度" class="page-section" size="small">
        <UniEvalTqdmBar
          :percent="jobStatus!.progress"
          :detail="jobStatus!.progressDetail"
          :job-status="jobStatus!.status"
        />
        <p class="hint">
          任务 ID: {{ jobId }} · {{ jobStatus!.totalSamples }} 条 · {{ jobStatus!.model }}
        </p>
        <p v-if="jobStatus!.error" class="error-text">{{ jobStatus!.error }}</p>
      </a-card>

      <a-card v-if="summary" title="汇总" class="page-section" size="small">
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic title="成功" :value="summary.success ?? 0" />
          </a-col>
          <a-col :span="8">
            <a-statistic title="失败" :value="summary.failed ?? 0" />
          </a-col>
          <a-col :span="8">
            <a-statistic title="总计" :value="summary.total ?? 0" />
          </a-col>
        </a-row>
      </a-card>

      <a-card v-if="resultRows.length" title="生成结果" class="page-section">
        <template #extra>
          <a-space>
            <a-button
              v-if="jobStatus?.status === 'completed' && jobId"
              size="small"
              @click="goToCombinedEval"
            >
              进入综合评测
            </a-button>
            <a-button size="small" @click="exportJson">导出 JSON</a-button>
            <a-button size="small" type="primary" @click="exportZip">下载 ZIP</a-button>
          </a-space>
        </template>
        <a-table
          :columns="resultColumns"
          :data-source="resultRows"
          :pagination="{ pageSize: 20 }"
          row-key="stem"
          size="small"
          :scroll="{ x: 900 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'text'">
              <span class="text-preview">{{ record.text || '—' }}</span>
            </template>
            <template v-else-if="column.dataIndex === 'audio'">
              <audio
                v-if="record.hasAudio && jobId"
                controls
                preload="none"
                :src="oralGenAudioUrl(jobId, record.stem)"
                class="audio-player"
              />
              <span v-else class="hint">—</span>
            </template>
            <template v-else-if="column.dataIndex === 'error'">
              <span v-if="record.error" class="error-text">{{ record.error }}</span>
              <a-tag v-else color="green">OK</a-tag>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import type { UploadProps } from 'ant-design-vue'
import { listModels, listPlatforms, type ModelVO } from '@/api/modelController'
import {
  createOralGenJobBuiltin,
  createOralGenJobUpload,
  downloadOralGenZip,
  getOralGenHealth,
  getOralGenJob,
  oralGenAudioUrl,
  type OralGenHealth,
  type OralGenJob,
  type OralGenResultRow,
} from '@/api/oralGenController'
import UniEvalTqdmBar from '@/components/UniEvalTqdmBar.vue'
import { useLoginUserStore } from '@/stores/loginUser'
import {
  defaultProviderPlatform,
  getModelPlatforms,
  modelSelectLabel,
  platformLabel,
  resolveModelId,
} from '@/utils/modelPlatform'

const emit = defineEmits<{ 'jobs-changed': [] }>()

const router = useRouter()
const loginUserStore = useLoginUserStore()

const health = ref<OralGenHealth | null>(null)
const healthLoading = ref(false)
const systemPrompt = ref('')

const filterPlatform = ref<string | undefined>()
const platformOptions = ref<string[]>(['openrouter', 'aihubmix'])
const models = ref<ModelVO[]>([])
const modelsLoading = ref(false)
const selectedModelId = ref<string | undefined>()
const selectedProviderPlatform = ref('openrouter')

const inputSource = ref<'builtin' | 'upload'>('builtin')
const sampleMode = ref<'all' | 'random'>('random')
const sampleCount = ref(2)
const seed = ref<number | undefined>()
const requestInterval = ref(1)
const uploadFiles = ref<File[]>([])
const uploadFileList = ref<UploadProps['fileList']>([])

const jobLoading = ref(false)
const jobId = ref<string | null>(null)
const jobStatus = ref<OralGenJob | null>(null)
const jobDetailRef = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const selectedModelRecord = computed(() =>
  models.value.find((m) => m.id === selectedModelId.value),
)

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

const audioIoModelOptions = computed(() =>
  models.value
    .filter((m) => {
      const ins = m.inputModalities || []
      const hasAudioIn =
        ins.some((x) => x.toLowerCase() === 'audio') ||
        (m.modality || '').toLowerCase().includes('audio')
      return hasAudioIn && modelHasAudioOutput(m)
    })
    .map((m) => ({ value: m.id, label: modelSelectLabel(m) })),
)

const canSubmit = computed(() => {
  if (!loginUserStore.loginUser?.id || !effectiveModelId.value) return false
  if (!health.value?.apiConfigured) return false
  if (inputSource.value === 'builtin') {
    return !!health.value?.questionwavDirOk && (health.value?.wavCount ?? 0) > 0
  }
  return uploadFiles.value.length > 0
})

const showProgress = computed(
  () =>
    jobStatus.value &&
    (jobStatus.value.status === 'running' ||
      jobStatus.value.status === 'pending' ||
      jobStatus.value.status === 'failed'),
)

const summary = computed(() => jobStatus.value?.summary)
const resultRows = computed(() => jobStatus.value?.rows || [])

const resultColumns = [
  { title: 'ID', dataIndex: 'stem', width: 90 },
  { title: '回复文本', dataIndex: 'text', ellipsis: true },
  { title: '生成音频', dataIndex: 'audio', width: 280 },
  { title: '状态', dataIndex: 'error', width: 200 },
]

function onUploadBefore(file: File) {
  uploadFiles.value = [...uploadFiles.value, file]
  uploadFileList.value = uploadFiles.value.map((f, i) => ({
    uid: `${i}-${f.name}`,
    name: f.name,
    status: 'done',
  }))
  return false
}

function onUploadRemove(file: { name?: string }) {
  uploadFiles.value = uploadFiles.value.filter((f) => f.name !== file.name)
  uploadFileList.value = uploadFiles.value.map((f, i) => ({
    uid: `${i}-${f.name}`,
    name: f.name,
    status: 'done',
  }))
}

async function loadHealth() {
  healthLoading.value = true
  try {
    health.value = await getOralGenHealth()
    systemPrompt.value = health.value.systemPrompt || ''
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '无法加载状态')
  } finally {
    healthLoading.value = false
  }
}

async function loadPlatforms() {
  try {
    const res = await listPlatforms()
    if (res.data.code === 0 && res.data.data?.length) {
      platformOptions.value = res.data.data
    }
  } catch {
    platformOptions.value = ['openrouter', 'aihubmix']
  }
}

async function loadModels() {
  modelsLoading.value = true
  try {
    const res = await listModels({
      inputModality: 'audio',
      platform: filterPlatform.value,
    })
    if (res.data.code === 0) models.value = res.data.data || []
    if (
      selectedModelId.value &&
      !audioIoModelOptions.value.some((o) => o.value === selectedModelId.value)
    ) {
      selectedModelId.value = undefined
    }
  } finally {
    modelsLoading.value = false
  }
}

function onFilterPlatformChange() {
  selectedModelId.value = undefined
  void loadModels()
}

function onModelChange() {
  selectedProviderPlatform.value = defaultProviderPlatform(
    selectedModelRecord.value,
    filterPlatform.value,
  )
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(id: string) {
  stopPolling()
  pollTimer = setInterval(() => void pollJob(id), 1000)
  void pollJob(id)
}

async function pollJob(id: string) {
  try {
    const job = await getOralGenJob(id)
    jobStatus.value = job
    if (job.status === 'completed' || job.status === 'failed') {
      stopPolling()
      emit('jobs-changed')
      if (job.status === 'completed') message.success('回复生成完成')
      else message.error(job.error || '任务失败')
    }
  } catch {
    stopPolling()
  }
}

async function scrollToJobDetail() {
  await nextTick()
  jobDetailRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function runJob() {
  if (!canSubmit.value || !effectiveModelId.value) return
  jobLoading.value = true
  jobStatus.value = null
  try {
    let id: string
    if (inputSource.value === 'builtin') {
      id = await createOralGenJobBuiltin({
        model: effectiveModelId.value,
        sampleMode: sampleMode.value,
        sampleCount: sampleMode.value === 'random' ? sampleCount.value : undefined,
        seed: seed.value,
        requestInterval: requestInterval.value,
      })
    } else {
      id = await createOralGenJobUpload(
        effectiveModelId.value,
        uploadFiles.value,
        requestInterval.value,
      )
    }
    jobId.value = id
    message.success('任务已创建')
    startPolling(id)
    await scrollToJobDetail()
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '创建任务失败')
  } finally {
    jobLoading.value = false
  }
}

async function loadJob(id: string) {
  stopPolling()
  jobId.value = id
  jobStatus.value = null
  try {
    const job = await getOralGenJob(id)
    jobStatus.value = job
    if (job.status === 'running' || job.status === 'pending') {
      startPolling(id)
    }
    await scrollToJobDetail()
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '加载任务失败')
  }
}

function exportJson() {
  const blob = new Blob([JSON.stringify(jobStatus.value, null, 2)], {
    type: 'application/json',
  })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `oral-gen-${jobId.value || Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function goToCombinedEval() {
  if (!jobId.value) return
  void router.push({
    path: '/oral-eval',
    query: { tab: 'combined', oralGenJob: jobId.value },
  })
}

async function exportZip() {
  if (!jobId.value) return
  try {
    const blob = await downloadOralGenZip(jobId.value)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `oral-gen-${jobId.value}.zip`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '导出失败')
  }
}

onMounted(() => {
  void loadHealth()
  void loadPlatforms()
  void loadModels()
})

onBeforeUnmount(() => {
  stopPolling()
})

defineExpose({ loadJob })
</script>

<style scoped>
.oral-gen-panel {
  margin-top: 0;
}

.hint {
  color: #888;
  font-size: 13px;
}

.error-text {
  color: #cf1322;
}

.system-prompt {
  background: #fafafa;
  color: #444;
}

.text-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.audio-player {
  width: 100%;
  max-width: 260px;
  height: 32px;
}
</style>
