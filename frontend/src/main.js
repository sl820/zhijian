import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import App from './App.vue'
import AppErrorBoundary from './components/AppErrorBoundary.vue'
import router from './router'
import { scriptoriumTheme } from './styles/echarts-theme'
import 'element-plus/dist/index.css'
import './styles/global.css'

const app = createApp(App)
const pinia = createPinia()

// 注册ECharts古书房主题
echarts.registerTheme('scriptorium', scriptoriumTheme)

// 注册所有Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 注册全局错误边界组件
app.component('AppErrorBoundary', AppErrorBoundary)

// 全局错误处理（兜底：errorCaptured 没拦住的错误在这里打印）
// 不阻断 → 让用户继续用，只是控制台有提示
app.config.errorHandler = (err, instance, info) => {
  // AppErrorBoundary 已处理过（errorCaptured 会先于 errorHandler 触发），
  // 这里只处理 boundary 之外的错误（如异步 Promise / 全局事件回调）
  if (import.meta.env.DEV) {
    console.groupCollapsed('[Vue errorHandler] uncaught')
    console.error(err)
    console.error('Vue info:', info)
    console.error('Component:', instance)
    console.groupEnd()
  }
}

// 全局未捕获 Promise rejection → 避免控制台一片红
window.addEventListener('unhandledrejection', (event) => {
  if (import.meta.env.DEV) {
    console.warn('[unhandledrejection]', event.reason)
  }
  // 阻止默认红字（Chrome devtools "Uncaught (in promise)"）
  event.preventDefault()
})

app.use(pinia)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
