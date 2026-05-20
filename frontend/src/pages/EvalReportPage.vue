<template>
  <div class="page-container eval-report-page">
    <div class="page-header">
      <PageTitle
        icon-key="eval-reports"
        title="评测报告"
        subtitle="跨类型选择已完成任务，按模型与维度对比汇总得分"
      />
    </div>

    <a-row :gutter="16">
      <a-col :xs="24" :lg="8">
        <a-card title="选择任务" size="small" class="page-section">
          <template #extra>
            <a-button size="small" :loading="loadingJobs" @click="loadAllJobs">刷新</a-button>
          </template>
          <p class="hint" style="margin-bottom: 12px">回复生成任务无可对比维度，仅语音/内容/听力/综合任务参与矩阵。</p>
          <a-spin :spinning="loadingJobs">
            <a-checkbox-group v-model:value="selectedJobKeys" style="width: 100%">
              <div v-for="group in jobGroups" :key="group.kind" class="job-group">
                <div class="job-group-title">
                  <a-tag :color="kindTagColor(group.kind)">{{ kindLabel(group.kind) }}</a-tag>
                  <span class="hint">{{ group.items.length }} 个已完成</span>
                </div>
                <div v-for="item in group.items" :key="item.key" class="job-option">
                  <a-checkbox :value="item.key" :disabled="'disabled' in item && item.disabled">
                    {{ item.displayName }}
                  </a-checkbox>
                </div>
                <a-empty v-if="!group.items.length" :image="false" description="无已完成任务" />
              </div>
            </a-checkbox-group>
          </a-spin>
        </a-card>

        <a-card title="维度筛选" size="small" class="page-section">
          <a-checkbox-group v-model:value="selectedDimensions" style="width: 100%">
            <div v-for="dim in availableDimensions" :key="dim.key" class="dim-option">
              <a-checkbox :value="dim.key">{{ dim.label }}</a-checkbox>
            </div>
          </a-checkbox-group>
          <a-empty v-if="!availableDimensions.length" :image="false" description="请先选择任务" />
        </a-card>

        <a-card title="模型筛选" size="small" class="page-section">
          <a-select
            v-model:value="modelFilter"
            allow-clear
            placeholder="全部模型"
            style="width: 100%"
            :options="modelFilterOptions"
          />
        </a-card>
      </a-col>

      <a-col :xs="24" :lg="16">
        <a-card title="对比矩阵" size="small" class="page-section">
          <template #extra>
            <span v-if="selectedJobKeys.length" class="hint">
              已选 {{ selectedJobKeys.length }} 个任务 · {{ tableRows.length }} 个模型
            </span>
          </template>
          <div class="report-table-wrap">
            <a-table
              :columns="tableColumns"
              :data-source="sortedRows"
              :pagination="false"
              row-key="modelName"
              size="small"
              :scroll="tableScroll"
              :loading="loadingDetails"
              @change="onTableChange"
            >
              <template #headerCell="{ column }">
                <template v-if="column.dataIndex && column.dataIndex !== 'modelName'">
                  <span class="sortable-header" @click="toggleSort(String(column.dataIndex))">
                    {{ column.title }}
                    <span v-if="sortCol === column.dataIndex">{{ sortAsc ? '↑' : '↓' }}</span>
                  </span>
                </template>
                <template v-else>{{ column.title }}</template>
              </template>
              <template #bodyCell="{ column, record }">
                <template v-if="column.dataIndex && column.dataIndex !== 'modelName'">
                  <span>{{ formatCellValues(record.cells[column.dataIndex as string]) }}</span>
                  <template v-if="record.cells[column.dataIndex as string]?.length > 1">
                    <a-tag
                      v-for="(tag, idx) in uniqueKindTags(record.cells[column.dataIndex as string])"
                      :key="idx"
                      size="small"
                      :color="kindTagColor(tag)"
                      class="cell-tag"
                    >
                      {{ kindLabel(tag) }}
                    </a-tag>
                  </template>
                </template>
              </template>
            </a-table>
          </div>
          <a-empty v-if="!selectedJobKeys.length" description="请从左侧选择已完成任务" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import PageTitle from '@/components/PageTitle.vue'
import { listOralGenJobs, type OralGenJob } from '@/api/oralGenController'
import {
  listContentEvalJobs,
  getContentEvalJob,
  type ContentEvalJob,
} from '@/api/contentEvalController'
import { listListenEvalJobs, getListenEvalJob, type ListenEvalJob } from '@/api/listenEvalController'
import {
  listOralCombinedJobs,
  getOralCombinedJob,
  type OralCombinedJob,
} from '@/api/oralCombinedEvalController'
import { listUnifiedEvalJobs, getUnifiedEvalJob, type UnifiedEvalJob } from '@/api/unifiedEvalController'
import {
  dimensionsForKinds,
  kindLabel,
  kindTagColor,
  type EvalReportJobKind,
} from '@/constants/evalReportDimensions'
import {
  buildReportRows,
  extractListenDynamicColumns,
  formatCellValues,
  sortValueForRow,
  staticDimensionLabels,
  type ReportCellValue,
} from '@/utils/evalReportExtract'

function parseJobKey(key: string): [EvalReportJobKind, string] {
  const i = key.indexOf(':')
  if (i <= 0) return [key as EvalReportJobKind, '']
  return [key.slice(0, i) as EvalReportJobKind, key.slice(i + 1)]
}

type JobListItem = {
  key: string
  kind: EvalReportJobKind
  jobId: string
  displayName: string
}

const loadingJobs = ref(false)
const loadingDetails = ref(false)
const selectedJobKeys = ref<string[]>([])
const selectedDimensions = ref<string[]>([])
const modelFilter = ref<string | undefined>(undefined)
const sortCol = ref<string | null>(null)
const sortAsc = ref(true)

const speechJobs = ref<UnifiedEvalJob[]>([])
const contentJobs = ref<ContentEvalJob[]>([])
const listenJobs = ref<ListenEvalJob[]>([])
const combinedJobs = ref<OralCombinedJob[]>([])
const oralGenJobs = ref<OralGenJob[]>([])

const jobDetails = ref<
  Map<string, UnifiedEvalJob | ContentEvalJob | ListenEvalJob | OralCombinedJob>
>(new Map())

function formatJobId(id: string) {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id
}

function jobTitle(job: { displayName?: string; jobId: string }) {
  return job.displayName?.trim() || formatJobId(job.jobId)
}

function toListItem(kind: EvalReportJobKind, job: { jobId: string; displayName?: string }): JobListItem {
  return {
    key: `${kind}:${job.jobId}`,
    kind,
    jobId: job.jobId,
    displayName: jobTitle(job),
  }
}

const jobGroups = computed(() => [
  {
    kind: 'speech' as const,
    items: speechJobs.value.map((j) => toListItem('speech', j)),
  },
  {
    kind: 'content' as const,
    items: contentJobs.value.map((j) => toListItem('content', j)),
  },
  {
    kind: 'listen' as const,
    items: listenJobs.value.map((j) => toListItem('listen', j)),
  },
  {
    kind: 'combined' as const,
    items: combinedJobs.value.map((j) => toListItem('combined', j)),
  },
  {
    kind: 'oral_gen' as const,
    items: oralGenJobs.value.map((j) => ({
      key: `oral_gen:${j.jobId}`,
      kind: 'oral_gen' as const,
      jobId: j.jobId,
      displayName: jobTitle(j),
      disabled: true,
    })),
  },
])

const selectedKinds = computed(() => {
  const kinds = new Set<EvalReportJobKind>()
  for (const key of selectedJobKeys.value) {
    const [kind] = parseJobKey(key)
    kinds.add(kind)
  }
  return kinds
})

const listenDynamicDims = computed(() => {
  const listenSelected = listenJobs.value.filter((j) =>
    selectedJobKeys.value.includes(`listen:${j.jobId}`),
  )
  return extractListenDynamicColumns(listenSelected).map((key) => ({
    key,
    label: staticDimensionLabels()[key] || key.replace(/^listen:/, '听力·'),
    kinds: ['listen'] as EvalReportJobKind[],
  }))
})

const availableDimensions = computed(() => {
  const staticDims = dimensionsForKinds(selectedKinds.value)
  const listenDims = selectedKinds.value.has('listen') ? listenDynamicDims.value : []
  const merged = [...staticDims]
  for (const d of listenDims) {
    if (!merged.some((m) => m.key === d.key)) merged.push(d)
  }
  return merged
})

watch(
  availableDimensions,
  (dims, prev) => {
    const keys = dims.map((d) => d.key)
    if (!prev?.length) {
      selectedDimensions.value = keys
      return
    }
    const kept = selectedDimensions.value.filter((k) => keys.includes(k))
    const added = keys.filter((k) => !kept.includes(k))
    selectedDimensions.value = kept.length ? [...kept, ...added] : keys
  },
  { immediate: true },
)

const dimLabels = computed(() => {
  const labels = staticDimensionLabels()
  for (const d of availableDimensions.value) {
    labels[d.key] = d.label
  }
  return labels
})

const tableRows = computed(() => {
  const selected = selectedJobKeys.value
    .map((key) => {
      const [kind, jobId] = parseJobKey(key)
      const job = jobDetails.value.get(key)
      if (!job) return null
      return { kind, jobId, job }
    })
    .filter(Boolean) as Array<{
    kind: EvalReportJobKind
    jobId: string
    job: UnifiedEvalJob | ContentEvalJob | ListenEvalJob | OralCombinedJob
  }>
  return buildReportRows(selected, modelFilter.value)
})

const sortedRows = computed(() => {
  const rows = [...tableRows.value]
  if (!sortCol.value) return rows
  const col = sortCol.value
  rows.sort((a, b) => {
    const va = sortValueForRow(a, col)
    const vb = sortValueForRow(b, col)
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    return sortAsc.value ? va - vb : vb - va
  })
  return rows
})

const modelFilterOptions = computed(() => {
  const names = new Set<string>()
  for (const row of tableRows.value) names.add(row.modelName)
  return [...names].sort().map((m) => ({ label: m, value: m }))
})

const tableScroll = computed(() => {
  if (selectedDimensions.value.length <= 4) return undefined
  return { x: Math.max(600, selectedDimensions.value.length * 120 + 180) }
})

const tableColumns = computed(() => {
  const cols: Array<Record<string, unknown>> = [
    {
      title: '模型',
      dataIndex: 'modelName',
      key: 'modelName',
      fixed: 'left',
      width: 180,
    },
  ]
  for (const key of selectedDimensions.value) {
    cols.push({
      title: dimLabels.value[key] || key,
      dataIndex: key,
      key,
    })
  }
  return cols
})

function toggleSort(key: string) {
  if (sortCol.value === key) sortAsc.value = !sortAsc.value
  else {
    sortCol.value = key
    sortAsc.value = false
  }
}

function onTableChange() {
  /* sort handled via header click */
}

function uniqueKindTags(cells?: ReportCellValue[]) {
  if (!cells?.length) return [] as EvalReportJobKind[]
  return [...new Set(cells.map((c) => c.kind))]
}

async function loadAllJobs() {
  loadingJobs.value = true
  try {
    const [speech, content, listen, combined, oralGen] = await Promise.all([
      listUnifiedEvalJobs().catch(() => ({ jobs: [] as UnifiedEvalJob[] })),
      listContentEvalJobs().catch(() => ({ jobs: [] as ContentEvalJob[] })),
      listListenEvalJobs().catch(() => ({ jobs: [] as ListenEvalJob[] })),
      listOralCombinedJobs().catch(() => ({ jobs: [] as OralCombinedJob[] })),
      listOralGenJobs().catch(() => ({ jobs: [] as OralGenJob[] })),
    ])
    speechJobs.value = (speech.jobs || []).filter((j) => j.status === 'completed')
    contentJobs.value = (content.jobs || []).filter((j) => j.status === 'completed')
    listenJobs.value = (listen.jobs || []).filter((j) => j.status === 'completed')
    combinedJobs.value = (combined.jobs || []).filter((j) => j.status === 'completed')
    oralGenJobs.value = (oralGen.jobs || []).filter((j) => j.status === 'completed')
  } catch {
    message.error('无法加载任务列表')
  } finally {
    loadingJobs.value = false
  }
}

async function loadSelectedDetails() {
  if (!selectedJobKeys.value.length) {
    jobDetails.value = new Map()
    return
  }
  loadingDetails.value = true
  try {
    const next = new Map(jobDetails.value)
    await Promise.all(
      selectedJobKeys.value.map(async (key) => {
        if (next.has(key)) return
        const [kind, jobId] = parseJobKey(key)
        try {
          if (kind === 'speech') next.set(key, await getUnifiedEvalJob(jobId))
          else if (kind === 'content') next.set(key, await getContentEvalJob(jobId))
          else if (kind === 'listen') next.set(key, await getListenEvalJob(jobId))
          else if (kind === 'combined') next.set(key, await getOralCombinedJob(jobId))
        } catch {
          message.warning(`无法加载任务 ${jobId}`)
        }
      }),
    )
    jobDetails.value = next
  } finally {
    loadingDetails.value = false
  }
}

watch(selectedJobKeys, () => {
  void loadSelectedDetails()
})

void loadAllJobs()
</script>

<style scoped>
.eval-report-page {
  max-width: 1400px;
  margin: 0 auto;
}

.job-group {
  margin-bottom: 16px;
}

.job-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.job-option,
.dim-option {
  margin-bottom: 6px;
}

.hint {
  color: #888;
  font-size: 13px;
}

.cell-tag {
  margin-left: 4px;
}

.sortable-header {
  cursor: pointer;
  user-select: none;
}

.report-table-wrap {
  width: 100%;
  overflow-x: auto;
}
</style>
