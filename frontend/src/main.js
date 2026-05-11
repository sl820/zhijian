import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import App from './App.vue'
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

app.use(pinia)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
