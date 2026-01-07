<template>
  <div class="mcp-manager">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="title-group">
          <h1>
            <span class="icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/>
              </svg>
            </span>
            MCP 服务器管理
          </h1>
          <p class="subtitle">管理 Model Context Protocol 服务器，扩展 AI 模型能力</p>
        </div>
      </div>
    </header>
    
    <!-- Content -->
    <div class="page-content">
      <!-- Preset Servers -->
      <section class="section">
        <div class="section-header">
          <h2>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M12 1v6m0 6v10M4.22 4.22l4.24 4.24m7.08 7.08l4.24 4.24M1 12h6m6 0h10M4.22 19.78l4.24-4.24m7.08-7.08l4.24-4.24"/>
            </svg>
            预置服务器
          </h2>
        </div>
        
        <div class="server-grid">
          <article v-for="server in presetServers" :key="server.name" class="server-card">
            <div class="card-header">
              <div class="server-info">
                <div class="server-icon preset">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                    <path d="M8 21h8M12 17v4"/>
                  </svg>
                </div>
                <div class="server-details">
                  <h3>{{ server.name }}</h3>
                  <span class="server-url">{{ server.server_url }}</span>
                </div>
              </div>
              <label class="toggle-switch">
                <input 
                  type="checkbox" 
                  :checked="server.status === 'enabled'"
                  @change="toggleServer(server)"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>
            
            <div class="card-body">
              <p class="server-desc">{{ server.description }}</p>
              <div class="server-tools">
                <span class="tools-label">工具:</span>
                <div class="tools-list">
                  <span v-for="tool in server.tools" :key="tool" class="tool-tag">
                    {{ tool }}
                  </span>
                </div>
              </div>
            </div>
            
            <div class="card-footer">
              <button class="test-btn" @click="testConnection(server)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                测试连接
              </button>
              <span :class="['status-badge', getStatusClass(server.status)]">
                <span class="status-dot"></span>
                {{ getStatusLabel(server.status) }}
              </span>
            </div>
          </article>
        </div>
      </section>
      
      <!-- Custom Servers -->
      <section class="section">
        <div class="section-header">
          <h2>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
            </svg>
            自定义服务器
          </h2>
          <button class="add-server-btn" @click="showAddDialog = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
            添加服务器
          </button>
        </div>
        
        <div v-if="customServers.length === 0" class="empty-state">
          <div class="empty-illustration">
            <svg viewBox="0 0 200 200" fill="none">
              <circle cx="100" cy="100" r="80" fill="#f1f5f9"/>
              <rect x="65" y="60" width="70" height="50" rx="4" fill="#e2e8f0"/>
              <circle cx="80" cy="75" r="4" fill="#cbd5e1"/>
              <circle cx="95" cy="75" r="4" fill="#cbd5e1"/>
              <rect x="65" y="120" width="70" height="30" rx="4" fill="#e2e8f0"/>
              <circle cx="80" cy="135" r="4" fill="#cbd5e1"/>
              <circle cx="95" cy="135" r="4" fill="#cbd5e1"/>
              <circle cx="100" cy="100" r="15" fill="#6366f1" opacity="0.2"/>
              <path d="M95 100h10M100 95v10" stroke="#6366f1" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <h3>暂无自定义服务器</h3>
          <p>添加您自己的 MCP 服务器来扩展 AI 能力</p>
          <button class="add-btn-primary" @click="showAddDialog = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
            添加服务器
          </button>
        </div>
        
        <div v-else class="server-grid">
          <article v-for="server in customServers" :key="server.id" class="server-card custom">
            <div class="card-header">
              <div class="server-info">
                <div class="server-icon custom">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                  </svg>
                </div>
                <div class="server-details">
                  <h3>{{ server.name }}</h3>
                  <span class="server-url">{{ server.server_url }}</span>
                </div>
              </div>
              <div class="card-actions">
                <button class="icon-btn" @click="editServer(server)" title="编辑">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="icon-btn danger" @click="deleteServer(server)" title="删除">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                  </svg>
                </button>
              </div>
            </div>
            
            <div class="card-body">
              <div class="server-tools" v-if="server.tools?.length">
                <span class="tools-label">工具:</span>
                <div class="tools-list">
                  <span v-for="tool in server.tools" :key="tool" class="tool-tag">
                    {{ tool }}
                  </span>
                </div>
              </div>
            </div>
            
            <div class="card-footer">
              <span :class="['status-badge', getStatusClass(server.status)]">
                <span class="status-dot"></span>
                {{ getStatusLabel(server.status) }}
              </span>
              <span v-if="server.last_check" class="last-check">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 6v6l4 2"/>
                </svg>
                {{ formatTime(server.last_check) }}
              </span>
            </div>
          </article>
        </div>
      </section>
    </div>
    
    <!-- Add/Edit Modal -->
    <a-modal
      v-model:open="showAddDialog"
      :title="editingServer ? '编辑服务器' : '添加 MCP 服务器'"
      width="640px"
      :footer="null"
      @cancel="closeDialog"
      class="server-modal"
    >
      <a-tabs v-model:activeKey="activeTab" class="modal-tabs">
        <a-tab-pane key="form" tab="表单配置">
          <div class="form-section">
            <div class="form-group">
              <label>服务器名称 <span class="required">*</span></label>
              <input v-model="formData.name" type="text" class="form-input" placeholder="My MCP Server" />
            </div>
            <div class="form-group">
              <label>服务器 URL <span class="required">*</span></label>
              <input v-model="formData.server_url" type="text" class="form-input" placeholder="https://mcp.example.com" />
            </div>
            <div class="form-group">
              <label>健康检查路径</label>
              <input v-model="formData.health_check_path" type="text" class="form-input" placeholder="/health" />
            </div>
            <div class="form-group">
              <label>工具列表 (逗号分隔)</label>
              <input v-model="toolsInput" type="text" class="form-input" placeholder="search, retrieve, store" />
            </div>
            <div class="form-group">
              <label>描述</label>
              <textarea v-model="formData.description" class="form-textarea" rows="3" placeholder="服务器描述..."></textarea>
            </div>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="json" tab="JSON 编辑">
          <div class="json-editor-section">
            <textarea 
              v-model="jsonInput"
              class="json-editor"
              :class="{ error: jsonError }"
              rows="15"
              placeholder='{"name": "...", "server_url": "...", "tools": [...]}'
            ></textarea>
            <p v-if="jsonError" class="error-text">{{ jsonError }}</p>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="upload" tab="文件上传">
          <div class="upload-section">
            <label class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
              <input type="file" accept=".json" @change="handleFileSelect" hidden />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
              </svg>
              <p class="upload-title">点击或拖拽文件到此区域上传</p>
              <p class="upload-hint">支持 .json 格式，最大 1MB</p>
            </label>
          </div>
        </a-tab-pane>
      </a-tabs>
      
      <div class="modal-footer">
        <button class="modal-btn secondary" @click="closeDialog">取消</button>
        <button class="modal-btn primary" @click="saveServer" :disabled="isSaving">
          <span v-if="isSaving" class="btn-spinner"></span>
          {{ editingServer ? '保存' : '添加' }}
        </button>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, createVNode } from 'vue'
import { mcpApi } from '@/api'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

const servers = ref([])
const showAddDialog = ref(false)
const activeTab = ref('form')
const editingServer = ref(null)
const isSaving = ref(false)
const jsonError = ref('')

const formData = ref({
  name: '',
  server_url: '',
  health_check_path: '/health',
  description: '',
  tools: []
})
const toolsInput = ref('')
const jsonInput = ref('')

const presetServers = computed(() => servers.value.filter(s => s.is_preset))
const customServers = computed(() => servers.value.filter(s => !s.is_preset))

onMounted(async () => {
  try {
    servers.value = await mcpApi.list()
  } catch (error) {
    console.error('Failed to load MCP servers:', error)
    message.error('加载服务器列表失败')
  }
})

const getStatusClass = (status) => {
  return status === 'enabled' ? 'success' : (status === 'error' ? 'error' : 'warning')
}

const getStatusLabel = (status) => {
  const map = {
    enabled: '已启用',
    disabled: '已禁用',
    error: '连接失败'
  }
  return map[status] || status
}

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

const toggleServer = async (server) => {
  try {
    const enable = server.status !== 'enabled'
    await mcpApi.toggle(server.name.toLowerCase(), enable)
    server.status = enable ? 'enabled' : 'disabled'
    message.success(enable ? '已启用' : '已禁用')
  } catch (error) {
    console.error('Failed to toggle server:', error)
    message.error('切换状态失败')
  }
}

const testConnection = async (server) => {
  const hide = message.loading('正在测试连接...', 0)
  try {
    const result = await mcpApi.test(server.id || 0)
    hide()
    if (result.connectivity) {
      message.success('连接成功')
    } else {
      message.error('连接失败')
    }
  } catch (error) {
    hide()
    message.error('测试失败: ' + error.message)
  }
}

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

const deleteServer = (server) => {
  Modal.confirm({
    title: '删除服务器',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要删除「${server.name}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await mcpApi.delete(server.id)
        servers.value = servers.value.filter(s => s.id !== server.id)
        message.success('删除成功')
      } catch (error) {
        message.error('删除失败: ' + error.message)
      }
    }
  });
}

const handleFileSelect = async (e) => {
  const file = e.target.files[0]
  if (file) await processFile(file)
}

const handleDrop = async (e) => {
  const file = e.dataTransfer.files[0]
  if (file) await processFile(file)
}

const processFile = async (file) => {
  if (!file.name.endsWith('.json')) {
    message.error('仅支持 .json 文件')
    return
  }
  
  if (file.size > 1024 * 1024) {
    message.error('文件大小不能超过 1MB')
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
    message.success('文件解析成功')
  } catch {
    message.error('无效的 JSON 格式')
  }
}

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

const saveServer = async () => {
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
  
  if (toolsInput.value) {
    formData.value.tools = toolsInput.value.split(',').map(t => t.trim()).filter(Boolean)
  }
  
  if (!formData.value.name || !formData.value.server_url) {
    message.warning('请填写必填字段')
    return
  }
  
  isSaving.value = true
  
  try {
    if (editingServer.value) {
      await mcpApi.update(editingServer.value.id, formData.value)
    } else {
      await mcpApi.addConfig(formData.value)
    }
    
    servers.value = await mcpApi.list()
    closeDialog()
    message.success('保存成功')
  } catch (error) {
    message.error('保存失败: ' + (error.response?.data?.message || error.message))
  } finally {
    isSaving.value = false
  }
}
</script>

<style lang="scss" scoped>
.mcp-manager {
  min-height: 100vh;
  background: var(--bg-body);
}

.page-header {
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
}

.page-content {
  padding: 32px 48px;
  max-width: 1600px;
}

.section {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  
  h2 {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
    
    svg {
      width: 20px;
      height: 20px;
      color: var(--primary);
    }
  }
}

.add-server-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: var(--primary-hover);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }
}

.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 20px;
}

.server-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.2s;
  
  &:hover {
    box-shadow: var(--shadow-md);
    border-color: rgba(99, 102, 241, 0.2);
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid var(--border-light);
    background: linear-gradient(to bottom, var(--bg-elevated) 0%, var(--bg-subtle) 100%);
  }
  
  .server-info {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  
  .server-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 22px;
      height: 22px;
    }
    
    &.preset {
      background: linear-gradient(135deg, var(--primary-light) 0%, rgba(99, 102, 241, 0.2) 100%);
      color: var(--primary);
    }
    
    &.custom {
      background: linear-gradient(135deg, var(--accent-light) 0%, rgba(245, 158, 11, 0.2) 100%);
      color: var(--accent);
    }
  }
  
  .server-details {
    h3 {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-heading);
      margin: 0 0 4px 0;
    }
    
    .server-url {
      font-size: 12px;
      font-family: var(--font-mono);
      color: var(--text-muted);
    }
  }
  
  .card-body {
    padding: 20px;
  }
  
  .server-desc {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0 0 16px 0;
  }
  
  .server-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    
    .tools-label {
      font-size: 12px;
      color: var(--text-muted);
    }
    
    .tools-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    
    .tool-tag {
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 500;
      color: var(--primary);
      background: var(--primary-light);
      border-radius: 20px;
    }
  }
  
  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-top: 1px solid var(--border-light);
    background: var(--bg-subtle);
  }
  
  .card-actions {
    display: flex;
    gap: 8px;
  }
}

.toggle-switch {
  position: relative;
  width: 48px;
  height: 26px;
  
  input {
    opacity: 0;
    width: 0;
    height: 0;
    
    &:checked + .toggle-slider {
      background: var(--primary);
      
      &::before {
        transform: translateX(22px);
      }
    }
  }
  
  .toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--border-color);
    border-radius: 26px;
    transition: all 0.2s;
    
    &::before {
      content: '';
      position: absolute;
      height: 20px;
      width: 20px;
      left: 3px;
      bottom: 3px;
      background: white;
      border-radius: 50%;
      transition: transform 0.2s;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
  }
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-subtle);
  border: none;
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: var(--primary-light);
    color: var(--primary);
  }
  
  &.danger:hover {
    background: var(--error-light);
    color: var(--error);
  }
}

.test-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  
  &.success {
    color: var(--success);
    .status-dot { background: var(--success); }
  }
  
  &.warning {
    color: #b45309;
    .status-dot { background: var(--warning); }
  }
  
  &.error {
    color: var(--error);
    .status-dot { background: var(--error); }
  }
}

.last-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
  
  svg {
    width: 12px;
    height: 12px;
  }
}

.empty-state {
  text-align: center;
  padding: 60px 24px;
  background: var(--bg-elevated);
  border: 2px dashed var(--border-color);
  border-radius: 16px;
  
  .empty-illustration {
    margin-bottom: 20px;
    
    svg {
      width: 160px;
      height: 160px;
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
  }
}

.add-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 24px;
  font-size: 15px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: var(--primary-hover);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
  }
}

// Modal Styles
:deep(.server-modal) {
  .ant-modal-content {
    border-radius: 20px;
  }
  
  .ant-modal-header {
    padding: 24px 24px 16px;
    border-bottom: none;
  }
  
  .ant-modal-body {
    padding: 0 24px 24px;
  }
}

.modal-tabs {
  :deep(.ant-tabs-nav) {
    margin-bottom: 20px;
  }
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 8px;
    
    .required {
      color: var(--error);
    }
  }
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 14px;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  outline: none;
  transition: all 0.2s;
  
  &::placeholder {
    color: var(--text-muted);
  }
  
  &:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-light);
    background: var(--bg-elevated);
  }
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.json-editor-section {
  .json-editor {
    width: 100%;
    padding: 16px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
    color: var(--text-primary);
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    outline: none;
    resize: vertical;
    transition: all 0.2s;
    
    &:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-light);
    }
    
    &.error {
      border-color: var(--error);
    }
  }
  
  .error-text {
    margin-top: 8px;
    font-size: 13px;
    color: var(--error);
  }
}

.upload-section {
  .upload-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    background: var(--bg-subtle);
    border: 2px dashed var(--border-color);
    border-radius: 16px;
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover {
      border-color: var(--primary);
      background: var(--primary-light);
    }
    
    svg {
      width: 48px;
      height: 48px;
      color: var(--text-muted);
      margin-bottom: 16px;
    }
    
    .upload-title {
      font-size: 15px;
      font-weight: 500;
      color: var(--text-secondary);
      margin-bottom: 4px;
    }
    
    .upload-hint {
      font-size: 13px;
      color: var(--text-muted);
    }
  }
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-light);
}

.modal-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 24px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  
  &.secondary {
    background: var(--bg-subtle);
    color: var(--text-secondary);
    
    &:hover {
      background: var(--border-color);
    }
  }
  
  &.primary {
    background: var(--primary);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--primary-hover);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
