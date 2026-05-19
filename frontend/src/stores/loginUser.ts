import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getLoginUser } from '@/api/userController'

export type LoginUser = {
  id?: string | number
  userName?: string
  userAvatar?: string
  userRole?: string
}

export const useLoginUserStore = defineStore('loginUser', () => {
  const loginUser = ref<LoginUser>({
    userName: '未登录',
  })

  async function fetchLoginUser() {
    try {
      const res = await getLoginUser()
      if (res.data.code === 0 && res.data.data) {
        loginUser.value = res.data.data
      }
    } catch (error) {
      loginUser.value = {
        userName: '未登录',
      }
    }
  }

  function setLoginUser(newLoginUser: any) {
    loginUser.value = newLoginUser
  }

  return {
    loginUser,
    fetchLoginUser,
    setLoginUser,
  }
})
