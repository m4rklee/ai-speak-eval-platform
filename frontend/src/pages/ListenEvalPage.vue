<template>
  <div class="page-container">
    <div class="page-header">
      <PageTitle
        icon-key="listen-eval"
        title="听力评测"
        subtitle="内置北极星 2201 题库（MMSU 四选一），使用模型库中支持音频输入的模型逐题推理并统计准确率"
      />
    </div>

    <a-card title="题库状态" class="page-section" size="small">
      <a-space wrap>
        <a-tag :color="health?.benchmarkOk ? 'green' : 'red'">
          题库 {{ health?.benchmarkOk ? '就绪' : '异常' }}
        </a-tag>
        <a-tag v-if="health?.questionCount" color="blue">{{ health.questionCount }} 题</a-tag>
        <a-tag :color="health?.audioDirOk ? 'green' : 'red'">音频目录</a-tag>
        <a-tag :color="health?.apiConfigured ? 'green' : 'orange'">API Key</a-tag>
      </a-space>
      <p v-if="health?.message && !health?.ready" class="hint">{{ health.message }}</p>
      <a-button size="small" style="margin-top: 8px" :loading="healthLoading" @click="loadHealth">
        刷新状态
      </a-button>
    </a-card>

    <a-card title="评测配置" class="page-section">
      <a-form layout="vertical">
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
          <span class="hint" style="margin-left: 8px">缩小模型列表；多平台模型需在下方指定调用平台</span>
        </a-form-item>
        <a-form-item label="模型（需支持音频输入）" required>
          <a-select
            v-model:value="selectedModelId"
            show-search
            placeholder="选择模型"
            :loading="modelsLoading"
            :options="audioInputModelOptions"
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
        <a-form-item label="抽样方式">
          <a-radio-group v-model:value="sampleMode">
            <a-radio value="all">全量 2201 题</a-radio>
            <a-radio value="random">随机 N 题（调试）</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="sampleMode === 'random'" label="随机题数 N">
          <a-input-number
            v-model:value="sampleCount"
            :min="1"
            :max="health?.questionCount || 2201"
            style="width: 160px"
          />
          <span class="hint" style="margin-left: 8px">可选 seed 复现</span>
        </a-form-item>
        <a-form-item v-if="sampleMode === 'random'" label="随机种子（可选）">
          <a-input-number v-model:value="seed" style="width: 160px" />
        </a-form-item>
        <a-collapse ghost>
          <a-collapse-panel key="adv" header="高级选项">
            <a-form-item label="任务名称（可选）">
              <a-input
                v-model:value="displayName"
                placeholder="留空则自动生成"
                :maxlength="64"
                style="max-width: 400px"
              />
            </a-form-item>
            <a-form-item label="评测轮次">
              <a-input-number v-model:value="evalRounds" :min="1" :max="5" style="width: 120px" />
              <span class="hint" style="margin-left: 8px">每题重复评测 1–5 次后汇总</span>
            </a-form-item>
            <a-form-item label="请求间隔（秒）">
              <a-input-number
                v-model:value="requestInterval"
                :min="0"
                :max="30"
                :step="0.5"
                style="width: 120px"
              />
            </a-form-item>
            <a-form-item label="并发 workers">
              <a-input-number v-model:value="workers" :min="1" :max="16" style="width: 120px" />
              <span class="hint" style="margin-left: 8px">
                同时处理的题目数；续跑 / 重跑时会使用此处与「请求间隔」的最新值
              </span>
            </a-form-item>
          </a-collapse-panel>
        </a-collapse>
        <a-button
          type="primary"
          :loading="jobLoading"
          :disabled="!canSubmit"
          @click="runJob"
        >
          开始评测
        </a-button>
        <p v-if="!loginUserStore.loginUser?.id" class="hint">请先登录后再提交评测</p>
      </a-form>
    </a-card>

    <div v-if="jobId && jobStatus" ref="jobDetailRef" class="job-detail-section">
      <JobInterruptedBanner
        :job="jobStatus"
        :loading="resumeLoading"
        @resume="handleResume"
      />
      <JobApiErrorAlert :job="jobStatus" />
      <JobDisplayNameEdit
        :job-id="jobId"
        :display-name="jobStatus.displayName"
        :on-save="saveJobDisplayName"
        @saved="onDisplayNameSaved"
      />
      <a-card v-if="showProgress" title="评测进度" class="page-section" size="small">
        <template #extra>
          <JobProgressActions
            :job="jobStatus"
            :pause-loading="pauseLoading"
            :resume-loading="resumeLoading"
            :rerun-loading="rerunLoading"
            @pause="handlePause"
            @resume="handleResume"
            @rerun="(opts) => handleRerun(opts)"
          />
        </template>
        <UniEvalTqdmBar
          :percent="jobStatus!.progress"
          :detail="jobStatus!.progressDetail"
          :job-status="jobStatus!.status"
        />
        <p class="hint">任务 ID: {{ jobId }} · {{ jobStatus!.totalSamples }} 题 · {{ jobStatus!.model }}</p>
        <p v-if="jobWorkers != null" class="hint">并发 workers：{{ jobWorkers }}</p>
        <p v-if="jobStatus!.evalRounds && jobStatus!.evalRounds > 1" class="hint">
          评测轮次：{{ jobStatus!.evalRounds }}
        </p>
        <JobTokenSummary :job="jobStatus" />
        <p v-if="jobStatus!.error" class="error-text">{{ jobStatus!.error }}</p>
      </a-card>

      <a-card v-if="overallAccuracy != null" title="总体结果" class="page-section" size="small">
        <JobTokenSummary :job="jobStatus" />
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic
              title="准确率"
              :value="(overallAccuracy * 100).toFixed(2)"
              suffix="%"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic title="正确" :value="summaryOverall?.correct ?? '—'" />
          </a-col>
          <a-col :span="8">
            <a-statistic title="总题数" :value="summaryOverall?.total ?? '—'" />
          </a-col>
        </a-row>
      </a-card>

      <a-card v-if="dimensionRows.length" title="按维度" class="page-section" size="small">
        <a-table
          :columns="bucketColumns"
          :data-source="dimensionRows"
          :pagination="false"
          row-key="name"
          size="small"
        />
      </a-card>

      <a-card v-if="datasetRows.length" title="按来源数据集" class="page-section" size="small">
        <a-table
          :columns="bucketColumns"
          :data-source="datasetRows"
          :pagination="{ pageSize: 15 }"
          row-key="name"
          size="small"
        />
      </a-card>

      <a-card v-if="detailRows.length" title="题目明细" class="page-section">
        <template #extra>
          <a-space>
            <a-button size="small" @click="exportJson">导出 JSON</a-button>
            <a-button size="small" @click="exportCsv">导出 CSV</a-button>
          </a-space>
        </template>
        <p class="hint" style="margin-bottom: 8px">点击行首展开或「详情」查看题目、选项与模型完整回复</p>
        <a-table
          :columns="detailColumns"
          :data-source="detailRows"
          :pagination="{ pageSize: 20 }"
          row-key="id"
          size="small"
          :scroll="{ x: 1200 }"
          :expanded-row-keys="expandedRowKeys"
          @expand="onTableExpand"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'question'">
              <span class="question-preview">{{ record.question || '—' }}</span>
            </template>
            <template v-else-if="column.dataIndex === 'action'">
              <a @click="toggleRowExpand(record.id)">详情</a>
            </template>
          </template>
          <template #expandedRowRender="{ record }">
            <div class="row-detail">
              <div class="detail-block">
                <div class="detail-label">题目</div>
                <div class="text-block">{{ record.question || '—' }}</div>
              </div>
              <div class="detail-block">
                <div class="detail-label">选项</div>
                <ul class="choices-list">
                  <li v-for="line in formatChoices(record)" :key="line.key">{{ line.text }}</li>
                </ul>
              </div>
              <div class="detail-block">
                <div class="detail-label">模型回复</div>
                <div class="text-block">{{ record.response || '—' }}</div>
              </div>
              <div v-if="record.error" class="detail-block">
                <div class="detail-label">错误</div>
                <div class="text-block error-text">{{ record.error }}</div>
              </div>
            </div>
          </template>
        </a-table>
      </a-card>
    </div>

    <EvalRecentJobsCard ref="recentCardRef" class="page-section" @view="onRecentView" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { listModels, listPlatforms, type ModelVO } from '@/api/modelController'
import {
  defaultProviderPlatform,
  getModelPlatforms,
  modelSelectLabel,
  platformLabel,
  resolveModelId,
} from '@/utils/modelPlatform'
import {
  createListenEvalJob,
  getListenEvalHealth,
  getListenEvalJob,
  pauseListenEvalJob,
  rerunListenEvalJob,
  resumeListenEvalJob,
  updateListenEvalJobDisplayName,
  type ListenEvalHealth,
  type ListenEvalJob,
  type ListenEvalPerRow,
} from '@/api/listenEvalController'
import PageTitle from '@/components/PageTitle.vue'
import EvalRecentJobsCard, {
  type EvalRecentJobItem,
} from '@/components/EvalRecentJobsCard.vue'
import UniEvalTqdmBar from '@/components/UniEvalTqdmBar.vue'
import JobInterruptedBanner from '@/components/eval/JobInterruptedBanner.vue'
import JobApiErrorAlert from '@/components/eval/JobApiErrorAlert.vue'
import JobTokenSummary from '@/components/eval/JobTokenSummary.vue'
import JobDisplayNameEdit from '@/components/eval/JobDisplayNameEdit.vue'
import JobProgressActions from '@/components/eval/JobProgressActions.vue'
import { useEvalJobPoll } from '@/composables/useEvalJobPoll'
import { useEvalJobControls } from '@/composables/useEvalJobControls'
import { useLoginUserStore } from '@/stores/loginUser'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()
const recentCardRef = ref<InstanceType<typeof EvalRecentJobsCard> | null>(null)

const health = ref<ListenEvalHealth | null>(null)
const healthLoading = ref(false)
const models = ref<ModelVO[]>([])
const modelsLoading = ref(false)
const platformOptions = ref<string[]>(['openrouter', 'aihubmix'])
const filterPlatform = ref<string | undefined>(undefined)
const selectedModelId = ref<string>()
const selectedProviderPlatform = ref<string>('openrouter')
const sampleMode = ref<'all' | 'random'>('random')
const sampleCount = ref(5)
const seed = ref<number | undefined>(undefined)
const requestInterval = ref(0)
const workers = ref(4)
const displayName = ref('')
const evalRounds = ref(1)

const { handlePollTerminal, handlePollCatch } = useEvalJobPoll({
  completedMessage: '听力评测完成',
  onRefreshRecent: () => recentCardRef.value?.loadRecentJobs(),
})

const jobLoading = ref(false)
const jobId = ref('')
const jobStatus = ref<ListenEvalJob | null>(null)
const jobDetailRef = ref<HTMLElement | null>(null)
const expandedRowKeys = ref<string[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

const parseModalities = (m: ModelVO) => {
  const inp = m.inputModalities
  if (Array.isArray(inp)) return inp
  if (typeof inp === 'string') {
    try {
      return JSON.parse(inp) as string[]
    } catch {
      return []
    }
  }
  return [] as string[]
}

const audioInputModels = computed(() =>
  models.value.filter((m) => parseModalities(m).includes('audio')),
)

const audioInputModelOptions = computed(() =>
  audioInputModels.value
    .filter((m) => !filterPlatform.value || getModelPlatforms(m).includes(filterPlatform.value))
    .map((m) => ({ label: modelSelectLabel(m), value: m.id })),
)

const selectedModelRecord = computed(() =>
  audioInputModels.value.find((m) => m.id === selectedModelId.value),
)

const providerPlatforms = computed(() => getModelPlatforms(selectedModelRecord.value))

const showProviderSelect = computed(() => providerPlatforms.value.length > 1)

const effectiveModelId = computed(() => {
  const m = selectedModelRecord.value
  if (!m) return ''
  const platforms = providerPlatforms.value
  const platform =
    platforms.length === 1 ? platforms[0] : selectedProviderPlatform.value
  return resolveModelId(m, platform)
})

const canSubmit = computed(() => {
  if (!loginUserStore.loginUser?.id || !effectiveModelId.value || jobLoading.value) return false
  if (!health.value?.ready) return false
  if (sampleMode.value === 'random' && (!sampleCount.value || sampleCount.value < 1)) return false
  return true
})

const showProgress = computed(
  () =>
    jobStatus.value &&
    (jobStatus.value.status === 'running' ||
      jobStatus.value.status === 'pending' ||
      jobStatus.value.status === 'paused' ||
      jobStatus.value.status === 'interrupted' ||
      jobStatus.value.progressDetail),
)

const jobWorkers = computed(() => jobStatus.value?.workers ?? null)

function getRuntimeOptions() {
  return {
    workers: workers.value,
    requestInterval: requestInterval.value,
  }
}

watch(
  () => jobStatus.value?.jobId,
  (id) => {
    if (!id || !jobStatus.value) return
    if (jobStatus.value.workers != null) workers.value = jobStatus.value.workers
    if (jobStatus.value.requestInterval != null) {
      requestInterval.value = jobStatus.value.requestInterval
    }
  },
)

const summaryOverall = computed(() => jobStatus.value?.summary?.overall)
const overallAccuracy = computed(() => summaryOverall.value?.accuracy ?? null)

const bucketColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '正确', dataIndex: 'correct', key: 'correct', width: 80 },
  { title: '总数', dataIndex: 'total', key: 'total', width: 80 },
  {
    title: '准确率',
    dataIndex: 'accuracy',
    key: 'accuracy',
    width: 100,
    customRender: ({ text }: { text: number }) =>
      text != null ? `${(text * 100).toFixed(1)}%` : '—',
  },
]

function bucketToRows(
  bucket?: Record<string, { correct: number; total: number; accuracy: number }>,
) {
  if (!bucket) return []
  return Object.entries(bucket).map(([name, v]) => ({
    name,
    correct: v.correct,
    total: v.total,
    accuracy: v.accuracy,
  }))
}

const dimensionRows = computed(() => bucketToRows(jobStatus.value?.summary?.byDimension))
const datasetRows = computed(() => bucketToRows(jobStatus.value?.summary?.bySourceDataset))

const detailColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 100, ellipsis: true },
  { title: '题目', dataIndex: 'question', key: 'question', ellipsis: true },
  { title: '维度', dataIndex: 'dimension', key: 'dimension', width: 120, ellipsis: true },
  { title: '预测', dataIndex: 'prediction', key: 'prediction', width: 56 },
  { title: '答案', dataIndex: 'answerLabel', key: 'answerLabel', width: 56 },
  {
    title: '正误',
    dataIndex: 'isCorrect',
    key: 'isCorrect',
    width: 56,
    customRender: ({ text }: { text: boolean | null }) =>
      text === true ? '✓' : text === false ? '✗' : '—',
  },
  { title: '模型回复', dataIndex: 'response', key: 'response', width: 140, ellipsis: true },
  { title: '', dataIndex: 'action', key: 'action', width: 56, fixed: 'right' as const },
]

const detailRows = computed(() => jobStatus.value?.perFile || [])

function formatChoices(record: ListenEvalPerRow) {
  const items: { key: string; text: string }[] = []
  const pairs: [string, string | undefined][] = [
    ['A', record.choiceA],
    ['B', record.choiceB],
    ['C', record.choiceC],
    ['D', record.choiceD],
    ['E', record.choiceE],
  ]
  for (const [label, text] of pairs) {
    const t = (text || '').trim()
    if (t) items.push({ key: label, text: `${label}. ${t}` })
  }
  return items.length ? items : [{ key: '-', text: '—' }]
}

function onTableExpand(expanded: boolean, record: ListenEvalPerRow) {
  const id = record.id
  if (expanded) {
    if (!expandedRowKeys.value.includes(id)) expandedRowKeys.value = [...expandedRowKeys.value, id]
  } else {
    expandedRowKeys.value = expandedRowKeys.value.filter((k) => k !== id)
  }
}

function toggleRowExpand(id: string) {
  if (expandedRowKeys.value.includes(id)) {
    expandedRowKeys.value = expandedRowKeys.value.filter((k) => k !== id)
  } else {
    expandedRowKeys.value = [...expandedRowKeys.value, id]
  }
}

async function loadHealth() {
  healthLoading.value = true
  try {
    health.value = await getListenEvalHealth()
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '无法加载题库状态')
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
      !audioInputModelOptions.value.some((o) => o.value === selectedModelId.value)
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

function requireLogin() {
  if (!loginUserStore.loginUser?.id) {
    message.warning('请先登录')
    return false
  }
  return true
}

async function scrollToJobDetail() {
  await nextTick()
  jobDetailRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
    const job = await getListenEvalJob(id)
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

async function runJob() {
  if (!requireLogin() || !effectiveModelId.value) return
  if (!health.value?.apiConfigured) {
    message.warning('请配置 OpenRouter 或 AiHubMix API Key')
    return
  }
  jobLoading.value = true
  jobStatus.value = null
  try {
    const id = await createListenEvalJob({
      model: effectiveModelId.value,
      sampleMode: sampleMode.value,
      sampleCount: sampleMode.value === 'random' ? sampleCount.value : undefined,
      seed: seed.value,
      requestInterval: requestInterval.value,
      workers: workers.value,
      displayName: displayName.value.trim() || undefined,
      evalRounds: evalRounds.value,
    })
    jobId.value = id
    message.success('任务已创建')
    void recentCardRef.value?.loadRecentJobs()
    startPolling(id)
    await scrollToJobDetail()
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '创建任务失败')
  } finally {
    jobLoading.value = false
  }
}

async function saveJobDisplayName(name: string) {
  if (!jobId.value) return
  await updateListenEvalJobDisplayName(jobId.value, name)
  if (jobStatus.value) {
    jobStatus.value = { ...jobStatus.value, displayName: name }
  }
}

function onDisplayNameSaved() {
  void recentCardRef.value?.loadRecentJobs()
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
  resumeJob: resumeListenEvalJob,
  pauseJob: pauseListenEvalJob,
  rerunJob: rerunListenEvalJob,
  startPolling,
  pollJob,
  getRuntimeOptions,
  onRefreshRecent: () => void recentCardRef.value?.loadRecentJobs(),
  resumePausedMessage: '已开始续跑（跳过已完成题目）',
})

async function loadJob(id: string) {
  if (!requireLogin()) return
  stopPolling()
  jobId.value = id
  jobStatus.value = null
  expandedRowKeys.value = []
  try {
    const job = await getListenEvalJob(id)
    jobStatus.value = job
    if (job.status === 'running' || job.status === 'pending') {
      startPolling(id)
    }
    await scrollToJobDetail()
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '加载任务失败')
  }
}

function onRecentView(item: EvalRecentJobItem) {
  if (item.kind === 'listening') {
    void loadJob(item.jobId)
    return
  }
  void router.push({
    path: '/oral-eval',
    query: { tab: item.kind, job: item.jobId },
  })
}

function exportJson() {
  const blob = new Blob([JSON.stringify(jobStatus.value, null, 2)], {
    type: 'application/json',
  })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `listen-eval-${jobId.value || Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function exportCsv() {
  const rows = detailRows.value as ListenEvalPerRow[]
  const header = [
    'id',
    'question',
    'choiceA',
    'choiceB',
    'choiceC',
    'choiceD',
    'choiceE',
    'dimension',
    'prediction',
    'answerLabel',
    'isCorrect',
    'response',
    'error',
  ]
  const lines = [
    header.join(','),
    ...rows.map((r) =>
      header
        .map((k) => {
          const v = (r as Record<string, unknown>)[k]
          const s = v == null ? '' : String(v)
          return `"${s.replace(/"/g, '""')}"`
        })
        .join(','),
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `listen-eval-${jobId.value || Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

watch(
  () => route.query.job,
  (id) => {
    if (typeof id === 'string' && id) void loadJob(id)
  },
)

onMounted(() => {
  void loadHealth()
  void loadPlatforms()
  void loadModels()
  const qJob = route.query.job
  if (typeof qJob === 'string' && qJob) void loadJob(qJob)
})

onBeforeUnmount(() => {
  stopPolling()
})

defineExpose({ loadJob })
</script>

<style scoped>
.hint {
  color: #888;
  font-size: 13px;
}

.error-text {
  color: #cf1322;
  margin-top: 8px;
}

.question-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.row-detail {
  padding: 4px 0 8px 48px;
}

.detail-block {
  margin-bottom: 12px;
}

.detail-label {
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.text-block {
  white-space: pre-wrap;
  word-break: break-word;
  color: #444;
  line-height: 1.5;
}

.choices-list {
  margin: 0;
  padding-left: 20px;
  color: #444;
  line-height: 1.6;
}
</style>
