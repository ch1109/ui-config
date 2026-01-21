<template>
  <div class="page-config-container">
    <!-- 顶部 Header -->
    <header class="top-header">
      <div class="header-left">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 18l2-2v-3m0-6V4l-2-2H8L6 4v3m0 6v3l2 2h8"/>
            <path d="M10 9h4"/>
            <path d="M10 13h2"/>
          </svg>
        </div>
        <div class="header-title">
          <h1>界面配置</h1>
          <span class="sync-time">已同步 ({{ syncTime }})</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="action-btn code-btn" title="查看代码" @click="handleCodeView">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>
          </svg>
        </button>
        <button class="action-btn" @click="handleImport">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          导入
        </button>
        <button class="action-btn" @click="handleExport">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出
        </button>
        <button class="action-btn" @click="handlePull">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v12m0 0l-4-4m4 4l4-4"/>
            <path d="M3 15v4a2 2 0 002 2h14a2 2 0 002-2v-4"/>
          </svg>
          拉取
        </button>
        <button class="action-btn primary-btn" @click="handlePush">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 19V7m0 0l-4 4m4-4l4 4"/>
            <path d="M5 12H3a2 2 0 00-2 2v5a2 2 0 002 2h18a2 2 0 002-2v-5a2 2 0 00-2-2h-2"/>
          </svg>
          推送
        </button>
      </div>
    </header>

    <!-- 主体内容区 -->
    <div class="main-body">
      <!-- 左侧项目列表 -->
      <aside class="project-sidebar">
        <!-- 搜索项目 -->
        <div class="sidebar-search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/>
          </svg>
          <input 
            v-model="projectSearchQuery"
            type="text"
            placeholder="搜索项目..."
            class="search-input"
          />
        </div>

        <!-- 添加新项目按钮 -->
        <button class="add-project-btn" @click="openProjectModal()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 4v16m-8-8h16"/>
          </svg>
          添加新项目
        </button>

        <!-- 项目列表 -->
        <div class="project-list">
          <div 
            v-for="project in filteredProjects" 
            :key="project.id"
            :class="['project-item', { active: currentProjectId === project.id }]"
            @click="selectProject(project)"
          >
            <div class="project-info">
              <h4 class="project-name">{{ project.name }}</h4>
              <p class="project-id">ID: {{ project.project_id }}</p>
              <p class="project-pages">{{ project.page_count || 0 }} 页面</p>
            </div>
            <div class="project-actions" @click.stop>
              <button class="project-action-btn" @click="openProjectModal(project)" title="编辑">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
              <button class="project-action-btn delete" @click="deleteProject(project)" title="删除">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="filteredProjects.length === 0" class="empty-projects">
            <p>暂无项目</p>
          </div>
        </div>
      </aside>

      <!-- 右侧页面列表 -->
      <main class="page-main">
        <!-- 顶部筛选栏 -->
        <div class="page-toolbar">
          <div class="filter-tabs">
            <button 
              v-for="tab in statusTabs" 
              :key="tab.value"
              :class="['filter-tab', { active: currentStatus === tab.value }]"
              @click="currentStatus = tab.value"
            >
              {{ tab.label }} {{ getStatusCount(tab.value) }}
            </button>
          </div>

          <div class="toolbar-right">
            <div class="search-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.35-4.35"/>
              </svg>
              <input 
                v-model="searchQuery"
                type="text"
                placeholder="搜索页面..."
                class="search-input"
              />
            </div>

            <button class="add-page-btn" @click="goToCreate">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 4v16m-8-8h16"/>
              </svg>
              添加新页面
            </button>
          </div>
        </div>

        <!-- 页面内容区 -->
        <div class="page-content">
          <!-- 加载状态 -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>加载中...</p>
          </div>

          <!-- 空状态 -->
          <div v-else-if="filteredPages.length === 0" class="empty-state">
            <div class="empty-illustration">
              <svg viewBox="0 0 200 200" fill="none">
                <circle cx="100" cy="100" r="80" fill="#f1f5f9"/>
                <rect x="60" y="50" width="80" height="100" rx="8" fill="#e2e8f0"/>
                <rect x="70" y="65" width="40" height="6" rx="3" fill="#cbd5e1"/>
                <rect x="70" y="80" width="60" height="6" rx="3" fill="#cbd5e1"/>
                <rect x="70" y="95" width="50" height="6" rx="3" fill="#cbd5e1"/>
                <circle cx="100" cy="130" r="15" fill="#3b82f6" opacity="0.2"/>
                <path d="M95 130h10M100 125v10" stroke="#3b82f6" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <h3>暂无页面配置</h3>
            <p>{{ selectedProject ? `项目「${selectedProject.name}」下还没有页面` : '创建您的第一个页面配置，开始使用 AI 辅助解析功能' }}</p>
            <button class="create-btn" @click="goToCreate">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 4v16m-8-8h16"/>
              </svg>
              开始创建
            </button>
          </div>

          <!-- 页面网格 -->
          <div v-else class="page-grid">
            <article 
              v-for="page in filteredPages" 
              :key="page.id"
              class="page-card"
              @click="goToEdit(page.page_id)"
            >
              <div class="card-thumbnail">
                <img 
                  v-if="page.screenshot_url" 
                  :src="page.screenshot_url" 
                  :alt="page.name_zh"
                  loading="lazy"
                />
                <div v-else class="thumbnail-placeholder">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                    <path d="M8 21h8M12 17v4"/>
                  </svg>
                </div>
              </div>
              
              <div class="card-content">
                <div class="card-header">
                  <h3 class="card-title">{{ page.name_zh }}</h3>
                  <span :class="['status-badge', getStatusClass(page.status)]">
                    {{ getStatusLabel(page.status) }}
                  </span>
                </div>
                
                <p class="card-id">{{ page.page_id }}</p>
                
                <div class="card-footer">
                  <span 
                    v-if="page.project_name" 
                    class="project-tag"
                    :style="{ background: getProjectColor(page.project_id) + '20', color: getProjectColor(page.project_id) }"
                  >
                    <span class="tag-dot" :style="{ background: getProjectColor(page.project_id) }"></span>
                    {{ page.project_name }}
                  </span>
                  <span class="update-time" v-if="page.updated_at">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M12 6v6l4 2"/>
                    </svg>
                    {{ formatTime(page.updated_at) }}
                  </span>
                </div>
              </div>
              
              <div class="card-actions">
                <button class="card-action-btn edit" @click.stop="goToEdit(page.page_id)" title="编辑">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="card-action-btn delete" @click.stop="handleDelete(page)" title="删除">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                  </svg>
                </button>
              </div>
            </article>
          </div>
        </div>
      </main>
    </div>

    <!-- 项目编辑弹窗 -->
    <a-modal
      v-model:open="projectModalVisible"
      :title="editingProject ? '编辑项目' : '新建项目'"
      :width="480"
      :footer="null"
      :destroyOnClose="true"
      class="project-modal"
    >
      <div class="project-form">
        <div class="form-group">
          <label>项目名称 <span class="required">*</span></label>
          <a-input 
            v-model:value="projectForm.name" 
            placeholder="请输入项目名称"
            :maxlength="100"
          />
        </div>
        <div class="form-group">
          <label>项目 ID <span class="required">*</span></label>
          <a-input 
            v-model:value="projectForm.project_id" 
            placeholder="例如：proj_default"
            :maxlength="50"
            :disabled="!!editingProject"
          />
          <p class="form-hint">项目唯一标识，创建后不可修改</p>
        </div>
        <div class="form-group">
          <label>项目描述</label>
          <a-textarea 
            v-model:value="projectForm.description" 
            placeholder="请输入项目描述（可选）"
            :rows="3"
            :maxlength="500"
          />
        </div>
        <div class="form-group">
          <label>项目颜色</label>
          <div class="color-picker">
            <button 
              v-for="color in projectColors" 
              :key="color"
              :class="['color-option', { active: projectForm.color === color }]"
              :style="{ background: color }"
              @click="projectForm.color = color"
            ></button>
          </div>
        </div>
        <div class="form-actions">
          <a-button @click="projectModalVisible = false">取消</a-button>
          <a-button type="primary" :loading="projectSaving" @click="saveProject">
            {{ editingProject ? '保存' : '创建' }}
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, createVNode } from 'vue'
import { useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { pageConfigApi, projectApi } from '@/api'

const router = useRouter()

// 同步时间（假数据占位）
const syncTime = ref(new Date().toLocaleString('zh-CN', {
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit'
}))

// 状态
const pages = ref([])
const projects = ref([])
const isLoading = ref(true)
const currentStatus = ref('')
const currentProjectId = ref(null)
const selectedProject = ref(null)
const searchQuery = ref('')
const projectSearchQuery = ref('')

// 项目弹窗
const projectModalVisible = ref(false)
const editingProject = ref(null)
const projectSaving = ref(false)
const projectForm = ref({
  name: '',
  project_id: '',
  description: '',
  color: '#3b82f6'
})

// 项目颜色选项
const projectColors = [
  '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899', 
  '#ef4444', '#f97316', '#eab308', '#22c55e', 
  '#14b8a6', '#06b6d4', '#64748b', '#1e293b'
]

// 状态标签
const statusTabs = [
  { label: '全部', value: '' },
  { label: '已配置', value: 'configured' },
  { label: '草稿', value: 'draft' },
  { label: '错误', value: 'error' }
]

// 过滤后的项目
const filteredProjects = computed(() => {
  if (!projectSearchQuery.value) {
    return projects.value
  }
  const query = projectSearchQuery.value.toLowerCase()
  return projects.value.filter(p => 
    p.name.toLowerCase().includes(query) ||
    (p.project_id && p.project_id.toLowerCase().includes(query))
  )
})

// 过滤后的页面
const filteredPages = computed(() => {
  let result = pages.value
  
  // 按项目筛选
  if (currentProjectId.value !== null) {
    result = result.filter(p => p.project_id === currentProjectId.value)
  }
  
  // 按状态筛选
  if (currentStatus.value) {
    result = result.filter(p => p.status === currentStatus.value)
  }
  
  // 搜索
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(p => 
      p.page_id.toLowerCase().includes(query) ||
      p.name_zh.toLowerCase().includes(query)
    )
  }
  
  return result
})

// 加载数据
onMounted(async () => {
  try {
    const [pagesRes, projectsRes] = await Promise.all([
      pageConfigApi.list(),
      projectApi.list()
    ])
    pages.value = pagesRes
    projects.value = projectsRes
    
    // 默认选中第一个项目
    if (projectsRes.length > 0) {
      selectProject(projectsRes[0])
    }
  } catch (error) {
    console.error('Failed to load data:', error)
    message.error('加载数据失败')
  } finally {
    isLoading.value = false
  }
})

// 获取状态数量
const getStatusCount = (status) => {
  let filtered = pages.value
  
  // 先按项目筛选
  if (currentProjectId.value !== null) {
    filtered = filtered.filter(p => p.project_id === currentProjectId.value)
  }
  
  if (!status) return filtered.length
  return filtered.filter(p => p.status === status).length
}

// 获取项目颜色
const getProjectColor = (projectId) => {
  const project = projects.value.find(p => p.id === projectId)
  return project?.color || '#3b82f6'
}

// 选择项目
const selectProject = (project) => {
  if (project) {
    currentProjectId.value = project.id
    selectedProject.value = project
  } else {
    currentProjectId.value = null
    selectedProject.value = null
  }
}

// 打开项目弹窗
const openProjectModal = (project = null) => {
  editingProject.value = project
  if (project) {
    projectForm.value = {
      name: project.name,
      project_id: project.project_id || `proj_${project.id}`,
      description: project.description || '',
      color: project.color || '#3b82f6'
    }
  } else {
    // 生成默认的项目 ID
    const timestamp = Date.now().toString(36)
    projectForm.value = {
      name: '',
      project_id: `proj_${timestamp}`,
      description: '',
      color: '#3b82f6'
    }
  }
  projectModalVisible.value = true
}

// 保存项目
const saveProject = async () => {
  if (!projectForm.value.name.trim()) {
    message.warning('请输入项目名称')
    return
  }
  
  if (!projectForm.value.project_id.trim()) {
    message.warning('请输入项目 ID')
    return
  }
  
  projectSaving.value = true
  try {
    if (editingProject.value) {
      // 更新
      const updated = await projectApi.update(editingProject.value.id, {
        name: projectForm.value.name,
        description: projectForm.value.description,
        color: projectForm.value.color
      })
      const index = projects.value.findIndex(p => p.id === editingProject.value.id)
      if (index > -1) {
        projects.value[index] = { ...projects.value[index], ...updated }
      }
      // 更新选中状态
      if (selectedProject.value?.id === editingProject.value.id) {
        selectedProject.value = { ...selectedProject.value, ...updated }
      }
      message.success('项目更新成功')
    } else {
      // 创建
      const created = await projectApi.create({
        name: projectForm.value.name,
        project_id: projectForm.value.project_id,
        description: projectForm.value.description,
        color: projectForm.value.color
      })
      projects.value.unshift(created)
      // 自动选中新创建的项目
      selectProject(created)
      message.success('项目创建成功')
    }
    projectModalVisible.value = false
  } catch (error) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    projectSaving.value = false
  }
}

// 删除项目
const deleteProject = (project) => {
  Modal.confirm({
    title: '删除项目',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要删除项目「${project.name}」吗？项目下的页面不会被删除，但会取消关联。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await projectApi.delete(project.id)
        projects.value = projects.value.filter(p => p.id !== project.id)
        // 如果删除的是当前选中的项目，选中第一个项目或清空
        if (currentProjectId.value === project.id) {
          if (projects.value.length > 0) {
            selectProject(projects.value[0])
          } else {
            currentProjectId.value = null
            selectedProject.value = null
          }
        }
        // 刷新页面列表
        const pagesRes = await pageConfigApi.list()
        pages.value = pagesRes
        message.success('项目已删除')
      } catch (error) {
        message.error('删除失败，请重试')
      }
    },
  })
}

// 状态样式
const getStatusClass = (status) => {
  const map = {
    configured: 'success',
    draft: 'warning',
    pending: 'info',
    error: 'error'
  }
  return map[status] || 'default'
}

const getStatusLabel = (status) => {
  const map = {
    configured: '已配置',
    draft: '草稿',
    pending: '待确认',
    error: '错误'
  }
  return map[status] || status
}

// 格式化时间
const formatTime = (time) => {
  const date = new Date(time)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString('zh-CN')
}

// 创建页面
const goToCreate = () => {
  // 如果选中了项目，带上项目ID
  if (currentProjectId.value) {
    router.push(`/page/new?project=${currentProjectId.value}`)
  } else {
    router.push('/page/new')
  }
}

// 编辑页面
const goToEdit = (pageId) => {
  router.push(`/page/${pageId}`)
}

// 删除页面
const handleDelete = (page) => {
  Modal.confirm({
    title: '删除页面配置',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要删除「${page.name_zh}」吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await pageConfigApi.delete(page.page_id)
        pages.value = pages.value.filter(p => p.id !== page.id)
        message.success('删除成功')
      } catch (error) {
        message.error('删除失败，请重试')
      }
    },
  })
}

// Header 按钮占位函数
const handleCodeView = () => {
  message.info('查看代码功能开发中...')
}

const handleImport = () => {
  message.info('导入功能开发中...')
}

const handleExport = () => {
  message.info('导出功能开发中...')
}

const handlePull = () => {
  message.info('拉取功能开发中...')
}

const handlePush = () => {
  message.info('推送功能开发中...')
}
</script>

<style lang="scss" scoped>
// 颜色变量
$primary: #3b82f6;
$primary-light: rgba(59, 130, 246, 0.1);
$primary-dark: #2563eb;
$success: #22c55e;
$success-light: rgba(34, 197, 94, 0.1);
$warning: #f59e0b;
$warning-light: rgba(245, 158, 11, 0.1);
$error: #ef4444;
$error-light: rgba(239, 68, 68, 0.1);

$text-primary: #1e293b;
$text-secondary: #475569;
$text-muted: #94a3b8;
$border-color: #e2e8f0;
$border-light: #f1f5f9;
$bg-body: #f8fafc;
$bg-elevated: #ffffff;
$bg-subtle: #f1f5f9;

.page-config-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: $bg-body;
}

// 顶部 Header
.top-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: $bg-elevated;
  border-bottom: 1px solid $border-color;
  position: sticky;
  top: 0;
  z-index: 100;

  .header-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .logo-icon {
    width: 36px;
    height: 36px;
    background: $primary;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 20px;
      height: 20px;
      color: white;
    }
  }

  .header-title {
    h1 {
      font-size: 18px;
      font-weight: 600;
      color: $text-primary;
      margin: 0;
      line-height: 1.3;
    }

    .sync-time {
      font-size: 12px;
      color: $text-muted;
    }
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 500;
    color: $text-secondary;
    background: $bg-elevated;
    border: 1px solid $border-color;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 16px;
      height: 16px;
    }

    &:hover {
      border-color: $primary;
      color: $primary;
      background: $primary-light;
    }

    &.code-btn {
      padding: 8px 10px;
    }

    &.primary-btn {
      background: $primary;
      border-color: $primary;
      color: white;

      &:hover {
        background: $primary-dark;
        border-color: $primary-dark;
      }
    }
  }
}

// 主体内容区
.main-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

// 左侧项目列表
.project-sidebar {
  width: 260px;
  background: $bg-elevated;
  border-right: 1px solid $border-color;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .sidebar-search {
    position: relative;
    padding: 16px;
    border-bottom: 1px solid $border-light;

    .search-icon {
      position: absolute;
      left: 28px;
      top: 50%;
      transform: translateY(-50%);
      width: 16px;
      height: 16px;
      color: $text-muted;
      pointer-events: none;
    }

    .search-input {
      width: 100%;
      height: 40px;
      padding: 0 12px 0 38px;
      font-size: 13px;
      background: $bg-subtle;
      border: 1px solid transparent;
      border-radius: 8px;
      outline: none;
      transition: all 0.2s;

      &::placeholder {
        color: $text-muted;
      }

      &:focus {
        background: $bg-elevated;
        border-color: $primary;
        box-shadow: 0 0 0 3px $primary-light;
      }
    }
  }

  .add-project-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 16px;
    padding: 12px 16px;
    font-size: 14px;
    font-weight: 500;
    color: white;
    background: $primary;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 18px;
      height: 18px;
    }

    &:hover {
      background: $primary-dark;
    }
  }

  .project-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px 16px;
  }

  .project-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 14px;
    margin-bottom: 8px;
    background: $bg-elevated;
    border: 1px solid $border-light;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: $primary;
      box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);

      .project-actions {
        opacity: 1;
      }
    }

    &.active {
      border-color: $primary;
      background: $primary-light;

      .project-name {
        color: $primary;
      }
    }
  }

  .project-info {
    flex: 1;
    min-width: 0;

    .project-name {
      font-size: 14px;
      font-weight: 600;
      color: $text-primary;
      margin: 0 0 4px 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .project-id {
      font-size: 11px;
      color: $text-muted;
      margin: 0 0 2px 0;
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }

    .project-pages {
      font-size: 12px;
      color: $text-secondary;
      margin: 0;
    }
  }

  .project-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.2s;
  }

  .project-action-btn {
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;

    svg {
      width: 14px;
      height: 14px;
      color: $text-muted;
    }

    &:hover {
      background: $bg-subtle;

      svg {
        color: $primary;
      }
    }

    &.delete:hover svg {
      color: $error;
    }
  }

  .empty-projects {
    padding: 32px 16px;
    text-align: center;

    p {
      font-size: 13px;
      color: $text-muted;
      margin: 0;
    }
  }
}

// 右侧页面列表
.page-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: $bg-elevated;
  border-bottom: 1px solid $border-light;

  .filter-tabs {
    display: flex;
    gap: 4px;
    background: $bg-subtle;
    padding: 4px;
    border-radius: 10px;
  }

  .filter-tab {
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: $text-secondary;
    background: transparent;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      color: $text-primary;
    }

    &.active {
      background: $primary;
      color: white;
    }
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .search-wrapper {
    position: relative;

    .search-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      width: 16px;
      height: 16px;
      color: $text-muted;
      pointer-events: none;
    }

    .search-input {
      width: 220px;
      height: 38px;
      padding: 0 12px 0 38px;
      font-size: 13px;
      background: $bg-subtle;
      border: 1px solid transparent;
      border-radius: 8px;
      outline: none;
      transition: all 0.2s;

      &::placeholder {
        color: $text-muted;
      }

      &:focus {
        background: $bg-elevated;
        border-color: $primary;
        box-shadow: 0 0 0 3px $primary-light;
      }
    }
  }

  .add-page-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: white;
    background: $primary;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 16px;
      height: 16px;
    }

    &:hover {
      background: $primary-dark;
    }
  }
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

// 加载状态
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;

  .loading-spinner {
    margin-bottom: 16px;
  }

  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid $border-color;
    border-top-color: $primary;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  p {
    color: $text-muted;
    font-size: 14px;
    margin: 0;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

// 空状态
.empty-state {
  text-align: center;
  padding: 60px 24px;

  .empty-illustration {
    margin-bottom: 20px;

    svg {
      width: 140px;
      height: 140px;
    }
  }

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
    margin: 0 0 8px 0;
  }

  p {
    font-size: 13px;
    color: $text-muted;
    margin: 0 0 20px 0;
    max-width: 280px;
    margin-left: auto;
    margin-right: auto;
  }

  .create-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    color: white;
    background: $primary;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 18px;
      height: 18px;
    }

    &:hover {
      background: $primary-dark;
    }
  }
}

// 页面网格
.page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.page-card {
  background: $bg-elevated;
  border: 1px solid $border-light;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
    border-color: rgba(59, 130, 246, 0.3);

    .card-actions {
      opacity: 1;
      transform: translateX(0);
    }

    .card-thumbnail img {
      transform: scale(1.03);
    }
  }
}

.card-thumbnail {
  height: 160px;
  overflow: hidden;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  position: relative;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .thumbnail-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;

    svg {
      width: 48px;
      height: 48px;
      color: $text-muted;
      opacity: 0.3;
    }
  }
}

.card-content {
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
  gap: 10px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
  margin: 0;
  line-height: 1.4;
}

.status-badge {
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;

  &.success {
    background: $success-light;
    color: $success;
  }

  &.warning {
    background: $warning-light;
    color: darken($warning, 10%);
  }

  &.info {
    background: $primary-light;
    color: $primary;
  }

  &.error {
    background: $error-light;
    color: $error;
  }
}

.card-id {
  font-size: 12px;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  color: $text-muted;
  margin: 0 0 12px 0;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;

  .project-tag {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
    border-radius: 4px;

    .tag-dot {
      width: 5px;
      height: 5px;
      border-radius: 50%;
    }
  }

  .update-time {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: $text-muted;
    margin-left: auto;

    svg {
      width: 12px;
      height: 12px;
    }
  }
}

.card-actions {
  position: absolute;
  right: 10px;
  top: 10px;
  display: flex;
  gap: 6px;
  opacity: 0;
  transform: translateX(6px);
  transition: all 0.2s;

  .card-action-btn {
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);

    svg {
      width: 14px;
      height: 14px;
    }

    &.edit {
      color: $primary;

      &:hover {
        background: $primary;
        color: white;
      }
    }

    &.delete {
      color: $error;

      &:hover {
        background: $error;
        color: white;
      }
    }
  }
}

// 项目弹窗表单
.project-form {
  .form-group {
    margin-bottom: 18px;

    label {
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: $text-primary;
      margin-bottom: 6px;

      .required {
        color: $error;
      }
    }

    .form-hint {
      font-size: 11px;
      color: $text-muted;
      margin: 4px 0 0 0;
    }
  }

  .color-picker {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;

    .color-option {
      width: 28px;
      height: 28px;
      border-radius: 6px;
      border: 2px solid transparent;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        transform: scale(1.1);
      }

      &.active {
        border-color: $text-primary;
        box-shadow: 0 0 0 2px white, 0 0 0 4px currentColor;
      }
    }
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 24px;
    padding-top: 18px;
    border-top: 1px solid $border-light;
  }
}
</style>
