<template>
  <div class="job-display-name-edit">
    <template v-if="!editing">
      <span class="job-display-name-edit__label">任务名称</span>
      <span class="job-display-name-edit__text">{{ title }}</span>
      <a-button type="link" size="small" @click="startEdit">编辑</a-button>
    </template>
    <template v-else>
      <span class="job-display-name-edit__label">任务名称</span>
      <a-input
        v-model:value="draft"
        :maxlength="64"
        size="small"
        class="job-display-name-edit__input"
        placeholder="1–64 字符"
        @press-enter="save"
      />
      <a-button type="link" size="small" :loading="saving" @click="save">保存</a-button>
      <a-button type="link" size="small" :disabled="saving" @click="cancel">取消</a-button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'

const props = defineProps<{
  jobId: string
  displayName?: string | null
  onSave: (name: string) => Promise<void>
}>()

const emit = defineEmits<{ saved: [name: string] }>()

const editing = ref(false)
const saving = ref(false)
const draft = ref('')

function formatJobId(id: string) {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id
}

const title = computed(() => props.displayName?.trim() || formatJobId(props.jobId))

watch(
  () => props.displayName,
  () => {
    if (!editing.value) draft.value = props.displayName?.trim() || ''
  },
)

function startEdit() {
  draft.value = props.displayName?.trim() || ''
  editing.value = true
}

function cancel() {
  editing.value = false
  draft.value = props.displayName?.trim() || ''
}

async function save() {
  const name = draft.value.trim()
  if (!name) {
    message.warning('任务名称不能为空')
    return
  }
  saving.value = true
  try {
    await props.onSave(name)
    editing.value = false
    emit('saved', name)
    message.success('任务名称已更新')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '更新失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.job-display-name-edit {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 8px;
  margin-bottom: 12px;
}
.job-display-name-edit__label {
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}
.job-display-name-edit__text {
  font-weight: 500;
}
.job-display-name-edit__input {
  width: min(280px, 100%);
}
</style>
