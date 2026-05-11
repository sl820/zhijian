import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue') },
  { path: '/collation', name: 'Collation', component: () => import('../views/CollationView.vue') },
  { path: '/compilation', name: 'Compilation', component: () => import('../views/CompilationView.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('../views/KnowledgeView.vue') },
  { path: '/qa', name: 'QA', component: () => import('../views/QAView.vue') },
  { path: '/map', name: 'Map', component: () => import('../views/MapView.vue') },
  { path: '/annotation', name: 'Annotation', component: () => import('../views/AnnotationView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
