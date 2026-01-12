<template>
  <div class="mcp-host-page">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2>🔌 MCP Host</h2>
        <p class="subtitle">完整的 AI Agent 系统</p>
      </div>

      <!-- 服务器状态 -->
      <div class="sidebar-section">
        <h3>📡 连接状态</h3>
        <div class="server-list">
          <div
            v-for="(server, key) in servers.stdio"
            :key="key"
            class="server-item"
          >
            <span class="server-icon">{{ server.running ? '🟢' : '⚪' }}</span>
            <span class="server-name">{{ key }}</span>
            <span class="server-tools">{{ server.tools_count }} 工具</span>
          </div>
          
          <div v-if="Object.keys(servers.stdio).length === 0" class="no-servers">
            暂无连接的服务器
          </div>
        </div>
      </div>

      <!-- 风险策略 -->
      <div class="sidebar-section">
        <h3>🛡️ 安全策略</h3>
        <div class="policy-info">
          <div class="policy-row">
            <span>确认等级</span>
            <span class="policy-value">{{ policyLabels }}</span>
          </div>
          <div class="policy-row">
            <span>超时时间</span>
            <span class="policy-value">{{ policy.confirmation_timeout }}秒</span>
          </div>
          <div class="policy-row">
            <span>允许修改</span>
            <span class="policy-value">{{ policy.allow_modification ? '是' : '否' }}</span>
          </div>
        </div>
      </div>

      <!-- 健康状态 -->
      <div class="sidebar-section">
        <h3>💚 系统状态</h3>
        <div class="health-info" v-if="health">
          <div class="health-row">
            <span>状态</span>
            <span class="health-value" :class="health.status">
              {{ health.status === 'healthy' ? '健康' : '异常' }}
            </span>
          </div>
          <div class="health-row">
            <span>活跃会话</span>
            <span class="health-value">{{ health.active_sessions }}</span>
          </div>
          <div class="health-row">
            <span>待确认</span>
            <span class="health-value warning" v-if="health.pending_confirmations > 0">
              {{ health.pending_confirmations }}
            </span>
            <span class="health-value" v-else>0</span>
          </div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="sidebar-section">
        <h3>⚡ 快捷操作</h3>
        <div class="quick-actions">
          <button class="action-btn" @click="refreshServers">
            🔄 刷新状态
          </button>
          <button class="action-btn" @click="showAuditLog = true">
            📋 审计日志
          </button>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <ChatPanel ref="chatPanel" />
    </main>

    <!-- 审计日志弹窗 -->
    <div v-if="showAuditLog" class="audit-modal">
      <div class="audit-content">
        <div class="audit-header">
          <h3>📋 审计日志</h3>
          <button class="close-btn" @click="showAuditLog = false">×</button>
        </div>
        <div class="audit-body">
          <div v-if="auditLogs.length === 0" class="no-logs">
            暂无审计记录
          </div>
          <div
            v-for="log in auditLogs"
            :key="log.id"
            class="log-item"
            :class="log.status"
          >
            <div class="log-header">
              <span class="log-tool">{{ log.tool_name }}</span>
              <span class="log-status" :class="log.status">
                {{ statusLabels[log.status] }}
              </span>
            </div>
            <div class="log-meta">
              <span class="log-risk" :class="log.risk_level">
                {{ riskLabels[log.risk_level] }}
              </span>
              <span class="log-time">{{ formatTime(log.approved_at) }}</span>
            </div>
            <div v-if="log.rejection_reason" class="log-reason">
              原因: {{ log.rejection_reason }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { mcpHostApi } from '@/api'
import ChatPanel from '@/components/MCPHost/ChatPanel.vue'

// 状态
const servers = reactive({
  stdio: {},
  sse: {}
})

const policy = reactive({
  confirmation_levels: ['high', 'critical'],
  confirmation_timeout: 300,
  allow_modification: true
})

const health = ref(null)
const auditLogs = ref([])
const showAuditLog = ref(false)
const chatPanel = ref(null)

// 标签映射
const statusLabels = {
  approved: '已批准',
  rejected: '已拒绝',
  modified: '已修改',
  expired: '已过期'
}

const riskLabels = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '极高风险'
}

// 计算属性
const policyLabels = computed(() => {
  return policy.confirmation_levels
    .map(l => riskLabels[l] || l)
    .join('、')
})

// 初始化
onMounted(async () => {
  await Promise.all([
    refreshServers(),
    loadPolicy(),
    loadHealth()
  ])
  
  // 定时刷新健康状态
  startHealthCheck()
})

// 定时器
let healthInterval = null

function startHealthCheck() {
  healthInterval = setInterval(loadHealth, 30000) // 每30秒刷新
}

onUnmounted(() => {
  if (healthInterval) {
    clearInterval(healthInterval)
  }
})

// 刷新服务器状态
async function refreshServers() {
  try {
    const res = await mcpHostApi.listServers()
    servers.stdio = res.stdio_servers || {}
    servers.sse = res.sse_servers || {}
  } catch (e) {
    console.error('获取服务器状态失败:', e)
  }
}

// 加载策略
async function loadPolicy() {
  try {
    const res = await mcpHostApi.getPolicy()
    Object.assign(policy, res)
  } catch (e) {
    console.error('获取策略失败:', e)
  }
}

// 加载健康状态
async function loadHealth() {
  try {
    health.value = await mcpHostApi.health()
  } catch (e) {
    console.error('获取健康状态失败:', e)
  }
}

// 加载审计日志
async function loadAuditLogs() {
  try {
    const res = await mcpHostApi.getAuditLog(null, 50)
    auditLogs.value = res.logs || []
  } catch (e) {
    console.error('获取审计日志失败:', e)
  }
}

// 显示审计日志
function showAuditLogModal() {
  loadAuditLogs()
  showAuditLog.value = true
}

// 格式化时间
function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.mcp-host-page {
  display: flex;
  height: 100vh;
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
}

/* MCP Host 内部侧边栏 - 使用更具体的选择器避免与全局侧边栏冲突 */
.mcp-host-page > .sidebar {
  position: relative !important;
  width: 280px;
  min-width: 280px;
  background: rgba(255, 255, 255, 0.03) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow-y: auto;
  z-index: 1;
}

.sidebar-header {
  margin-bottom: 24px;
}

.sidebar-header h2 {
  margin: 0;
  color: #fff;
  font-size: 20px;
}

.subtitle {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
}

.sidebar-section {
  margin-bottom: 24px;
}

.sidebar-section h3 {
  margin: 0 0 12px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 服务器列表 */
.server-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.server-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.server-icon {
  font-size: 10px;
}

.server-name {
  flex: 1;
  color: #fff;
  font-size: 14px;
}

.server-tools {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.no-servers {
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  text-align: center;
  padding: 12px;
}

/* 策略信息 */
.policy-info,
.health-info {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
}

.policy-row,
.health-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.policy-row:not(:last-child),
.health-row:not(:last-child) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.policy-row span:first-child,
.health-row span:first-child {
  color: rgba(255, 255, 255, 0.6);
}

.policy-value,
.health-value {
  color: #fff;
}

.health-value.healthy {
  color: #10b981;
}

.health-value.warning {
  color: #f59e0b;
}

/* 快捷操作 */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-btn {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.2);
}

/* 主内容 */
.main-content {
  flex: 1;
  padding: 20px;
  overflow: hidden;
}

/* 审计日志弹窗 */
.audit-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.audit-content {
  background: #1e1e2e;
  border-radius: 16px;
  width: 600px;
  max-width: 90%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.audit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.audit-header h3 {
  margin: 0;
  color: #fff;
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

.audit-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.no-logs {
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  padding: 40px;
}

.log-item {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  margin-bottom: 10px;
  border-left: 3px solid;
}

.log-item.approved,
.log-item.modified {
  border-color: #10b981;
}

.log-item.rejected {
  border-color: #ef4444;
}

.log-item.expired {
  border-color: #6b7280;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.log-tool {
  color: #fff;
  font-weight: 500;
}

.log-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}

.log-status.approved,
.log-status.modified {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.log-status.rejected {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.log-status.expired {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.log-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
}

.log-risk {
  padding: 2px 8px;
  border-radius: 10px;
}

.log-risk.low {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.log-risk.medium {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.log-risk.high {
  background: rgba(249, 115, 22, 0.2);
  color: #f97316;
}

.log-risk.critical {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.log-time {
  color: rgba(255, 255, 255, 0.5);
}

.log-reason {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

/* 滚动条 */
.sidebar::-webkit-scrollbar,
.audit-body::-webkit-scrollbar {
  width: 6px;
}

.sidebar::-webkit-scrollbar-track,
.audit-body::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar::-webkit-scrollbar-thumb,
.audit-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

/* 响应式 */
@media (max-width: 768px) {
  .mcp-host-page {
    flex-direction: column;
  }
  
  .mcp-host-page > .sidebar {
    width: 100%;
    min-width: 100%;
    max-height: 200px;
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
}
</style>

