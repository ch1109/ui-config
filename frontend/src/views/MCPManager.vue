<template>
  <div class="mcp-manager">
    <header class="page-header">
      <h1><span class="icon">🔌</span>MCP 服务器管理</h1>
      <p class="subtitle">管理 Model Context Protocol 服务器，扩展 AI 模型能力</p>
    </header>
    
    <div class="page-content">
      <!-- 预置服务器 -->
      <section class="section">
        <h2 class="section-title">📦 预置服务器</h2>
        <div class="server-grid">
          <div 
            v-for="server in presetServers" 
            :key="server.name"
            class="server-card card"
          >
            <div class="server-header">
              <div class="server-info">
                <h3>{{ server.name }}</h3>
                <p class="server-url">{{ server.server_url }}</p>
              </div>
              <label class="switch">
                <input 
                  type="checkbox" 
                  :checked="server.status === 'enabled'"
                  @change="toggleServer(server)"
                />
                <span class="slider"></span>
              </label>
            </div>
            
            <p class="server-desc">{{ server.description }}</p>
            
            <div class="server-tools">
              <span class="tool-label">工具:</span>
              <span 
                v-for="tool in server.tools" 
                :key="tool"
                class="tag tag-primary"
              >
                {{ tool }}
              </span>
            </div>
            
            <div class="server-footer">
              <span class="tag" :class="getStatusClass(server.status)">
                {{ getStatusLabel(server.status) }}
              </span>
              <button class="btn btn-ghost btn-sm" @click="testConnection(server)">
                🔗 测试连接
              </button>
            </div>
          </div>
        </div>
      </section>
      
      <!-- 自定义服务器 -->
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">⚙️ 自定义服务器</h2>
          <button class="btn btn-primary" @click="showAddDialog = true">
            + 添加服务器
          </button>
        </div>
        
        <div v-if="customServers.length === 0" class="empty-state">
          <div class="icon">🔌</div>
          <div class="title">暂无自定义服务器</div>
          <div class="description">点击"添加服务器"配置您的 MCP 服务器</div>
        </div>
        
        <div v-else class="server-grid">
          <div 
            v-for="server in customServers" 
            :key="server.id"
            class="server-card card"
          >
            <div class="server-header">
              <div class="server-info">
                <h3>{{ server.name }}</h3>
                <p class="server-url">{{ server.server_url }}</p>
              </div>
              <div class="server-actions">
                <button class="btn btn-ghost btn-sm" @click="editServer(server)">
                  ✏️
                </button>
                <button class="btn btn-ghost btn-sm" @click="deleteServer(server)">
                  🗑️
                </button>
              </div>
            </div>
            
            <div class="server-tools">
              <span class="tool-label">工具:</span>
              <span 
                v-for="tool in server.tools" 
                :key="tool"
                class="tag tag-primary"
              >
                {{ tool }}
              </span>
            </div>
            
            <div class="server-footer">
              <span class="tag" :class="getStatusClass(server.status)">
                {{ getStatusLabel(server.status) }}
              </span>
              <span v-if="server.last_check" class="last-check">
                最后检查: {{ formatTime(server.last_check) }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
    
    <!-- 添加/编辑弹窗 -->
    <Transition name="fade">
      <div v-if="showAddDialog" class="modal-overlay" @click.self="closeDialog">
        <div class="modal card">
          <div class="modal-header">
            <h3>{{ editingServer ? '编辑服务器' : '添加 MCP 服务器' }}</h3>
            <button class="close-btn" @click="closeDialog">×</button>
          </div>
          
          <div class="modal-tabs">
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'form' }"
              @click="activeTab = 'form'"
            >
              表单配置
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'json' }"
              @click="activeTab = 'json'"
            >
              JSON 编辑
            </button>
            <button 
              class="tab-btn" 
              :class="{ active: activeTab === 'upload' }"
              @click="activeTab = 'upload'"
            >
              文件上传
            </button>
          </div>
          
          <div class="modal-body">
            <!-- 表单配置 -->
            <div v-if="activeTab === 'form'" class="form-content">
              <div class="form-group">
                <label>服务器名称 <span class="required">*</span></label>
                <input v-model="formData.name" class="input" placeholder="My MCP Server" />
              </div>
              
              <div class="form-group">
                <label>服务器 URL <span class="required">*</span></label>
                <input v-model="formData.server_url" class="input" placeholder="https://mcp.example.com" />
              </div>
              
              <div class="form-group">
                <label>健康检查路径</label>
                <input v-model="formData.health_check_path" class="input" placeholder="/health" />
              </div>
              
              <div class="form-group">
                <label>工具列表 (逗号分隔)</label>
                <input v-model="toolsInput" class="input" placeholder="search, retrieve, store" />
              </div>
              
              <div class="form-group">
                <label>描述</label>
                <textarea v-model="formData.description" class="textarea" rows="3"></textarea>
              </div>
            </div>
            
            <!-- JSON 编辑 -->
            <div v-if="activeTab === 'json'" class="json-content">
              <textarea 
                v-model="jsonInput"
                class="textarea json-editor"
                rows="15"
                placeholder='{"name": "...", "server_url": "...", "tools": [...]}'
              ></textarea>
              <p v-if="jsonError" class="error-text">{{ jsonError }}</p>
            </div>
            
            <!-- 文件上传 -->
            <div v-if="activeTab === 'upload'" class="upload-content">
              <div 
                class="upload-zone"
                :class="{ dragover: isDragover }"
                @dragover.prevent="isDragover = true"
                @dragleave="isDragover = false"
                @drop.prevent="handleFileDrop"
                @click="$refs.fileInput.click()"
              >
                <div class="upload-icon">📁</div>
                <p>拖拽 JSON 文件到此处，或点击选择</p>
                <p class="hint">支持 .json 格式，最大 1MB</p>
              </div>
              <input 
                ref="fileInput"
                type="file"
                accept=".json"
                style="display: none"
                @change="handleFileSelect"
              />
            </div>
          </div>
          
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeDialog">取消</button>
            <button class="btn btn-primary" @click="saveServer" :disabled="isSaving">
              {{ isSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
    
    <!-- 删除确认 -->
    <ConfirmDialog
      v-model:visible="showDeleteConfirm"
      title="删除服务器"
      :message="`确定要删除「${deletingServer?.name}」吗？`"
      confirm-text="删除"
      confirm-class="btn-danger"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { mcpApi } from '@/api'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

// 状态
const servers = ref([])
const showAddDialog = ref(false)
const activeTab = ref('form')
const editingServer = ref(null)
const isSaving = ref(false)
const isDragover = ref(false)
const jsonError = ref('')
const showDeleteConfirm = ref(false)
const deletingServer = ref(null)

// 表单数据
const formData = ref({
  name: '',
  server_url: '',
  health_check_path: '/health',
  description: '',
  tools: []
})
const toolsInput = ref('')
const jsonInput = ref('')

// 计算属性
const presetServers = computed(() => servers.value.filter(s => s.is_preset))
const customServers = computed(() => servers.value.filter(s => !s.is_preset))

// 加载数据
onMounted(async () => {
  try {
    servers.value = await mcpApi.list()
  } catch (error) {
    console.error('Failed to load MCP servers:', error)
  }
})

// 状态样式
const getStatusClass = (status) => {
  const map = {
    enabled: 'tag-success',
    disabled: 'tag-warning',
    error: 'tag-error'
  }
  return map[status] || ''
}

const getStatusLabel = (status) => {
  const map = {
    enabled: '已启用',
    disabled: '已禁用',
    error: '连接失败'
  }
  return map[status] || status
}

// 格式化时间
const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 切换服务器状态
const toggleServer = async (server) => {
  try {
    const enable = server.status !== 'enabled'
    await mcpApi.toggle(server.name.toLowerCase(), enable)
    server.status = enable ? 'enabled' : 'disabled'
  } catch (error) {
    console.error('Failed to toggle server:', error)
  }
}

// 测试连接
const testConnection = async (server) => {
  try {
    const result = await mcpApi.test(server.id || 0)
    if (result.connectivity) {
      alert('✅ 连接成功')
    } else {
      alert('❌ 连接失败')
    }
  } catch (error) {
    alert('❌ 测试失败: ' + error.message)
  }
}

// 编辑服务器
const editServer = (server) => {
  editingServer.value = server
  formData.value = {
    name: server.name,
    server_url: server.server_url,
    health_check_path: server.health_check_path || '/health',
    description: server.description || '',
    tools: server.tools || []
  }
  toolsInput.value = server.tools?.join(', ') || ''
  showAddDialog.value = true
}

// 删除服务器
const deleteServer = (server) => {
  deletingServer.value = server
  showDeleteConfirm.value = true
}

const confirmDelete = async () => {
  showDeleteConfirm.value = false
  if (!deletingServer.value) return
  
  try {
    await mcpApi.delete(deletingServer.value.id)
    servers.value = servers.value.filter(s => s.id !== deletingServer.value.id)
  } catch (error) {
    alert('删除失败: ' + error.message)
  }
}

// 文件处理
const handleFileDrop = (e) => {
  isDragover.value = false
  const file = e.dataTransfer.files[0]
  if (file) processFile(file)
}

const handleFileSelect = (e) => {
  const file = e.target.files[0]
  if (file) processFile(file)
}

const processFile = async (file) => {
  if (!file.name.endsWith('.json')) {
    jsonError.value = '仅支持 .json 文件'
    return
  }
  
  if (file.size > 1024 * 1024) {
    jsonError.value = '文件大小不能超过 1MB'
    return
  }
  
  const text = await file.text()
  try {
    const data = JSON.parse(text)
    formData.value = {
      name: data.name || '',
      server_url: data.server_url || '',
      health_check_path: data.health_check_path || '/health',
      description: data.description || '',
      tools: data.tools || []
    }
    toolsInput.value = data.tools?.join(', ') || ''
    jsonInput.value = text
    activeTab.value = 'form'
    jsonError.value = ''
  } catch {
    jsonError.value = '无效的 JSON 格式'
  }
}

// 关闭弹窗
const closeDialog = () => {
  showAddDialog.value = false
  editingServer.value = null
  formData.value = {
    name: '',
    server_url: '',
    health_check_path: '/health',
    description: '',
    tools: []
  }
  toolsInput.value = ''
  jsonInput.value = ''
  jsonError.value = ''
  activeTab.value = 'form'
}

// 保存服务器
const saveServer = async () => {
  // 处理 JSON 输入
  if (activeTab.value === 'json') {
    try {
      const data = JSON.parse(jsonInput.value)
      formData.value = {
        name: data.name || '',
        server_url: data.server_url || '',
        health_check_path: data.health_check_path || '/health',
        description: data.description || '',
        tools: data.tools || []
      }
    } catch {
      jsonError.value = '无效的 JSON 格式'
      return
    }
  }
  
  // 处理工具列表
  if (toolsInput.value) {
    formData.value.tools = toolsInput.value.split(',').map(t => t.trim()).filter(Boolean)
  }
  
  // 验证
  if (!formData.value.name || !formData.value.server_url) {
    alert('请填写必填字段')
    return
  }
  
  isSaving.value = true
  
  try {
    if (editingServer.value) {
      await mcpApi.update(editingServer.value.id, formData.value)
    } else {
      await mcpApi.addConfig(formData.value)
    }
    
    // 重新加载
    servers.value = await mcpApi.list()
    closeDialog()
  } catch (error) {
    alert('保存失败: ' + (error.response?.data?.message || error.message))
  } finally {
    isSaving.value = false
  }
}
</script>

<style lang="scss" scoped>
.mcp-manager {
  min-height: 100vh;
}

.section {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 20px;
}

.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 20px;
}

.server-card {
  .server-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }
  
  .server-info h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 4px;
  }
  
  .server-url {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }
  
  .server-desc {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 16px;
    line-height: 1.5;
  }
  
  .server-tools {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
    
    .tool-label {
      font-size: 12px;
      color: var(--text-muted);
    }
  }
  
  .server-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }
  
  .last-check {
    font-size: 11px;
    color: var(--text-muted);
  }
  
  .server-actions {
    display: flex;
    gap: 4px;
  }
}

// Switch 开关
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  
  input {
    opacity: 0;
    width: 0;
    height: 0;
  }
  
  .slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--bg-hover);
    border-radius: 24px;
    transition: all 0.3s;
    
    &::before {
      content: '';
      position: absolute;
      width: 18px;
      height: 18px;
      left: 3px;
      bottom: 3px;
      background: var(--text-secondary);
      border-radius: 50%;
      transition: all 0.3s;
    }
  }
  
  input:checked + .slider {
    background: var(--primary);
    
    &::before {
      transform: translateX(20px);
      background: white;
    }
  }
}

// Modal
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  width: 560px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
  
  h3 {
    font-size: 18px;
    font-weight: 600;
  }
  
  .close-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: var(--radius-md);
    
    &:hover {
      background: var(--bg-hover);
    }
  }
}

.modal-tabs {
  display: flex;
  gap: 4px;
  padding: 16px 0;
  border-bottom: 1px solid var(--border-color);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.json-editor {
  font-family: var(--font-mono);
  font-size: 13px;
}

.upload-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover,
  &.dragover {
    border-color: var(--primary);
    background: var(--primary-light);
  }
  
  .upload-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }
  
  p {
    color: var(--text-secondary);
    margin-bottom: 4px;
  }
  
  .hint {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

