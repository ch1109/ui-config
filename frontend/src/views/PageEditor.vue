<template>
  <div class="page-editor">
    <header class="page-header">
      <div class="header-content">
        <router-link to="/" class="back-btn">
          ← 返回
        </router-link>
        <h1>
          <span class="icon">{{ isNew ? '➕' : '✏️' }}</span>
          {{ isNew ? '添加页面配置' : '编辑页面配置' }}
        </h1>
      </div>
      <div class="header-actions">
        <span v-if="store.isDirty" class="tag tag-warning">未保存</span>
        <button class="btn btn-secondary" @click="handleReset">
          重置
        </button>
        <button class="btn btn-primary" @click="handleSave" :disabled="isSaving">
          {{ isSaving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </header>
    
    <div class="editor-layout">
      <!-- 左侧：图片上传 -->
      <div class="left-panel">
        <div class="panel-section card">
          <h3>📷 页面截图</h3>
          <ImageUploader
            v-model="imageUrl"
            :disabled="isParsing"
            @upload-success="onImageUploaded"
            @upload-error="onUploadError"
          />
          
          <button 
            class="btn btn-primary ai-btn"
            @click="handleAIParse"
            :disabled="!imageUrl || isParsing"
          >
            <span v-if="isParsing" class="loading">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </span>
            <span v-else>🤖 AI 辅助填写</span>
          </button>
        </div>
        
        <!-- JSON 预览 -->
        <div class="panel-section card">
          <h3>📋 JSON 预览</h3>
          <pre class="json-preview"><code>{{ jsonPreview }}</code></pre>
          <div class="preview-actions">
            <button class="btn btn-ghost" @click="copyJson">
              📋 复制
            </button>
            <button class="btn btn-ghost" @click="downloadJson">
              💾 下载
            </button>
          </div>
        </div>
      </div>
      
      <!-- 中间：配置表单 -->
      <div class="center-panel">
        <ConfigEditor
          :config="store.draftConfig"
          :session-id="currentSessionId"
          :errors="validationErrors"
          @config-changed="onConfigChanged"
        />
      </div>
      
      <!-- 右侧：AI 助手 - 始终显示 -->
      <div class="right-panel">
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
    
    <!-- 冲突提示弹窗 -->
    <ConfirmDialog
      v-model:visible="showConflictDialog"
      title="配置冲突"
      message="AI 已更新配置，但您有未保存的修改。请选择："
    >
      <template #footer>
        <button class="btn btn-secondary" @click="handleKeepMine">
          保留我的修改
        </button>
        <button class="btn btn-primary" @click="handleApplyAI">
          应用 AI 更新
        </button>
      </template>
    </ConfirmDialog>
    
    <!-- Toast -->
    <Transition name="slide">
      <div v-if="store.toast" class="toast" :class="store.toast.type">
        {{ store.toast.message }}
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUiConfigStore } from '@/stores/uiConfig'
import { pageConfigApi, configApi } from '@/api'
import ImageUploader from '@/components/PageConfig/ImageUploader.vue'
import ConfigEditor from '@/components/PageConfig/ConfigEditor.vue'
import ClarifyPanel from '@/components/AIAssistant/ClarifyPanel.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const store = useUiConfigStore()

// 状态
const isNew = computed(() => route.name === 'PageCreate')
const imageUrl = ref('')
const currentSessionId = ref('')
const parseResult = ref(null)
const parseStatus = ref('')
const isParsing = ref(false)
const isSaving = ref(false)
const showAIPanel = ref(false)
const showConflictDialog = ref(false)
const pendingAIConfig = ref(null)
const validationErrors = ref({})
const streamingContent = ref('')  // 流式输出的实时内容

// 轮询定时器
let pollTimer = null

// JSON 预览
const jsonPreview = computed(() => {
  const config = store.draftConfig
  const result = {
    pages: {
      [config.page_id || 'unnamed']: {
        name: config.name,
        description: config.description,
        buttonList: config.button_list,
        optionalActions: config.optional_actions
      }
    }
  }
  return JSON.stringify(result, null, 2)
})

// 加载页面配置
onMounted(async () => {
  store.resetConfig()
  
  if (!isNew.value && route.params.id) {
    try {
      const response = await pageConfigApi.get(route.params.id)
      store.setOriginalConfig({
        page_id: response.page_id,
        name: response.name,
        description: response.description,
        button_list: response.button_list || [],
        optional_actions: response.optional_actions || [],
        ai_context: response.ai_context || { behavior_rules: '', page_goal: '' }
      })
      imageUrl.value = response.screenshot_url || ''
    } catch (error) {
      console.error('Failed to load page:', error)
      router.push('/')
    }
  }
})

// 图片上传成功
const onImageUploaded = (result) => {
  imageUrl.value = result.file_url
  store.showToast('图片上传成功')
}

const onUploadError = (error) => {
  store.showToast(error.message || '上传失败', 'error')
}

// AI 解析
const handleAIParse = async () => {
  if (!imageUrl.value) {
    store.showToast('请先上传页面截图', 'warning')
    return
  }
  
  isParsing.value = true
  showAIPanel.value = true
  parseStatus.value = 'parsing'
  streamingContent.value = ''  // 重置流式内容
  
  try {
    const stream = pageConfigApi.parseStream(
      imageUrl.value,
      // onMessage - 实时接收流式数据
      (data) => {
        if (data.type === 'start') {
          console.log('开始解析:', data.message)
        } else if (data.type === 'content') {
          // 实时更新流式内容
          streamingContent.value += data.content
        }
      },
      // onComplete - 解析完成
      (result) => {
        isParsing.value = false
        parseStatus.value = 'completed'
        parseResult.value = result
        streamingContent.value = ''  // 清空流式内容
        store.showToast('AI 解析完成')
      },
      // onError - 错误处理
      (error) => {
        isParsing.value = false
        parseStatus.value = 'failed'
        streamingContent.value = ''
        store.showToast(error || '解析失败', 'error')
      }
    )
    
    // 保存引用以便清理
    window._currentParseStream = stream
    
  } catch (error) {
    isParsing.value = false
    parseStatus.value = 'failed'
    store.showToast(error.response?.data?.message || '解析失败', 'error')
  }
}

// 轮询解析状态
const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  
  pollTimer = setInterval(async () => {
    try {
      const status = await pageConfigApi.getParseStatus(currentSessionId.value)
      parseStatus.value = status.status
      
      if (status.status === 'completed' || status.status === 'clarifying') {
        parseResult.value = status.result
        
        if (status.status === 'completed') {
          isParsing.value = false
          clearInterval(pollTimer)
          // 注意：不再自动应用结果，等待用户在 AI 助手中确认
        }
      } else if (status.status === 'failed') {
        isParsing.value = false
        clearInterval(pollTimer)
        store.showToast(status.error || '解析失败', 'error')
      }
    } catch (error) {
      console.error('Poll error:', error)
    }
  }, 1000)
}

// 应用 AI 结果
const applyAIResult = (result) => {
  const { conflict } = store.tryApplyAiUpdate(result)
  
  if (conflict) {
    pendingAIConfig.value = result
    showConflictDialog.value = true
  } else {
    store.showToast('AI 解析完成，配置已填充')
  }
}

// 冲突处理
const handleApplyAI = () => {
  store.forceApplyAiUpdate(pendingAIConfig.value)
  showConflictDialog.value = false
  store.showToast('已应用 AI 更新')
}

const handleKeepMine = () => {
  store.keepUserEdit()
  showConflictDialog.value = false
}

// AI 配置更新回调 - 仅更新预览，不应用到表单
const onAIConfigUpdated = (config) => {
  parseResult.value = config
}

// 用户确认配置后才应用到表单
const onAIConfigConfirmed = (config) => {
  applyAIResult(config)
  store.showToast('配置已应用到表单')
}

const onAICompleted = () => {
  isParsing.value = false
  if (pollTimer) clearInterval(pollTimer)
}

// 配置变更
const onConfigChanged = (config) => {
  store.applyUserEdit(config)
}

// 重置 - 清空所有配置内容
const handleReset = () => {
  // 清空图片
  imageUrl.value = ''
  // 清空 AI 助手状态
  showAIPanel.value = false
  currentSessionId.value = ''
  parseResult.value = null
  parseStatus.value = ''
  isParsing.value = false
  // 清空表单配置
  store.resetConfig()
  store.showToast('配置已重置')
}

// 保存
const handleSave = async () => {
  // 验证
  const errors = validateConfig()
  if (Object.keys(errors).length > 0) {
    validationErrors.value = errors
    store.showToast('请检查表单错误', 'error')
    return
  }
  
  isSaving.value = true
  
  try {
    const config = store.draftConfig
    
    // 构建保存数据
    const saveData = {
      page_id: config.page_id,
      name: config.name,
      description: config.description,
      button_list: config.button_list.filter(b => b.trim()),
      optional_actions: config.optional_actions.filter(a => a.trim()),
      ai_context: config.ai_context,
      screenshot_url: imageUrl.value
    }
    
    if (isNew.value) {
      await pageConfigApi.create(saveData)
    } else {
      await pageConfigApi.update(route.params.id, saveData)
    }
    
    store.showToast('保存成功')
    store.isDirty = false
    
    if (isNew.value) {
      router.push(`/page/${config.page_id}`)
    }
  } catch (error) {
    store.showToast(error.response?.data?.message || '保存失败', 'error')
  } finally {
    isSaving.value = false
  }
}

// 验证配置
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
  
  const validButtons = config.button_list?.filter(b => b.trim()) || []
  if (validButtons.length === 0) {
    errors.button_list = '至少保留一个按钮配置'
  }
  
  return errors
}

// 复制 JSON
const copyJson = async () => {
  try {
    await navigator.clipboard.writeText(jsonPreview.value)
    store.showToast('已复制到剪贴板')
  } catch {
    store.showToast('复制失败', 'error')
  }
}

// 下载 JSON
const downloadJson = () => {
  const blob = new Blob([jsonPreview.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${store.draftConfig.page_id || 'config'}_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// 清理
watch(() => route.path, () => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style lang="scss" scoped>
.page-editor {
  min-height: 100vh;
  background: var(--bg-primary);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  .back-btn {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 8px;
    display: inline-block;
    
    &:hover {
      color: var(--primary);
      text-decoration: none;
    }
  }
  
  h1 {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.editor-layout {
  display: grid;
  grid-template-columns: 320px 1fr 360px;
  gap: 24px;
  padding: 32px 40px;
  min-height: calc(100vh - 140px);
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-section {
  h3 {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.ai-btn {
  width: 100%;
  margin-top: 16px;
  
  .loading {
    display: flex;
    gap: 4px;
  }
}

.json-preview {
  background: var(--bg-secondary);
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-family: var(--font-mono);
  overflow-x: auto;
  max-height: 300px;
  margin: 0;
  
  code {
    color: var(--primary);
  }
}

.preview-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.center-panel {
  min-width: 0;
}

.ai-placeholder {
  text-align: center;
  padding: 40px 20px;
  
  .icon {
    font-size: 48px;
    margin-bottom: 16px;
  }
  
  h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
  }
  
  p {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
  }
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>

