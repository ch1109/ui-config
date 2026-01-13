<template>
  <div class="page-editor">
    <!-- Header -->
    <header class="editor-header">
      <div class="header-left">
        <button class="back-btn" @click="$router.push('/')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          返回列表
        </button>
        <div class="header-divider"></div>
        <div class="header-title">
          <span class="title-icon">
            <svg v-if="isNew" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </span>
          {{ isNew ? '添加页面配置' : '编辑页面配置' }}
        </div>
      </div>
      <div class="header-actions">
        <span v-if="store.isDirty" class="unsaved-badge">
          <span class="dot"></span>
          未保存
        </span>
        <button class="action-btn secondary" @click="handleReset">
          重置
        </button>
        <button class="action-btn primary" @click="handleSave" :disabled="isSaving">
          <span v-if="isSaving" class="btn-spinner"></span>
          保存配置
        </button>
      </div>
    </header>
    
    <!-- Main Content -->
    <div class="editor-body">
      <div class="editor-grid">
        <!-- Left Panel: Screenshot & Preview -->
        <aside class="panel panel-left">
          <!-- Screenshot Card -->
          <div class="panel-card">
            <div class="card-header">
              <h3>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <path d="M21 15l-5-5L5 21"/>
                </svg>
                页面截图
              </h3>
            </div>
            <div class="card-body">
              <ImageUploader
                v-model="imageUrl"
                :disabled="isParsing"
                @upload-success="onImageUploaded"
                @upload-error="onUploadError"
              />
              
              <button 
                class="ai-parse-btn"
                @click="handleAIParse"
                :disabled="!imageUrl || isParsing"
              >
                <span v-if="isParsing" class="btn-spinner"></span>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7 7 0 0113 23a7 7 0 01-7.07-7H5a1 1 0 110-2h1a7 7 0 017-7h1V5.73A2 2 0 0112 2z"/>
                </svg>
                {{ isParsing ? '正在分析...' : 'AI 辅助填写' }}
              </button>
            </div>
          </div>
          
          <!-- JSON Preview Card -->
          <div class="panel-card">
            <div class="card-header">
              <h3>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>
                </svg>
                JSON 预览
              </h3>
              <div class="card-actions">
                <button class="icon-btn" @click="copyJson" title="复制">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/>
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                  </svg>
                </button>
                <button class="icon-btn" @click="downloadJson" title="下载">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                  </svg>
                </button>
              </div>
            </div>
            <div class="card-body">
              <div class="json-preview-container">
                <pre><code>{{ jsonPreview }}</code></pre>
              </div>
            </div>
          </div>
        </aside>
        
        <!-- Center Panel: Config Form -->
        <main class="panel panel-center">
          <div class="panel-card config-card">
            <div class="card-header">
              <h3>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                配置详情
              </h3>
            </div>
            <div class="card-body">
              <ConfigEditor
                :config="store.draftConfig"
                :session-id="currentSessionId"
                :errors="validationErrors"
                @config-changed="onConfigChanged"
              />
            </div>
          </div>
        </main>
        
        <!-- Right Panel: AI Assistant -->
        <aside class="panel panel-right">
          <div class="panel-card ai-card">
            <div class="card-header">
              <h3>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
                UI config 填写助手
              </h3>
            </div>
            <div class="card-body">
              <ClarifyPanel
                :session-id="currentSessionId"
                :parse-result="parseResult"
                :status="parseStatus"
                :current-config="store.draftConfig"
                :image-url="imageUrl"
                :streaming-content="streamingContent"
                @config-updated="onAIConfigUpdated"
                @config-confirmed="onAIConfigConfirmed"
                @completed="onAICompleted"
              />
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, createVNode } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUiConfigStore } from '@/stores/uiConfig'
import { pageConfigApi } from '@/api'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

import ImageUploader from '@/components/PageConfig/ImageUploader.vue'
import ConfigEditor from '@/components/PageConfig/ConfigEditor.vue'
import ClarifyPanel from '@/components/AIAssistant/ClarifyPanel.vue'

const route = useRoute()
const router = useRouter()
const store = useUiConfigStore()

const isNew = computed(() => route.name === 'PageCreate')
const imageUrl = ref('')
const currentSessionId = ref('')
const parseResult = ref(null)
const parseStatus = ref('')
const isParsing = ref(false)
const isSaving = ref(false)
const showAIPanel = ref(false)
const pendingAIConfig = ref(null)
const validationErrors = ref({})
const streamingContent = ref('')
let pollTimer = null

// JSON Preview
const jsonPreview = computed(() => {
  const config = store.draftConfig
  const buttonList = (config.button_list || []).filter(btn => btn && btn.trim())
  const optionalActions = (config.optional_actions || []).filter(action => action && action.trim())
  const result = {
    pages: {
      [config.page_id || 'unnamed']: {
        name: config.name,
        description: config.description,
        buttonList,
        optionalActions
      }
    }
  }
  return JSON.stringify(result, null, 2)
})

onMounted(async () => {
  store.resetConfig()
  if (!isNew.value && route.params.id) {
    try {
      const response = await pageConfigApi.get(route.params.id)
      // ai_context 已废弃，数据现在合并在 description 中
      store.setOriginalConfig({
        page_id: response.page_id,
        name: response.name,
        description: response.description,
        button_list: response.button_list || [],
        optional_actions: response.optional_actions || []
      })
      imageUrl.value = response.screenshot_url || ''
    } catch (error) {
      console.error('Failed to load page:', error)
      message.error('加载页面失败')
      router.push('/')
    }
  }
})

// Image Upload
const onImageUploaded = (result) => {
  imageUrl.value = result.file_url
  message.success('图片上传成功')
}

const onUploadError = (error) => {
  message.error(error.message || '上传失败')
}

// AI Parse
const handleAIParse = async () => {
  if (!imageUrl.value) {
    message.warning('请先上传页面截图')
    return
  }
  
  isParsing.value = true
  showAIPanel.value = true
  parseStatus.value = 'parsing'
  streamingContent.value = ''
  
  try {
    const stream = pageConfigApi.parseStream(
      imageUrl.value,
      (data) => {
        if (data.type === 'content') {
          streamingContent.value += data.content
        }
      },
      (result) => {
        isParsing.value = false
        parseStatus.value = 'completed'
        parseResult.value = result
        streamingContent.value = ''
        message.success('AI 解析完成')
      },
      (error) => {
        isParsing.value = false
        parseStatus.value = 'failed'
        streamingContent.value = ''
        message.error(error || '解析失败')
      }
    )
    window._currentParseStream = stream
  } catch (error) {
    isParsing.value = false
    parseStatus.value = 'failed'
    message.error(error.response?.data?.message || '解析失败')
  }
}

// Apply AI Result with Conflict Check
const applyAIResult = (result) => {
  const { conflict } = store.tryApplyAiUpdate(result)
  
  if (conflict) {
    pendingAIConfig.value = result
    Modal.confirm({
      title: '配置冲突',
      icon: createVNode(ExclamationCircleOutlined),
      content: 'AI 已更新配置，但您有未保存的修改。是否应用 AI 更新？',
      okText: '应用 AI 更新',
      cancelText: '保留我的修改',
      onOk() {
        store.forceApplyAiUpdate(pendingAIConfig.value)
        message.success('已应用 AI 更新')
      },
      onCancel() {
        store.keepUserEdit()
      }
    });
  } else {
    message.success('AI 解析完成，配置已填充')
  }
}

const onAIConfigUpdated = (config) => {
  parseResult.value = config
}

const onAIConfigConfirmed = (config) => {
  applyAIResult(config)
  message.success('配置已应用到表单')
}

const onAICompleted = () => {
  isParsing.value = false
  if (pollTimer) clearInterval(pollTimer)
}

const onConfigChanged = (config) => {
  store.applyUserEdit(config)
}

const handleReset = () => {
  Modal.confirm({
    title: '确认重置',
    content: '确定要重置所有配置吗？此操作将清空当前所有未保存的内容。',
    onOk() {
      imageUrl.value = ''
      showAIPanel.value = false
      currentSessionId.value = ''
      parseResult.value = null
      parseStatus.value = ''
      isParsing.value = false
      store.resetConfig()
      message.success('配置已重置')
    }
  })
}

const validateConfig = () => {
  const errors = {}
  const config = store.draftConfig
  
  if (!config.page_id?.trim()) {
    errors.page_id = '页面 ID 为必填项'
  } else if (!/^[a-zA-Z0-9_\.]+$/.test(config.page_id)) {
    errors.page_id = '只能包含字母、数字、下划线和点'
  }
  
  if (!config.name?.['zh-CN']?.trim()) {
    errors.name_zh = '中文名称为必填项'
  }
  
  if (!config.name?.en?.trim()) {
    errors.name_en = '英文名称为必填项'
  }
  
  return errors
}

const handleSave = async () => {
  const errors = validateConfig()
  if (Object.keys(errors).length > 0) {
    validationErrors.value = errors
    message.error('请检查表单错误')
    return
  }
  
  isSaving.value = true
  
  try {
    const config = store.draftConfig
    // ai_context 已废弃，不再单独发送
    const saveData = {
      page_id: config.page_id,
      name: config.name,
      description: config.description,
      button_list: config.button_list.filter(b => b.trim()),
      optional_actions: config.optional_actions.filter(a => a.trim()),
      screenshot_url: imageUrl.value
    }
    
    if (isNew.value) {
      await pageConfigApi.create(saveData)
    } else {
      await pageConfigApi.update(route.params.id, saveData)
    }
    
    message.success('保存成功')
    store.isDirty = false
    
    if (isNew.value) {
      router.push(`/page/${config.page_id}`)
    }
  } catch (error) {
    message.error(error.response?.data?.message || '保存失败')
  } finally {
    isSaving.value = false
  }
}

const copyJson = async () => {
  try {
    await navigator.clipboard.writeText(jsonPreview.value)
    message.success('已复制到剪贴板')
  } catch {
    message.error('复制失败')
  }
}

const downloadJson = () => {
  const blob = new Blob([jsonPreview.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.draftConfig.page_id || 'config'}_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

watch(() => route.path, () => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style lang="scss" scoped>
.page-editor {
  min-height: 100vh;
  background: var(--bg-body);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-light);
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: blur(8px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: var(--bg-subtle);
    color: var(--text-primary);
  }
}

.header-divider {
  width: 1px;
  height: 24px;
  background: var(--border-color);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-heading);
  
  .title-icon {
    width: 32px;
    height: 32px;
    background: var(--primary-light);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 18px;
      height: 18px;
      color: var(--primary);
    }
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.unsaved-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--warning);
  background: var(--warning-light);
  border-radius: 20px;
  
  .dot {
    width: 6px;
    height: 6px;
    background: var(--warning);
    border-radius: 50%;
    animation: pulse-dot 1.5s infinite;
  }
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
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
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.editor-body {
  padding: 24px 32px;
}

.editor-grid {
  display: grid;
  grid-template-columns: 360px 1fr 420px;
  gap: 24px;
  max-width: 1900px;
  margin: 0 auto;
  align-items: stretch;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
}

.panel-left,
.panel-right {
  align-self: stretch;
}

.panel-left .panel-card,
.panel-right .panel-card {
  display: flex;
  flex-direction: column;
}

.panel-left .panel-card:last-child,
.panel-right .panel-card {
  flex: 1 1 0;
}

.panel-left .panel-card .card-body,
.panel-right .panel-card .card-body {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-left .panel-card .card-body {
  gap: 16px;
}

.panel-left .json-preview-container {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
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
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(to bottom, var(--bg-elevated) 0%, var(--bg-subtle) 100%);
  
  h3 {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
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
    gap: 4px;
  }
}

.icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: var(--bg-subtle);
    color: var(--primary);
  }
}

.card-body {
  padding: 20px;
}

.ai-parse-btn {
  width: 100%;
  height: 44px;
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, var(--primary) 0%, #818cf8 100%);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
  
  svg {
    width: 20px;
    height: 20px;
  }
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.json-preview-container {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  border-radius: 12px;
  padding: 16px;
  max-height: 480px;
  min-height: 280px;
  overflow: auto;
  
  pre {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.7;
    color: #e2e8f0;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

.config-card {
  height: fit-content;
  
  .card-body {
    padding: 24px;
  }
}

.ai-card {
  height: 100%;

  .card-body {
    padding: 0;
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
  }
}

// 响应式调整
@media (max-width: 1600px) {
  .editor-grid {
    grid-template-columns: 320px 1fr 380px;
  }
}

@media (max-width: 1400px) {
  .editor-grid {
    grid-template-columns: 280px 1fr 340px;
  }
}

@media (max-width: 1200px) {
  .editor-grid {
    grid-template-columns: 1fr;
  }
  
  .panel-left,
  .panel-right {
    flex-direction: row;
    
    .panel-card {
      flex: 1;
    }
  }
}
</style>
