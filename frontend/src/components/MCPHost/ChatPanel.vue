<template>
  <div class="chat-panel">
    <!-- 头部 -->
    <div class="chat-header">
      <div class="header-left">
        <div class="title">
          <span class="icon">🤖</span>
          <span>MCP Host 对话</span>
        </div>
        <div class="status" :class="statusClass">
          {{ statusText }}
        </div>
      </div>
      <div class="header-right">
        <button class="btn-icon" @click="showSettings = true" title="设置">
          ⚙️
        </button>
        <button class="btn-icon" @click="clearChat" title="清空对话">
          🗑️
        </button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">💬</div>
        <div class="empty-text">开始与 AI 对话</div>
        <div class="empty-hint">AI 可以调用 MCP 工具来帮助你完成任务</div>
      </div>

      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="message"
        :class="msg.role"
      >
        <div class="message-avatar">
          {{ msg.role === 'user' ? '👤' : msg.role === 'tool' ? '🔧' : '🤖' }}
        </div>
        <div class="message-content">
          <div class="message-header">
            <span class="message-role">{{ roleLabels[msg.role] }}</span>
            <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div class="message-text" v-html="formatMessage(msg.content)"></div>
          
          <!-- 工具调用信息 -->
          <div v-if="msg.toolCalls && msg.toolCalls.length" class="tool-calls">
            <div v-for="call in msg.toolCalls" :key="call.id" class="tool-call">
              <div class="tool-call-header">
                <span class="tool-name">📦 {{ call.name }}</span>
                <span class="tool-status" :class="call.status">
                  {{ toolStatusLabels[call.status] }}
                </span>
              </div>
              <div v-if="call.arguments" class="tool-args">
                <pre>{{ JSON.stringify(call.arguments, null, 2) }}</pre>
              </div>
              <div v-if="call.result" class="tool-result">
                <pre>{{ JSON.stringify(call.result, null, 2) }}</pre>
              </div>
              <div v-if="call.error" class="tool-error">
                ❌ {{ call.error }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="isLoading" class="message assistant loading">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div v-if="currentStep" class="step-indicator">
            {{ currentStep }}
          </div>
        </div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <ConfirmationModal
      v-if="pendingConfirmation"
      :request="pendingConfirmation"
      @confirm="handleConfirm"
      @reject="handleReject"
      @close="pendingConfirmation = null"
    />

    <!-- 输入区域 -->
    <div class="chat-input">
      <textarea
        ref="inputRef"
        v-model="inputText"
        :disabled="isLoading || !!pendingConfirmation"
        placeholder="输入消息... (Shift+Enter 换行，Enter 发送)"
        @keydown="handleKeydown"
        rows="1"
      ></textarea>
      <button
        class="send-btn"
        :disabled="!inputText.trim() || isLoading || !!pendingConfirmation"
        @click="sendMessage"
      >
        {{ isLoading ? '⏳' : '➤' }}
      </button>
    </div>

    <!-- 设置弹窗 -->
    <div v-if="showSettings" class="settings-modal">
      <div class="settings-content">
        <div class="settings-header">
          <h3>⚙️ LLM 设置</h3>
          <button class="close-btn" @click="showSettings = false">×</button>
        </div>
        <div class="settings-body">
          <div class="form-group">
            <label>Provider</label>
            <select v-model="llmConfig.provider">
              <option value="zhipu">智谱 GLM (推荐)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama (本地)</option>
            </select>
          </div>
          <div class="form-group">
            <label>模型</label>
            <input v-model="llmConfig.model" placeholder="gpt-4o" />
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input
              v-model="llmConfig.apiKey"
              type="password"
              placeholder="sk-..."
            />
          </div>
          <div class="form-group">
            <label>Base URL (可选)</label>
            <input v-model="llmConfig.baseUrl" placeholder="https://api.openai.com/v1" />
          </div>
          <div class="form-group">
            <label>Temperature: {{ llmConfig.temperature }}</label>
            <input
              type="range"
              v-model.number="llmConfig.temperature"
              min="0"
              max="2"
              step="0.1"
            />
          </div>
        </div>
        <div class="settings-footer">
          <button class="btn-primary" @click="saveSettings">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { mcpHostApi } from '@/api'
import ConfirmationModal from './ConfirmationModal.vue'

// 状态
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const currentStep = ref('')
const showSettings = ref(false)
const pendingConfirmation = ref(null)
const sessionId = ref(null)
const messagesContainer = ref(null)
const inputRef = ref(null)

// LLM 配置（默认使用智谱，API Key 由后端环境变量提供）
const llmConfig = reactive({
  provider: 'zhipu',
  model: 'glm-4',
  apiKey: '',  // 智谱模式下留空，使用后端环境变量
  baseUrl: '',
  temperature: 0.7,
  maxTokens: 4096
})

// 标签映射
const roleLabels = {
  user: '用户',
  assistant: 'AI 助手',
  tool: '工具结果',
  system: '系统'
}

const toolStatusLabels = {
  pending: '等待中',
  executing: '执行中',
  success: '成功',
  error: '失败',
  rejected: '已拒绝'
}

// 计算属性
const statusClass = computed(() => {
  if (isLoading.value) return 'loading'
  if (pendingConfirmation.value) return 'pending'
  return 'ready'
})

const statusText = computed(() => {
  if (isLoading.value) return '思考中...'
  if (pendingConfirmation.value) return '等待确认'
  return '就绪'
})

// 初始化
onMounted(async () => {
  // 加载保存的配置
  const savedConfig = localStorage.getItem('mcpHostLLMConfig')
  if (savedConfig) {
    Object.assign(llmConfig, JSON.parse(savedConfig))
  }
  
  // 创建会话
  await createSession()
})

// 创建会话
async function createSession() {
  try {
    const res = await mcpHostApi.createSession()
    sessionId.value = res.session_id
  } catch (e) {
    console.error('创建会话失败:', e)
  }
}

// 发送消息
async function sendMessage() {
  if (!inputText.value.trim() || isLoading.value) return
  if (!sessionId.value) await createSession()
  
  const userMessage = inputText.value.trim()
  inputText.value = ''
  
  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: userMessage,
    timestamp: new Date()
  })
  
  scrollToBottom()
  isLoading.value = true
  currentStep.value = '正在分析...'
  
  // 准备 AI 回复
  const assistantMessage = reactive({
    role: 'assistant',
    content: '',
    toolCalls: [],
    timestamp: new Date()
  })
  messages.value.push(assistantMessage)
  
  // 流式对话
  mcpHostApi.chatStream(
    sessionId.value,
    userMessage,
    llmConfig,
    // onEvent
    (event) => {
      handleStreamEvent(event, assistantMessage)
    },
    // onComplete
    () => {
      isLoading.value = false
      currentStep.value = ''
      scrollToBottom()
    },
    // onError
    (error) => {
      isLoading.value = false
      currentStep.value = ''
      assistantMessage.content += `\n\n❌ 错误: ${error}`
    }
  )
}

// 处理流式事件
function handleStreamEvent(event, assistantMessage) {
  switch (event.type) {
    case 'state':
      currentStep.value = event.message || event.state
      break
      
    case 'tool_call':
      if (event.state === 'preparing') {
        assistantMessage.toolCalls.push({
          id: Date.now(),
          name: event.tool,
          arguments: event.arguments,
          status: 'pending'
        })
      } else if (event.state === 'executing') {
        const call = assistantMessage.toolCalls.find(c => c.name === event.tool)
        if (call) call.status = 'executing'
      }
      currentStep.value = `正在调用工具: ${event.tool}`
      break
      
    case 'tool_result':
      const toolCall = assistantMessage.toolCalls.find(c => c.name === event.tool)
      if (toolCall) {
        toolCall.status = event.success ? 'success' : 'error'
        toolCall.result = event.result
        toolCall.error = event.error
      }
      break
      
    case 'confirmation_required':
      isLoading.value = false
      pendingConfirmation.value = event
      break
      
    case 'final':
      assistantMessage.content = event.content
      break
      
    case 'error':
      assistantMessage.content += `\n\n❌ ${event.error}`
      break
  }
  
  scrollToBottom()
}

// 处理确认
async function handleConfirm(modifiedArgs) {
  const request = pendingConfirmation.value
  pendingConfirmation.value = null
  isLoading.value = true
  currentStep.value = '正在执行...'
  
  // 找到最后一条 AI 消息
  const lastAssistantMsg = [...messages.value].reverse().find(m => m.role === 'assistant')
  
  mcpHostApi.confirmAndContinueStream(
    sessionId.value,
    request.request_id,
    true,
    modifiedArgs,
    llmConfig,
    (event) => handleStreamEvent(event, lastAssistantMsg),
    () => {
      isLoading.value = false
      currentStep.value = ''
    },
    (error) => {
      isLoading.value = false
      if (lastAssistantMsg) {
        lastAssistantMsg.content += `\n\n❌ 错误: ${error}`
      }
    }
  )
}

// 处理拒绝
async function handleReject(reason) {
  const request = pendingConfirmation.value
  pendingConfirmation.value = null
  
  try {
    await mcpHostApi.confirmToolCall(sessionId.value, request.request_id, false, null, reason)
    
    // 添加拒绝消息
    const lastAssistantMsg = [...messages.value].reverse().find(m => m.role === 'assistant')
    if (lastAssistantMsg) {
      const toolCall = lastAssistantMsg.toolCalls.find(c => c.name === request.tool)
      if (toolCall) {
        toolCall.status = 'rejected'
        toolCall.error = reason || '用户拒绝了此操作'
      }
    }
  } catch (e) {
    console.error('拒绝失败:', e)
  }
}

// 清空对话
async function clearChat() {
  messages.value = []
  if (sessionId.value) {
    try {
      await mcpHostApi.deleteSession(sessionId.value)
    } catch (e) {
      // 忽略
    }
  }
  await createSession()
}

// 保存设置
function saveSettings() {
  localStorage.setItem('mcpHostLLMConfig', JSON.stringify(llmConfig))
  showSettings.value = false
}

// 处理键盘事件
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 格式化消息（支持简单的 Markdown）
function formatMessage(content) {
  if (!content) return ''
  return content
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

// 格式化时间
function formatTime(date) {
  if (!date) return ''
  const d = new Date(date)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 监听消息变化，自动滚动
watch(messages, scrollToBottom, { deep: true })
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 16px;
  overflow: hidden;
  font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 头部 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.icon {
  font-size: 24px;
}

.status {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  font-weight: 500;
}

.status.ready {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.status.loading {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.status.pending {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.header-right {
  display: flex;
  gap: 8px;
}

.btn-icon {
  width: 36px;
  height: 36px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* 消息列表 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 18px;
  font-weight: 500;
}

.empty-hint {
  font-size: 14px;
  margin-top: 8px;
  opacity: 0.7;
}

/* 消息样式 */
.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant,
.message.tool {
  align-self: flex-start;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
}

.message-content {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 12px 16px;
  min-width: 100px;
}

.message.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  opacity: 0.7;
}

.message-role {
  font-weight: 500;
  color: #fff;
}

.message-time {
  color: rgba(255, 255, 255, 0.5);
}

.message-text {
  color: #fff;
  line-height: 1.6;
  word-break: break-word;
}

.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9em;
}

.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.4);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

/* 工具调用 */
.tool-calls {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-call {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 10px 12px;
  border-left: 3px solid #3b82f6;
}

.tool-call-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tool-name {
  font-weight: 500;
  color: #fff;
}

.tool-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}

.tool-status.pending {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.tool-status.executing {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.tool-status.success {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.tool-status.error,
.tool-status.rejected {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.tool-args,
.tool-result {
  font-size: 12px;
}

.tool-args pre,
.tool-result pre {
  background: rgba(0, 0, 0, 0.3);
  padding: 8px;
  border-radius: 6px;
  margin: 0;
  overflow-x: auto;
  color: rgba(255, 255, 255, 0.8);
}

.tool-error {
  font-size: 12px;
  color: #ef4444;
  margin-top: 4px;
}

/* 加载动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-8px);
  }
}

.step-indicator {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 8px;
}

/* 输入区域 */
.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.05);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-input textarea {
  flex: 1;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px 16px;
  color: #fff;
  font-size: 14px;
  resize: none;
  min-height: 44px;
  max-height: 120px;
  font-family: inherit;
}

.chat-input textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.chat-input textarea:focus {
  outline: none;
  border-color: #667eea;
}

.send-btn {
  width: 48px;
  height: 48px;
  border: none;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 设置弹窗 */
.settings-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.settings-content {
  background: #1e1e2e;
  border-radius: 16px;
  width: 400px;
  max-width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.settings-header h3 {
  margin: 0;
  color: #fff;
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

.settings-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  margin-bottom: 8px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
}

.form-group input[type="range"] {
  padding: 0;
  background: transparent;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.settings-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: flex-end;
}

.btn-primary {
  padding: 10px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover {
  transform: translateY(-1px);
}

/* 滚动条 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}
</style>

