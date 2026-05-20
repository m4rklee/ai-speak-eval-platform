import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import '@/styles/page-layout.css'

import '@/access'

/** Ant Design Table 等触发的 ResizeObserver 循环告警（浏览器已知问题，不影响功能） */
const resizeObserverLoopRe =
  /ResizeObserver loop (completed with undelivered notifications|limit exceeded)/

window.addEventListener(
  'error',
  (event) => {
    if (event.message && resizeObserverLoopRe.test(event.message)) {
      event.stopImmediatePropagation()
    }
  },
  true,
)

const NativeResizeObserver = window.ResizeObserver
window.ResizeObserver = class extends NativeResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    super((entries, observer) => {
      window.requestAnimationFrame(() => callback(entries, observer))
    })
  }
}

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(Antd)

app.mount('#app')
