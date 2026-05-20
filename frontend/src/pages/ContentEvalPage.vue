<template>
  <div :class="embedded ? 'content-eval-embedded' : 'content-eval-page'">
    <div v-if="!embedded" class="page-header">
      <h1>内容评测</h1>
      <p class="subtitle">
        基于 GPT-4o 评测大模型回复文本：语法准确表达 (0–100)、主题聚焦拓展 (0–4)、回复简洁清晰 (0–3)
      </p>
    </div>

    <a-card title="服务状态" class="section" size="small">
      <a-space wrap>
        <a-tag :color="health?.questionDirOk ? 'green' : 'red'">
          题库 {{ health?.questionDirOk ? '就绪' : '异常' }}
        </a-tag>
        <a-tag v-if="health?.questionCount" color="blue">{{ health.questionCount }} 题</a-tag>
        <span v-if="health?.judgeModel" class="hint">Judge: {{ health.judgeModel }}</span>
        <span v-if="health?.questionDirMessage && !health?.questionDirOk" class="hint">
          {{ health.questionDirMessage }}
        </span>
      </a-space>
      <a-alert
        v-if="health && !health.questionDirOk"
        type="warning"
        show-icon
        style="margin-top: 12px"
        message="题库未就绪"
        :description="health.questionDirMessage || '请配置 content_eval 题库目录后刷新状态'"
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
        <a-form-item label="Judge 模型">
          <a-select
            v-model:value="judgeModel"
            show-search
            placeholder="选择文本模型"
            :loading="judgeModelsLoading"
            :options="judgeModelOptions"
            style="width: 280px"
          />
        </a-form-item>
      </a-form>
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="single" tab="单条评测">
          <a-form layout="vertical">
            <a-form-item label="题目 ID（内置题库）">
              <a-select
                v-model:value="selectedQuestionId"
                show-search
                :filter-option="filterQuestion"
                :loading="questionsLoading"
                placeholder="选择题目，如 00001"
                style="width: 280px"
                @change="onQuestionChange"
              >
                <a-select-option v-for="id in questionIds" :key="id" :value="id">
                  {{ id }}
                </a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item v-if="questionPreview" label="题目预览">
              <a-typography-paragraph class="question-preview" :content="questionPreview" />
            </a-form-item>
            <a-form-item label="大模型回复">
              <a-textarea
                v-model:value="answerText"
                :rows="5"
                placeholder="粘贴英文回复文本，或下方上传 .txt 文件（文件名可自动匹配题目）"
              />
            </a-form-item>
            <a-form-item label="或上传 answer .txt">
              <a-upload
                :multiple="false"
                :show-upload-list="!!singleFile"
                accept=".txt,text/plain"
                :before-upload="onSingleFileBeforeUpload"
                @remove="singleFile = null"
              >
                <a-button>
                  <UploadOutlined />
                  选择文件
                </a-button>
              </a-upload>
              <p v-if="singleFile" class="hint">已选：{{ singleFile.name }}</p>
            </a-form-item>
          </a-form>
          <a-button
            type="primary"
            :loading="singleLoading"
            :disabled="!readyForEval"
            @click="runSingle"
          >
            开始评测
          </a-button>
          <p v-if="!loginUserStore.loginUser?.id" class="hint">请先登录后再提交评测</p>
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
              选择多个 .txt
            </a-button>
          </a-upload>
          <a-button
            type="primary"
            class="action-btn"
            :loading="jobLoading"
            :disabled="!canSubmitBatch('multi')"
            @click="runBatch('multi')"
          >
            提交批量任务（{{ multiFiles.length }} 个文件）
          </a-button>
          <p class="hint">answer 文件名按 stem 匹配内置题目（如 00174_环境安静_女.txt → 00174）</p>
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
                选择文件夹（含 txt）
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
              :disabled="!canSubmitBatch('dir')"
              @click="runBatch('dir')"
            >
              提交任务
            </a-button>
          </a-space>
          <p class="hint">answer 文件名按 stem 匹配内置题目</p>
        </a-tab-pane>

        <a-tab-pane key="multiModel" tab="多模型对比">
          <EvalMultiModelSlots
            accept-ext="txt"
            file-label="txt"
            :max-models="maxModelsPerJob"
            :loading="multiModelLoading"
            :submit-disabled="!health?.questionDirOk"
            :show-login-hint="!loginUserStore.loginUser?.id"
            @submit="runMultiModelBatch"
          />
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <a-card v-if="singleResult" title="单条评测结果" class="section" size="small">
      <template #extra>
        <a-space>
          <a-button size="small" @click="exportSingleJson">导出 JSON</a-button>
          <a-button size="small" @click="exportSingleCsv">导出 CSV</a-button>
        </a-space>
      </template>
      <a-row :gutter="16">
        <a-col :span="6">
          <a-statistic title="语法准确表达" :value="singleResult.grammarScore ?? '—'" suffix="/ 100" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="主题聚焦拓展" :value="singleResult.themeFocusScore ?? '—'" suffix="/ 4" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="回复简洁清晰" :value="singleResult.answerClarityScore ?? '—'" suffix="/ 3" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="综合" :value="formatScore(singleResult.compositeScore)" suffix="/ 100" />
        </a-col>
      </a-row>
      <p v-if="singleResult.reason" class="hint" style="margin-top: 12px">{{ singleResult.reason }}</p>
      <a-descriptions bordered size="small" :column="1" style="margin-top: 12px">
        <a-descriptions-item label="题目">
          <span v-if="singleResult.questionId" class="id-tag">{{ singleResult.questionId }}</span>
          {{ singleResult.question || '—' }}
        </a-descriptions-item>
        <a-descriptions-item label="回答">
          <div class="text-block">{{ singleResult.answer || '—' }}</div>
        </a-descriptions-item>
      </a-descriptions>
      <a-collapse style="margin-top: 12px">
        <a-collapse-panel key="detail" header="维度详情 JSON">
          <pre class="json-block">{{ JSON.stringify(singleResult.dimensions, null, 2) }}</pre>
        </a-collapse-panel>
      </a-collapse>
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
        <span v-if="jobStatus!.judgeModel"> · Judge: {{ jobStatus!.judgeModel }}</span>
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
        <a-button size="small" @click="exportBatchJson">导出 JSON</a-button>
        <a-button size="small" @click="exportBatchCsv">导出 CSV</a-button>
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

    <a-card v-if="displaySummary && !isMultiModelJob" title="批量汇总" class="section" size="small">
      <JobTokenSummary :job="jobStatus" />
      <a-descriptions bordered size="small" :column="3">
        <a-descriptions-item label="文件数">{{ displaySummary.fileCount ?? '—' }}</a-descriptions-item>
        <a-descriptions-item label="成功数">{{ displaySummary.okCount ?? '—' }}</a-descriptions-item>
        <a-descriptions-item label="语法均值">{{ formatScore(displaySummary.grammarMean) }}</a-descriptions-item>
        <a-descriptions-item label="主题均值">{{ formatScore(displaySummary.themeFocusMean) }}</a-descriptions-item>
        <a-descriptions-item label="简洁均值">{{ formatScore(displaySummary.answerClarityMean) }}</a-descriptions-item>
        <a-descriptions-item label="综合均值">{{ formatScore(displaySummary.compositeMean) }}</a-descriptions-item>
      </a-descriptions>
    </a-card>

    <a-card v-if="tableRows.length" :title="isMultiModelJob ? '逐文件明细' : '评测结果'" class="section">
      <template v-if="!isMultiModelJob" #extra>
        <a-space>
          <a-button size="small" @click="exportBatchJson">导出 JSON</a-button>
          <a-button size="small" @click="exportBatchCsv">导出 CSV</a-button>
        </a-space>
      </template>
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
      <p v-if="!isMultiModelJob" class="hint" style="margin-bottom: 8px">
        点击行首展开图标，或「详情」查看题目与回答全文
      </p>
      <a-table
        :columns="detailColumns"
        :data-source="filteredTableRows"
        :pagination="{ pageSize: 20 }"
        row-key="rowKey"
        size="small"
        :scroll="{ x: 1100 }"
        :expanded-row-keys="expandedRowKeys"
        @expand="onTableExpand"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'action'">
            <a @click="toggleRowExpand(record.rowKey)">详情</a>
          </template>
        </template>
        <template #expandedRowRender="{ record }">
          <div class="row-detail">
            <div class="detail-block">
              <div class="detail-label">题目（{{ record.questionId || '—' }}）</div>
              <div class="text-block">{{ record.question || '—' }}</div>
            </div>
            <div class="detail-block">
              <div class="detail-label">回答</div>
              <div class="text-block">{{ record.answer || '—' }}</div>
            </div>
            <div v-if="record.reason" class="detail-block">
              <div class="detail-label">评分理由</div>
              <div class="text-block muted">{{ record.reason }}</div>
            </div>
            <a-collapse v-if="record.dimensions && Object.keys(record.dimensions).length" ghost>
              <a-collapse-panel key="json" header="维度详情 JSON">
                <pre class="json-block">{{ JSON.stringify(record.dimensions, null, 2) }}</pre>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </template>
      </a-table>
    </a-card>

    <a-card
      v-else-if="jobStatus && (jobStatus.status === 'completed' || jobStatus.status === 'failed')"
      title="评测结果"
      class="section"
      size="small"
    >
      <a-empty description="该任务无明细结果（可能已过期，请重新提交评测）" />
    </a-card>

    <a-card v-if="!embedded && recentJobs.length" title="最近任务" class="section" size="small">
      <template #extra>
        <a-button size="small" :loading="recentJobsLoading" @click="loadRecentJobs">刷新</a-button>
      </template>
      <a-list size="small" :data-source="recentJobs">
        <template #renderItem="{ item }">
          <a-list-item
            class="recent-job-item"
            :class="{ 'recent-job-item-active': item.jobId === jobId }"
          >
            <a-list-item-meta>
              <template #title>
                <a-space :size="8">
                  <span class="job-id-text" :title="item.jobId">{{ jobTitle(item) }}</span>
                  <a-tag :color="statusColor(item.status)" class="job-status-tag">
                    {{ statusLabel(item.status) }}
                  </a-tag>
                  <span v-if="item.jobId === jobId" class="viewing-tag">当前查看</span>
                </a-space>
              </template>
              <template #description>
                {{ formatJobDescription(item) }}
              </template>
            </a-list-item-meta>
            <template #actions>
              <a-button
                type="link"
                size="small"
                :loading="loadingJobId === item.jobId"
                @click="loadJob(item.jobId)"
              >
                查看
              </a-button>
            </template>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'
import { FileZipOutlined, FolderOpenOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { useLoginUserStore } from '@/stores/loginUser'
import type { ModelEvalSlot } from '@/api/unifiedEvalController'
import {
  createContentEvalJob,
  createContentMultiModelJob,
  evaluateContentSingle,
  getContentEvalHealth,
  getContentEvalJob,
  pauseContentEvalJob,
  rerunContentEvalJob,
  resumeContentEvalJob,
  updateContentEvalJobDisplayName,
  getContentEvalQuestion,
  listContentEvalJobs,
  listContentEvalQuestions,
  type ContentEvalHealth,
  type ContentEvalJob,
  type ContentEvalSingleResult,
} from '@/api/contentEvalController'
import { listModels, type ModelVO } from '@/api/modelController'
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
import { modelSelectLabel } from '@/utils/modelPlatform'

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ (e: 'jobs-changed'): void }>()

const loginUserStore = useLoginUserStore()

const health = ref<ContentEvalHealth | null>(null)
const healthLoading = ref(false)
const activeTab = ref('single')
const batchUpload = useEvalBatchUpload('txt')
const { multiFileList, dirInputRef, multiFiles, dirFiles, zipFile, dirSelectionHint } = batchUpload
const maxModelsPerJob = 10

const questionIds = ref<string[]>([])
const questionsLoading = ref(false)
const selectedQuestionId = ref<string>()
const questionPreview = ref('')

const answerText = ref('')
const singleFile = ref<File | null>(null)
const singleLoading = ref(false)
const singleResult = ref<ContentEvalSingleResult | null>(null)

const jobLoading = ref(false)
const multiModelLoading = ref(false)
const jobId = ref('')
const jobStatus = ref<ContentEvalJob | null>(null)
const detailModelFilter = ref<string | undefined>(undefined)
const recentJobs = ref<ContentEvalJob[]>([])
const recentJobsLoading = ref(false)
const loadingJobId = ref('')
const expandedRowKeys = ref<string[]>([])
const displayName = ref('')
const evalRounds = ref(1)
const judgeModel = ref<string>()
const judgeModels = ref<ModelVO[]>([])
const judgeModelsLoading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const createMeta = computed(() => ({
  displayName: displayName.value.trim() || undefined,
  evalRounds: evalRounds.value,
  judgeModel: judgeModel.value || undefined,
}))

const judgeModelOptions = computed(() =>
  judgeModels.value.map((m) => ({ value: m.id, label: modelSelectLabel(m) })),
)

const { handlePollTerminal, handlePollCatch } = useEvalJobPoll({
  completedMessage: '评测完成',
  onRefreshRecent: () => afterJobCreated(),
})

const readyForEval = computed(
  () =>
    !!loginUserStore.loginUser?.id &&
    health.value?.questionDirOk &&
    (!!answerText.value.trim() || !!singleFile.value) &&
    (!!selectedQuestionId.value || !!singleFile.value),
)

function canSubmitBatch(mode: 'multi' | 'dir') {
  return (
    !!loginUserStore.loginUser?.id &&
    !!health.value?.questionDirOk &&
    batchUpload.batchReady(mode)
  )
}

const showProgress = computed(
  () =>
    jobId.value &&
    jobStatus.value &&
    ['pending', 'running', 'paused', 'interrupted', 'completed', 'failed'].includes(jobStatus.value.status),
)

const isMultiModelJob = computed(
  () =>
    jobStatus.value?.jobType === 'multi_model' ||
    (jobStatus.value?.models?.length ?? 0) > 0,
)

const compareRows = computed(() => jobStatus.value?.comparison?.byModel ?? [])

const compareColumns = [
  { title: '模型', dataIndex: 'modelName', width: 160, ellipsis: true },
  { title: '文件数', dataIndex: 'fileCount', width: 80 },
  {
    title: '语法均值',
    dataIndex: 'grammarMean',
    width: 100,
    customRender: ({ text }: { text: number }) => formatScore(text),
  },
  {
    title: '主题均值',
    dataIndex: 'themeFocusMean',
    width: 100,
    customRender: ({ text }: { text: number }) => formatScore(text),
  },
  {
    title: '简洁均值',
    dataIndex: 'answerClarityMean',
    width: 100,
    customRender: ({ text }: { text: number }) => formatScore(text),
  },
  {
    title: '综合均值',
    dataIndex: 'compositeMean',
    width: 100,
    customRender: ({ text }: { text: number }) => formatScore(text),
  },
]

const displaySummary = computed(() => jobStatus.value?.summary ?? null)

function mapPerFileRow(raw: Record<string, unknown>, modelName?: string, idx = 0) {
  return {
    rowKey: `${modelName || ''}:${String(raw.fileName ?? idx)}-${idx}`,
    fileName: String(raw.fileName ?? ''),
    modelName: modelName ?? (raw.modelName as string | undefined),
    questionId: String(raw.questionId ?? ''),
    question: String(raw.question ?? ''),
    answer: String(raw.answer ?? ''),
    grammarScore: raw.grammarScore as number | undefined,
    themeFocusScore: raw.themeFocusScore as number | undefined,
    answerClarityScore: raw.answerClarityScore as number | undefined,
    compositeScore: raw.compositeScore as number | undefined,
    status: String(raw.status ?? 'ok'),
    reason: raw.reason as string | undefined,
    dimensions: raw.dimensions as Record<string, unknown> | undefined,
  }
}

const tableRows = computed(() => {
  if (isMultiModelJob.value && jobStatus.value?.models?.length) {
    const rows: ReturnType<typeof mapPerFileRow>[] = []
    let idx = 0
    for (const model of jobStatus.value.models) {
      for (const row of model.perFile || []) {
        rows.push(mapPerFileRow(row as Record<string, unknown>, model.modelName, idx++))
      }
    }
    return rows
  }
  const rows = jobStatus.value?.perFile ?? []
  return rows.map((raw, idx) => mapPerFileRow(raw as Record<string, unknown>, undefined, idx))
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
  type ColDef = {
    title: string
    dataIndex: string
    width?: number
    ellipsis?: boolean
    fixed?: 'right'
  }
  const cols: ColDef[] = [{ title: '文件名', dataIndex: 'fileName', width: 160, ellipsis: true }]
  if (isMultiModelJob.value) {
    cols.push({ title: '模型', dataIndex: 'modelName', width: 140, ellipsis: true })
  }
  cols.push(
    { title: '题目 ID', dataIndex: 'questionId', width: 90 },
    { title: '语法 (0-100)', dataIndex: 'grammarScore', width: 110 },
    { title: '主题 (0-4)', dataIndex: 'themeFocusScore', width: 100 },
    { title: '简洁 (0-3)', dataIndex: 'answerClarityScore', width: 100 },
    { title: '综合', dataIndex: 'compositeScore', width: 80 },
    { title: '状态', dataIndex: 'status', width: 80 },
    { title: '操作', dataIndex: 'action', width: 70, fixed: 'right' },
  )
  return cols
})

function toggleRowExpand(key: string) {
  const i = expandedRowKeys.value.indexOf(key)
  if (i >= 0) {
    expandedRowKeys.value = expandedRowKeys.value.filter((k) => k !== key)
  } else {
    expandedRowKeys.value = [...expandedRowKeys.value, key]
  }
}

function onTableExpand(expanded: boolean, record: { rowKey: string }) {
  if (expanded) {
    if (!expandedRowKeys.value.includes(record.rowKey)) {
      expandedRowKeys.value = [...expandedRowKeys.value, record.rowKey]
    }
  } else {
    expandedRowKeys.value = expandedRowKeys.value.filter((k) => k !== record.rowKey)
  }
}

function formatScore(v: number | undefined | null) {
  if (v == null) return '—'
  return typeof v === 'number' ? v.toFixed(2) : String(v)
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '进行中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
  }
  return map[status] || 'default'
}

function formatJobId(id: string) {
  if (!id) return '—'
  return id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id
}

function jobTitle(item: ContentEvalJob) {
  return item.displayName?.trim() || formatJobId(item.jobId)
}

function formatJobDescription(item: ContentEvalJob) {
  const parts: string[] = []
  if (item.jobType === 'multi_model' && item.modelCount) {
    parts.push(`${item.modelCount} 模型`)
  }
  parts.push(`${item.totalFiles} 个文件`)
  if (item.createdAt) parts.push(item.createdAt)
  if (item.status === 'running' || item.status === 'pending') {
    parts.push(`进度 ${item.progress ?? 0}%`)
  }
  if (item.status === 'completed' && item.summary?.compositeMean != null) {
    parts.push(`综合均值 ${formatScore(item.summary.compositeMean)}`)
  }
  if (item.status === 'failed' && item.error) {
    parts.push(item.error.slice(0, 40))
  }
  return parts.join(' · ')
}

function filterQuestion(input: string, option: { value: string }) {
  return option.value.toLowerCase().includes(input.toLowerCase())
}

function requireLogin(): boolean {
  if (!loginUserStore.loginUser?.id) {
    message.warning('请先登录后再提交评测')
    return false
  }
  return true
}

async function loadJudgeModels() {
  judgeModelsLoading.value = true
  try {
    const res = await listModels({ inputModality: 'text' })
    if (res.data.code === 0) judgeModels.value = res.data.data || []
  } finally {
    judgeModelsLoading.value = false
  }
}

async function loadHealth() {
  healthLoading.value = true
  try {
    health.value = await getContentEvalHealth()
    if (health.value?.judgeModel && !judgeModel.value) {
      judgeModel.value = health.value.judgeModel
    }
  } catch {
    message.error('无法获取服务状态')
  } finally {
    healthLoading.value = false
  }
}

async function loadQuestions() {
  questionsLoading.value = true
  try {
    const data = await listContentEvalQuestions()
    questionIds.value = data.ids
    if (!selectedQuestionId.value && data.ids.length) {
      selectedQuestionId.value = data.ids[0]
    }
  } catch {
    message.error('无法加载题目列表')
  } finally {
    questionsLoading.value = false
  }
}

async function onQuestionChange(id: string) {
  if (!id) {
    questionPreview.value = ''
    return
  }
  try {
    const data = await getContentEvalQuestion(id)
    questionPreview.value = data.question
  } catch {
    questionPreview.value = ''
  }
}

watch(selectedQuestionId, (id) => {
  if (id) void onQuestionChange(id)
})

const onSingleFileBeforeUpload: UploadProps['beforeUpload'] = (file) => {
  singleFile.value = file as File
  return false
}

async function submitJob(files: File[], archive?: File) {
  jobStatus.value = null
  singleResult.value = null
  detailModelFilter.value = undefined
  const id = await createContentEvalJob(files, archive, createMeta.value)
  jobId.value = id
  message.success('任务已创建')
  startPolling(id)
  await afterJobCreated()
}

async function runSingle() {
  if (!requireLogin()) return
  singleLoading.value = true
  singleResult.value = null
  try {
    singleResult.value = await evaluateContentSingle({
      questionId: selectedQuestionId.value,
      answer: answerText.value.trim() || undefined,
      file: singleFile.value ?? undefined,
    })
    message.success('评测完成')
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '评测失败')
  } finally {
    singleLoading.value = false
  }
}

async function runBatch(mode: 'multi' | 'dir') {
  if (!requireLogin()) return
  if (!health.value?.questionDirOk) {
    message.warning('题库未就绪，请检查配置后刷新状态')
    return
  }
  const { files, archive } = batchUpload.filesForSubmit(mode)
  if (!files.length && !archive) {
    message.warning('请选择文件或 zip')
    return
  }
  jobLoading.value = true
  try {
    await submitJob(files, archive ?? undefined)
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '创建任务失败')
  } finally {
    jobLoading.value = false
  }
}

async function runMultiModelBatch(slots: ModelEvalSlot[]) {
  if (!requireLogin()) return
  if (!health.value?.questionDirOk) {
    message.warning('题库未就绪，请检查配置后刷新状态')
    return
  }
  multiModelLoading.value = true
  jobStatus.value = null
  singleResult.value = null
  detailModelFilter.value = undefined
  try {
    const id = await createContentMultiModelJob(slots, createMeta.value)
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

function startPolling(id: string) {
  stopPolling()
  pollTimer = setInterval(() => void pollJob(id), 1500)
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
    const job = await getContentEvalJob(id)
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
  await updateContentEvalJobDisplayName(jobId.value, name)
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
  resumeJob: resumeContentEvalJob,
  pauseJob: pauseContentEvalJob,
  rerunJob: rerunContentEvalJob,
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
  stopPolling()
  loadingJobId.value = id
  jobId.value = id
  singleResult.value = null
  expandedRowKeys.value = []
  detailModelFilter.value = undefined
  jobStatus.value = null

  try {
    const job = await getContentEvalJob(id)
    jobStatus.value = job
    if (job.status === 'running' || job.status === 'pending') {
      startPolling(id)
    }
    if (job.status === 'completed') {
      message.success(`已加载任务（${job.totalFiles} 个文件）`)
    } else if (job.status === 'failed') {
      message.warning(job.error || '任务失败')
    } else {
      message.info('任务加载中，请稍候…')
    }
  } catch (e: unknown) {
    jobId.value = ''
    jobStatus.value = null
    message.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loadingJobId.value = ''
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
  recentJobsLoading.value = true
  try {
    const data = await listContentEvalJobs()
    recentJobs.value = data.jobs || []
  } catch {
    message.error('无法加载最近任务')
  } finally {
    recentJobsLoading.value = false
  }
}

function downloadFile(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

const CSV_HEADERS = [
  'fileName',
  'modelName',
  'questionId',
  'question',
  'answer',
  'grammarScore',
  'themeFocusScore',
  'answerClarityScore',
  'compositeScore',
  'status',
  'reason',
] as const

function rowsToCsv(rows: Array<Record<string, unknown>>) {
  const lines = [
    CSV_HEADERS.join(','),
    ...rows.map((r) => CSV_HEADERS.map((h) => JSON.stringify(r[h] ?? '')).join(',')),
  ]
  return `\uFEFF${lines.join('\n')}`
}

function exportSingleJson() {
  if (!singleResult.value) return
  downloadFile(
    JSON.stringify({ result: singleResult.value, exportedAt: new Date().toISOString() }, null, 2),
    `content-eval-single-${Date.now()}.json`,
    'application/json',
  )
}

function exportSingleCsv() {
  if (!singleResult.value) return
  const r = singleResult.value
  downloadFile(
    rowsToCsv([
      {
        fileName: r.fileName,
        modelName: '',
        questionId: r.questionId,
        question: r.question,
        answer: r.answer ?? '',
        grammarScore: r.grammarScore,
        themeFocusScore: r.themeFocusScore,
        answerClarityScore: r.answerClarityScore,
        compositeScore: r.compositeScore,
        status: r.status,
        reason: r.reason ?? '',
      },
    ]),
    `content-eval-single-${Date.now()}.csv`,
    'text/csv;charset=utf-8',
  )
}

function exportBatchJson() {
  if (!jobStatus.value) return
  downloadFile(
    JSON.stringify(
      {
        jobId: jobId.value,
        job: jobStatus.value,
        exportedAt: new Date().toISOString(),
      },
      null,
      2,
    ),
    `content-eval-${jobId.value || Date.now()}.json`,
    'application/json',
  )
}

function exportBatchCsv() {
  if (isMultiModelJob.value && compareRows.value.length) {
    const summaryHeader = [
      'modelName',
      'fileCount',
      'grammarMean',
      'themeFocusMean',
      'answerClarityMean',
      'compositeMean',
    ]
    const detailHeader = [...CSV_HEADERS]
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
    downloadFile(
      lines.join('\n'),
      `content-eval-multi-${Date.now()}.csv`,
      'text/csv;charset=utf-8',
    )
    return
  }
  if (!tableRows.value.length) return
  downloadFile(
    rowsToCsv(tableRows.value as unknown as Array<Record<string, unknown>>),
    `content-eval-${jobId.value || Date.now()}.csv`,
    'text/csv;charset=utf-8',
  )
}

defineExpose({ loadJob })

onMounted(async () => {
  await loadHealth()
  void loadJudgeModels()
  await loadQuestions()
  if (!props.embedded) await loadRecentJobs()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.content-eval-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.content-eval-embedded {
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

.question-preview {
  margin: 0;
  color: #333;
  background: #fafafa;
  padding: 8px 12px;
  border-radius: 4px;
}

.json-block {
  margin: 0;
  font-size: 12px;
  max-height: 320px;
  overflow: auto;
}

.row-detail {
  padding: 4px 0 8px 48px;
}

.detail-block {
  margin-bottom: 12px;
}

.detail-label {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.text-block {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  background: #fafafa;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
}

.text-block.muted {
  color: #666;
  background: #fff;
}

.id-tag {
  display: inline-block;
  margin-right: 8px;
  padding: 0 6px;
  font-size: 12px;
  color: #1890ff;
  background: #e6f7ff;
  border-radius: 4px;
}

.recent-job-item {
  transition: background 0.2s;
  border-radius: 6px;
  padding-inline: 8px;
}

.recent-job-item-active {
  background: #e6f7ff;
}

.job-id-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

.job-status-tag {
  margin: 0;
}

.viewing-tag {
  font-size: 12px;
  color: #1890ff;
}
</style>
