<template>
  <div class="page-list">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="title-group">
          <h1>
            <span class="icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
            </span>
            页面配置
          </h1>
          <p class="subtitle">管理所有页面的 UI 配置，支持 AI 智能解析</p>
        </div>
      </div>
      <a-button type="primary" size="large" class="add-btn" @click="goToCreate">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="btn-icon">
            <path d="M12 4v16m-8-8h16"/>
          </svg>
        </template>
        添加页面
      </a-button>
    </header>
    
    <!-- Content -->
    <div class="page-content">
      <!-- Filter Bar -->
      <div class="filter-bar">
        <div class="filter-left">
          <!-- 项目筛选 -->
          <div class="project-filter">
            <a-dropdown :trigger="['click']" placement="bottomLeft">
              <button class="project-select-btn" :style="selectedProject ? { borderColor: selectedProject.color } : {}">
                <span v-if="selectedProject" class="project-dot" :style="{ background: selectedProject.color }"></span>
                <span class="project-name">{{ selectedProject ? selectedProject.name : '全部项目' }}</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="arrow-icon">
                  <path d="M6 9l6 6 6-6"/>
                </svg>
              </button>
              <template #overlay>
                <div class="project-dropdown">
                  <div class="dropdown-header">
                    <span>选择项目</span>
                    <button class="add-project-btn" @click="openProjectModal()">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 4v16m-8-8h16"/>
                      </svg>
                      新建
                    </button>
                  </div>
                  <div class="dropdown-list">
                    <div 
                      class="dropdown-item"
                      :class="{ active: !currentProjectId }"
                      @click="selectProject(null)"
                    >
                      <span class="project-dot all"></span>
                      <span>全部项目</span>
                      <span class="item-count">{{ pages.length }}</span>
                    </div>
                    <div 
                      class="dropdown-item"
                      :class="{ active: currentProjectId === 0 }"
                      @click="selectProject({ id: 0, name: '未分配', color: '#9ca3af' })"
                    >
                      <span class="project-dot" style="background: #9ca3af"></span>
                      <span>未分配</span>
                      <span class="item-count">{{ getProjectPageCount(0) }}</span>
                    </div>
                    <div 
                      v-for="project in projects" 
                      :key="project.id"
                      class="dropdown-item"
                      :class="{ active: currentProjectId === project.id }"
                      @click="selectProject(project)"
                    >
                      <span class="project-dot" :style="{ background: project.color }"></span>
                      <span>{{ project.name }}</span>
                      <span class="item-count">{{ project.page_count }}</span>
                      <div class="item-actions" @click.stop>
                        <button class="item-action-btn" @click="openProjectModal(project)" title="编辑">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                          </svg>
                        </button>
                        <button class="item-action-btn delete" @click="deleteProject(project)" title="删除">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </a-dropdown>
          </div>
          
          <!-- 状态筛选 -->
          <div class="filter-tabs">
            <button 
              v-for="tab in statusTabs" 
              :key="tab.value"
              :class="['filter-tab', { active: currentStatus === tab.value }]"
              @click="currentStatus = tab.value"
            >
              {{ tab.label }}
              <span class="tab-count">{{ getStatusCount(tab.value) }}</span>
            </button>
          </div>
        </div>
        
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
      </div>
      
      <!-- Loading State -->
      <div v-if="isLoading" class="loading-state">
        <div class="loading-spinner">
          <div class="spinner"></div>
        </div>
        <p>加载中...</p>
      </div>
      
      <!-- Empty State -->
      <div v-else-if="filteredPages.length === 0" class="empty-state">
        <div class="empty-illustration">
          <svg viewBox="0 0 200 200" fill="none">
            <circle cx="100" cy="100" r="80" fill="#f1f5f9"/>
            <rect x="60" y="50" width="80" height="100" rx="8" fill="#e2e8f0"/>
            <rect x="70" y="65" width="40" height="6" rx="3" fill="#cbd5e1"/>
            <rect x="70" y="80" width="60" height="6" rx="3" fill="#cbd5e1"/>
            <rect x="70" y="95" width="50" height="6" rx="3" fill="#cbd5e1"/>
            <circle cx="100" cy="130" r="15" fill="#6366f1" opacity="0.2"/>
            <path d="M95 130h10M100 125v10" stroke="#6366f1" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <h3>暂无页面配置</h3>
        <p>{{ selectedProject ? `项目「${selectedProject.name}」下还没有页面` : '创建您的第一个页面配置，开始使用 AI 辅助解析功能' }}</p>
        <a-button type="primary" size="large" @click="goToCreate">
          <template #icon>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="btn-icon">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
          </template>
          开始创建
        </a-button>
      </div>
      
      <!-- Page Grid -->
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
            <button class="action-btn edit" @click.stop="goToEdit(page.page_id)" title="编辑">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="action-btn delete" @click.stop="handleDelete(page)" title="删除">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
              </svg>
            </button>
          </div>
        </article>
      </div>
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

// 状态
const pages = ref([])
const projects = ref([])
const isLoading = ref(true)
const currentStatus = ref('')
const currentProjectId = ref(null)
const selectedProject = ref(null)
const searchQuery = ref('')

// 项目弹窗
const projectModalVisible = ref(false)
const editingProject = ref(null)
const projectSaving = ref(false)
const projectForm = ref({
  name: '',
  description: '',
  color: '#6366f1'
})

// 项目颜色选项
const projectColors = [
  '#6366f1', '#8b5cf6', '#ec4899', '#ef4444', 
  '#f97316', '#eab308', '#22c55e', '#14b8a6', 
  '#06b6d4', '#3b82f6', '#64748b', '#1e293b'
]

// 状态标签
const statusTabs = [
  { label: '全部', value: '' },
  { label: '已配置', value: 'configured' },
  { label: '草稿', value: 'draft' }
]

// 过滤后的页面
const filteredPages = computed(() => {
  let result = pages.value
  
  // 按项目筛选
  if (currentProjectId.value !== null) {
    if (currentProjectId.value === 0) {
      result = result.filter(p => !p.project_id)
    } else {
      result = result.filter(p => p.project_id === currentProjectId.value)
    }
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
    if (currentProjectId.value === 0) {
      filtered = filtered.filter(p => !p.project_id)
    } else {
      filtered = filtered.filter(p => p.project_id === currentProjectId.value)
    }
  }
  
  if (!status) return filtered.length
  return filtered.filter(p => p.status === status).length
}

// 获取项目下的页面数量
const getProjectPageCount = (projectId) => {
  if (projectId === 0) {
    return pages.value.filter(p => !p.project_id).length
  }
  return pages.value.filter(p => p.project_id === projectId).length
}

// 获取项目颜色
const getProjectColor = (projectId) => {
  const project = projects.value.find(p => p.id === projectId)
  return project?.color || '#6366f1'
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
      description: project.description || '',
      color: project.color || '#6366f1'
    }
  } else {
    projectForm.value = {
      name: '',
      description: '',
      color: '#6366f1'
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
  
  projectSaving.value = true
  try {
    if (editingProject.value) {
      // 更新
      const updated = await projectApi.update(editingProject.value.id, projectForm.value)
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
      const created = await projectApi.create(projectForm.value)
      projects.value.unshift(created)
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
        // 如果删除的是当前选中的项目，清除选中
        if (currentProjectId.value === project.id) {
          currentProjectId.value = null
          selectedProject.value = null
        }
        // 刷新页面列表
        const pagesRes = await pageConfigApi.list()
        pages.value = pagesRes
        message.success('项目已删除')
      } catch (error) {
        message.error('删除失败，请重试')
      }
    },
  });
}

// 状态样式
const getStatusClass = (status) => {
  const map = {
    configured: 'success',
    draft: 'warning',
    pending: 'info'
  }
  return map[status] || 'default'
}

const getStatusLabel = (status) => {
  const map = {
    configured: '已配置',
    draft: '草稿',
    pending: '待确认'
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
  if (currentProjectId.value && currentProjectId.value !== 0) {
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
  });
}
</script>

<style lang="scss" scoped>
.page-list {
  min-height: 100vh;
  background: var(--bg-body);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 40px 48px 32px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-light);
  
  .title-group {
    h1 {
      font-size: 28px;
      font-weight: 700;
      color: var(--text-heading);
      margin: 0 0 8px 0;
      display: flex;
      align-items: center;
      gap: 14px;
      letter-spacing: -0.02em;
    }
    
    .icon-wrapper {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, var(--primary-light) 0%, rgba(99, 102, 241, 0.05) 100%);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      
      svg {
        width: 24px;
        height: 24px;
        color: var(--primary);
      }
    }
    
    .subtitle {
      color: var(--text-muted);
      font-size: 15px;
      margin: 0;
      padding-left: 58px;
    }
  }
  
  .add-btn {
    height: 46px;
    padding: 0 28px;
    font-size: 15px;
    font-weight: 600;
    border-radius: 12px;
    
    .btn-icon {
      width: 18px;
      height: 18px;
    }
  }
}

.page-content {
  padding: 32px 48px;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  gap: 24px;
}

.filter-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

// 项目筛选
.project-filter {
  position: relative;
}

.project-select-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 160px;
  
  &:hover {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px var(--primary-light);
  }
  
  .project-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  
  .project-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    flex: 1;
    text-align: left;
  }
  
  .arrow-icon {
    width: 16px;
    height: 16px;
    color: var(--text-muted);
  }
}

.project-dropdown {
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  min-width: 260px;
  overflow: hidden;
}

.dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-light);
  
  span {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
  }
  
  .add-project-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    color: var(--primary);
    background: var(--primary-light);
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    
    svg {
      width: 12px;
      height: 12px;
    }
    
    &:hover {
      background: var(--primary);
      color: white;
    }
  }
}

.dropdown-list {
  max-height: 320px;
  overflow-y: auto;
  padding: 8px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  
  .project-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    
    &.all {
      background: linear-gradient(135deg, #6366f1, #8b5cf6, #ec4899);
    }
  }
  
  span:nth-child(2) {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .item-count {
    font-size: 12px;
    color: var(--text-muted);
    background: var(--bg-subtle);
    padding: 2px 8px;
    border-radius: 10px;
  }
  
  .item-actions {
    display: none;
    gap: 4px;
    margin-left: 8px;
  }
  
  .item-action-btn {
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 6px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s;
    
    svg {
      width: 14px;
      height: 14px;
      color: var(--text-muted);
    }
    
    &:hover {
      background: var(--bg-subtle);
      
      svg {
        color: var(--primary);
      }
    }
    
    &.delete:hover svg {
      color: var(--error);
    }
  }
  
  &:hover {
    background: var(--bg-subtle);
    
    .item-actions {
      display: flex;
    }
    
    .item-count {
      display: none;
    }
  }
  
  &.active {
    background: var(--primary-light);
    
    span:nth-child(2) {
      color: var(--primary);
      font-weight: 500;
    }
  }
}

.filter-tabs {
  display: flex;
  gap: 6px;
  background: var(--bg-elevated);
  padding: 6px;
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: var(--bg-subtle);
    color: var(--text-primary);
  }
  
  &.active {
    background: var(--primary);
    color: white;
    
    .tab-count {
      background: rgba(255, 255, 255, 0.2);
      color: white;
    }
  }
  
  .tab-count {
    font-size: 12px;
    font-weight: 600;
    padding: 2px 8px;
    background: var(--bg-subtle);
    border-radius: 10px;
    color: var(--text-muted);
  }
}

.search-wrapper {
  position: relative;
  width: 280px;
  
  .search-icon {
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    color: var(--text-muted);
    pointer-events: none;
  }
  
  .search-input {
    width: 100%;
    height: 44px;
    padding: 0 16px 0 44px;
    font-size: 14px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    outline: none;
    transition: all 0.2s;
    
    &::placeholder {
      color: var(--text-muted);
    }
    
    &:hover {
      border-color: var(--primary);
    }
    
    &:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-light);
    }
  }
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 20px;
  
  .loading-spinner {
    margin-bottom: 16px;
  }
  
  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-color);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  
  p {
    color: var(--text-muted);
    font-size: 14px;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 80px 24px;
  
  .empty-illustration {
    margin-bottom: 24px;
    
    svg {
      width: 180px;
      height: 180px;
    }
  }
  
  h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-heading);
    margin-bottom: 8px;
  }
  
  p {
    font-size: 14px;
    color: var(--text-muted);
    margin-bottom: 24px;
    max-width: 320px;
    margin-left: auto;
    margin-right: auto;
  }
}

.page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
}

.page-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
    border-color: rgba(99, 102, 241, 0.2);
    
    .card-actions {
      opacity: 1;
      transform: translateX(0);
    }
    
    .card-thumbnail img {
      transform: scale(1.05);
    }
  }
}

.card-thumbnail {
  height: 180px;
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
      width: 56px;
      height: 56px;
      color: var(--text-muted);
      opacity: 0.3;
    }
  }
}

.card-content {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-heading);
  margin: 0;
  line-height: 1.4;
}

.status-badge {
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 20px;
  white-space: nowrap;
  flex-shrink: 0;
  
  &.success {
    background: var(--success-light);
    color: var(--success);
  }
  
  &.warning {
    background: var(--warning-light);
    color: #b45309;
  }
  
  &.info {
    background: var(--primary-light);
    color: var(--primary);
  }
}

.card-id {
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin: 0 0 16px 0;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  
  .project-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    border-radius: 6px;
    
    .tag-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }
  }
  
  .update-time {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted);
    margin-left: auto;
    
    svg {
      width: 14px;
      height: 14px;
    }
  }
}

.card-actions {
  position: absolute;
  right: 12px;
  top: 12px;
  display: flex;
  gap: 8px;
  opacity: 0;
  transform: translateX(8px);
  transition: all 0.2s;
  
  .action-btn {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    
    svg {
      width: 16px;
      height: 16px;
    }
    
    &.edit {
      color: var(--primary);
      
      &:hover {
        background: var(--primary);
        color: white;
      }
    }
    
    &.delete {
      color: var(--error);
      
      &:hover {
        background: var(--error);
        color: white;
      }
    }
  }
}

// 项目弹窗
.project-form {
  .form-group {
    margin-bottom: 20px;
    
    label {
      display: block;
      font-size: 14px;
      font-weight: 500;
      color: var(--text-primary);
      margin-bottom: 8px;
      
      .required {
        color: var(--error);
      }
    }
  }
  
  .color-picker {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    
    .color-option {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      border: 2px solid transparent;
      cursor: pointer;
      transition: all 0.2s;
      
      &:hover {
        transform: scale(1.1);
      }
      
      &.active {
        border-color: var(--text-heading);
        box-shadow: 0 0 0 2px white, 0 0 0 4px currentColor;
      }
    }
  }
  
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid var(--border-light);
  }
}
</style>
