<template>
  <div class="page-list">
    <header class="page-header">
      <div class="header-content">
        <h1><span class="icon">📄</span>页面配置</h1>
        <p class="subtitle">管理所有页面的 UI 配置，支持 AI 辅助解析</p>
      </div>
      <router-link to="/page/new" class="btn btn-primary">
        <span>+</span> 添加页面
      </router-link>
    </header>
    
    <div class="page-content">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <div class="filter-tabs">
          <button 
            v-for="tab in statusTabs" 
            :key="tab.value"
            class="tab-btn"
            :class="{ active: currentStatus === tab.value }"
            @click="currentStatus = tab.value"
          >
            {{ tab.label }}
            <span class="count">{{ getStatusCount(tab.value) }}</span>
          </button>
        </div>
        
        <div class="search-box">
          <input 
            v-model="searchQuery"
            type="text" 
            class="input"
            placeholder="搜索页面..."
          />
        </div>
      </div>
      
      <!-- 页面列表 -->
      <div v-if="isLoading" class="loading-state">
        <div class="loading">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <p>加载中...</p>
      </div>
      
      <div v-else-if="filteredPages.length === 0" class="empty-state">
        <div class="icon">📭</div>
        <div class="title">暂无页面配置</div>
        <div class="description">点击"添加页面"开始创建您的第一个配置</div>
      </div>
      
      <div v-else class="page-grid">
        <div 
          v-for="page in filteredPages" 
          :key="page.id"
          class="page-card card"
          @click="goToEdit(page.page_id)"
        >
          <div class="card-thumb">
            <img 
              v-if="page.screenshot_url" 
              :src="page.screenshot_url" 
              alt="页面截图"
            />
            <div v-else class="placeholder">
              <span>📱</span>
            </div>
          </div>
          
          <div class="card-body">
            <h3 class="card-title">{{ page.name_zh }}</h3>
            <p class="card-id">{{ page.page_id }}</p>
            
            <div class="card-footer">
              <span class="tag" :class="getStatusClass(page.status)">
                {{ getStatusLabel(page.status) }}
              </span>
              <span class="time" v-if="page.updated_at">
                {{ formatTime(page.updated_at) }}
              </span>
            </div>
          </div>
          
          <div class="card-actions">
            <button class="action-btn edit" @click.stop="goToEdit(page.page_id)" title="编辑">
              ✏️
            </button>
            <button class="action-btn delete" @click.stop="handleDelete(page)" title="删除">
              🗑️
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 删除确认 -->
    <ConfirmDialog
      v-model:visible="showDeleteConfirm"
      title="删除页面配置"
      :message="`确定要删除「${deletingPage?.name_zh}」吗？此操作不可恢复。`"
      confirm-text="删除"
      confirm-class="btn-danger"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { pageConfigApi } from '@/api'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const router = useRouter()

// 状态
const pages = ref([])
const isLoading = ref(true)
const currentStatus = ref('')
const searchQuery = ref('')
const showDeleteConfirm = ref(false)
const deletingPage = ref(null)

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
    configured: 'tag-success',
    draft: 'tag-warning',
    pending: 'tag-primary'
  }
  return map[status] || ''
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

// 编辑页面
const goToEdit = (pageId) => {
  router.push(`/page/${pageId}`)
}

// 删除页面
const handleDelete = (page) => {
  deletingPage.value = page
  showDeleteConfirm.value = true
}

const confirmDelete = async () => {
  showDeleteConfirm.value = false
  if (!deletingPage.value) return
  
  try {
    await pageConfigApi.delete(deletingPage.value.page_id)
    pages.value = pages.value.filter(p => p.id !== deletingPage.value.id)
  } catch (error) {
    alert('删除失败，请重试')
  }
}
</script>

<style lang="scss" scoped>
.page-list {
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.filter-tabs {
  display: flex;
  gap: 4px;
  background: var(--bg-card);
  padding: 4px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
  
  .count {
    font-size: 11px;
    padding: 2px 6px;
    background: var(--bg-hover);
    border-radius: 999px;
  }
  
  &:hover {
    color: var(--text-primary);
  }
  
  &.active {
    background: var(--primary-light);
    color: var(--primary);
    
    .count {
      background: rgba(0, 217, 255, 0.2);
    }
  }
}

.search-box {
  width: 280px;
  
  .input {
    background: var(--bg-card);
  }
}

.loading-state {
  text-align: center;
  padding: 80px 20px;
  
  p {
    margin-top: 16px;
    color: var(--text-secondary);
  }
}

.page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.page-card {
  padding: 0;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
  position: relative;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }
  
  .card-thumb {
    height: 160px;
    background: var(--bg-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    
    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    
    .placeholder {
      font-size: 48px;
      opacity: 0.3;
    }
  }
  
  .card-body {
    padding: 16px;
  }
  
  .card-title {
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .card-id {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    margin-bottom: 12px;
  }
  
  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .time {
    font-size: 12px;
    color: var(--text-muted);
  }
  
  .card-actions {
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    gap: 6px;
    opacity: 1;
  }
  
  .action-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
    
    &:hover {
      transform: scale(1.1);
    }
    
    &.edit:hover {
      background: rgba(0, 217, 255, 0.3);
      border-color: var(--primary);
    }
    
    &.delete:hover {
      background: rgba(239, 68, 68, 0.3);
      border-color: var(--error);
    }
  }
}
</style>

