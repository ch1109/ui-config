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
        <p>创建您的第一个页面配置，开始使用 AI 辅助解析功能</p>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, createVNode } from 'vue'
import { useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { pageConfigApi } from '@/api'

const router = useRouter()

// 状态
const pages = ref([])
const isLoading = ref(true)
const currentStatus = ref('')
const searchQuery = ref('')

// 状态标签
const statusTabs = [
  { label: '全部', value: '' },
  { label: '已配置', value: 'configured' },
  { label: '草稿', value: 'draft' },
  { label: '待确认', value: 'pending' }
]

// 过滤后的页面
const filteredPages = computed(() => {
  let result = pages.value
  
  if (currentStatus.value) {
    result = result.filter(p => p.status === currentStatus.value)
  }
  
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
    const response = await pageConfigApi.list()
    pages.value = response
  } catch (error) {
    console.error('Failed to load pages:', error)
    message.error('加载页面列表失败')
  } finally {
    isLoading.value = false
  }
})

// 获取状态数量
const getStatusCount = (status) => {
  if (!status) return pages.value.length
  return pages.value.filter(p => p.status === status).length
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
  router.push('/page/new')
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
  
  .update-time {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted);
    
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
</style>
