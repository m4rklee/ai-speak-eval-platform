import { createRouter, createWebHistory } from 'vue-router'
import UserLoginPage from '@/pages/user/UserLoginPage.vue'
import UserRegisterpage from '@/pages/user/UserRegisterpage.vue'
import UserManagePage from '@/pages/admin/UserManagePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/oral-eval',
    },
    {
      path: '/oral-eval',
      name: 'OralEval',
      component: () => import('@/pages/OralEvalPage.vue'),
      meta: { title: '口语评测' },
    },
    {
      path: '/listen-eval',
      name: 'ListenEval',
      component: () => import('@/pages/ListenEvalPage.vue'),
      meta: { title: '听力评测' },
    },
    {
      path: '/content-eval',
      redirect: { path: '/oral-eval', query: { tab: 'content' } },
    },
    {
      path: '/models',
      name: 'ModelCatalogPage',
      component: () => import('@/pages/ModelCatalogPage.vue'),
      meta: { title: '模型库' },
    },
    {
      path: '/side-by-side',
      name: 'SideBySidePage',
      component: () => import('@/pages/SideBySidePage.vue'),
      meta: { title: '模型对比' },
    },
    {
      path: '/prompt-lab',
      name: 'PromptLabPage',
      component: () => import('@/pages/PromptLabPage.vue'),
      meta: { title: 'Prompt Lab' },
    },
    {
      path: '/scenario',
      name: 'ScenarioManagePage',
      component: () => import('@/pages/ScenarioManagePage.vue'),
      meta: { title: '场景管理' },
    },
    {
      path: '/admin/userManage',
      name: '用户管理',
      component: UserManagePage,
    },
    {
      path: '/user/login',
      name: '用户登录',
      component: UserLoginPage,
    },
    {
      path: '/user/register',
      name: '用户注册',
      component: UserRegisterpage,
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/oral-eval',
    },
  ],
})

export default router
