<template>
  <div id="userRegisterPage">
    <h2 class="title">用户注册</h2>
    <a-form :model="formState" @finish="handleSubmit">
      <a-form-item
        name="userAccount"
        :rules="[
          { required: true, message: '请输入账号' },
          { min: 4, message: '账号长度不能小于4位' },
        ]"
      >
        <a-input v-model:value="formState.userAccount" placeholder="请输入账号" />
      </a-form-item>

      <a-form-item
        name="userPassword"
        :rules="[
          { required: true, message: '请输入密码' },
          { min: 8, message: '密码长度不能小于8位' },
        ]"
      >
        <a-input-password v-model:value="formState.userPassword" placeholder="请输入密码" />
      </a-form-item>

      <a-form-item
        name="checkPassword"
        :rules="[
          { required: true, message: '请确认密码' },
          { min: 8, message: '确认密码长度不能小于8位' },
          { validator: validateCheckPassword },
        ]"
      >
        <a-input-password v-model:value="formState.checkPassword" placeholder="请再次输入密码" />
      </a-form-item>

      <div class="tips">已有账号 <RouterLink to="/user/login">去登录</RouterLink></div>

      <a-form-item>
        <a-button type="primary" html-type="submit" :loading="submitting" style="width: 100%">
          注册
        </a-button>
      </a-form-item>
    </a-form>
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
#userRegisterPage {
  width: 360px;
  max-width: calc(100vw - 48px);
  margin: 48px auto;
}

.title {
  margin-bottom: 24px;
  text-align: center;
}

.tips {
  margin-bottom: 16px;
  color: #666;
  font-size: 13px;
  text-align: right;
}
</style>
