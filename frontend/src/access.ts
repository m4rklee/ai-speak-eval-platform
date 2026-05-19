import { message } from 'ant-design-vue'
import router from '@/router'
import { useLoginUserStore } from '@/stores/loginUser'

let firstFetchLoginUser = true

router.beforeEach(async (to) => {
  const loginUserStore = useLoginUserStore()
  if (firstFetchLoginUser) {
    try {
      await loginUserStore.fetchLoginUser()
    } finally {
      firstFetchLoginUser = false
    }
  }

  const loginUser = loginUserStore.loginUser
  if (to.fullPath.startsWith('/admin')) {
    if (!loginUser || loginUser.userRole !== 'admin') {
      message.error('没有权限')
      return `/user/login?redirect=${encodeURIComponent(to.fullPath)}`
    }
  }
})
