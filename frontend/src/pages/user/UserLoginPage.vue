<template>
  <div class="user-auth-page">
    <a-card class="user-auth-card" :bordered="false">
      <h2 class="title">用户登录</h2>
      <a-form :model="formState" layout="vertical" @finish="handleSubmit">
        <a-form-item name="userAccount" :rules="[{ required: true, message: '请输入账号' }]">
          <a-input v-model:value="formState.userAccount" placeholder="请输入账号" size="large" />
        </a-form-item>
        <a-form-item
          name="userPassword"
          :rules="[
            { required: true, message: '请输入密码' },
            { min: 8, message: '密码长度不能小于8位' },
          ]"
        >
          <a-input-password
            v-model:value="formState.userPassword"
            placeholder="请输入密码"
            size="large"
          />
        </a-form-item>
        <div class="tips">
          没有账号 <RouterLink to="/user/register">去注册</RouterLink>
        </div>
        <a-form-item>
          <a-button type="primary" html-type="submit" block size="large">登录</a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { userLogin, type UserLoginRequest } from '@/api/userController'
import { useLoginUserStore } from '@/stores/loginUser'

const formState = reactive<UserLoginRequest>({
  userAccount: '',
  userPassword: '',
})

const router = useRouter()
const loginUserStore = useLoginUserStore()

const handleSubmit = async (values: UserLoginRequest) => {
  const res = await userLogin(values)
  if (res.data.code === 0 && res.data.data) {
    await loginUserStore.fetchLoginUser()
    message.success('登录成功')
    router.push({ path: '/oral-eval', replace: true })
  } else {
    message.error('登录失败, ' + res.data.message)
  }
}
</script>

<style scoped>
.user-auth-page {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  min-height: calc(100vh - 64px - 48px);
  padding: 48px 24px;
  box-sizing: border-box;
}

.user-auth-card {
  width: 100%;
  max-width: 400px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.title {
  margin: 0 0 24px;
  text-align: center;
  font-size: 22px;
  font-weight: 600;
}

.tips {
  margin-bottom: 16px;
  color: #666;
  font-size: 13px;
  text-align: right;
}
</style>
