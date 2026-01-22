<template>
  <a-modal
    :open="visible"
    :title="null"
    :width="720"
    :footer="null"
    :maskClosable="false"
    class="duplicate-page-modal"
    @cancel="handleCancel"
  >
    <!-- 自定义标题 -->
    <template #title>
      <div class="modal-header">
        <div class="header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
        </div>
        <div class="header-content">
          <h3>存在同名页面</h3>
          <p>检测到页面名称/页面ID重合，请在弹窗中修改当前页面后再保存，支持同名页面，如不更改点击保存修改到列表将显示两个同名页面。</p>
        </div>
        <button class="close-btn" @click="handleCancel">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </template>
    
    <div class="modal-body">
      <!-- 左侧：已存在的页面（只读） -->
      <div class="page-section existing-page">
        <div class="section-header">
          <span class="section-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
          </span>
          <span class="section-title">已存在的页面</span>
        </div>
        
        <div class="form-content readonly">
          <div class="form-field">
            <label>页面ID:</label>
            <div class="field-value">{{ existingPage?.page_id || '-' }}</div>
          </div>
          
          <div class="form-field">
            <label>页面名称:</label>
            <div class="field-value">{{ existingPage?.name?.['zh-CN'] || '-' }}</div>
          </div>
          
          <div class="form-field description-field">
            <label>页面描述:</label>
            <div class="field-value description-value">{{ existingPage?.description?.['zh-CN'] || '-' }}</div>
          </div>
        </div>
      </div>
      
      <!-- 右侧：当前页面（可修改） -->
      <div class="page-section current-page">
        <div class="section-header">
          <span class="section-icon editable">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </span>
          <span class="section-title">当前页面（可修改）</span>
        </div>
        
        <div class="form-content editable">
          <div class="form-field">
            <label>
              <span class="required">*</span>页面ID:
            </label>
            <input 
              v-model="currentData.page_id"
              type="text"
              class="form-input"
              placeholder="例如: 1.0home_page，单词间用下划线分隔"
            />
            <span class="field-hint">格式: {页面编号}{英文名称}，如home_page，单词间用下划线分隔</span>
          </div>
          
          <div class="form-field">
            <label>页面名称:</label>
            <input 
              v-model="currentData.name_zh"
              type="text"
              class="form-input"
              placeholder="请输入页面名称"
            />
          </div>
          
          <div class="form-field description-field">
            <label>
              <span class="required">*</span>页面描述:
            </label>
            <textarea 
              v-model="currentData.description_zh"
              class="form-textarea"
              rows="6"
              placeholder="请输入页面描述..."
              maxlength="1000"
            ></textarea>
            <span class="char-count">{{ currentData.description_zh?.length || 0 }}/1000</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 底部操作按钮 -->
    <div class="modal-footer">
      <button class="btn btn-cancel" @click="handleCancel">取消</button>
      <button class="btn btn-draft" @click="handleSaveDraft" :disabled="saving">
        <span v-if="savingDraft" class="btn-spinner"></span>
        保存草稿
      </button>
      <button class="btn btn-primary" @click="handleReplaceSave" :disabled="saving">
        <span v-if="savingReplace" class="btn-spinner"></span>
        替换保存
      </button>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  existingPage: {
    type: Object,
    default: () => ({})
  },
  currentConfig: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:visible', 'cancel', 'save-draft', 'replace-save', 'config-changed'])

const currentData = ref({
  page_id: '',
  name_zh: '',
  description_zh: ''
})

const savingDraft = ref(false)
const savingReplace = ref(false)
const saving = computed(() => savingDraft.value || savingReplace.value)

// 监听 visible 和 currentConfig 变化，初始化数据
watch(() => [props.visible, props.currentConfig], ([visible, config]) => {
  if (visible && config) {
    currentData.value = {
      page_id: config.page_id || '',
      name_zh: config.name?.['zh-CN'] || '',
      description_zh: config.description?.['zh-CN'] || ''
    }
  }
}, { immediate: true, deep: true })

// 监听当前数据变化，通知父组件
watch(currentData, (newData) => {
  emit('config-changed', newData)
}, { deep: true })

const handleCancel = () => {
  emit('update:visible', false)
  emit('cancel')
}

const handleSaveDraft = async () => {
  savingDraft.value = true
  try {
    await emit('save-draft', currentData.value)
  } finally {
    savingDraft.value = false
  }
}

const handleReplaceSave = async () => {
  savingReplace.value = true
  try {
    await emit('replace-save', currentData.value)
  } finally {
    savingReplace.value = false
  }
}
</script>

<style lang="scss" scoped>
.duplicate-page-modal {
  :deep(.ant-modal-content) {
    border-radius: 16px;
    overflow: hidden;
  }
  
  :deep(.ant-modal-header) {
    padding: 0;
    border-bottom: none;
  }
  
  :deep(.ant-modal-body) {
    padding: 0;
  }
  
  :deep(.ant-modal-close) {
    display: none;
  }
}

.modal-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 24px 24px 16px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-bottom: 1px solid #fcd34d;
  position: relative;
  
  .header-icon {
    width: 48px;
    height: 48px;
    background: white;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(251, 191, 36, 0.3);
    
    svg {
      width: 28px;
      height: 28px;
      color: #f59e0b;
    }
  }
  
  .header-content {
    flex: 1;
    
    h3 {
      margin: 0 0 8px 0;
      font-size: 18px;
      font-weight: 600;
      color: #92400e;
    }
    
    p {
      margin: 0;
      font-size: 13px;
      color: #a16207;
      line-height: 1.5;
    }
  }
  
  .close-btn {
    position: absolute;
    top: 16px;
    right: 16px;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    
    svg {
      width: 20px;
      height: 20px;
      color: #92400e;
    }
    
    &:hover {
      background: rgba(146, 64, 14, 0.1);
    }
  }
}

.modal-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  padding: 0;
}

.page-section {
  padding: 20px;
  
  &.existing-page {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
  }
  
  &.current-page {
    background: white;
  }
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
  
  .section-icon {
    width: 28px;
    height: 28px;
    background: #e2e8f0;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 16px;
      height: 16px;
      color: #64748b;
    }
    
    &.editable {
      background: #dbeafe;
      
      svg {
        color: #3b82f6;
      }
    }
  }
  
  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: #334155;
  }
}

.form-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  
  label {
    font-size: 13px;
    font-weight: 500;
    color: #64748b;
    
    .required {
      color: #ef4444;
      margin-right: 2px;
    }
  }
  
  .field-value {
    font-size: 14px;
    color: #334155;
    padding: 10px 12px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    min-height: 42px;
    display: flex;
    align-items: center;
    
    &.description-value {
      min-height: 120px;
      align-items: flex-start;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-y: auto;
      max-height: 180px;
    }
  }
  
  .field-hint {
    font-size: 12px;
    color: #94a3b8;
  }
  
  &.description-field {
    flex: 1;
    position: relative;
    
    .char-count {
      position: absolute;
      bottom: 8px;
      right: 12px;
      font-size: 12px;
      color: #94a3b8;
    }
  }
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  color: #334155;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  outline: none;
  transition: all 0.2s;
  
  &::placeholder {
    color: #94a3b8;
  }
  
  &:hover {
    border-color: #cbd5e1;
  }
  
  &:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
}

.form-textarea {
  resize: none;
  min-height: 120px;
  line-height: 1.6;
  font-family: inherit;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.btn {
  display: inline-flex;
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
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  &.btn-cancel {
    background: white;
    color: #64748b;
    border: 1px solid #e2e8f0;
    
    &:hover:not(:disabled) {
      background: #f8fafc;
      color: #334155;
    }
  }
  
  &.btn-draft {
    background: white;
    color: #3b82f6;
    border: 1px solid #3b82f6;
    
    &:hover:not(:disabled) {
      background: #eff6ff;
    }
  }
  
  &.btn-primary {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    
    &:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
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

.btn-draft .btn-spinner {
  border-color: rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
