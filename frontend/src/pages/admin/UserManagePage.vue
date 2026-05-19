<template>
  <div id="userManagePage" class="page-container">
    <div class="page-header">
      <PageTitle
        icon-key="user-manage"
        title="用户管理"
        subtitle="管理平台用户账号、角色与权限"
      />
    </div>
    <!-- 搜索表单 -->
    <a-card class="page-section" size="small">
    <a-form layout="inline" :model="searchParams" @finish="doSearch">
      <a-form-item label="账号">
        <a-input v-model:value="searchParams.userAccount" placeholder="输入账号" />
      </a-form-item>
      <a-form-item label="用户名">
        <a-input v-model:value="searchParams.userName" placeholder="输入用户名" />
      </a-form-item>
      <a-form-item>
        <a-button type="primary" html-type="submit">搜索</a-button>
      </a-form-item>
    </a-form>
    </a-card>
    <!-- 表格 -->
    <a-table
      class="page-section"
      :columns="columns"
      :data-source="data"
      :pagination="pagination"
      @change="doTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'userAvatar'">
          <a-image :src="record.userAvatar" :width="120" />
        </template>
        <template v-else-if="column.dataIndex === 'userRole'">
          <div v-if="record.userRole === 'admin'">
            <a-tag color="green">管理员</a-tag>
          </div>
          <div v-else>
            <a-tag color="blue">普通用户</a-tag>
          </div>
        </template>
        <template v-else-if="column.dataIndex === 'createTime'">
          {{ dayjs(record.createTime).format('YYYY-MM-DD HH:mm:ss') }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button danger @click="doDelete(record.id)">删除</a-button>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import PageTitle from '@/components/PageTitle.vue'
import dayjs from 'dayjs'
import type { TablePaginationConfig, TableProps } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { deleteUser, listUserVoByPage, type UserVO } from '@/api/userController'

const searchParams = reactive({
  current: 1,
  pageSize: 10,
  userAccount: '',
  userName: '',
})

const data = ref<UserVO[]>([])
const total = ref(0)

const columns = [
  {
    title: '账号',
    dataIndex: 'userAccount',
  },
  {
    title: '用户名',
    dataIndex: 'userName',
  },
  {
    title: '头像',
    dataIndex: 'userAvatar',
  },
  {
    title: '角色',
    dataIndex: 'userRole',
  },
  {
    title: '创建时间',
    dataIndex: 'createTime',
  },
  {
    title: '操作',
    key: 'action',
  },
]

const pagination = computed<TablePaginationConfig>(() => ({
  current: searchParams.current,
  pageSize: searchParams.pageSize,
  total: total.value,
  showSizeChanger: true,
}))

const loadData = async () => {
  const res = await listUserVoByPage({ ...searchParams })
  if (res.data.code === 0) {
    data.value = res.data.data.records ?? []
    total.value = res.data.data.total ?? 0
  } else {
    message.error('加载用户失败, ' + res.data.message)
  }
}

const doSearch = () => {
  searchParams.current = 1
  loadData()
}

const doTableChange: TableProps['onChange'] = (page) => {
  searchParams.current = page.current ?? 1
  searchParams.pageSize = page.pageSize ?? 10
  loadData()
}

const doDelete = async (id: string | number) => {
  const res = await deleteUser({ id })
  if (res.data.code === 0) {
    message.success('删除成功')
    loadData()
  } else {
    message.error('删除失败, ' + res.data.message)
  }
}

onMounted(() => {
  loadData()
})
</script>
