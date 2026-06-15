import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue') },
  { path: '/ocr', name: 'OCR', component: () => import('../views/OCRView.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('../views/KnowledgeView.vue') },
  { path: '/qa', name: 'QA', component: () => import('../views/QAView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
