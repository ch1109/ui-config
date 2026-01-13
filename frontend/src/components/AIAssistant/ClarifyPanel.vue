<template>
  <div class="clarify-panel">
    <!-- Header -->
    <div class="panel-header">
      <div class="assistant-info">
        <div class="avatar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
          </svg>
        </div>
        <span class="name">UI config 填写助手</span>
      </div>
      <span v-if="status" :class="['status-badge', status]">
        <span class="status-dot"></span>
        {{ statusText }}
      </span>
    </div>
    
    <!-- Chat Container -->
    <div class="chat-container" ref="chatContainer">
      <!-- Welcome Message -->
      <div class="message assistant" v-if="chatHistory.length === 0 && !status">
        <div class="bubble">
          <div class="welcome-content">
            <div class="welcome-icon">👋</div>
            <div class="welcome-text">
              <p>你好！上传页面截图并点击"AI 辅助填写"，我将帮助您自动识别页面元素。</p>
              <p class="sub">您也可以直接在下方输入框描述您想要配置的页面功能。</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Chat History -->
      <template v-for="(item, index) in chatHistory" :key="index">
        <div class="message" :class="item.role">
          <div class="bubble-wrapper">
            <div v-if="item.role === 'assistant'" class="avatar small">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
              </svg>
            </div>
            <div class="bubble">
              <img 
                v-if="item.image" 
                :src="item.image" 
                class="chat-image"
                @click="previewImage(item.image)"
              />
              <span v-html="formatMessage(item.content)"></span>
              <span v-if="item.isStreaming" class="streaming-cursor">▊</span>
            </div>
          </div>
          <span class="timestamp">{{ formatTime(item.timestamp) }}</span>
        </div>
      </template>
      
      <!-- Parsing State -->
      <div v-if="status === 'parsing'" class="message assistant">
        <div class="bubble-wrapper">
          <div class="avatar small">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
            </svg>
          </div>
          <div class="bubble">
            <template v-if="streamingContent">
              <pre class="streaming-output">{{ streamingContent }}</pre>
              <span class="streaming-cursor">▊</span>
            </template>
            <template v-else>
              <div class="parsing-message">
                <span class="parsing-icon">🔍</span>
                正在分析页面截图，识别可交互元素...
              </div>
            </template>
          </div>
        </div>
      </div>
      
      <!-- Loading -->
      <div v-if="isLoading" class="message assistant">
        <div class="bubble-wrapper">
          <div class="avatar small">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
            </svg>
          </div>
          <div class="bubble loading">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
      
      <!-- Config Preview -->
      <template v-if="showConfigPreview && pendingConfig">
        <div class="message assistant">
          <div class="bubble-wrapper">
            <div class="avatar small">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
              </svg>
            </div>
            <div class="bubble config-preview">
              <div class="preview-header">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 6L9 17l-5-5"/>
                </svg>
                解析完成！以下是识别到的配置信息：
              </div>
              
              <div class="config-summary">
                <div class="config-item" v-if="pendingConfig.page_name">
                  <label>页面名称：</label>
                  <span>{{ pendingConfig.page_name['zh-CN'] || '' }}</span>
                </div>
                <div class="config-item" v-if="pendingConfig.button_list?.length">
                  <label>识别到的按钮 ({{ pendingConfig.button_list.length }}个)：</label>
                  <div class="tag-list">
                    <span v-for="btn in pendingConfig.button_list" :key="btn" class="config-tag">{{ btn }}</span>
                  </div>
                </div>
                <div class="config-item" v-if="pendingConfig.optional_actions?.length">
                  <label>可选操作：</label>
                  <div class="tag-list">
                    <span v-for="action in pendingConfig.optional_actions" :key="action" class="config-tag accent">{{ action }}</span>
                  </div>
                </div>
              </div>
              
              <div class="preview-actions">
                <button class="action-btn secondary" @click="rejectConfig">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 4v6h6M23 20v-6h-6"/>
                    <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/>
                  </svg>
                  重新识别
                </button>
                <button class="action-btn primary" @click="confirmConfig">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                  确认应用
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
      
      <!-- Clarification Question -->
      <template v-if="currentQuestion && status === 'clarifying'">
        <div class="message assistant">
          <div class="bubble-wrapper">
            <div class="avatar small">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
              </svg>
            </div>
            <div class="bubble">
              {{ currentQuestion.question_text || currentQuestion }}
            </div>
          </div>
          
          <div v-if="currentQuestion.options" class="quick-options">
            <button
              v-for="opt in currentQuestion.options"
              :key="opt"
              class="option-btn"
              @click="selectOption(opt)"
            >
              {{ opt }}
            </button>
          </div>
        </div>
      </template>
    </div>
    
    <!-- Image Preview Modal -->
    <a-image
      :width="200"
      :style="{ display: 'none' }"
      :preview="{
        visible: !!previewImageUrl,
        onVisibleChange: (vis) => { if (!vis) previewImageUrl = null },
        src: previewImageUrl
      }"
    />

    <!-- Pending Image Preview -->
    <div v-if="pendingImage" class="pending-image">
      <img :src="pendingImagePreview" />
      <button class="remove-btn" @click="removePendingImage">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
    
    <!-- Input Area -->
    <div class="input-area">
      <div class="input-wrapper">
        <label class="upload-btn" :class="{ disabled: isLoading }">
          <input 
            type="file" 
            accept="image/png,image/jpeg,.png,.jpg,.jpeg"
            @change="handleImageUpload"
            :disabled="isLoading"
          />
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </label>
        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="输入修改建议或问题..."
          :disabled="isLoading"
          @keydown="handleKeydown"
          rows="1"
        ></textarea>
        <button 
          class="send-btn"
          :disabled="(!inputText.trim() && !pendingImage) || isLoading"
          @click="sendMessage"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
          </svg>
        </button>
      </div>
      
      <div class="input-hint">
        Enter 发送 · Shift+Enter 换行
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { clarifyApi, pageConfigApi } from '@/api'

const props = defineProps({
  sessionId: String,
  parseResult: Object,
  status: String,
  currentConfig: Object,
  imageUrl: String,
  streamingContent: String
})

const emit = defineEmits(['config-updated', 'config-confirmed', 'completed'])

const chatHistory = ref([])
const currentQuestion = ref(null)
const inputText = ref('')
const isLoading = ref(false)
const chatContainer = ref(null)
const pendingImage = ref(null)
const pendingImagePreview = ref(null)
const previewImageUrl = ref(null)
const showConfigPreview = ref(false)
const pendingConfig = ref(null)
const configConfirmed = ref(false)

const statusText = computed(() => {
  const map = {
    pending: '等待中',
    parsing: '分析中...',
    clarifying: '对话中',
    completed: '已完成',
    failed: '失败'
  }
  return map[props.status] || ''
})

watch(() => props.parseResult, (newResult) => {
  if (newResult && props.status === 'completed' && !configConfirmed.value) {
    pendingConfig.value = newResult
    showConfigPreview.value = true
    scrollToBottom()
  }
  
  if (newResult?.clarification_questions?.length > 0) {
    currentQuestion.value = newResult.clarification_questions[0]
  } else {
    currentQuestion.value = null
  }
}, { immediate: true })

watch(() => props.status, (newStatus, oldStatus) => {
  if (newStatus === 'parsing' && oldStatus !== 'parsing') {
    chatHistory.value.push({
      role: 'assistant',
      content: '正在分析页面截图，请稍候...',
      timestamp: new Date()
    })
    configConfirmed.value = false
    showConfigPreview.value = false
    scrollToBottom()
  }
  
  if (newStatus === 'clarifying' && props.parseResult) {
    chatHistory.value.push({
      role: 'assistant',
      content: '我已完成初步分析，还有一些问题需要确认：',
      timestamp: new Date()
    })
    
    if (props.parseResult.clarification_questions?.length > 0) {
      currentQuestion.value = props.parseResult.clarification_questions[0]
    }
    scrollToBottom()
  }
})

watch(() => props.streamingContent, () => {
  if (props.streamingContent) {
    scrollToBottom()
  }
})

const confirmConfig = () => {
  if (pendingConfig.value) {
    emit('config-confirmed', pendingConfig.value)
    configConfirmed.value = true
    showConfigPreview.value = false
    
    chatHistory.value.push({
      role: 'user',
      content: '确认应用此配置',
      timestamp: new Date()
    })
    scrollToBottom()
  }
}

const rejectConfig = () => {
  showConfigPreview.value = false
  chatHistory.value.push({
      role: 'user',
      content: '需要重新识别',
      timestamp: new Date()
    })
  chatHistory.value.push({
    role: 'assistant',
    content: '好的，请重新上传图片或描述您的需求，我会重新分析。',
    timestamp: new Date()
  })
  scrollToBottom()
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const beforeImageUpload = (file) => {
  pendingImage.value = file
  const reader = new FileReader()
  reader.onload = (e) => {
    pendingImagePreview.value = e.target.result
  }
  reader.readAsDataURL(file)
  return false
}

// 处理图片上传
const handleImageUpload = (e) => {
  const file = e.target.files?.[0]
  if (file) {
    // 验证文件类型
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg']
    if (!allowedTypes.includes(file.type)) {
      return
    }
    beforeImageUpload(file)
  }
  // 重置 input
  e.target.value = ''
}

const removePendingImage = () => {
  pendingImage.value = null
  pendingImagePreview.value = null
}

const previewImage = (url) => {
  previewImageUrl.value = url
}

const sendMessage = async () => {
  if ((!inputText.value.trim() && !pendingImage.value) || isLoading.value) return
  
  const userMessage = inputText.value.trim()
  const userImage = pendingImagePreview.value
  
  inputText.value = ''
  removePendingImage()
  
  chatHistory.value.push({
    role: 'user',
    content: userMessage || '(上传了图片)',
    image: userImage,
    timestamp: new Date()
  })
  
  scrollToBottom()
  isLoading.value = true
  
  try {
    if (props.sessionId && (props.status === 'clarifying' || props.status === 'completed')) {
      let accumulatedContent = ''
      const aiMessageIndex = chatHistory.value.length
      chatHistory.value.push({
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true
      })
      
      const stream = clarifyApi.chatStream(
        props.sessionId,
        userMessage,
        props.currentConfig,
        (data) => {
          if (data.type === 'content') {
            accumulatedContent += data.content
            chatHistory.value[aiMessageIndex].content = accumulatedContent
            scrollToBottom()
          }
        },
        (result) => {
          chatHistory.value[aiMessageIndex].isStreaming = false
          chatHistory.value[aiMessageIndex].content = accumulatedContent || '好的，我已根据您的建议更新了配置。'
          
          if (result) {
            pendingConfig.value = result
            showConfigPreview.value = true
            configConfirmed.value = false
          }
          isLoading.value = false
          scrollToBottom()
        },
        (error) => {
          chatHistory.value[aiMessageIndex].isStreaming = false
          chatHistory.value[aiMessageIndex].content = `❌ ${error || '请求失败，请重试'}`
          isLoading.value = false
          scrollToBottom()
        }
      )
      window._currentChatStream = stream
      
    } else {
      chatHistory.value.push({
        role: 'assistant',
        content: '请先上传页面截图并点击"AI 辅助填写"，我会帮您识别页面元素。',
        timestamp: new Date()
      })
      isLoading.value = false
    }
  } catch (error) {
    chatHistory.value.push({
      role: 'assistant',
      content: `❌ ${error.response?.data?.message || '请求失败，请重试'}`,
      timestamp: new Date()
    })
    isLoading.value = false
  } finally {
    scrollToBottom()
  }
}

const selectOption = (option) => {
  inputText.value = option
  sendMessage()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

const formatMessage = (text) => {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

const formatTime = (date) => {
  return new Date(date).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style lang="scss" scoped>
.clarify-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 580px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
}

.assistant-info {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .name {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-heading);
  }
}

.avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--primary) 0%, #818cf8 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  
  svg {
    width: 18px;
    height: 18px;
    color: white;
  }
  
  &.small {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    flex-shrink: 0;
    
    svg {
      width: 14px;
      height: 14px;
    }
  }
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 20px;
  
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  
  &.parsing {
    background: var(--primary-light);
    color: var(--primary);
    .status-dot { background: var(--primary); animation: pulse 1.5s infinite; }
  }
  
  &.clarifying {
    background: var(--warning-light);
    color: #b45309;
    .status-dot { background: var(--warning); }
  }
  
  &.completed {
    background: var(--success-light);
    color: var(--success);
    .status-dot { background: var(--success); }
  }
  
  &.failed {
    background: var(--error-light);
    color: var(--error);
    .status-dot { background: var(--error); }
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: var(--bg-subtle);
  min-height: 350px;
}

.message {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  
  &.user {
    align-items: flex-end;
    
    .bubble {
      background: var(--primary);
      color: white;
      border-radius: 16px 16px 4px 16px;
    }
  }
  
  &.assistant {
    align-items: flex-start;
    
    .bubble {
      background: var(--bg-elevated);
      border: 1px solid var(--border-light);
      border-radius: 4px 16px 16px 16px;
    }
  }
}

.bubble-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 90%;
}

.bubble {
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: var(--shadow-sm);
  
  &.loading {
    display: flex;
    gap: 6px;
    padding: 16px 20px;
  }
  
  &.config-preview {
    max-width: 100%;
    width: 100%;
  }
}

.welcome-content {
  display: flex;
  gap: 12px;
  
  .welcome-icon {
    font-size: 24px;
    flex-shrink: 0;
  }
  
  .welcome-text {
    p {
      margin: 0 0 8px 0;
      
      &.sub {
        font-size: 12px;
        color: var(--text-muted);
        margin-bottom: 0;
      }
    }
  }
}

.parsing-message {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .parsing-icon {
    font-size: 18px;
  }
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: var(--success);
  
  svg {
    width: 18px;
    height: 18px;
  }
}

.config-summary {
  background: var(--bg-subtle);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}

.config-item {
  margin-bottom: 12px;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  label {
    font-size: 12px;
    color: var(--text-muted);
    display: block;
    margin-bottom: 6px;
  }
  
  span {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-heading);
  }
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.config-tag {
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: 20px;
  
  &.accent {
    background: var(--accent-light);
    color: var(--accent);
  }
}

.preview-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
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
    
    &:hover {
      background: var(--primary-hover);
    }
  }
}

.quick-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-left: 38px;
}

.option-btn {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--primary);
  background: var(--bg-elevated);
  border: 1px solid var(--primary);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: var(--primary);
    color: white;
  }
}

.timestamp {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 6px;
  padding: 0 4px;
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
  
  &:nth-child(1) { animation-delay: -0.32s; }
  &:nth-child(2) { animation-delay: -0.16s; }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.streaming-output {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.streaming-cursor {
  animation: blink 1s infinite;
  color: var(--primary);
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.chat-image {
  max-width: 200px;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: transform 0.2s;
  
  &:hover {
    transform: scale(1.02);
  }
}

.pending-image {
  position: relative;
  margin: 0 20px 10px;
  
  img {
    max-width: 120px;
    border-radius: 8px;
    border: 2px solid var(--primary);
  }
  
  .remove-btn {
    position: absolute;
    top: -8px;
    right: -8px;
    width: 24px;
    height: 24px;
    background: var(--error);
    border: none;
    border-radius: 50%;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 12px;
      height: 12px;
    }
  }
}

.input-area {
  padding: 16px 20px;
  background: var(--bg-elevated);
  border-top: 1px solid var(--border-light);
}

.input-wrapper {
  display: flex;
  gap: 10px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 10px 14px;
  align-items: flex-end;
  transition: all 0.2s;
  
  &:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-light);
  }
  
  textarea {
    flex: 1;
    border: none;
    background: transparent;
    font-size: 14px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    resize: none;
    outline: none;
    min-height: 20px;
    max-height: 100px;
    
    &::placeholder {
      color: var(--text-muted);
    }
  }
}

.upload-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  
  input {
    display: none;
  }
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover:not(.disabled) {
    background: var(--bg-elevated);
    color: var(--primary);
    border-color: var(--primary);
  }
  
  &.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.send-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  background: var(--primary);
  border: none;
  border-radius: 10px;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover:not(:disabled) {
    background: var(--primary-hover);
    transform: scale(1.05);
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 8px;
  text-align: center;
}
</style>
