<template>
  <a-card v-if="loginUserStore.loginUser?.id" title="最近任务" class="eval-recent-jobs-card" size="small">
    <template #extra>
      <a-space>
        <a-select
          v-model:value="recentFilter"
          style="width: 120px"
          size="small"
          :options="recentFilterOptions"
        />
        <a-button size="small" :loading="recentLoading" @click="loadRecentJobs">
          刷新
        </a-button>
      </a-space>
    </template>
    <a-list v-if="filteredRecentJobs.length" size="small" :data-source="filteredRecentJobs">
      <template #renderItem="{ item }">
        <a-list-item>
          <a-list-item-meta :title="item.title" :description="item.description" />
          <template #actions>
            <a-tag :color="kindTagColor(item.kind)">{{ kindLabel(item.kind) }}</a-tag>
            <a-tag :color="statusColor(item.status)">{{ statusLabel(item.status) }}</a-tag>
            <a @click="onView(item)">查看</a>
          </template>
        </a-list-item>
      </template>
    </a-list>
    <a-empty v-else description="暂无任务" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useLoginUserStore } from '@/stores/loginUser'
import { listContentEvalJobs, type ContentEvalJob } from '@/api/contentEvalController'
import {
  listOralCombinedJobs,
  type OralCombinedJob,
} from '@/api/oralCombinedEvalController'
import { listListenEvalJobs, type ListenEvalJob } from '@/api/listenEvalController'
import { listOralGenJobs, type OralGenJob } from '@/api/oralGenController'
import { listUnifiedEvalJobs, type UnifiedEvalJob } from '@/api/unifiedEvalController'

export type EvalRecentKind = 'oral_gen' | 'speech' | 'content' | 'combined' | 'listening'

export type EvalRecentJobItem = {
  kind: EvalRecentKind
  jobId: string
  title: string
  description: string
  status: string
  createdAt: string
  sortKey: number
}

const emit = defineEmits<{
  view: [item: EvalRecentJobItem]
}>()

const loginUserStore = useLoginUserStore()
const recentJobs = ref<EvalRecentJobItem[]>([])
const recentLoading = ref(false)
const recentFilter = ref<'all' | EvalRecentKind>('all')

const recentFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '回复生成', value: 'oral_gen' },
  { label: '语音', value: 'speech' },
  { label: '内容', value: 'content' },
  { label: '综合', value: 'combined' },
  { label: '听力', value: 'listening' },
]

const filteredRecentJobs = computed(() => {
  if (recentFilter.value === 'all') return recentJobs.value
  return recentJobs.value.filter((j) => j.kind === recentFilter.value)
})

function parseTime(iso?: string): number {
  if (!iso) return 0
  const t = Date.parse(iso)
  return Number.isNaN(t) ? 0 : t
}

function formatJobId(id: string) {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id
}

function formatUniDescription(item: UnifiedEvalJob) {
  const parts: string[] = []
  if (item.jobType === 'multi_model' && item.modelCount) {
    parts.push(`${item.modelCount} 模型`)
  }
  parts.push(`${item.totalFiles} 文件`)
  parts.push(item.status)
  if (item.createdAt) parts.push(item.createdAt)
  return parts.join(' · ')
}

function formatContentDescription(item: ContentEvalJob) {
  const parts = [`${item.totalFiles} 文件`, item.status]
  if (item.createdAt) parts.push(item.createdAt)
  return parts.join(' · ')
}

function formatCombinedDescription(item: OralCombinedJob) {
  const parts: string[] = []
  if (item.pipelineMode) parts.push('一站式')
  parts.push(`${item.totalFiles} 组成对`, item.status)
  if (item.summary?.okCount != null) {
    parts.push(`成功 ${item.summary.okCount}`)
  }
  if (item.createdAt) parts.push(item.createdAt)
  return parts.join(' · ')
}

function formatOralGenDescription(item: OralGenJob) {
  const parts = [`${item.totalSamples} 条`, item.status]
  if (item.summary?.success != null) {
    parts.push(`成功 ${item.summary.success}`)
  }
  if (item.createdAt) parts.push(item.createdAt)
  return parts.join(' · ')
}

function formatListenDescription(item: ListenEvalJob) {
  const parts = [`${item.totalSamples} 题`, item.status]
  if (item.summary?.overall?.accuracy != null) {
    parts.push(`准确率 ${(item.summary.overall.accuracy * 100).toFixed(1)}%`)
  }
  if (item.createdAt) parts.push(item.createdAt)
  return parts.join(' · ')
}

function kindLabel(kind: EvalRecentKind) {
  const map: Record<EvalRecentKind, string> = {
    oral_gen: '回复生成',
    speech: '语音',
    content: '内容',
    combined: '综合',
    listening: '听力',
  }
  return map[kind]
}

function kindTagColor(kind: EvalRecentKind) {
  if (kind === 'oral_gen') return 'geekblue'
  if (kind === 'speech') return 'blue'
  if (kind === 'content') return 'purple'
  if (kind === 'combined') return 'cyan'
  return 'orange'
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

function onView(item: EvalRecentJobItem) {
  emit('view', item)
}

async function loadRecentJobs() {
  if (!loginUserStore.loginUser?.id) {
    recentJobs.value = []
    return
  }
  recentLoading.value = true
  try {
    const [oralGenData, uniData, contentData, combinedData, listenData] = await Promise.all([
      listOralGenJobs().catch(() => ({ jobs: [] as OralGenJob[] })),
      listUnifiedEvalJobs().catch(() => ({ jobs: [] as UnifiedEvalJob[] })),
      listContentEvalJobs().catch(() => ({ jobs: [] as ContentEvalJob[] })),
      listOralCombinedJobs().catch(() => ({ jobs: [] as OralCombinedJob[] })),
      listListenEvalJobs().catch(() => ({ jobs: [] as ListenEvalJob[] })),
    ])
    const oralGen: EvalRecentJobItem[] = (oralGenData.jobs || []).map((item) => ({
      kind: 'oral_gen' as const,
      jobId: item.jobId,
      title: formatJobId(item.jobId),
      description: formatOralGenDescription(item),
      status: item.status,
      createdAt: item.createdAt || '',
      sortKey: parseTime(item.createdAt),
    }))
    const speech: EvalRecentJobItem[] = (uniData.jobs || []).map((item) => ({
      kind: 'speech' as const,
      jobId: item.jobId,
      title: formatJobId(item.jobId),
      description: formatUniDescription(item),
      status: item.status,
      createdAt: item.createdAt || '',
      sortKey: parseTime(item.createdAt),
    }))
    const content: EvalRecentJobItem[] = (contentData.jobs || []).map((item) => ({
      kind: 'content' as const,
      jobId: item.jobId,
      title: formatJobId(item.jobId),
      description: formatContentDescription(item),
      status: item.status,
      createdAt: item.createdAt || '',
      sortKey: parseTime(item.createdAt),
    }))
    const combined: EvalRecentJobItem[] = (combinedData.jobs || []).map((item) => ({
      kind: 'combined' as const,
      jobId: item.jobId,
      title: formatJobId(item.jobId),
      description: formatCombinedDescription(item),
      status: item.status,
      createdAt: item.createdAt || '',
      sortKey: parseTime(item.createdAt),
    }))
    const listening: EvalRecentJobItem[] = (listenData.jobs || []).map((item) => ({
      kind: 'listening' as const,
      jobId: item.jobId,
      title: formatJobId(item.jobId),
      description: formatListenDescription(item),
      status: item.status,
      createdAt: item.createdAt || '',
      sortKey: parseTime(item.createdAt),
    }))
    recentJobs.value = [...oralGen, ...speech, ...content, ...combined, ...listening].sort(
      (a, b) => b.sortKey - a.sortKey,
    )
  } catch {
    message.error('无法加载最近任务')
  } finally {
    recentLoading.value = false
  }
}

watch(
  () => loginUserStore.loginUser?.id,
  (id) => {
    if (id) void loadRecentJobs()
    else recentJobs.value = []
  },
)

onMounted(() => {
  void loadRecentJobs()
})

defineExpose({ loadRecentJobs })
</script>

<style scoped>
.eval-recent-jobs-card {
  margin-top: 8px;
}
</style>
