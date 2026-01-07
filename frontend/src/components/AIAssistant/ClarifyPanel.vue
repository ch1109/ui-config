<template>
  <div class="clarify-panel card">
    <div class="panel-header">
      <div class="assistant-info">
        <div class="avatar">🤖</div>
        <span class="name">AI 助手</span>
        <span v-if="status" class="status-badge" :class="statusClass">
          {{ statusText }}
        </span>
      </div>
    </div>
    
    <div class="chat-container" ref="chatContainer">
      <!-- 初始欢迎消息 -->
      <div class="message assistant" v-if="chatHistory.length === 0 && !status">
        <div class="bubble">
          👋 你好！上传页面截图并点击"AI 辅助填写"，我将帮助您自动识别页面元素。
          <br><br>
          您也可以直接在下方输入框描述您想要配置的页面功能。
        </div>
      </div>
      
      <!-- 对话历史 -->
      <template v-for="(item, index) in chatHistory" :key="index">
        <div class="message" :class="item.role">
          <div class="bubble">
            <!-- 如果有图片 -->
            <img 
              v-if="item.image" 
              :src="item.image" 
              class="chat-image"
              @click="previewImage(item.image)"
            />
            <span v-html="formatMessage(item.content)"></span>
          </div>
          <span class="timestamp">{{ formatTime(item.timestamp) }}</span>
        </div>
      </template>
      
      <!-- 解析中状态 -->
      <div v-if="status === 'parsing'" class="message assistant">
        <div class="bubble">
          👋 你好！我正在分析页面截图，识别可交互元素...
        </div>
      </div>
      
      <!-- 加载状态 -->
      <div v-if="isLoading" class="message assistant">
        <div class="bubble loading">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </div>
      
      <!-- 配置概览 - 需要用户确认 -->
      <template v-if="showConfigPreview && pendingConfig">
        <div class="message assistant">
          <div class="bubble config-preview">
            <div class="preview-header">
              ✅ 解析完成！以下是识别到的配置信息：
            </div>
            
            <div class="config-summary">
              <div class="config-item" v-if="pendingConfig.page_name">
                <label>页面名称：</label>
                <span>{{ pendingConfig.page_name['zh-CN'] || '' }}</span>
              </div>
              
              <div class="config-item" v-if="pendingConfig.page_description">
                <label>页面描述：</label>
                <span class="desc">{{ pendingConfig.page_description['zh-CN'] || '' }}</span>
              </div>
              
              <div class="config-item" v-if="pendingConfig.button_list?.length">
                <label>识别到的按钮 ({{ pendingConfig.button_list.length }}个)：</label>
                <div class="tag-list">
                  <span class="tag" v-for="btn in pendingConfig.button_list" :key="btn">{{ btn }}</span>
                </div>
              </div>
              
              <div class="config-item" v-if="pendingConfig.optional_actions?.length">
                <label>可选操作：</label>
                <div class="tag-list">
                  <span class="tag" v-for="action in pendingConfig.optional_actions" :key="action">{{ action }}</span>
                </div>
              </div>
              
              <div class="config-item" v-if="pendingConfig.overall_confidence">
                <label>置信度：</label>
                <span class="confidence" :class="getConfidenceClass(pendingConfig.overall_confidence)">
                  {{ Math.round(pendingConfig.overall_confidence * 100) }}%
                </span>
              </div>
            </div>
            
            <div class="preview-actions">
              <button class="btn btn-secondary" @click="rejectConfig">
                🔄 重新识别
              </button>
              <button class="btn btn-primary" @click="confirmConfig">
                ✓ 确认应用到表单
              </button>
            </div>
          </div>
        </div>
      </template>
      
      <!-- 已确认提示 -->
      <div v-if="configConfirmed" class="message assistant">
        <div class="bubble success">
          ✅ 配置已应用到左侧表单，您可以继续修改或直接保存
        </div>
      </div>
      
      <!-- 失败提示 -->
      <div v-if="status === 'failed'" class="message assistant">
        <div class="bubble error">
          ❌ 解析失败，请重试或手动填写配置
        </div>
      </div>
      
      <!-- 当前澄清问题 -->
      <template v-if="currentQuestion && status === 'clarifying'">
        <div class="message assistant">
          <div class="bubble">
            {{ currentQuestion.question_text || currentQuestion }}
          </div>
          
          <!-- 快捷选项 -->
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
    
    <!-- 图片预览弹层 -->
    <div v-if="previewImageUrl" class="image-preview-overlay" @click="previewImageUrl = null">
      <img :src="previewImageUrl" />
    </div>
    
    <!-- 待上传图片预览 -->
    <div v-if="pendingImage" class="pending-image">
      <img :src="pendingImagePreview" />
      <button class="remove-btn" @click="removePendingImage">✕</button>
    </div>
    
    <!-- 输入区域 - 始终显示 -->
    <div class="input-area">
      <div class="input-toolbar">
        <button class="toolbar-btn" @click="triggerImageUpload" :disabled="isLoading" title="上传图片">
          📷
        </button>
        <input
          ref="imageInput"
          type="file"
          accept="image/*"
          class="hidden-input"
          @change="handleImageSelect"
        />
      </div>
      
      <div class="input-wrapper">
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
          ➤
        </button>
      </div>
      
      <div class="input-hint">
        <span>Enter 发送 · Shift+Enter 换行</span>
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
  imageUrl: String
})

const emit = defineEmits(['config-updated', 'config-confirmed', 'completed'])

// 状态
const chatHistory = ref([])
const currentQuestion = ref(null)
const inputText = ref('')
const isLoading = ref(false)
const chatContainer = ref(null)
const inputRef = ref(null)
const imageInput = ref(null)
const pendingImage = ref(null)
const pendingImagePreview = ref(null)
const previewImageUrl = ref(null)
const showConfigPreview = ref(false)
const pendingConfig = ref(null)
const configConfirmed = ref(false)

// 计算属性
const statusClass = computed(() => ({
  'status-parsing': props.status === 'parsing',
  'status-clarifying': props.status === 'clarifying',
  'status-completed': props.status === 'completed',
  'status-failed': props.status === 'failed'
}))

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

// 监听解析结果变化 - 显示配置概览
watch(() => props.parseResult, (newResult) => {
  if (newResult && props.status === 'completed' && !configConfirmed.value) {
    // 显示配置概览，等待用户确认
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

// 监听状态变化
watch(() => props.status, (newStatus, oldStatus) => {
  if (newStatus === 'parsing' && oldStatus !== 'parsing') {
    // 开始解析，添加消息
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

// 确认配置
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

// 拒绝配置，重新识别
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

// 获取置信度样式
const getConfidenceClass = (confidence) => {
  if (confidence >= 0.85) return 'high'
  if (confidence >= 0.6) return 'medium'
  return 'low'
}

// 处理键盘事件
const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 触发图片上传
const triggerImageUpload = () => {
  imageInput.value?.click()
}

// 处理图片选择
const handleImageSelect = (e) => {
  const file = e.target.files[0]
  if (file) {
    pendingImage.value = file
    const reader = new FileReader()
    reader.onload = (e) => {
      pendingImagePreview.value = e.target.result
    }
    reader.readAsDataURL(file)
  }
  e.target.value = ''
}

// 移除待上传图片
const removePendingImage = () => {
  pendingImage.value = null
  pendingImagePreview.value = null
}

// 预览图片
const previewImage = (url) => {
  previewImageUrl.value = url
}

// 发送消息
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
      // 使用聊天接口进行配置修改
      const response = await clarifyApi.chat(props.sessionId, {
        message: userMessage,
        current_config: props.currentConfig
      })
      
      chatHistory.value.push({
        role: 'assistant',
        content: response.message || '好的，我已根据您的建议更新了配置。',
        timestamp: new Date()
      })
      
      if (response.updated_config) {
        // 显示更新后的配置概览
        pendingConfig.value = response.updated_config
        showConfigPreview.value = true
        configConfirmed.value = false
      }
    } else {
      // 没有会话时的通用回复
      chatHistory.value.push({
        role: 'assistant',
        content: '请先上传页面截图并点击"AI 辅助填写"，我会帮您识别页面元素。',
        timestamp: new Date()
      })
    }
    
  } catch (error) {
    console.error('Chat error:', error)
    chatHistory.value.push({
      role: 'assistant',
      content: `❌ ${error.response?.data?.message || '请求失败，请重试'}`,
      timestamp: new Date()
    })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

// 选择快捷选项
const selectOption = (option) => {
  inputText.value = option
  sendMessage()
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// 格式化消息
const formatMessage = (text) => {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

// 格式化时间
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
  max-height: calc(100vh - 200px);
  padding: 0;
  overflow: hidden;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.assistant-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar {
  font-size: 24px;
}

.name {
  font-weight: 600;
  font-size: 14px;
}

.status-badge {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  margin-left: auto;
  
  &.status-parsing {
    background: var(--primary-light);
    color: var(--primary);
  }
  
  &.status-clarifying {
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning);
  }
  
  &.status-completed {
    background: rgba(16, 185, 129, 0.15);
    color: var(--success);
  }
  
  &.status-failed {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message {
  margin-bottom: 16px;
  
  &.user {
    text-align: right;
    
    .bubble {
      background: var(--primary);
      color: #000;
    }
  }
  
  &.assistant {
    .bubble {
      background: var(--bg-secondary);
    }
  }
}

.bubble {
  display: inline-block;
  max-width: 90%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  text-align: left;
  
  &.loading {
    display: inline-flex;
    gap: 4px;
    padding: 12px 16px;
  }
  
  &.success {
    background: rgba(16, 185, 129, 0.15);
    color: var(--success);
  }
  
  &.error {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }
  
  &.config-preview {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    max-width: 100%;
    width: 100%;
  }
}

.preview-header {
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--success);
}

.config-summary {
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.config-item {
  margin-bottom: 10px;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  label {
    display: block;
    font-size: 11px;
    color: var(--text-muted);
    margin-bottom: 4px;
  }
  
  span {
    font-size: 13px;
    color: var(--text-primary);
    
    &.desc {
      display: block;
      line-height: 1.5;
    }
  }
  
  .confidence {
    font-weight: 600;
    
    &.high { color: var(--success); }
    &.medium { color: var(--warning); }
    &.low { color: var(--error); }
  }
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
  
  .tag {
    font-size: 11px;
    padding: 3px 8px;
    background: var(--primary-light);
    color: var(--primary);
    border-radius: 4px;
  }
}

.preview-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  
  .btn {
    font-size: 12px;
    padding: 6px 12px;
  }
}

.chat-image {
  max-width: 200px;
  max-height: 150px;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  display: block;
  
  &:hover {
    opacity: 0.9;
  }
}

.dot {
  width: 6px;
  height: 6px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
  
  &:nth-child(1) { animation-delay: -0.32s; }
  &:nth-child(2) { animation-delay: -0.16s; }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.timestamp {
  display: block;
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}

.quick-options {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-btn {
  padding: 6px 14px;
  border: 1px solid var(--primary);
  border-radius: 16px;
  background: transparent;
  color: var(--primary);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
  
  &:hover {
    background: var(--primary-light);
  }
}

.image-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  cursor: pointer;
  
  img {
    max-width: 90vw;
    max-height: 90vh;
    border-radius: 8px;
  }
}

.pending-image {
  position: relative;
  padding: 8px 16px;
  border-top: 1px solid var(--border-color);
  
  img {
    max-height: 80px;
    border-radius: 8px;
  }
  
  .remove-btn {
    position: absolute;
    top: 4px;
    right: 12px;
    width: 20px;
    height: 20px;
    border: none;
    background: var(--error);
    color: white;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    &:hover {
      transform: scale(1.1);
    }
  }
}

.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
}

.input-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.toolbar-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    background: var(--bg-hover);
    border-color: var(--primary);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.hidden-input {
  display: none;
}

.input-wrapper {
  display: flex;
  gap: 8px;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 8px 8px 8px 14px;
  align-items: flex-end;
  
  textarea {
    flex: 1;
    border: none;
    background: transparent;
    outline: none;
    font-size: 13px;
    color: var(--text-primary);
    resize: none;
    min-height: 20px;
    max-height: 100px;
    line-height: 1.4;
    font-family: inherit;
    
    &::placeholder {
      color: var(--text-muted);
    }
  }
}

.send-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--primary);
  color: #000;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  flex-shrink: 0;
  
  &:hover:not(:disabled) {
    transform: scale(1.05);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  text-align: center;
}
</style>
