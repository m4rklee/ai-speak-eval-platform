<template>
  <a-layout-header class="header">
    <a-row :wrap="false">
      <a-col flex="240px">
        <RouterLink to="/oral-eval" class="brand-link">
          <div class="header-left">
            <AppLogo :size="36" />
            <div class="brand-text">
              <span class="site-title">AI 评测平台</span>
              <span class="site-tagline">语音 · 听力 · 模型评测</span>
            </div>
          </div>
        </RouterLink>
      </a-col>
      <a-col flex="auto">
        <a-menu
          v-model:selectedKeys="selectedKeys"
          mode="horizontal"
          :items="menuItems"
          @click="handleMenuClick"
        />
      </a-col>
      <a-col>
        <div class="user-login-status">
          <div v-if="loginUserStore.loginUser.id">
            <a-dropdown>
              <a-space>
                <a-avatar :src="loginUserStore.loginUser.userAvatar" />
                {{ loginUserStore.loginUser.userName ?? '无名' }}
              </a-space>
              <template #overlay>
                <a-menu>
                  <a-menu-item @click="doLogout">
                    <LogoutOutlined />
                    退出登录
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
          <div v-else>
            <a-button type="primary" href="/user/login">登录</a-button>
          </div>
        </div>
      </a-col>
    </a-row>
  </a-layout-header>
</template>
<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { type MenuProps, message } from 'ant-design-vue'
import { useLoginUserStore } from '@/stores/loginUser.ts'
import { userLogout } from '@/api/userController.ts'
import { LogoutOutlined } from '@ant-design/icons-vue'
import AppLogo from '@/components/AppLogo.vue'
import { PAGE_ICON_META, type PageIconKey } from '@/constants/pageIcons'

const MENU_ICON_KEYS: Record<string, PageIconKey> = {
  '/oral-eval': 'oral-eval',
  '/listen-eval': 'listen-eval',
  '/models': 'models',
  '/side-by-side': 'side-by-side',
  '/prompt-lab': 'prompt-lab',
  '/scenario': 'scenario',
  '/admin/userManage': 'user-manage',
}

function menuIcon(key: string) {
  const iconKey = MENU_ICON_KEYS[key]
  if (!iconKey) return undefined
  const { icon } = PAGE_ICON_META[iconKey]
  return () => h(icon)
}

const loginUserStore = useLoginUserStore()
const router = useRouter()
const route = useRoute()

const NAV_PATHS = [
  '/oral-eval',
  '/listen-eval',
  '/models',
  '/side-by-side',
  '/prompt-lab',
  '/scenario',
  '/admin/userManage',
]

const selectedKeys = ref<string[]>(['/oral-eval'])

function resolveSelectedKey(path: string): string {
  if (path === '/' || path === '/content-eval') return '/oral-eval'
  if (NAV_PATHS.includes(path)) return path
  if (path.startsWith('/admin')) return '/admin/userManage'
  return '/oral-eval'
}

router.afterEach((to) => {
  selectedKeys.value = [resolveSelectedKey(to.path)]
})

selectedKeys.value = [resolveSelectedKey(route.path)]

const MENU_LABELS: Record<string, string> = {
  '/oral-eval': '口语评测',
  '/listen-eval': '听力评测',
  '/models': '模型库',
  '/side-by-side': '模型对比',
  '/prompt-lab': 'Prompt Lab',
  '/scenario': '场景管理',
  '/admin/userManage': '用户管理',
}

const originItems: MenuProps['items'] = Object.entries(MENU_LABELS).map(([key, label]) => ({
  key,
  icon: menuIcon(key),
  label,
  title: label,
}))

const filterMenus = (menus = [] as MenuProps['items']) => {
  return menus?.filter((menu) => {
    const menuKey = menu?.key as string
    if (menuKey?.startsWith('/admin')) {
      const loginUser = loginUserStore.loginUser
      if (!loginUser || loginUser.userRole !== 'admin') {
        return false
      }
    }
    return true
  })
}

const menuItems = computed<MenuProps['items']>(() => filterMenus(originItems))

const handleMenuClick: MenuProps['onClick'] = (e) => {
  const key = e.key as string
  if (key.startsWith('/')) {
    selectedKeys.value = [key]
    router.push(key)
  }
}

const doLogout = async () => {
  const res = await userLogout()
  if (res.data.code === 0) {
    loginUserStore.setLoginUser({
      userName: '未登录',
    })
    message.success('退出登录成功')
    await router.push('/user/login')
  } else {
    message.error('退出登录失败, ' + res.data.message)
  }
}
</script>

<style scoped>
.header {
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  padding: 0 24px;
}

.brand-link {
  color: inherit;
  text-decoration: none;
}

.brand-link:hover .site-title {
  color: #1677ff;
}

.header-left {
  display: flex;
  align-items: center;
  height: 64px;
  gap: 10px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.site-title {
  margin: 0;
  color: #1f1f1f;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.2;
  transition: color 0.2s;
}

.site-tagline {
  color: #8c8c8c;
  font-size: 11px;
  line-height: 1;
  letter-spacing: 0.02em;
}

.user-login-status {
  display: flex;
  align-items: center;
  height: 64px;
}
</style>
