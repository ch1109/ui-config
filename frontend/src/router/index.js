import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/intent',
    name: 'IntentConfig',
    component: () => import('@/views/IntentConfig.vue'),
    meta: { title: '意图配置' }
  },
  {
    path: '/',
    name: 'PageList',
    component: () => import('@/views/PageList.vue'),
    meta: { title: '页面配置' }
  },
  {
    path: '/page/new',
    name: 'PageCreate',
    component: () => import('@/views/PageEditor.vue'),
    meta: { title: '添加页面' }
  },
  {
    path: '/page/:id',
    name: 'PageEdit',
    component: () => import('@/views/PageEditor.vue'),
    meta: { title: '编辑页面' }
  },
  {
    path: '/system-prompt',
    name: 'SystemPrompt',
    component: () => import('@/views/SystemPromptConfig.vue'),
    meta: { title: '提示词配置' }
  },
  {
    path: '/mcp',
    name: 'MCPManager',
    component: () => import('@/views/MCPManager.vue'),
    meta: { title: 'MCP 服务器管理' }
  },
  {
    path: '/mcp-host',
    name: 'MCPHost',
    component: () => import('@/views/MCPHostPage.vue'),
    meta: { title: 'MCP Host 对话' }
  },
  {
    path: '/sampling',
    name: 'Sampling',
    component: () => import('@/views/SamplingPage.vue'),
    meta: { title: 'MCP Sampling 管理' }
  }
  // 已合并到 MCPManager.vue:
  // - /mcp-test (MCP 功能测试)
  // - /mcp-real (真实 MCP 测试)
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫 - 设置页面标题
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'UI Config'} - UI Config 智能配置系统`
  next()
})

export default router

