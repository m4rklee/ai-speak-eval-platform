<template>
  <div class="user-auth-page">
    <a-card class="user-auth-card" :bordered="false">
      <h2 class="title">用户注册</h2>
      <a-form :model="formState" layout="vertical" @finish="handleSubmit">
      <a-form-item
        name="userAccount"
        :rules="[
          { required: true, message: '请输入账号' },
          { min: 4, message: '账号长度不能小于4位' },
        ]"
      >
        <a-input v-model:value="formState.userAccount" placeholder="请输入账号" size="large" />
      </a-form-item>

      <a-form-item
        name="userPassword"
        :rules="[
          { required: true, message: '请输入密码' },
          { min: 8, message: '密码长度不能小于8位' },
        ]"
      >
        <a-input-password v-model:value="formState.userPassword" placeholder="请输入密码" size="large" />
      </a-form-item>

      <a-form-item
        name="checkPassword"
        :rules="[
          { required: true, message: '请确认密码' },
          { min: 8, message: '确认密码长度不能小于8位' },
          { validator: validateCheckPassword },
        ]"
      >
        <a-input-password
          v-model:value="formState.checkPassword"
          placeholder="请再次输入密码"
          size="large"
        />
      </a-form-item>

      <div class="tips">已有账号 <RouterLink to="/user/login">去登录</RouterLink></div>

      <a-form-item>
        <a-button type="primary" html-type="submit" :loading="submitting" block size="large">
          注册
        </a-button>
      </a-form-item>
    </a-form>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { userRegister, type UserRegisterRequest } from '@/api/userController'

const router = useRouter()
const submitting = ref(false)

const formState = reactive<UserRegisterRequest>({
  userAccount: '',
  userPassword: '',
  checkPassword: '',
})

const validateCheckPassword = async () => {
  if (formState.checkPassword && formState.checkPassword !== formState.userPassword) {
    return Promise.reject('两次输入的密码不一致')
  }
  return Promise.resolve()
}

const handleSubmit = async (values: UserRegisterRequest) => {
  submitting.value = true
  try {
    const res = await userRegister(values)
    if (res.data.code === 0) {
      message.success('注册成功，请登录')
      await router.push('/user/login')
    } else {
      message.error('注册失败, ' + res.data.message)
    }
  } finally {
    submitting.value = false
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
