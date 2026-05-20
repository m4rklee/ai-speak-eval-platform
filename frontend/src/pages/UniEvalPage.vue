<template>
  <div :class="embedded ? 'uni-eval-embedded' : 'uni-eval-page'">
    <div v-if="!embedded" class="page-header">
      <h1>Uni 统一语音评测</h1>
      <p class="subtitle">MultiPA（发音准确性 / 流利度 / 韵律）+ APG-MOS（BVCC / SOMOS），不调用大模型</p>
    </div>

    <a-card title="引擎状态" class="section" size="small">
      <a-space wrap>
        <a-tag :color="health?.pathsOk ? 'green' : 'red'">
          路径 {{ health?.pathsOk ? '正常' : '异常' }}
        </a-tag>
        <a-tag :color="engineReady ? 'green' : 'orange'">
          {{ engineStatusLabel }}
        </a-tag>
        <a-tag v-if="health?.daemonReady" color="green">Daemon 就绪</a-tag>
        <a-tag v-else-if="health?.daemonRunning" color="orange">Daemon 加载中</a-tag>
        <a-tag v-else-if="health" color="red">Daemon 未就绪</a-tag>
        <span v-if="health?.pathsMessage && health.pathsOk" class="hint">{{ health.pathsMessage }}</span>
      </a-space>
      <a-alert
        v-if="showDaemonGateHint"
        type="warning"
        show-icon
        style="margin-top: 12px"
        message="评测引擎未就绪"
        description="MultiPA / APG-MOS 常驻服务未启动或仍在加载模型。请在服务器执行：bash scripts/eval-daemons.sh restart，完成后点击「刷新状态」。"
      />
      <a-button size="small" style="margin-top: 8px" :loading="healthLoading" @click="loadHealth">
        刷新状态
      </a-button>
    </a-card>

    <a-card class="section">
      <a-form layout="inline" class="batch-meta-form">
        <a-form-item label="任务名称（可选）">
          <a-input v-model:value="displayName" placeholder="留空则自动生成" :maxlength="64" style="width: 200px" />
        </a-form-item>
        <a-form-item label="评测轮次">
          <a-input-number v-model:value="evalRounds" :min="1" :max="5" style="width: 80px" />
        </a-form-item>
      </a-form>
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="single" tab="单文件">
          <a-upload-dragger
            :multiple="false"
            :show-upload-list="false"
            accept=".wav,audio/wav"
            :before-upload="onSingleBeforeUpload"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p>拖拽或点击上传单个 .wav</p>
          </a-upload-dragger>
          <a-button
            type="primary"
            class="action-btn"
            :loading="singleLoading"
            :disabled="!singleFile || !engineReady"
            @click="runSingle"
          >
            开始评测
          </a-button>
          <p v-if="singleFile" class="hint">已选：{{ singleFile.name }}</p>
        </a-tab-pane>

        <a-tab-pane key="multi" tab="多文件">
          <a-upload
            :multiple="true"
            :file-list="multiFileList"
            :accept="batchUpload.acceptMime"
            :before-upload="batchUpload.onMultiBeforeUpload"
            @remove="batchUpload.onMultiRemove"
          >
            <a-button>
              <UploadOutlined />
              选择多个 wav
            </a-button>
          </a-upload>
          <a-button
            type="primary"
            class="action-btn"
            :loading="jobLoading"
            :disabled="!batchUpload.batchReady('multi') || !engineReady"
            @click="runBatch('multi')"
          >
            提交批量任务（{{ multiFiles.length }} 个文件）
          </a-button>
        </a-tab-pane>

        <a-tab-pane key="dir" tab="目录 / ZIP">
          <a-space direction="vertical" style="width: 100%">
            <div>
              <input
                :ref="(el) => { dirInputRef = el as HTMLInputElement | null }"
                type="file"
                webkitdirectory
                directory
                multiple
                :accept="batchUpload.acceptMime"
                style="display: none"
                @change="batchUpload.onDirChange"
              />
              <a-button @click="batchUpload.pickDirectory">
                <FolderOpenOutlined />
                选择文件夹（含 wav）
              </a-button>
              <span v-if="dirFiles.length" class="hint">{{ dirSelectionHint }}</span>
            </div>
            <a-upload
              :multiple="false"
              :show-upload-list="!!zipFile"
              accept=".zip"
              :before-upload="batchUpload.onZipBeforeUpload"
              @remove="zipFile = null"
            >
              <a-button>
                <FileZipOutlined />
                或上传 zip 包
              </a-button>
            </a-upload>
            <a-button
              type="primary"
              :loading="jobLoading"
              :disabled="!batchUpload.batchReady('dir') || !engineReady"
              @click="runBatch('dir')"
            >
              提交任务
            </a-button>
          </a-space>
        </a-tab-pane>

        <a-tab-pane key="multiModel" tab="多模型对比">
          <EvalMultiModelSlots
            accept-ext="wav"
            file-label="wav"
            :max-models="maxModelsPerJob"
            :loading="multiModelLoading"
            :submit-disabled="!engineReady"
            :show-login-hint="!loginUserStore.loginUser?.id"
            @submit="runMultiModelBatch"
          />
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <JobInterruptedBanner
      v-if="jobId && jobStatus"
      :job="jobStatus"
      :loading="resumeLoading"
      @resume="handleResume"
    />
    <JobApiErrorAlert v-if="jobId && jobStatus" :job="jobStatus" />
    <JobDisplayNameEdit
      v-if="jobId && jobStatus"
      :job-id="jobId"
      :display-name="jobStatus.displayName"
      :on-save="saveJobDisplayName"
      @saved="onDisplayNameSaved"
    />
    <a-card v-if="showProgress" title="评测进度" class="section" size="small">
      <template #extra>
        <JobProgressActions
          :job="jobStatus"
          :pause-loading="pauseLoading"
          :resume-loading="resumeLoading"
          :rerun-loading="rerunLoading"
          @pause="handlePause"
          @resume="handleResume"
          @rerun="handleRerun"
        />
      </template>
      <UniEvalTqdmBar
        :percent="jobStatus!.progress"
        :detail="jobStatus!.progressDetail"
        :job-status="jobStatus!.status"
      />
      <p class="hint">
        任务 ID: {{ jobId }}
        <span v-if="isMultiModelJob"> · {{ jobStatus!.modelCount }} 模型</span>
        · {{ jobStatus!.totalFiles }} 个文件
        <span v-if="jobStatus!.evalRounds && jobStatus!.evalRounds > 1">
          · 轮次 {{ jobStatus!.evalRounds }}
        </span>
      </p>
      <JobTokenSummary :job="jobStatus" />
      <p v-if="jobStatus!.error" class="error-text">{{ jobStatus!.error }}</p>
    </a-card>

    <a-card v-if="compareRows.length" title="模型对比汇总" class="section" size="small">
      <JobTokenSummary :job="jobStatus" />
      <a-space style="margin-bottom: 12px">
        <a-button size="small" @click="exportJson">导出 JSON</a-button>
        <a-button size="small" @click="exportCsv">导出 CSV</a-button>
      </a-space>
      <a-table
        :columns="compareColumns"
        :data-source="compareRows"
        :pagination="false"
        row-key="modelName"
        size="small"
        :scroll="{ x: 900 }"
      />
    </a-card>

    <a-card v-if="displaySummary && !isMultiModelJob" title="汇总" class="section" size="small">
      <a-descriptions bordered size="small" :column="3">
        <a-descriptions-item label="文件数">{{ displaySummary.fileCount ?? '—' }}</a-descriptions-item>
        <a-descriptions-item
          v-for="(val, key) in displaySummary.multipa || {}"
          :key="String(key)"
          :label="String(key)"
        >
          {{ formatScore(val) }}
        </a-descriptions-item>
        <a-descriptions-item label="BVCC 均值">
          {{ formatScore(displaySummary.apgMosBvccMean) }}
        </a-descriptions-item>
        <a-descriptions-item label="SOMOS 均值">
          {{ formatScore(displaySummary.apgMosSomosMean) }}
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <a-card v-if="tableRows.length" :title="isMultiModelJob ? '逐文件明细' : '评测结果'" class="section">
      <a-space v-if="!isMultiModelJob" style="margin-bottom: 12px">
        <a-button size="small" @click="exportJson">导出 JSON</a-button>
        <a-button size="small" @click="exportCsv">导出 CSV</a-button>
      </a-space>
      <a-space v-if="isMultiModelJob && modelFilterOptions.length" style="margin-bottom: 12px">
        <span>筛选模型：</span>
        <a-select
          v-model:value="detailModelFilter"
          style="width: 220px"
          :options="modelFilterOptions"
          allow-clear
          placeholder="全部模型"
        />
      </a-space>
      <a-table
        :columns="detailColumns"
        :data-source="filteredTableRows"
        :pagination="{ pageSize: 20 }"
        :row-key="detailRowKey"
        size="small"
        :scroll="{ x: 1200 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'wavname'">
            <a-space :size="4">
              <a-button
                type="text"
                size="small"
                class="play-btn"
                :class="{ playing: playingKey === playKey(record) }"
                :disabled="!canPlayAudio"
                :title="canPlayAudio ? '播放音频' : '该任务无音频缓存，请重新评测'"
                @click="playJobAudio(record.wavname, record.modelName)"
              >
                <SoundOutlined />
              </a-button>
              <span class="wav-name">{{ record.wavname }}</span>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card v-if="!embedded && recentJobs.length" title="最近任务" class="section" size="small">
      <a-list size="small" :data-source="recentJobs">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta
              :title="formatJobId(item.jobId)"
              :description="formatJobDescription(item)"
            />
            <template #actions>
              <a @click="loadJob(item.jobId)">查看</a>
            </template>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'
import {
  FileZipOutlined,
  FolderOpenOutlined,
  InboxOutlined,
  SoundOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'
import { useLoginUserStore } from '@/stores/loginUser'
import {
  createMultiModelEvalJob,
  createUnifiedEvalJob,
  getJobAudioUrl,
  getUnifiedEvalHealth,
  getUnifiedEvalJob,
  pauseUnifiedEvalJob,
  rerunUnifiedEvalJob,
  resumeUnifiedEvalJob,
  updateUnifiedEvalJobDisplayName,
  listUnifiedEvalJobs,
  type ModelEvalSlot,
  type UnifiedEvalHealth,
  type UnifiedEvalJob,
} from '@/api/unifiedEvalController'
import EvalMultiModelSlots from '@/components/eval/EvalMultiModelSlots.vue'
import UniEvalTqdmBar from '@/components/UniEvalTqdmBar.vue'
import JobInterruptedBanner from '@/components/eval/JobInterruptedBanner.vue'
import JobApiErrorAlert from '@/components/eval/JobApiErrorAlert.vue'
import JobTokenSummary from '@/components/eval/JobTokenSummary.vue'
import JobDisplayNameEdit from '@/components/eval/JobDisplayNameEdit.vue'
import JobProgressActions from '@/components/eval/JobProgressActions.vue'
import { useEvalJobPoll } from '@/composables/useEvalJobPoll'
import { useEvalJobControls } from '@/composables/useEvalJobControls'
import { useEvalBatchUpload } from '@/composables/useEvalBatchUpload'

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ (e: 'jobs-changed'): void }>()

const loginUserStore = useLoginUserStore()

const health = ref<UnifiedEvalHealth | null>(null)
const healthLoading = ref(false)
const activeTab = ref('single')
const singleFile = ref<File | null>(null)
const singleLoading = ref(false)
const batchUpload = useEvalBatchUpload('wav')
const { multiFileList, dirInputRef, multiFiles, dirFiles, zipFile, dirSelectionHint } = batchUpload
const jobLoading = ref(false)
const multiModelLoading = ref(false)
const maxModelsPerJob = 10
const detailModelFilter = ref<string | undefined>(undefined)
const jobId = ref('')
const jobStatus = ref<UnifiedEvalJob | null>(null)
const recentJobs = ref<UnifiedEvalJob[]>([])
const displayName = ref('')
const evalRounds = ref(1)
const playingKey = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null
let audioEl: HTMLAudioElement | null = null

const createMeta = computed(() => ({
  displayName: displayName.value.trim() || undefined,
  evalRounds: evalRounds.value,
}))

const { handlePollTerminal, handlePollCatch } = useEvalJobPoll({
  completedMessage: '批量评测完成',
  onRefreshRecent: () => afterJobCreated(),
})

const canPlayAudio = computed(
  () => !!jobId.value && (jobStatus.value?.audioAvailable ?? jobStatus.value?.status === 'completed'),
)

const engineReady = computed(
  () =>
    !!health.value?.pathsOk &&
    !!health.value?.unifiedEvalEnabled &&
    !!health.value?.daemonReady,
)

const showDaemonGateHint = computed(
  () =>
    !!health.value?.pathsOk &&
    !!health.value?.unifiedEvalEnabled &&
    !health.value?.daemonReady,
)

const engineStatusLabel = computed(() => {
  if (!health.value) return '检测中…'
  if (!health.value.unifiedEvalEnabled) return '未启用'
  if (!health.value.pathsOk) return '路径异常'
  if (!health.value.daemonReady) {
    return health.value.daemonRunning ? '等待 Daemon' : 'Daemon 未就绪'
  }
  return '可提交评测'
})

const showProgress = computed(
  () =>
    jobId.value &&
    jobStatus.value &&
    ['pending', 'running', 'paused', 'interrupted', 'completed', 'failed'].includes(jobStatus.value.status),
)

const displaySummary = computed(() => jobStatus.value?.summary ?? null)

const isMultiModelJob = computed(
  () =>
    jobStatus.value?.jobType === 'multi_model' ||
    (jobStatus.value?.models?.length ?? 0) > 0,
)

const compareRows = computed(() => jobStatus.value?.comparison?.byModel ?? [])

const compareColumns = [
  { title: '模型', dataIndex: 'modelName', width: 180, ellipsis: true },
  { title: '文件数', dataIndex: 'fileCount', width: 80 },
  { title: '发音准确性', dataIndex: 'accuracyMean', width: 100, customRender: ({ text }: { text: number }) => formatScore(text) },
  { title: '流利度', dataIndex: 'fluencyMean', width: 80, customRender: ({ text }: { text: number }) => formatScore(text) },
  { title: '韵律', dataIndex: 'naturalnessMean', width: 80, customRender: ({ text }: { text: number }) => formatScore(text) },
  { title: 'BVCC', dataIndex: 'apgMosBvccMean', width: 80, customRender: ({ text }: { text: number }) => formatScore(text) },
  { title: 'SOMOS', dataIndex: 'apgMosSomosMean', width: 80, customRender: ({ text }: { text: number }) => formatScore(text) },
]

function mapPerFileRow(raw: Record<string, unknown>, modelName?: string) {
  const rawInner = raw.raw as Record<string, unknown> | undefined
  const multipa = (raw.multipa || rawInner?.multipa) as Record<string, unknown> | undefined
  const apgMos = (raw.apgMos || raw.apg_mos || rawInner?.apg_mos) as
    | Record<string, number>
    | undefined
  return {
    wavname: String(raw.wavname ?? ''),
    modelName: modelName ?? (raw.modelName as string | undefined),
    status: String(raw.status ?? 'ok'),
    accuracy: numOr(raw.accuracy, multipa?.['发音准确性'], multipa?.accuracy),
    fluency: numOr(raw.fluency, multipa?.['流利度'], multipa?.fluency),
    naturalness: numOr(raw.naturalness, multipa?.['韵律'], multipa?.prosody),
    bvcc: numOr(raw.bvcc, apgMos?.bvcc),
    somos: numOr(raw.somos, apgMos?.somos),
    transcriptS: String(raw.transcriptS ?? multipa?.transcript_S ?? ''),
    reason: raw.reason as string | undefined,
  }
}

const tableRows = computed(() => {
  if (isMultiModelJob.value && jobStatus.value?.models?.length) {
    const rows: ReturnType<typeof mapPerFileRow>[] = []
    for (const model of jobStatus.value.models) {
      for (const row of model.perFile || []) {
        rows.push(mapPerFileRow(row as Record<string, unknown>, model.modelName))
      }
    }
    return rows
  }
  if (!jobStatus.value?.perFile?.length) return []
  return jobStatus.value.perFile.map((row) => mapPerFileRow(row as Record<string, unknown>))
})

const modelFilterOptions = computed(() => {
  const names = new Set<string>()
  for (const row of tableRows.value) {
    if (row.modelName) names.add(row.modelName)
  }
  return Array.from(names).map((n) => ({ label: n, value: n }))
})

const filteredTableRows = computed(() => {
  if (!detailModelFilter.value) return tableRows.value
  return tableRows.value.filter((r) => r.modelName === detailModelFilter.value)
})

const detailColumns = computed(() => {
  type ColDef = { title: string; dataIndex: string; width?: number; ellipsis?: boolean }
  const cols: ColDef[] = [
    { title: '文件名', dataIndex: 'wavname', width: 200, ellipsis: true },
  ]
  if (isMultiModelJob.value) {
    cols.push({ title: '模型', dataIndex: 'modelName', width: 140, ellipsis: true })
  }
  cols.push(
    { title: '发音准确性', dataIndex: 'accuracy', width: 100 },
    { title: '流利度', dataIndex: 'fluency', width: 80 },
    { title: '韵律', dataIndex: 'naturalness', width: 80 },
    { title: 'BVCC', dataIndex: 'bvcc', width: 80 },
    { title: 'SOMOS', dataIndex: 'somos', width: 80 },
    { title: '转写', dataIndex: 'transcriptS', ellipsis: true },
    { title: '状态', dataIndex: 'status', width: 80 },
  )
  return cols
})

function detailRowKey(r: { modelName?: string; wavname: string }) {
  return `${r.modelName || ''}:${r.wavname}`
}

function numOr(...vals: unknown[]): number | undefined {
  for (const v of vals) {
    if (v != null && v !== '' && !Number.isNaN(Number(v))) return Number(v)
  }
  return undefined
}

function formatScore(v: number | undefined | null) {
  if (v == null) return '—'
  return typeof v === 'number' ? v.toFixed(4) : String(v)
}

function formatJobId(id: string) {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id
}

function formatJobDescription(item: UnifiedEvalJob) {
  const parts: string[] = []
  if (item.jobType === 'multi_model' && item.modelCount) {
    parts.push(`${item.modelCount} 模型`)
  }
  parts.push(`${item.totalFiles} 文件`)
  parts.push(item.status)
  if (item.createdAt) parts.push(item.createdAt)
  return parts.join(' · ')
}

async function runMultiModelBatch(slots: ModelEvalSlot[]) {
  if (!requireLogin()) return
  if (!engineReady.value) {
    warnEngineNotReady()
    return
  }
  multiModelLoading.value = true
  jobStatus.value = null
  detailModelFilter.value = undefined
  try {
    const id = await createMultiModelEvalJob(slots, createMeta.value)
    jobId.value = id
    message.success('多模型任务已创建')
    startPolling(id)
    await afterJobCreated()
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '创建任务失败')
  } finally {
    multiModelLoading.value = false
  }
}

function playKey(record: { wavname: string; modelName?: string }) {
  return `${record.modelName || ''}:${record.wavname}`
}

async function playJobAudio(wavname: string, modelName?: string) {
  if (!jobId.value) return
  const key = playKey({ wavname, modelName })
  if (playingKey.value === key && audioEl && !audioEl.paused) {
    audioEl.pause()
    playingKey.value = ''
    return
  }
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
  const url = getJobAudioUrl(jobId.value, wavname, modelName)
  try {
    const res = await fetch(url, { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    audioEl = new Audio(blobUrl)
    audioEl.onended = () => {
      URL.revokeObjectURL(blobUrl)
      playingKey.value = ''
    }
    audioEl.onerror = () => {
      URL.revokeObjectURL(blobUrl)
      message.error('无法播放音频')
      playingKey.value = ''
    }
    playingKey.value = key
    await audioEl.play()
  } catch {
    message.error('无法播放音频（旧任务需重新评测后才可回放）')
    playingKey.value = ''
  }
}

function warnEngineNotReady() {
  if (showDaemonGateHint.value) {
    message.warning(
      '评测 daemon 未就绪，请在服务器执行 bash scripts/eval-daemons.sh restart 后点击「刷新状态」',
    )
    return
  }
  message.warning('评测引擎不可用，请查看上方「引擎状态」')
}

function requireLogin(): boolean {
  if (!loginUserStore.loginUser?.id) {
    message.warning('请先登录后再提交评测')
    return false
  }
  return true
}

async function loadHealth() {
  healthLoading.value = true
  try {
    health.value = await getUnifiedEvalHealth()
  } catch {
    message.error('无法获取引擎状态')
  } finally {
    healthLoading.value = false
  }
}

const onSingleBeforeUpload: UploadProps['beforeUpload'] = (file) => {
  singleFile.value = file as File
  return false
}

async function submitEvalJob(files: File[], archive?: File) {
  jobStatus.value = null
  const id = await createUnifiedEvalJob(files, archive, createMeta.value)
  jobId.value = id
  message.success('任务已创建')
  startPolling(id)
  await afterJobCreated()
}

async function runSingle() {
  if (!requireLogin() || !singleFile.value) return
  if (!engineReady.value) {
    warnEngineNotReady()
    return
  }
  singleLoading.value = true
  try {
    await submitEvalJob([singleFile.value])
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '创建任务失败')
  } finally {
    singleLoading.value = false
  }
}

async function runBatch(mode: 'multi' | 'dir') {
  if (!requireLogin()) return
  if (!engineReady.value) {
    warnEngineNotReady()
    return
  }
  const { files, archive } = batchUpload.filesForSubmit(mode)
  if (!files.length && !archive) {
    message.warning('请选择文件或 zip')
    return
  }
  jobLoading.value = true
  try {
    await submitEvalJob(files, archive ?? undefined)
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
    const job = await getUnifiedEvalJob(id)
    jobStatus.value = job
    if (
      job.status === 'completed' ||
      job.status === 'failed' ||
      job.status === 'interrupted' ||
      job.status === 'paused'
    ) {
      stopPolling()
      if (job.status !== 'paused') {
        handlePollTerminal(job)
      }
    }
  } catch (e: unknown) {
    stopPolling()
    handlePollCatch(e)
  }
}

async function saveJobDisplayName(name: string) {
  if (!jobId.value) return
  await updateUnifiedEvalJobDisplayName(jobId.value, name)
  if (jobStatus.value) {
    jobStatus.value = { ...jobStatus.value, displayName: name }
  }
}

function onDisplayNameSaved() {
  void loadRecentJobs()
  emit('jobs-changed')
}

const {
  pauseLoading,
  rerunLoading,
  resumeLoading,
  handlePause,
  handleRerun,
  handleResume,
} = useEvalJobControls({
  jobId,
  resumeJob: resumeUnifiedEvalJob,
  pauseJob: pauseUnifiedEvalJob,
  rerunJob: rerunUnifiedEvalJob,
  startPolling,
  pollJob,
  onRefreshRecent: () => {
    void loadRecentJobs()
    emit('jobs-changed')
  },
  onResumeSuccess: () => afterJobCreated(),
})

async function loadJob(id: string) {
  if (!requireLogin()) return
  jobId.value = id
  detailModelFilter.value = undefined
  try {
    jobStatus.value = await getUnifiedEvalJob(id)
    if (jobStatus.value.status === 'running' || jobStatus.value.status === 'pending') {
      startPolling(id)
    }
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '加载失败')
  }
}

async function afterJobCreated() {
  if (props.embedded) {
    emit('jobs-changed')
    return
  }
  await loadRecentJobs()
}

async function loadRecentJobs() {
  if (!loginUserStore.loginUser?.id) return
  try {
    const data = await listUnifiedEvalJobs()
    recentJobs.value = data.jobs || []
  } catch {
    /* ignore */
  }
}

function exportPayload() {
  return {
    job: jobStatus.value,
    exportedAt: new Date().toISOString(),
  }
}

function exportJson() {
  const blob = new Blob([JSON.stringify(exportPayload(), null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `uni-eval-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function exportCsv() {
  if (isMultiModelJob.value && compareRows.value.length) {
    const summaryHeader = [
      'modelName',
      'fileCount',
      'accuracyMean',
      'fluencyMean',
      'naturalnessMean',
      'apgMosBvccMean',
      'apgMosSomosMean',
    ]
    const detailHeader = [
      'modelName',
      'wavname',
      'accuracy',
      'fluency',
      'naturalness',
      'bvcc',
      'somos',
      'status',
    ]
    const lines = [
      '# summary',
      summaryHeader.join(','),
      ...compareRows.value.map((r) =>
        summaryHeader.map((h) => JSON.stringify((r as Record<string, unknown>)[h] ?? '')).join(','),
      ),
      '',
      '# detail',
      detailHeader.join(','),
      ...tableRows.value.map((r) =>
        detailHeader.map((h) => JSON.stringify((r as Record<string, unknown>)[h] ?? '')).join(','),
      ),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `uni-eval-multi-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    return
  }
  const rows = tableRows.value
  const header = ['wavname', 'accuracy', 'fluency', 'naturalness', 'bvcc', 'somos', 'status']
  const lines = [
    header.join(','),
    ...rows.map((r) =>
      header.map((h) => JSON.stringify((r as Record<string, unknown>)[h] ?? '')).join(','),
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `uni-eval-${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

defineExpose({ loadJob })

onMounted(async () => {
  await loadHealth()
  if (!props.embedded) await loadRecentJobs()
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
.uni-eval-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.uni-eval-embedded {
  max-width: 100%;
  padding: 0;
}

.page-header h1 {
  margin: 0 0 8px;
  font-size: 24px;
}

.subtitle {
  color: #666;
  margin: 0 0 16px;
}

.section {
  margin-bottom: 16px;
}

.action-btn {
  margin-top: 12px;
}

.hint {
  color: #888;
  font-size: 13px;
  margin-top: 8px;
}

.error-text {
  color: #cf1322;
}

.play-btn {
  color: #1890ff;
  padding: 0 4px;
}

.play-btn.playing {
  color: #52c41a;
}

.wav-name {
  word-break: break-all;
}
</style>
