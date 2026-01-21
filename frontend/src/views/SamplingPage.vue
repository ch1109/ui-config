<template>
  <div class="sampling-page">
    <!-- 页面头部 -->
    <header class="page-header">
      <div class="header-content">
        <h1>🧠 MCP Sampling 管理</h1>
        <p class="subtitle">管理 MCP Server 的 LLM 请求能力</p>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" @click="refreshAll" :disabled="loading">
          <span :class="{ rotating: loading }">🔄</span>
          刷新
        </button>
      </div>
    </header>

    <!-- 状态概览 -->
    <section class="status-overview">
      <div class="status-card">
        <div class="status-icon">📊</div>
        <div class="status-info">
          <span class="status-value">{{ status?.pending_requests_count || 0 }}</span>
          <span class="status-label">待审核请求</span>
        </div>
      </div>
      <div class="status-card">
        <div class="status-icon">🖥️</div>
        <div class="status-info">
          <span class="status-value">{{ samplingServers.length }}</span>
          <span class="status-label">支持的服务器</span>
        </div>
      </div>
      <div class="status-card">
        <div class="status-icon">⏱️</div>
        <div class="status-info">
          <span class="status-value">{{ config.rate_limit_per_minute }}/分钟</span>
          <span class="status-label">全局速率限制</span>
        </div>
      </div>
      <div class="status-card">
        <div class="status-icon">🔒</div>
        <div class="status-info">
          <span class="status-value">{{ config.require_approval ? '开启' : '关闭' }}</span>
          <span class="status-label">人工审核</span>
        </div>
      </div>
    </section>

    <!-- 主要内容区 -->
    <div class="main-content">
      <!-- 左侧：配置面板 -->
      <section class="config-panel">
        <div class="panel-header">
          <h2>⚙️ 安全配置</h2>
          <button class="btn-save" @click="saveConfig" :disabled="saving">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
        </div>
        
        <div class="config-form">
          <!-- Token 限制 -->
          <div class="config-group">
            <h3>Token 限制</h3>
            <div class="form-row">
              <label>最大 Token 限制</label>
              <input 
                type="number" 
                v-model.number="config.max_tokens_limit" 
                min="100" 
                max="32000"
              />
              <span class="hint">单次请求允许的最大 token 数</span>
            </div>
            <div class="form-row">
              <label>默认 Token 数</label>
              <input 
                type="number" 
                v-model.number="config.default_max_tokens" 
                min="100" 
                max="8000"
              />
              <span class="hint">请求未指定时使用的默认值</span>
            </div>
          </div>

          <!-- 速率限制 -->
          <div class="config-group">
            <h3>速率限制</h3>
            <div class="form-row">
              <label>全局限制（/分钟）</label>
              <input 
                type="number" 
                v-model.number="config.rate_limit_per_minute" 
                min="1" 
                max="1000"
              />
            </div>
            <div class="form-row">
              <label>每 Server 限制（/分钟）</label>
              <input 
                type="number" 
                v-model.number="config.rate_limit_per_server" 
                min="1" 
                max="100"
              />
            </div>
          </div>

          <!-- 审核策略 -->
          <div class="config-group">
            <h3>审核策略</h3>
            <div class="form-row checkbox-row">
              <label>
                <input type="checkbox" v-model="config.require_approval" />
                启用人工审核
              </label>
              <span class="hint">启用后，超过阈值的请求需要人工批准</span>
            </div>
            <div class="form-row" v-if="config.require_approval">
              <label>自动批准阈值</label>
              <input 
                type="number" 
                v-model.number="config.auto_approve_threshold" 
                min="10" 
                max="1000"
              />
              <span class="hint">低于此 token 数的请求自动批准</span>
            </div>
            <div class="form-row" v-if="config.require_approval">
              <label>审核超时（秒）</label>
              <input 
                type="number" 
                v-model.number="config.approval_timeout_seconds" 
                min="60" 
                max="3600"
              />
            </div>
          </div>

          <!-- 内容过滤 -->
          <div class="config-group">
            <h3>内容过滤</h3>
            <div class="form-row checkbox-row">
              <label>
                <input type="checkbox" v-model="config.enable_content_filter" />
                启用内容过滤
              </label>
            </div>
            <div class="form-row" v-if="config.enable_content_filter">
              <label>禁止关键词</label>
              <textarea 
                v-model="blockedKeywordsText" 
                placeholder="每行一个关键词"
                rows="3"
              ></textarea>
            </div>
          </div>

          <!-- Server 权限 -->
          <div class="config-group">
            <h3>Server 权限</h3>
            <div class="form-row">
              <label>黑名单 Server</label>
              <textarea 
                v-model="blockedServersText" 
                placeholder="每行一个 Server Key"
                rows="2"
              ></textarea>
              <span class="hint">这些 Server 将被禁止使用 Sampling</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 右侧：请求队列 + 服务器列表 -->
      <div class="right-column">
        <section class="requests-panel">
          <div class="panel-header">
            <h2>📋 待审核请求</h2>
            <button class="btn-cleanup" @click="cleanupExpired" :disabled="cleaning">
              {{ cleaning ? '清理中...' : '清理过期' }}
            </button>
          </div>

          <div class="requests-list" v-if="pendingRequests.length > 0">
            <div 
              v-for="request in pendingRequests" 
              :key="request.id" 
              class="request-card"
            >
              <div class="request-header">
                <span class="request-server">{{ request.server_key }}</span>
                <span class="request-time">{{ formatTime(request.created_at) }}</span>
              </div>
              
              <div class="request-content">
                <div class="request-messages">
                  <div 
                    v-for="(msg, idx) in request.messages.slice(-2)" 
                    :key="idx"
                    class="message-preview"
                    :class="msg.role"
                  >
                    <span class="role-badge">{{ msg.role }}</span>
                    <span class="message-text">{{ getMessageText(msg) }}</span>
                  </div>
                </div>
                
                <div class="request-meta">
                  <span class="meta-item">
                    <span class="meta-icon">🎯</span>
                    {{ request.max_tokens }} tokens
                  </span>
                  <span class="meta-item" v-if="request.system_prompt">
                    <span class="meta-icon">📝</span>
                    有系统提示词
                  </span>
                </div>
              </div>

              <div class="request-actions">
                <button 
                  class="btn-approve" 
                  @click="approveRequest(request)"
                  :disabled="processingId === request.id"
                >
                  ✓ 批准
                </button>
                <button 
                  class="btn-reject" 
                  @click="showRejectModal(request)"
                  :disabled="processingId === request.id"
                >
                  ✗ 拒绝
                </button>
                <button 
                  class="btn-detail" 
                  @click="showDetailModal(request)"
                >
                  详情
                </button>
              </div>
            </div>
          </div>

          <div class="empty-state" v-else>
            <div class="empty-icon">📭</div>
            <p>暂无待审核的请求</p>
            <span class="empty-hint">
              {{ config.require_approval ? '当 MCP Server 发起高 Token 请求时会显示在这里' : '当前审核功能已关闭' }}
            </span>
          </div>
        </section>

        <!-- 支持的服务器列表 -->
        <section class="servers-section">
          <h2>🖥️ 支持 Sampling 的服务器</h2>
          <div class="servers-grid" v-if="samplingServers.length > 0">
            <div 
              v-for="server in samplingServers" 
              :key="server.server_key"
              class="server-card"
              :class="{ active: server.listener_active || server.connected }"
            >
              <div class="server-status">
                <span class="status-dot" :class="{ active: server.listener_active || server.connected }"></span>
              </div>
              <div class="server-info">
                <span class="server-name">{{ server.server_key }}</span>
                <span class="server-transport">{{ server.transport.toUpperCase() }}</span>
              </div>
            </div>
          </div>
          <div class="empty-state small" v-else>
            <p>暂无支持 Sampling 的服务器</p>
            <span class="empty-hint">请先在 MCP 管理页面启动服务器</span>
          </div>
        </section>
      </div>
    </div>

    <!-- 拒绝原因弹窗 -->
    <div v-if="rejectModalVisible" class="modal-overlay" @click.self="rejectModalVisible = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>拒绝请求</h3>
          <button class="close-btn" @click="rejectModalVisible = false">×</button>
        </div>
        <div class="modal-body">
          <p>请输入拒绝原因（可选）：</p>
          <textarea 
            v-model="rejectReason" 
            placeholder="例如：请求内容不符合要求"
            rows="3"
          ></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="rejectModalVisible = false">取消</button>
          <button class="btn-confirm" @click="confirmReject">确认拒绝</button>
        </div>
      </div>
    </div>

    <!-- 请求详情弹窗 -->
    <div v-if="detailModalVisible" class="modal-overlay" @click.self="detailModalVisible = false">
      <div class="modal-content large">
        <div class="modal-header">
          <h3>请求详情</h3>
          <button class="close-btn" @click="detailModalVisible = false">×</button>
        </div>
        <div class="modal-body" v-if="selectedRequest">
          <div class="detail-section">
            <h4>基本信息</h4>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">请求 ID</span>
                <span class="detail-value mono">{{ selectedRequest.id }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">来源 Server</span>
                <span class="detail-value">{{ selectedRequest.server_key }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Max Tokens</span>
                <span class="detail-value">{{ selectedRequest.max_tokens }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">温度</span>
                <span class="detail-value">{{ selectedRequest.temperature || '默认' }}</span>
              </div>
            </div>
          </div>
          
          <div class="detail-section" v-if="selectedRequest.system_prompt">
            <h4>系统提示词</h4>
            <pre class="detail-code">{{ selectedRequest.system_prompt }}</pre>
          </div>
          
          <div class="detail-section">
            <h4>消息内容</h4>
            <div class="messages-detail">
              <div 
                v-for="(msg, idx) in selectedRequest.messages" 
                :key="idx"
                class="message-item"
                :class="msg.role"
              >
                <span class="role-label">{{ msg.role }}</span>
                <div class="message-content">{{ getMessageText(msg) }}</div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="detailModalVisible = false">关闭</button>
          <button class="btn-reject" @click="showRejectModal(selectedRequest)">拒绝</button>
          <button class="btn-approve" @click="approveRequest(selectedRequest); detailModalVisible = false">批准</button>
        </div>
      </div>
    </div>

    <!-- 提示消息 -->
    <div v-if="toast.visible" class="toast" :class="toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { mcpHostApi } from '@/api'

// 状态
const loading = ref(false)
const saving = ref(false)
const cleaning = ref(false)
const processingId = ref(null)

const status = ref(null)
const config = reactive({
  max_tokens_limit: 4096,
  default_max_tokens: 1024,
  rate_limit_per_minute: 60,
  rate_limit_per_server: 10,
  enable_content_filter: true,
  blocked_keywords: [],
  require_approval: false,
  auto_approve_threshold: 100,
  approval_timeout_seconds: 300,
  allowed_servers: [],
  blocked_servers: []
})

const pendingRequests = ref([])
const samplingServers = ref([])

// 弹窗状态
const rejectModalVisible = ref(false)
const detailModalVisible = ref(false)
const selectedRequest = ref(null)
const rejectReason = ref('')

// 提示消息
const toast = reactive({
  visible: false,
  message: '',
  type: 'info'
})

// 计算属性 - 关键词列表文本
const blockedKeywordsText = computed({
  get: () => config.blocked_keywords.join('\n'),
  set: (val) => {
    config.blocked_keywords = val.split('\n').map(s => s.trim()).filter(s => s)
  }
})

const blockedServersText = computed({
  get: () => config.blocked_servers.join('\n'),
  set: (val) => {
    config.blocked_servers = val.split('\n').map(s => s.trim()).filter(s => s)
  }
})

// 定时刷新
let refreshInterval = null

onMounted(async () => {
  await refreshAll()
  // 每 10 秒刷新待审核请求
  refreshInterval = setInterval(refreshRequests, 10000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

// 刷新所有数据
async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([
      loadConfig(),
      loadStatus(),
      refreshRequests(),
      loadServers()
    ])
  } finally {
    loading.value = false
  }
}

// 加载配置
async function loadConfig() {
  try {
    const res = await mcpHostApi.getSamplingConfig()
    Object.assign(config, res)
  } catch (e) {
    showToast('加载配置失败', 'error')
  }
}

// 加载状态
async function loadStatus() {
  try {
    status.value = await mcpHostApi.getSamplingStatus()
  } catch (e) {
    console.error('加载状态失败:', e)
  }
}

// 刷新待审核请求
async function refreshRequests() {
  try {
    const res = await mcpHostApi.getSamplingRequests()
    pendingRequests.value = res.requests || []
  } catch (e) {
    console.error('加载请求失败:', e)
  }
}

// 加载服务器列表
async function loadServers() {
  try {
    const res = await mcpHostApi.getSamplingServers()
    samplingServers.value = res.servers || []
  } catch (e) {
    console.error('加载服务器失败:', e)
  }
}

// 保存配置
async function saveConfig() {
  saving.value = true
  try {
    await mcpHostApi.updateSamplingConfig({
      max_tokens_limit: config.max_tokens_limit,
      default_max_tokens: config.default_max_tokens,
      rate_limit_per_minute: config.rate_limit_per_minute,
      rate_limit_per_server: config.rate_limit_per_server,
      enable_content_filter: config.enable_content_filter,
      blocked_keywords: config.blocked_keywords,
      require_approval: config.require_approval,
      auto_approve_threshold: config.auto_approve_threshold,
      approval_timeout_seconds: config.approval_timeout_seconds,
      blocked_servers: config.blocked_servers
    })
    showToast('配置已保存', 'success')
  } catch (e) {
    showToast('保存失败: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

// 批准请求
async function approveRequest(request) {
  processingId.value = request.id
  try {
    await mcpHostApi.approveSamplingRequest(request.id)
    showToast('请求已批准', 'success')
    await refreshRequests()
  } catch (e) {
    showToast('批准失败: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    processingId.value = null
  }
}

// 显示拒绝弹窗
function showRejectModal(request) {
  selectedRequest.value = request
  rejectReason.value = ''
  rejectModalVisible.value = true
  detailModalVisible.value = false
}

// 确认拒绝
async function confirmReject() {
  if (!selectedRequest.value) return
  
  processingId.value = selectedRequest.value.id
  rejectModalVisible.value = false
  
  try {
    await mcpHostApi.rejectSamplingRequest(
      selectedRequest.value.id, 
      rejectReason.value || '用户拒绝了此请求'
    )
    showToast('请求已拒绝', 'success')
    await refreshRequests()
  } catch (e) {
    showToast('拒绝失败: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    processingId.value = null
    selectedRequest.value = null
  }
}

// 显示详情弹窗
function showDetailModal(request) {
  selectedRequest.value = request
  detailModalVisible.value = true
}

// 清理过期请求
async function cleanupExpired() {
  cleaning.value = true
  try {
    const res = await mcpHostApi.cleanupSamplingRequests()
    if (res.expired_count > 0) {
      showToast(`已清理 ${res.expired_count} 个过期请求`, 'success')
      await refreshRequests()
    } else {
      showToast('没有过期请求需要清理', 'info')
    }
  } catch (e) {
    showToast('清理失败', 'error')
  } finally {
    cleaning.value = false
  }
}

// 获取消息文本
function getMessageText(msg) {
  if (!msg || !msg.content) return ''
  if (typeof msg.content === 'string') return msg.content
  if (msg.content.type === 'text') return msg.content.text || ''
  if (msg.content.type === 'image') return '[图片内容]'
  return JSON.stringify(msg.content)
}

// 格式化时间
function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = (now - date) / 1000
  
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 显示提示消息
function showToast(message, type = 'info') {
  toast.message = message
  toast.type = type
  toast.visible = true
  setTimeout(() => {
    toast.visible = false
  }, 3000)
}
</script>

<style scoped>
.sampling-page {
  min-height: 100vh;
  height: 100%;
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
  padding: 24px;
  color: #fff;
  display: flex;
  flex-direction: column;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.header-content h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  background: linear-gradient(135deg, #60a5fa, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-refresh:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.rotating {
  display: inline-block;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 状态概览 */
.status-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 10px;
}

.status-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.status-icon {
  font-size: 28px;
}

.status-info {
  display: flex;
  flex-direction: column;
}

.status-value {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.status-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

/* 主内容区 */
.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: stretch;
}

/* 右侧列容器 */
.right-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 配置面板 */
.config-panel {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.requests-panel {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.btn-save,
.btn-cleanup {
  padding: 8px 16px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-save:hover:not(:disabled),
.btn-cleanup:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.btn-save:disabled,
.btn-cleanup:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 配置表单 */
.config-form {
  padding: 12px 16px 8px;
}

.config-group {
  margin-bottom: 10px;
}

.config-group h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.form-row {
  margin-bottom: 8px;
}

.form-row label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.form-row input[type="number"],
.form-row textarea {
  width: 100%;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  transition: all 0.2s;
}

.form-row input:focus,
.form-row textarea:focus {
  outline: none;
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
}

.form-row textarea {
  resize: vertical;
  min-height: 60px;
}

.checkbox-row label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-row input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #3b82f6;
}

.hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

/* 请求列表 */
.requests-list {
  padding: 12px 16px;
  overflow-y: auto;
  flex: 1;
}

.request-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s;
}

.request-card:hover {
  border-color: rgba(59, 130, 246, 0.3);
}

.request-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.request-server {
  font-weight: 600;
  color: #60a5fa;
}

.request-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.request-messages {
  margin-bottom: 12px;
}

.message-preview {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-bottom: 8px;
}

.message-preview:last-child {
  margin-bottom: 0;
}

.role-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.message-preview.user .role-badge {
  background: rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.message-preview.assistant .role-badge {
  background: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.message-text {
  flex: 1;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.request-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.request-actions {
  display: flex;
  gap: 8px;
}

.btn-approve,
.btn-reject,
.btn-detail {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-approve {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.btn-approve:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.3);
}

.btn-reject {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.btn-reject:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
}

.btn-detail {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.btn-detail:hover {
  background: rgba(255, 255, 255, 0.15);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
  text-align: center;
  flex: 1;
}

.empty-state.small {
  padding: 12px 16px;
  flex: 0;
}

.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.empty-state p {
  margin: 0 0 6px;
  font-size: 15px;
  color: rgba(255, 255, 255, 0.7);
}

.empty-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.empty-state.small .empty-icon {
  display: none;
}

.empty-state.small p {
  font-size: 14px;
  margin-bottom: 4px;
}

/* 服务器列表 */
.servers-section {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px 16px;
  flex-shrink: 0;
}

.servers-section h2 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
}

.servers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}

.server-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.server-card.active {
  border-color: rgba(16, 185, 129, 0.3);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
}

.status-dot.active {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

.server-info {
  display: flex;
  flex-direction: column;
}

.server-name {
  font-size: 14px;
  font-weight: 500;
  color: #fff;
}

.server-transport {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #1e1e2e;
  border-radius: 16px;
  width: 480px;
  max-width: 90%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-content.large {
  width: 700px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
}

.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.modal-body p {
  margin: 0 0 12px;
  color: rgba(255, 255, 255, 0.8);
}

.modal-body textarea {
  width: 100%;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  resize: vertical;
}

.modal-body textarea:focus {
  outline: none;
  border-color: #3b82f6;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-cancel {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.btn-confirm {
  padding: 10px 20px;
  background: #ef4444;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

/* 详情弹窗 */
.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.detail-value {
  font-size: 14px;
  color: #fff;
}

.detail-value.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #60a5fa;
}

.detail-code {
  margin: 0;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 150px;
  overflow-y: auto;
}

.messages-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-item {
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.role-label {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.message-item.user .role-label {
  background: rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.message-item.assistant .role-label {
  background: rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.message-content {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.5;
}

/* 提示消息 */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 14px;
  z-index: 2000;
  animation: slideUp 0.3s ease;
}

.toast.success {
  background: rgba(16, 185, 129, 0.9);
  color: #fff;
}

.toast.error {
  background: rgba(239, 68, 68, 0.9);
  color: #fff;
}

.toast.info {
  background: rgba(59, 130, 246, 0.9);
  color: #fff;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translate(-50%, 20px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

/* 滚动条 */
.config-form::-webkit-scrollbar,
.requests-list::-webkit-scrollbar,
.modal-body::-webkit-scrollbar {
  width: 6px;
}

.config-form::-webkit-scrollbar-track,
.requests-list::-webkit-scrollbar-track,
.modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.config-form::-webkit-scrollbar-thumb,
.requests-list::-webkit-scrollbar-thumb,
.modal-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

/* 响应式 */
@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .right-column {
    flex-direction: column;
  }
  
  .status-overview {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .sampling-page {
    padding: 16px;
  }
  
  .status-overview {
    grid-template-columns: 1fr;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
