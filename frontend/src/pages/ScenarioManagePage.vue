<template>
  <div class="page-container">
    <div class="page-header page-header--toolbar">
      <div class="page-header-main">
        <PageTitle
          icon-key="scenario"
          title="场景管理"
          subtitle="管理系统预设与自定义评测场景及题目"
        />
      </div>
      <a-button type="primary" @click="openCreateModal">新建场景</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="scenarios"
      :loading="loading"
      row-key="id"
      :pagination="false"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'sourceType'">
          <a-tag :color="record.sourceType === 'system' ? 'blue' : 'green'">
            {{ record.sourceType === 'system' ? '系统预设' : '自定义' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="openDetail(record)">查看</a-button>
            <template v-if="record.sourceType === 'custom'">
              <a-button type="link" size="small" @click="openEditModal(record)">编辑</a-button>
              <a-button type="link" size="small" @click="openImport(record)">导入</a-button>
              <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </template>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="formModalOpen"
      :title="editingId ? '编辑场景' : '新建场景'"
      @ok="handleSaveScenario"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="场景名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="3" />
        </a-form-item>
        <a-form-item label="分类">
          <a-input v-model:value="form.category" placeholder="如 general / coding" />
        </a-form-item>
      </a-form>
    </a-modal>

    <input
      ref="fileInputRef"
      type="file"
      accept=".json,application/json"
      style="display: none"
      @change="handleFileImport"
    />

    <a-drawer
      v-model:open="detailOpen"
      :title="detailScenario?.name || '场景详情'"
      width="720"
    >
      <p v-if="detailScenario?.description" class="desc">{{ detailScenario.description }}</p>
      <a-table
        :columns="itemColumns"
        :data-source="detailItems"
        :loading="detailLoading"
        row-key="id"
        size="small"
        :pagination="itemPagination"
        @change="onItemTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'prompt'">
            <span class="ellipsis">{{ record.prompt }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-popconfirm
              v-if="detailScenario?.sourceType === 'custom'"
              title="确定删除该用例？"
              @confirm="handleDeleteItem(record.id)"
            >
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import PageTitle from '@/components/PageTitle.vue'
import { message } from 'ant-design-vue'
import {
  addScenario,
  deleteScenario,
  deleteScenarioItem,
  importScenarioItems,
  listScenarioItems,
  listScenarios,
  updateScenario,
  type ScenarioItemVO,
  type ScenarioVO,
} from '@/api/scenarioController'

const loading = ref(false)
const scenarios = ref<ScenarioVO[]>([])
const formModalOpen = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({ name: '', description: '', category: '' })
const fileInputRef = ref<HTMLInputElement>()
const importTargetId = ref<string | null>(null)

const detailOpen = ref(false)
const detailScenario = ref<ScenarioVO | null>(null)
const detailItems = ref<ScenarioItemVO[]>([])
const detailLoading = ref(false)
const itemPagination = reactive({ current: 1, pageSize: 10, total: 0 })

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '来源', key: 'sourceType' },
  { title: '分类', dataIndex: 'category', key: 'category' },
  { title: '用例数', dataIndex: 'itemCount', key: 'itemCount' },
  { title: '操作', key: 'action', width: 280 },
]

const itemColumns = [
  { title: '提示词', key: 'prompt', ellipsis: true },
  { title: '期望答案', dataIndex: 'expectedAnswer', ellipsis: true },
  { title: '分类', dataIndex: 'category', width: 100 },
  { title: '操作', key: 'action', width: 80 },
]

const loadScenarios = async () => {
  loading.value = true
  try {
    const res = await listScenarios()
    if (res.data.code === 0) {
      scenarios.value = res.data.data || []
    }
  } catch {
    message.error('加载场景失败')
  } finally {
    loading.value = false
  }
}

const openCreateModal = () => {
  editingId.value = null
  form.name = ''
  form.description = ''
  form.category = ''
  formModalOpen.value = true
}

const openEditModal = (record: ScenarioVO) => {
  editingId.value = record.id
  form.name = record.name
  form.description = record.description || ''
  form.category = record.category || ''
  formModalOpen.value = true
}

const handleSaveScenario = async () => {
  if (!form.name.trim()) {
    message.warning('请输入场景名称')
    return
  }
  try {
    if (editingId.value) {
      const res = await updateScenario(editingId.value, {
        name: form.name,
        description: form.description,
        category: form.category,
      })
      if (res.data.code === 0) message.success('更新成功')
    } else {
      const res = await addScenario({
        name: form.name,
        description: form.description,
        category: form.category,
      })
      if (res.data.code === 0) message.success('创建成功')
    }
    formModalOpen.value = false
    await loadScenarios()
  } catch {
    message.error('保存失败')
  }
}

const handleDelete = async (id: string) => {
  const res = await deleteScenario(id)
  if (res.data.code === 0) {
    message.success('已删除')
    await loadScenarios()
  }
}

const openImport = (record: ScenarioVO) => {
  importTargetId.value = record.id
  fileInputRef.value?.click()
}

const handleFileImport = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !importTargetId.value) return
  try {
    const text = await file.text()
    const items = JSON.parse(text)
    if (!Array.isArray(items)) throw new Error('JSON 须为数组')
    const res = await importScenarioItems(importTargetId.value, items)
    if (res.data.code === 0) {
      message.success(`成功导入 ${res.data.data} 条用例`)
      await loadScenarios()
    } else {
      message.error(res.data.message || '导入失败')
    }
  } catch (err: unknown) {
    message.error(err instanceof Error ? err.message : 'JSON 解析失败')
  }
}

const openDetail = async (record: ScenarioVO) => {
  detailScenario.value = record
  detailOpen.value = true
  itemPagination.current = 1
  await loadDetailItems()
}

const loadDetailItems = async () => {
  if (!detailScenario.value) return
  detailLoading.value = true
  try {
    const res = await listScenarioItems(
      detailScenario.value.id,
      itemPagination.current,
      itemPagination.pageSize,
    )
    if (res.data.code === 0 && res.data.data) {
      detailItems.value = res.data.data.records
      itemPagination.total = res.data.data.total
    }
  } finally {
    detailLoading.value = false
  }
}

const onItemTableChange = (pag: { current?: number }) => {
  itemPagination.current = pag.current || 1
  loadDetailItems()
}

const handleDeleteItem = async (itemId: string) => {
  const res = await deleteScenarioItem(itemId)
  if (res.data.code === 0) {
    message.success('已删除')
    await loadDetailItems()
    await loadScenarios()
  }
}

onMounted(loadScenarios)
</script>

<style scoped>
.desc {
  color: #666;
  margin-bottom: 16px;
}
.ellipsis {
  display: block;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
