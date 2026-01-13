<template>
  <div class="system-prompt-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="title-group">
          <h1>
            <span class="icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
              </svg>
            </span>
            提示词配置
          </h1>
          <p class="subtitle">配置 VL 模型的系统提示词，影响页面解析效果</p>
        </div>
      </div>
    </header>
    
    <!-- Content -->
    <div class="page-content">
      <div class="content-grid">
        <!-- Main Editor -->
        <div class="editor-section">
          <!-- Model Selection Card -->
          <div class="panel-card model-card">
            <div class="card-header">
              <h3>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
                视觉模型选择
              </h3>
              <span class="model-badge" :class="selectedModel === 'glm-4.6v' ? 'badge-zhipu' : 'badge-qwen'">
                {{ selectedModel === 'glm-4.6v' ? '智谱 AI' : '本地部署' }}
              </span>
            </div>
            <div class="card-body model-selector">
              <div class="model-options">
                <label 
                  v-for="model in availableModels" 
                  :key="model.id"
                  class="model-option"
                  :class="{ selected: selectedModel === model.id }"
                >
                  <input 
                    type="radio" 
                    :value="model.id" 
                    v-model="selectedModel"
                    @change="handleModelChange"
                    :disabled="isLoading"
                  />
                  <div class="model-info">
                    <div class="model-header">
                      <span class="model-name">{{ model.name }}</span>
                      <span class="model-provider">{{ model.provider }}</span>
                    </div>
                    <p class="model-desc">{{ model.description }}</p>
                  </div>
                  <span class="check-icon" v-if="selectedModel === model.id">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                      <path d="M20 6L9 17l-5-5"/>
                    </svg>
                  </span>
                </label>
              </div>
            </div>
          </div>
          <div class="panel-card">
            <div class="card-header">
              <h3>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>
                </svg>
                System Prompt
              </h3>
              <div class="card-actions">
                <button class="action-btn secondary" @click="handleCopy" :disabled="isLoading">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                  </svg>
                  复制
                </button>
                <button class="action-btn secondary" @click="handleReset" :disabled="isLoading">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 4v6h6M23 20v-6h-6"/>
                    <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/>
                  </svg>
                  恢复默认
                </button>
                <button 
                  class="action-btn primary" 
                  @click="handleSave" 
                  :disabled="!hasChanges || isLoading || !isValid"
                >
                  <span v-if="isLoading" class="btn-spinner"></span>
                  <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                    <path d="M17 21v-8H7v8M7 3v5h8"/>
                  </svg>
                  保存
                </button>
              </div>
            </div>
            
            <div class="card-body">
              <div class="editor-container">
                <textarea
                  v-model="promptContent"
                  class="prompt-editor"
                  :class="{ error: !isValid }"
                  :disabled="isLoading"
                  placeholder="请输入 System Prompt..."
                  @input="handleInput"
                ></textarea>
                
                <div class="editor-footer">
                  <div class="char-counter" :class="counterClass">
                    <span class="count">{{ charCount }}</span>
                    <span class="separator">/</span>
                    <span class="max">{{ maxLength }}</span>
                    <span class="label">字符</span>
                  </div>
                  
                  <div class="status-hints">
                    <div v-if="charCount < recommendedMin" class="hint warning">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                      </svg>
                      建议不少于 100 字符以提升解析效果
                    </div>
                    <div v-if="!isValid" class="hint error">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M15 9l-6 6M9 9l6 6"/>
                      </svg>
                      已达到最大字符限制
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, createVNode } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { systemPromptApi } from '@/api'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

// 常量
const maxLength = 10000
const recommendedMin = 100

// 状态
const promptContent = ref('')
const originalContent = ref('')
const isLoading = ref(false)
const pendingNavigation = ref(null)

// 模型选择状态
const selectedModel = ref('glm-4.6v')
const originalModel = ref('glm-4.6v')
const availableModels = ref([
  {
    id: 'glm-4.6v',
    name: 'GLM-4.6V',
    description: '智谱 AI 视觉模型，图像理解能力强，支持中英文',
    provider: '智谱 AI'
  },
  {
    id: 'qwen2.5-vl-7b',
    name: 'Qwen2.5-VL-7B',
    description: '通义千问视觉模型，本地部署版本，响应速度快',
    provider: '阿里云 / 本地部署'
  }
])

// 计算属性
const charCount = computed(() => promptContent.value.length)
const isValid = computed(() => charCount.value <= maxLength)
const hasChanges = computed(() => 
  promptContent.value !== originalContent.value || 
  selectedModel.value !== originalModel.value
)

const counterClass = computed(() => ({
  warning: charCount.value > maxLength * 0.9 && charCount.value <= maxLength,
  error: charCount.value > maxLength
}))

// 加载数据
onMounted(async () => {
  isLoading.value = true
  try {
    const response = await systemPromptApi.getCurrent()
    promptContent.value = response.prompt_content
    originalContent.value = response.prompt_content
    selectedModel.value = response.selected_model || 'glm-4.6v'
    originalModel.value = response.selected_model || 'glm-4.6v'
    
    // 尝试加载可用模型列表
    try {
      const modelsResponse = await systemPromptApi.getModels()
      if (modelsResponse.models && modelsResponse.models.length > 0) {
        availableModels.value = modelsResponse.models
      }
    } catch (modelError) {
      console.warn('Failed to load models list, using defaults:', modelError)
    }
  } catch (error) {
    console.error('Failed to load prompt:', error)
    message.error('加载提示词失败')
  } finally {
    isLoading.value = false
  }
})

// 模型切换处理
const handleModelChange = async () => {
  // 模型切换后会触发 hasChanges，用户需要点击保存按钮来保存
  message.info(`已选择 ${selectedModel.value === 'glm-4.6v' ? 'GLM-4.6V' : 'Qwen2.5-VL-7B'} 模型，请点击保存按钮确认`)
}

// 输入处理
const handleInput = () => {
  if (promptContent.value.length > maxLength) {
    promptContent.value = promptContent.value.slice(0, maxLength)
  }
}

// 复制提示词
const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(promptContent.value)
    message.success('已复制到剪贴板')
  } catch (error) {
    // 降级方案：使用 document.execCommand
    const textarea = document.createElement('textarea')
    textarea.value = promptContent.value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      message.success('已复制到剪贴板')
    } catch (e) {
      message.error('复制失败，请手动复制')
    }
    document.body.removeChild(textarea)
  }
}

// 保存
const handleSave = async () => {
  if (!isValid.value) return
  
  isLoading.value = true
  try {
    await systemPromptApi.update({
      prompt_content: promptContent.value,
      selected_model: selectedModel.value
    })
    originalContent.value = promptContent.value
    originalModel.value = selectedModel.value
    message.success('保存成功')
  } catch (error) {
    message.error(error.response?.data?.message || '保存失败')
  } finally {
    isLoading.value = false
  }
}

// 恢复默认
const handleReset = () => {
  Modal.confirm({
    title: '恢复默认',
    icon: createVNode(ExclamationCircleOutlined),
    content: '确定要恢复为默认模板吗？当前内容将被覆盖。',
    onOk: async () => {
      isLoading.value = true
      try {
        const response = await systemPromptApi.reset()
        promptContent.value = response.prompt_content
        originalContent.value = response.prompt_content
        message.success('已恢复默认配置')
      } catch (error) {
        message.error('恢复失败')
      } finally {
        isLoading.value = false
      }
    }
  });
}

// 离开页面确认
onBeforeRouteLeave((to, from, next) => {
  if (hasChanges.value) {
    Modal.confirm({
      title: '未保存的更改',
      icon: createVNode(ExclamationCircleOutlined),
      content: '您有未保存的更改，确定要离开吗？',
      okText: '离开',
      cancelText: '取消',
      onOk() {
        next()
      },
      onCancel() {
        // Stay
      }
    });
    return false
  }
  next()
})

const handleBeforeUnload = (e) => {
  if (hasChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style lang="scss" scoped>
.system-prompt-page {
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
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  max-width: 1600px;
}

.panel-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(to bottom, var(--bg-elevated) 0%, var(--bg-subtle) 100%);
  
  h3 {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
    
    svg {
      width: 18px;
      height: 18px;
      color: var(--primary);
    }
  }
  
  .card-actions {
    display: flex;
    gap: 10px;
  }
}

.card-body {
  padding: 24px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &.secondary {
    background: var(--bg-subtle);
    color: var(--text-secondary);
    
    &:hover:not(:disabled) {
      background: var(--border-color);
      color: var(--text-primary);
    }
  }
  
  &.primary {
    background: var(--primary);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    
    &:hover:not(:disabled) {
      background: var(--primary-hover);
      transform: translateY(-1px);
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

.editor-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.prompt-editor {
  width: 100%;
  min-height: 500px;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-primary);
  background: var(--bg-subtle);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  outline: none;
  resize: vertical;
  transition: all 0.2s;
  
  &::placeholder {
    color: var(--text-muted);
  }
  
  &:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-light);
    background: var(--bg-elevated);
  }
  
  &.error {
    border-color: var(--error);
    
    &:focus {
      box-shadow: 0 0 0 3px var(--error-light);
    }
  }
}

.editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.char-counter {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-muted);
  
  .count {
    font-weight: 600;
    color: var(--text-secondary);
  }
  
  .separator {
    color: var(--text-muted);
  }
  
  .max {
    color: var(--text-muted);
  }
  
  .label {
    margin-left: 4px;
    color: var(--text-muted);
  }
  
  &.warning .count {
    color: var(--warning);
  }
  
  &.error .count {
    color: var(--error);
  }
}

.status-hints {
  display: flex;
  gap: 12px;
}

.hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
  &.warning {
    background: var(--warning-light);
    color: #b45309;
  }
  
  &.error {
    background: var(--error-light);
    color: var(--error);
  }
}

// 模型选择卡片样式
.model-card {
  margin-bottom: 20px;
  
  .card-header {
    .model-badge {
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 500;
      
      &.badge-zhipu {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
      }
      
      &.badge-qwen {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
      }
    }
  }
}

.model-selector {
  padding: 16px 24px !important;
}

.model-options {
  display: flex;
  gap: 16px;
}

.model-option {
  flex: 1;
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  background: var(--bg-subtle);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  input[type="radio"] {
    display: none;
  }
  
  &:hover:not(.selected) {
    border-color: var(--primary-light);
    background: var(--bg-elevated);
  }
  
  &.selected {
    border-color: var(--primary);
    background: var(--primary-light);
    
    .model-name {
      color: var(--primary);
    }
  }
  
  .model-info {
    flex: 1;
  }
  
  .model-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }
  
  .model-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-heading);
  }
  
  .model-provider {
    font-size: 11px;
    padding: 2px 8px;
    background: var(--bg-elevated);
    border-radius: 4px;
    color: var(--text-muted);
  }
  
  .model-desc {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.5;
  }
  
  .check-icon {
    width: 24px;
    height: 24px;
    background: var(--primary);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    
    svg {
      width: 14px;
      height: 14px;
      color: white;
    }
  }
}

@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  .model-options {
    flex-direction: column;
  }
}
</style>
