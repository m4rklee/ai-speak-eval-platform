<template>
  <div class="page-container">
    <div class="page-header page-header--toolbar">
      <div class="page-header-main">
        <PageTitle
          icon-key="models"
          title="模型库"
          subtitle="浏览与筛选平台模型，支持按输入/输出模态过滤"
        />
      </div>
      <a-space v-if="isAdmin">
        <a-button :loading="syncing === 'openrouter'" @click="handleSync('openrouter')">
          同步 OpenRouter
        </a-button>
        <a-button :loading="syncing === 'aihubmix'" @click="handleSync('aihubmix')">
          同步 AiHubMix
        </a-button>
      </a-space>
    </div>

    <a-card class="page-section filter-card">
      <a-form layout="inline">
        <a-form-item label="平台">
          <a-select v-model:value="filters.platform" allow-clear style="width: 140px" @change="load">
            <a-select-option value="openrouter">OpenRouter</a-select-option>
            <a-select-option value="aihubmix">AiHubMix</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="输入模态">
          <a-select v-model:value="filters.inputModality" allow-clear style="width: 120px" @change="load">
            <a-select-option value="text">文本</a-select-option>
            <a-select-option value="audio">音频</a-select-option>
            <a-select-option value="image">图片</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="输出模态">
          <a-select v-model:value="filters.outputModality" allow-clear style="width: 120px" @change="load">
            <a-select-option value="text">文本</a-select-option>
            <a-select-option value="audio">音频</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键词">
          <a-input v-model:value="filters.keyword" placeholder="模型名" allow-clear @pressEnter="load" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="load">查询</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-table
      :columns="columns"
      :data-source="models"
      :loading="loading"
      row-key="id"
      :pagination="{ pageSize: 20, showSizeChanger: true }"
      size="small"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'platform'">
          <a-space wrap>
            <a-tag v-for="p in platformTags(record)" :key="p" :color="p === 'openrouter' ? 'blue' : 'purple'">
              {{ p }}
            </a-tag>
          </a-space>
        </template>
        <template v-else-if="column.key === 'inputModalities'">
          <a-space wrap>
            <a-tag v-for="m in record.inputModalities || []" :key="m" color="blue">{{ m }}</a-tag>
          </a-space>
        </template>
        <template v-else-if="column.key === 'outputModalities'">
          <a-space wrap>
            <a-tag v-for="m in record.outputModalities || []" :key="m" color="green">{{ m }}</a-tag>
          </a-space>
        </template>
        <template v-else-if="column.key === 'inputPrice'">
          {{ formatPrice(record.inputPrice) }}
        </template>
        <template v-else-if="column.key === 'outputPrice'">
          {{ formatPrice(record.outputPrice) }}
        </template>
        <template v-else-if="column.key === 'releasedAt'">
          {{ formatDate(record.releasedAt) }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import PageTitle from '@/components/PageTitle.vue'
import { message } from 'ant-design-vue'
import { listModels, syncModels, type ModelVO } from '@/api/modelController'
import { useLoginUserStore } from '@/stores/loginUser'

const loginUserStore = useLoginUserStore()
const isAdmin = computed(() => loginUserStore.loginUser.userRole === 'admin')

const loading = ref(false)
const syncing = ref('')
const models = ref<ModelVO[]>([])
const filters = reactive({
  platform: undefined as string | undefined,
  inputModality: undefined as string | undefined,
  outputModality: undefined as string | undefined,
  keyword: '',
  sortBy: 'name' as string,
  sortOrder: 'asc' as 'asc' | 'desc',
})

type SortableKey = 'inputPrice' | 'outputPrice' | 'releasedAt' | 'contextLength'

const sortState = reactive<{ field?: SortableKey; order?: 'ascend' | 'descend' }>({})

const colSort = (field: SortableKey) => ({
  key: field,
  sortOrder: sortState.field === field ? sortState.order : undefined,
  sorter: true,
  showSorterTooltip: { title: '点击切换升序/降序' },
})

const columns = computed(() => [
  { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true, width: 200 },
  { title: 'ID', dataIndex: 'id', key: 'id', ellipsis: true, width: 180 },
  { title: '平台', key: 'platform', width: 100 },
  { title: '输入模态', key: 'inputModalities', width: 140 },
  { title: '输出模态', key: 'outputModalities', width: 120 },
  { title: '输入价格/1M', dataIndex: 'inputPrice', width: 120, ...colSort('inputPrice') },
  { title: '输出价格/1M', dataIndex: 'outputPrice', width: 120, ...colSort('outputPrice') },
  { title: '发布时间', dataIndex: 'releasedAt', width: 120, ...colSort('releasedAt') },
  { title: '上下文', dataIndex: 'contextLength', width: 100, ...colSort('contextLength') },
])

const formatPrice = (p?: string | number) => {
  if (p == null) return '—'
  const n = Number(p)
  return Number.isFinite(n) ? `$${n.toFixed(4)}` : '—'
}

const formatDate = (d?: string) => {
  if (!d) return '—'
  return d.slice(0, 10)
}

const platformTags = (record: ModelVO) => {
  if (record.platforms?.length) return record.platforms
  return record.platform.split(',').map((p) => p.trim()).filter(Boolean)
}

const onTableChange = (
  _pag: unknown,
  _filters: unknown,
  sorter: { columnKey?: string; field?: string; order?: 'ascend' | 'descend' } | Array<{
    columnKey?: string
    field?: string
    order?: 'ascend' | 'descend'
  }>
) => {
  const s = Array.isArray(sorter) ? sorter.find((x) => x.order) ?? sorter[0] : sorter
  const field = (s?.columnKey ?? s?.field) as SortableKey | undefined
  if (!field || !s?.order) {
    sortState.field = undefined
    sortState.order = undefined
    filters.sortBy = 'name'
    filters.sortOrder = 'asc'
    load()
    return
  }
  sortState.field = field
  sortState.order = s.order
  filters.sortBy = field
  filters.sortOrder = s.order === 'descend' ? 'desc' : 'asc'
  load()
}

const load = async () => {
  loading.value = true
  try {
    const res = await listModels({
      platform: filters.platform,
      inputModality: filters.inputModality,
      outputModality: filters.outputModality,
      keyword: filters.keyword || undefined,
      sortBy: sortState.field ? filters.sortBy : 'name',
      sortOrder: sortState.field ? filters.sortOrder : 'asc',
    })
    if (res.data.code === 0) models.value = res.data.data || []
  } catch {
    message.error('加载模型失败')
  } finally {
    loading.value = false
  }
}

const handleSync = async (platform: 'openrouter' | 'aihubmix') => {
  syncing.value = platform
  try {
    const res = await syncModels(platform)
    if (res.data.code === 0) {
      const n = res.data.data?.[platform] ?? Object.values(res.data.data || {})[0]
      message.success(`同步完成，共 ${n ?? 0} 个模型`)
      await load()
    } else {
      message.error(res.data.message || '同步失败')
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } }; message?: string }
    message.error(err.response?.data?.message || err.message || '同步失败')
  } finally {
    syncing.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.filter-card {
  margin-bottom: 0;
}
</style>
