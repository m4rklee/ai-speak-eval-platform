<template>
  <div class="page-container">
    <div class="page-header">
      <PageTitle
        icon-key="oral-eval"
        title="口语评测"
        subtitle="语音：MultiPA + APG-MOS 发音与自然度；内容：大模型 Judge 三维文本评分（语法 / 主题 / 简洁）"
      />
    </div>

    <a-tabs v-model:activeKey="mainTab" class="main-tabs" @change="onMainTabChange">
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
import UniEvalPage from '@/pages/UniEvalPage.vue'
import ContentEvalPage from '@/pages/ContentEvalPage.vue'
import CombinedEvalPanel from '@/pages/CombinedEvalPanel.vue'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()

const mainTab = ref<'speech' | 'content' | 'combined'>('speech')
const uniPanelRef = ref<InstanceType<typeof UniEvalPage> | null>(null)
const contentPanelRef = ref<InstanceType<typeof ContentEvalPage> | null>(null)
const combinedPanelRef = ref<InstanceType<typeof CombinedEvalPanel> | null>(null)
const recentCardRef = ref<InstanceType<typeof EvalRecentJobsCard> | null>(null)

function applyTabFromRoute() {
  const tab = route.query.tab
  if (tab === 'content') mainTab.value = 'content'
  else if (tab === 'combined') mainTab.value = 'combined'
  else if (tab === 'speech') mainTab.value = 'speech'
}

function tabQuery(tab: string) {
  if (tab === 'content') return { tab: 'content' }
  if (tab === 'combined') return { tab: 'combined' }
  return {}
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
  mainTab.value = item.kind
  await router.replace({ path: '/oral-eval', query: tabQuery(item.kind) })
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
    if (mainTab.value === 'speech') {
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

onMounted(() => {
  applyTabFromRoute()
  void loadJobFromRoute()
})
</script>

<style scoped>
.main-tabs {
  margin-bottom: 8px;
}
</style>
