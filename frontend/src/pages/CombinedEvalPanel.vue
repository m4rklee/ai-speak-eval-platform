<template>
  <div :class="embedded ? 'combined-eval-embedded' : 'combined-eval-page'">
    <a-card title="引擎状态" class="section" size="small">
      <a-space wrap>
        <a-tag :color="health?.pathsOk ? 'green' : 'red'">
          语音路径 {{ health?.pathsOk ? '正常' : '异常' }}
        </a-tag>
        <a-tag :color="engineReady ? 'green' : 'orange'">
          {{ engineStatusLabel }}
        </a-tag>
        <a-tag :color="health?.questionDirOk ? 'green' : 'red'">
          题库 {{ health?.questionDirOk ? '就绪' : '异常' }}
        </a-tag>
        <a-tag v-if="health?.questionCount" color="blue">{{ health.questionCount }} 题</a-tag>
        <span v-if="health?.judgeModel" class="hint">Judge: {{ health.judgeModel }}</span>
      </a-space>
      <a-alert
        v-if="showEngineHint"
        type="warning"
        show-icon
        style="margin-top: 12px"
        message="评测引擎未就绪"
        :description="engineHintText"
      />
      <a-button size="small" style="margin-top: 8px" :loading="healthLoading" @click="loadHealth">
        刷新状态
      </a-button>
    </a-card>

    <a-card class="section">
      <a-tabs v-model:activeKey="batchMode" size="small">
        <a-tab-pane key="multi" tab="多文件">
          <a-space wrap class="upload-actions">
            <a-upload
              :multiple="true"
              :file-list="multiWavFileList"
              accept=".wav,audio/wav"
              :before-upload="onMultiWavBeforeUpload"
              @remove="onMultiWavRemove"
            >
              <a-button>
                <SoundOutlined />
                选择音频 (.wav)
              </a-button>
            </a-upload>
            <a-upload
              :multiple="true"
              :file-list="multiTxtFileList"
              accept=".txt,text/plain"
              :before-upload="onMultiTxtBeforeUpload"
              @remove="onMultiTxtRemove"
            >
              <a-button>
                <FileTextOutlined />
                选择文本 (.txt)
              </a-button>
            </a-upload>
          </a-space>
          <p v-if="multiWavFiles.length || multiTxtFiles.length" class="hint">
            已选 {{ multiWavFiles.length }} 个 wav、{{ multiTxtFiles.length }} 个 txt
          </p>
          <p class="hint">
            wav 与 txt 的文件名 stem 须完全一致（如 00174.wav 与 00174.txt）；内容评测仍按 txt 的 stem 匹配内置题库
          </p>
        </a-tab-pane>
        <a-tab-pane key="dir" tab="目录 / ZIP">
          <a-space direction="vertical" style="width: 100%">
            <div>
              <input
                ref="dirInputRef"
                type="file"
                webkitdirectory
                directory
                multiple
                style="display: none"
                @change="onDirChange"
              />
              <a-button @click="pickDirectory">
                <FolderOpenOutlined />
                选择文件夹（含 wav 与 txt）
              </a-button>
              <span v-if="allFiles.length" class="hint">已选 {{ allFiles.length }} 个文件</span>
            </div>
            <a-upload
              :multiple="false"
              :show-upload-list="!!zipFile"
              accept=".zip"
              :before-upload="onZipBeforeUpload"
              @remove="zipFile = null"
            >
              <a-button>
                <FileZipOutlined />
                或上传 zip 包
              </a-button>
            </a-upload>
          </a-space>
        </a-tab-pane>
      </a-tabs>

      <a-table
        v-if="pairPreview.length"
        class="pair-table"
        size="small"
        :pagination="false"
        :data-source="pairPreview"
        :columns="pairColumns"
        row-key="stem"
      />

      <a-button
        type="primary"
        class="action-btn"
        :loading="jobLoading"
        :disabled="!canSubmit"
        @click="runBatch"
      >
        提交综合评测（{{ pairedCount }} 组）
      </a-button>
      <p v-if="!loginUserStore.loginUser?.id" class="hint">请先登录后再提交评测</p>
    </a-card>

    <a-card v-if="jobId" id="combined-job-detail" title="任务进度" class="section" size="small">
      <a-space direction="vertical" style="width: 100%">
        <a-space>
          <span class="job-id-text">{{ jobId }}</span>
          <a-tag :color="statusColor(jobStatus?.status || '')">
            {{ statusLabel(jobStatus?.status || '') }}
          </a-tag>
          <span v-if="jobStatus">{{ jobStatus.progress }}%</span>
        </a-space>
        <UniEvalTqdmBar
          v-if="jobStatus"
          :percent="jobStatus.progress"
          :detail="jobStatus.progressDetail"
          :job-status="jobStatus.status"
        />
        <a-alert v-if="jobStatus?.error" type="error" :message="jobStatus.error" show-icon />
      </a-space>
    </a-card>

    <a-card
      v-if="tableRows.length"
      title="评测结果"
      class="section"
      size="small"
    >
      <template #extra>
        <a-space>
          <a-button size="small" @click="exportJson">导出 JSON</a-button>
          <a-button size="small" @click="exportCsv">导出 CSV</a-button>
        </a-space>
      </template>
      <a-descriptions v-if="jobStatus?.summary" size="small" :column="4" bordered class="summary-desc">
        <a-descriptions-item label="成对样本">{{ jobStatus.summary.pairCount }}</a-descriptions-item>
        <a-descriptions-item label="完全成功">{{ jobStatus.summary.okCount }}</a-descriptions-item>
        <a-descriptions-item label="部分成功">{{ jobStatus.summary.partialCount }}</a-descriptions-item>
        <a-descriptions-item label="发音均值">
          {{ formatScore(jobStatus.summary.accuracyMean) }}
        </a-descriptions-item>
        <a-descriptions-item label="流利度均值">
          {{ formatScore(jobStatus.summary.fluencyMean) }}
        </a-descriptions-item>
        <a-descriptions-item label="内容综合均值">
          {{ formatScore(jobStatus.summary.compositeMean) }}
        </a-descriptions-item>
      </a-descriptions>
      <a-table
        size="small"
        :scroll="{ x: 1400 }"
        :data-source="tableRows"
        :columns="resultColumns"
        row-key="stem"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="rowStatusColor(record.status)">{{ rowStatusLabel(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'play'">
            <a-button
              v-if="jobStatus?.audioAvailable"
              type="link"
              size="small"
              @click="playAudio(record.wavName)"
            >
              播放
            </a-button>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'
import {
  FileTextOutlined,
  FileZipOutlined,
  FolderOpenOutlined,
  SoundOutlined,
} from '@ant-design/icons-vue'
import { useLoginUserStore } from '@/stores/loginUser'
import { getContentEvalHealth } from '@/api/contentEvalController'
import {
  createOralCombinedJob,
  getOralCombinedAudioUrl,
  getOralCombinedHealth,
  getOralCombinedJob,
  type OralCombinedHealth,
  type OralCombinedJob,
  type OralCombinedPerFile,
} from '@/api/oralCombinedEvalController'
import { getUnifiedEvalHealth } from '@/api/unifiedEvalController'
import UniEvalTqdmBar from '@/components/UniEvalTqdmBar.vue'

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ (e: 'jobs-changed'): void }>()

const loginUserStore = useLoginUserStore()

const health = ref<OralCombinedHealth | null>(null)
const healthLoading = ref(false)
const batchMode = ref<'multi' | 'dir'>('multi')
const multiWavFiles = ref<File[]>([])
const multiTxtFiles = ref<File[]>([])
const multiWavFileList = ref<UploadProps['fileList']>([])
const multiTxtFileList = ref<UploadProps['fileList']>([])
const dirFiles = ref<File[]>([])
const zipFile = ref<File | null>(null)
const dirInputRef = ref<HTMLInputElement | null>(null)
const jobLoading = ref(false)
const jobId = ref('')
const jobStatus = ref<OralCombinedJob | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null
let audioEl: HTMLAudioElement | null = null

type PairRow = {
  stem: string
  wavName?: string
  txtName?: string
  paired: boolean
}

const allFiles = computed(() => {
  if (batchMode.value === 'multi') return [...multiWavFiles.value, ...multiTxtFiles.value]
  return dirFiles.value
})

const pairPreview = computed<PairRow[]>(() => buildPairs(allFiles.value))

const pairedCount = computed(() => pairPreview.value.filter((p) => p.paired).length)

const canSubmit = computed(() => {
  const hasInput =
    batchMode.value === 'dir'
      ? allFiles.value.length > 0 || !!zipFile.value
      : multiWavFiles.value.length > 0 || multiTxtFiles.value.length > 0
  return (
    !!loginUserStore.loginUser?.id &&
    engineReady.value &&
    pairedCount.value > 0 &&
    pairPreview.value.every((p) => p.paired) &&
    hasInput
  )
})

const engineReady = computed(
  () =>
    !!health.value?.pathsOk &&
    !!health.value?.daemonReady &&
    !!health.value?.questionDirOk,
)

const engineStatusLabel = computed(() => {
  if (!health.value?.pathsOk) return '路径异常'
  if (!health.value?.daemonReady) return 'Daemon 未就绪'
  if (!health.value?.questionDirOk) return '题库异常'
  return '就绪'
})

const showEngineHint = computed(
  () => !!health.value && (!health.value.pathsOk || !health.value.daemonReady || !health.value.questionDirOk),
)

const engineHintText = computed(() => {
  const parts: string[] = []
  if (health.value && !health.value.daemonReady) {
    parts.push('请在服务器执行：bash scripts/eval-daemons.sh restart')
  }
  if (health.value && !health.value.questionDirOk) {
    parts.push(health.value.questionDirMessage || '内容题库未就绪')
  }
  if (health.value && !health.value.pathsOk) {
    parts.push(health.value.pathsMessage)
  }
  return parts.join('；') || '请刷新状态'
})

const tableRows = computed(() => jobStatus.value?.perFile || [])

const pairColumns = [
  { title: 'Stem', dataIndex: 'stem', width: 160 },
  { title: 'WAV', dataIndex: 'wavName', ellipsis: true },
  { title: 'TXT', dataIndex: 'txtName', ellipsis: true },
  {
    title: '配对',
    key: 'paired',
    width: 80,
    customRender: ({ record }: { record: PairRow }) =>
      record.paired ? '✓' : '✗',
  },
]

const resultColumns = [
  { title: 'Stem', dataIndex: 'stem', width: 120, fixed: 'left' as const },
  { title: '状态', key: 'status', width: 88 },
  { title: '发音', dataIndex: ['speech', 'accuracy'], width: 72 },
  { title: '流利', dataIndex: ['speech', 'fluency'], width: 72 },
  { title: '自然度', dataIndex: ['speech', 'naturalness'], width: 80 },
  { title: 'BVCC', dataIndex: ['speech', 'apgMos', 'bvcc'], width: 72 },
  { title: '语法', dataIndex: ['content', 'grammarScore'], width: 72 },
  { title: '主题', dataIndex: ['content', 'themeFocusScore'], width: 72 },
  { title: '简洁', dataIndex: ['content', 'answerClarityScore'], width: 72 },
  { title: '内容综合', dataIndex: ['content', 'compositeScore'], width: 88 },
  { title: '播放', key: 'play', width: 72, fixed: 'right' as const },
]

function buildPairs(files: File[]): PairRow[] {
  const wavMap = new Map<string, string>()
  const txtMap = new Map<string, string>()
  for (const f of files) {
    const lower = f.name.toLowerCase()
    const stem = f.name.replace(/\.[^.]+$/, '')
    if (lower.endsWith('.wav')) wavMap.set(stem, f.name)
    else if (lower.endsWith('.txt')) txtMap.set(stem, f.name)
  }
  const stems = new Set([...wavMap.keys(), ...txtMap.keys()])
  return [...stems].sort().map((stem) => ({
    stem,
    wavName: wavMap.get(stem),
    txtName: txtMap.get(stem),
    paired: wavMap.has(stem) && txtMap.has(stem),
  }))
}

function formatScore(v?: number | null) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(2)
}

function statusColor(status: string) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'processing'
  return 'default'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    completed: '完成',
    failed: '失败',
    running: '进行中',
    pending: '排队',
  }
  return map[status] || status
}

function rowStatusColor(status: string) {
  if (status === 'ok') return 'green'
  if (status === 'partial') return 'orange'
  return 'red'
}

function rowStatusLabel(status: string) {
  const map: Record<string, string> = {
    ok: '成功',
    partial: '部分',
    error: '失败',
  }
  return map[status] || status
}

async function loadHealthFromLegacyApis(): Promise<OralCombinedHealth> {
  const [uni, content] = await Promise.all([getUnifiedEvalHealth(), getContentEvalHealth()])
  const pathsMsg = uni.pathsMessage || ''
  const daemonMsg =
    uni.pathsOk && !uni.daemonReady
      ? `${pathsMsg ? pathsMsg + '; ' : ''}评测 daemon 未就绪，请执行 bash scripts/eval-daemons.sh restart`
      : pathsMsg
  return {
    pathsOk: uni.pathsOk,
    pathsMessage: daemonMsg,
    daemonRunning: uni.daemonRunning,
    daemonReady: uni.daemonReady,
    questionDirOk: content.questionDirOk,
    questionDirMessage: content.questionDirMessage,
    questionCount: content.questionCount,
    judgeModel: content.judgeModel,
    maxFilesPerJob: content.maxFilesPerJob,
    engine: uni.engine || 'daemon',
  }
}

async function loadHealth() {
  healthLoading.value = true
  try {
    health.value = await getOralCombinedHealth()
  } catch {
    try {
      health.value = await loadHealthFromLegacyApis()
    } catch {
      message.error('无法获取引擎状态')
    }
  } finally {
    healthLoading.value = false
  }
}

function appendMultiFile(
  f: File,
  filesRef: typeof multiWavFiles,
  listRef: typeof multiWavFileList,
) {
  filesRef.value.push(f)
  listRef.value = [
    ...(listRef.value || []),
    { uid: `${Date.now()}-${f.name}`, name: f.name, status: 'done' },
  ]
}

function removeMultiFile(
  name: string,
  filesRef: typeof multiWavFiles,
  listRef: typeof multiWavFileList,
) {
  filesRef.value = filesRef.value.filter((f) => f.name !== name)
  listRef.value = (listRef.value || []).filter((f) => f.name !== name)
}

const onMultiWavBeforeUpload: UploadProps['beforeUpload'] = (file) => {
  const f = file as File
  if (!f.name.toLowerCase().endsWith('.wav')) {
    message.warning('请选择 .wav 音频文件')
    return false
  }
  appendMultiFile(f, multiWavFiles, multiWavFileList)
  return false
}

const onMultiWavRemove: UploadProps['onRemove'] = (file) => {
  removeMultiFile(file.name, multiWavFiles, multiWavFileList)
}

const onMultiTxtBeforeUpload: UploadProps['beforeUpload'] = (file) => {
  const f = file as File
  if (!f.name.toLowerCase().endsWith('.txt')) {
    message.warning('请选择 .txt 文本文件')
    return false
  }
  appendMultiFile(f, multiTxtFiles, multiTxtFileList)
  return false
}

const onMultiTxtRemove: UploadProps['onRemove'] = (file) => {
  removeMultiFile(file.name, multiTxtFiles, multiTxtFileList)
}

function pickDirectory() {
  dirInputRef.value?.click()
}

function onDirChange(e: Event) {
  const input = e.target as HTMLInputElement
  const list = input.files
  if (!list) return
  dirFiles.value = Array.from(list).filter((f) => {
    const l = f.name.toLowerCase()
    return l.endsWith('.wav') || l.endsWith('.txt')
  })
  message.info(`已选择 ${dirFiles.value.length} 个文件`)
  input.value = ''
}

const onZipBeforeUpload: UploadProps['beforeUpload'] = (file) => {
  zipFile.value = file as File
  return false
}

function requireLogin(): boolean {
  if (!loginUserStore.loginUser?.id) {
    message.warning('请先登录后再提交评测')
    return false
  }
  return true
}

async function runBatch() {
  if (!requireLogin() || !engineReady.value) {
    if (!engineReady.value) message.warning('评测引擎未就绪')
    return
  }
  if (!canSubmit.value) {
    message.warning('请确保每组 wav/txt 均已配对')
    return
  }

  const files =
    batchMode.value === 'multi'
      ? [...multiWavFiles.value, ...multiTxtFiles.value]
      : dirFiles.value
  const archive = batchMode.value === 'dir' ? zipFile.value : null
  if (!files.length && !archive) {
    message.warning('请选择文件或 zip')
    return
  }

  jobLoading.value = true
  jobStatus.value = null
  try {
    const id = await createOralCombinedJob(files, archive ?? undefined)
    jobId.value = id
    message.success('综合评测任务已创建')
    startPolling(id)
    emit('jobs-changed')
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '创建任务失败')
  } finally {
    jobLoading.value = false
  }
}

function startPolling(id: string) {
  stopPolling()
  pollTimer = setInterval(() => void pollJob(id), 1000)
  void pollJob(id)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollJob(id: string) {
  try {
    const job = await getOralCombinedJob(id)
    jobStatus.value = job
    if (job.status === 'completed' || job.status === 'failed') {
      stopPolling()
      emit('jobs-changed')
      if (job.status === 'completed') message.success('综合评测完成')
      else message.error(job.error || '任务失败')
    }
  } catch {
    stopPolling()
  }
}

async function loadJob(id: string) {
  if (!requireLogin()) return
  jobId.value = id
  jobStatus.value = null
  try {
    const job = await getOralCombinedJob(id)
    jobStatus.value = job
    if (job.status === 'running' || job.status === 'pending') {
      startPolling(id)
    }
    document.getElementById('combined-job-detail')?.scrollIntoView({ behavior: 'smooth' })
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '加载失败')
  }
}

async function playAudio(wavName: string) {
  if (!jobId.value) return
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
  const url = getOralCombinedAudioUrl(jobId.value, wavName)
  try {
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    audioEl = new Audio(blobUrl)
    audioEl.onended = () => URL.revokeObjectURL(blobUrl)
    await audioEl.play()
  } catch {
    message.error('无法播放音频')
  }
}

function exportPayload() {
  return { job: jobStatus.value, exportedAt: new Date().toISOString() }
}

function exportJson() {
  const blob = new Blob([JSON.stringify(exportPayload(), null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `oral-combined-${jobId.value || Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function rowsToCsv(rows: OralCombinedPerFile[]) {
  const headers = [
    'stem',
    'wavName',
    'txtName',
    'status',
    'accuracy',
    'fluency',
    'naturalness',
    'apgBvcc',
    'apgSomos',
    'grammarScore',
    'themeFocusScore',
    'answerClarityScore',
    'compositeScore',
  ]
  const lines = [headers.join(',')]
  for (const r of rows) {
    lines.push(
      [
        r.stem,
        r.wavName,
        r.txtName,
        r.status,
        r.speech?.accuracy ?? '',
        r.speech?.fluency ?? '',
        r.speech?.naturalness ?? '',
        r.speech?.apgMos?.bvcc ?? '',
        r.speech?.apgMos?.somos ?? '',
        r.content?.grammarScore ?? '',
        r.content?.themeFocusScore ?? '',
        r.content?.answerClarityScore ?? '',
        r.content?.compositeScore ?? '',
      ].join(','),
    )
  }
  return lines.join('\n')
}

function exportCsv() {
  const blob = new Blob([rowsToCsv(tableRows.value)], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `oral-combined-${jobId.value || Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

defineExpose({ loadJob })

onMounted(() => {
  void loadHealth()
})

onUnmounted(() => {
  stopPolling()
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
})
</script>

<style scoped>
.combined-eval-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.combined-eval-embedded {
  max-width: 100%;
  padding: 0;
}

.section {
  margin-bottom: 16px;
}

.hint {
  color: #888;
  font-size: 12px;
  margin-top: 8px;
}

.action-btn {
  margin-top: 16px;
}

.upload-actions {
  margin-bottom: 4px;
}

.pair-table {
  margin-top: 16px;
}

.job-id-text {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.summary-desc {
  margin-bottom: 12px;
}
</style>
