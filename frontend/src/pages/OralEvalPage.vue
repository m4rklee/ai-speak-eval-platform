<template>
  <div class="page-container">
    <div class="page-header">
      <PageTitle
        icon-key="oral-eval"
        title="口语评测"
        subtitle="回复生成 | 综合评测（一站式）| 语音/内容评测"
      />
    </div>

    <a-tabs v-model:activeKey="mainTab" class="main-tabs" @change="onMainTabChange">
      <a-tab-pane key="generate" tab="回复生成">
        <OralGenPanel ref="genPanelRef" @jobs-changed="onJobsChanged" />
      </a-tab-pane>
      <a-tab-pane key="speech" tab="语音评测 (Uni)">
        <UniEvalPage ref="uniPanelRef" embedded @jobs-changed="onJobsChanged" />
      </a-tab-pane>
      <a-tab-pane key="content" tab="内容评测">
        <ContentEvalPage ref="contentPanelRef" embedded @jobs-changed="onJobsChanged" />
      </a-tab-pane>
      <a-tab-pane key="combined" tab="综合评测">
        <CombinedEvalPanel ref="combinedPanelRef" embedded @jobs-changed="onJobsChanged" />
      </a-tab-pane>
    </a-tabs>

    <EvalRecentJobsCard ref="recentCardRef" class="page-section" @view="viewRecentJob" />
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useLoginUserStore } from '@/stores/loginUser'
import PageTitle from '@/components/PageTitle.vue'
import EvalRecentJobsCard, {
  type EvalRecentJobItem,
} from '@/components/EvalRecentJobsCard.vue'
import OralGenPanel from '@/pages/OralGenPanel.vue'
import UniEvalPage from '@/pages/UniEvalPage.vue'
import ContentEvalPage from '@/pages/ContentEvalPage.vue'
import CombinedEvalPanel from '@/pages/CombinedEvalPanel.vue'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

type OralTab = 'generate' | 'speech' | 'content' | 'combined'

const mainTab = ref<OralTab>('generate')
const genPanelRef = ref<InstanceType<typeof OralGenPanel> | null>(null)
const uniPanelRef = ref<InstanceType<typeof UniEvalPage> | null>(null)
const contentPanelRef = ref<InstanceType<typeof ContentEvalPage> | null>(null)
const combinedPanelRef = ref<InstanceType<typeof CombinedEvalPanel> | null>(null)
const recentCardRef = ref<InstanceType<typeof EvalRecentJobsCard> | null>(null)

function applyTabFromRoute() {
  const tab = route.query.tab
  if (tab === 'generate') mainTab.value = 'generate'
  else if (tab === 'content') mainTab.value = 'content'
  else if (tab === 'combined') mainTab.value = 'combined'
  else if (tab === 'speech') mainTab.value = 'speech'
}

function tabQuery(tab: string) {
  if (tab === 'generate') return { tab: 'generate' }
  if (tab === 'content') return { tab: 'content' }
  if (tab === 'combined') return { tab: 'combined' }
  if (tab === 'speech') return { tab: 'speech' }
  return { tab: 'generate' }
}

function onMainTabChange(key: string) {
  router.replace({ path: '/oral-eval', query: tabQuery(key) })
}

function onJobsChanged() {
  void recentCardRef.value?.loadRecentJobs()
}

async function viewRecentJob(item: EvalRecentJobItem) {
  if (!loginUserStore.loginUser?.id) {
    message.warning('请先登录')
    return
  }
  if (item.kind === 'listening') {
    await router.push({ path: '/listen-eval', query: { job: item.jobId } })
    return
  }
  if (item.kind === 'oral_gen') {
    mainTab.value = 'generate'
    await router.replace({ path: '/oral-eval', query: { tab: 'generate', job: item.jobId } })
    await nextTick()
    try {
      await genPanelRef.value?.loadJob(item.jobId)
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '加载任务失败')
    }
    return
  }
  mainTab.value = item.kind as 'speech' | 'content' | 'combined'
  await router.replace({ path: '/oral-eval', query: { ...tabQuery(item.kind), job: item.jobId } })
  await nextTick()
  try {
    if (item.kind === 'speech') {
      await uniPanelRef.value?.loadJob(item.jobId)
    } else if (item.kind === 'content') {
      await contentPanelRef.value?.loadJob(item.jobId)
    } else {
      await combinedPanelRef.value?.loadJob(item.jobId)
    }
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '加载任务失败')
  }
}

async function loadJobFromRoute() {
  const id = route.query.job
  if (typeof id !== 'string' || !id) return
  applyTabFromRoute()
  await nextTick()
  try {
    if (mainTab.value === 'generate') {
      await genPanelRef.value?.loadJob(id)
    } else if (mainTab.value === 'speech') {
      await uniPanelRef.value?.loadJob(id)
    } else if (mainTab.value === 'content') {
      await contentPanelRef.value?.loadJob(id)
    } else {
      await combinedPanelRef.value?.loadJob(id)
    }
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '加载任务失败')
  }
}

watch(
  () => route.query.tab,
  () => applyTabFromRoute(),
)

watch(
  () => route.query.job,
  () => {
    void loadJobFromRoute()
  },
)

async function handleOralGenImportQuery() {
  const og = route.query.oralGenJob
  if (typeof og !== 'string' || !og) return
  mainTab.value = 'combined'
  await router.replace({ path: '/oral-eval', query: { tab: 'combined' } })
  await nextTick()
  try {
    await combinedPanelRef.value?.importOralGenJob(og, true)
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : '导入失败')
  }
}

onMounted(() => {
  applyTabFromRoute()
  void loadJobFromRoute()
  void handleOralGenImportQuery()
})

watch(
  () => route.query.oralGenJob,
  () => {
    void handleOralGenImportQuery()
  },
)
</script>

<style scoped>
.main-tabs {
  margin-bottom: 8px;
}
</style>
