<template>
  <div class="config-editor">
    <!-- 基本信息区 -->
    <section class="section">
      <div class="section-header">
        <div class="section-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
        </div>
        <h3>基本信息</h3>
      </div>
      
      <div class="form-grid">
        <div class="form-field full-width">
          <label>
            页面 ID (英文标识)
            <span class="required">*</span>
          </label>
          <input 
            v-model="localConfig.page_id"
            type="text"
            class="form-input"
            :class="{ error: errors.page_id }"
            placeholder="例如: 1.0home_page, 4.1face_authorization_page"
            @input="handleChange"
          />
          <span class="field-hint" :class="{ error: errors.page_id }">
            {{ errors.page_id || '格式: {页面编号}{英文名称}，如 4.1face_authorization_page，单词间用下划线分隔' }}
          </span>
        </div>
        
        <div class="form-field">
          <label>
            页面名称 (中文)
            <span class="required">*</span>
          </label>
          <input 
            v-model="localConfig.name['zh-CN']"
            type="text"
            class="form-input"
            :class="{ error: errors.name_zh }"
            placeholder="例如: 首页、用户中心"
            @input="handleChange"
          />
          <span v-if="errors.name_zh" class="field-hint error">{{ errors.name_zh }}</span>
        </div>
        
        <div class="form-field">
          <label>
            Page Name (EN)
            <span class="required">*</span>
          </label>
          <input 
            v-model="localConfig.name.en"
            type="text"
            class="form-input"
            :class="{ error: errors.name_en }"
            placeholder="e.g. Home Page, User Profile"
            @input="handleChange"
          />
          <span v-if="errors.name_en" class="field-hint error">{{ errors.name_en }}</span>
        </div>
        
        <div class="form-field full-width">
          <label>
            页面描述 (中文)
            <span class="label-hint">包含功能说明、行为规则和页面目标</span>
          </label>
          <textarea 
            v-model="localConfig.description['zh-CN']"
            class="form-textarea description-textarea"
            rows="8"
            :placeholder="descriptionPlaceholder"
            @input="handleChange"
          ></textarea>
          <div class="field-help">
            <button type="button" class="help-toggle" @click="showDescriptionHelp = !showDescriptionHelp">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 16v-4M12 8h.01"/>
              </svg>
              {{ showDescriptionHelp ? '收起格式说明' : '查看格式说明' }}
            </button>
            <div v-if="showDescriptionHelp" class="help-content">
              <p><strong>推荐格式：</strong></p>
              <pre>页面功能概述...

用户可执行的操作：
- 操作1
- 操作2

## 行为规则
AI 在此页面应遵循的约束...

## 页面目标
用户在此页面的主要目标...</pre>
            </div>
          </div>
        </div>
        
        <div class="form-field full-width">
          <label>
            Page Description (EN)
            <span class="label-hint">Optional</span>
          </label>
          <textarea 
            v-model="localConfig.description.en"
            class="form-textarea"
            rows="4"
            placeholder="Describe the page features and available user actions..."
            @input="handleChange"
          ></textarea>
        </div>
      </div>
    </section>
    
    <!-- 页面能力区 -->
    <section class="section">
      <div class="section-header">
        <div class="section-icon accent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"/>
            <rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/>
          </svg>
        </div>
        <h3>页面能力</h3>
      </div>
      
      <div class="form-field">
        <label>
          可点击按钮
        </label>
        <div class="list-editor">
          <div 
            v-for="(btn, index) in localConfig.button_list" 
            :key="index"
            class="list-item"
          >
            <input 
              v-model="localConfig.button_list[index]"
              type="text"
              class="form-input"
              placeholder="按钮 ID (snake_case)"
              @input="handleChange"
            />
            <button 
              v-if="localConfig.button_list.length > 1"
              class="remove-btn"
              @click="removeButton(index)"
              type="button"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M15 9l-6 6M9 9l6 6"/>
              </svg>
            </button>
          </div>
          <button class="add-btn" @click="addButton" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 8v8M8 12h8"/>
            </svg>
            添加按钮
          </button>
        </div>
        <span v-if="errors.button_list" class="field-hint error">{{ errors.button_list }}</span>
      </div>
      
      <div class="form-field">
        <label>可选操作</label>
        <div class="list-editor">
          <div 
            v-for="(action, index) in localConfig.optional_actions" 
            :key="index"
            class="list-item"
          >
            <input 
              v-model="localConfig.optional_actions[index]"
              type="text"
              class="form-input"
              placeholder="操作 ID"
              @input="handleChange"
            />
            <button 
              class="remove-btn"
              @click="removeAction(index)"
              type="button"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M15 9l-6 6M9 9l6 6"/>
              </svg>
            </button>
          </div>
          <button class="add-btn" @click="addAction" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 8v8M8 12h8"/>
            </svg>
            添加操作
          </button>
        </div>
      </div>
    </section>
    
  </div>
</template>

<script setup>
import { reactive, watch, onMounted, ref } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  sessionId: String,
  errors: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['config-changed'])

// 显示帮助提示
const showDescriptionHelp = ref(false)

// 描述占位符
const descriptionPlaceholder = `描述此页面的功能和用户可执行的操作...

示例格式：
用户中心是管理个人信息的核心页面。

用户可执行的操作：
- 修改头像和昵称
- 更新联系方式
- 修改密码

## 行为规则
- 引导用户完善必填信息
- 敏感操作需二次确认

## 页面目标
帮助用户维护个人信息，确保账户安全`

// 本地配置副本
const localConfig = reactive({
  page_id: '',
  name: { 'zh-CN': '', en: '' },
  description: { 'zh-CN': '', en: '' },
  button_list: [''],
  optional_actions: []
})

// 初始化
onMounted(() => {
  syncFromProps()
})

// 监听 props 变化
watch(() => props.config, () => {
  syncFromProps()
}, { deep: true })

// 同步 props 到本地
const syncFromProps = () => {
  if (props.config) {
    localConfig.page_id = props.config.page_id || ''
    localConfig.name = {
      'zh-CN': props.config.name?.['zh-CN'] || '',
      en: props.config.name?.en || ''
    }
    // 如果有旧的 ai_context 数据，合并到中文和英文描述中
    let descZh = props.config.description?.['zh-CN'] || ''
    let descEn = props.config.description?.en || ''
    if (props.config.ai_context) {
      const { behavior_rules, page_goal } = props.config.ai_context
      // 合并到中文描述
      if (behavior_rules && !descZh.includes('## 行为规则')) {
        descZh += `\n\n## 行为规则\n${behavior_rules}`
      }
      if (page_goal && !descZh.includes('## 页面目标')) {
        descZh += `\n\n## 页面目标\n${page_goal}`
      }
      // 合并到英文描述
      if (behavior_rules && !descEn.includes('## Behavior Rules')) {
        descEn += `\n\n## Behavior Rules\n${behavior_rules}`
      }
      if (page_goal && !descEn.includes('## Page Goal')) {
        descEn += `\n\n## Page Goal\n${page_goal}`
      }
    }
    localConfig.description = {
      'zh-CN': descZh.trim(),
      en: descEn.trim()
    }
    localConfig.button_list = props.config.button_list?.length 
      ? [...props.config.button_list] 
      : ['']
    localConfig.optional_actions = props.config.optional_actions 
      ? [...props.config.optional_actions] 
      : []
  }
}

// 处理变更
const handleChange = () => {
  emit('config-changed', {
    page_id: localConfig.page_id,
    name: { ...localConfig.name },
    description: { ...localConfig.description },
    button_list: [...localConfig.button_list],
    optional_actions: [...localConfig.optional_actions]
  })
}

const addButton = () => {
  localConfig.button_list.push('')
  handleChange()
}

const removeButton = (index) => {
  if (localConfig.button_list.length <= 1) {
    return
  }
  localConfig.button_list.splice(index, 1)
  handleChange()
}

const addAction = () => {
  localConfig.optional_actions.push('')
  handleChange()
}

const removeAction = (index) => {
  localConfig.optional_actions.splice(index, 1)
  handleChange()
}
</script>

<style lang="scss" scoped>
.config-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section {
  padding: 20px;
  background: var(--bg-subtle);
  border-radius: 12px;
  
  &:hover {
    background: rgba(241, 245, 249, 0.8);
  }
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  
  h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
  }
}

.section-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-light);
  
  svg {
    width: 18px;
    height: 18px;
    color: var(--primary);
  }
  
  &.accent {
    background: var(--accent-light);
    svg { color: var(--accent); }
  }
  
  &.success {
    background: var(--success-light);
    svg { color: var(--success); }
  }
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  
  &.full-width {
    grid-column: 1 / -1;
  }
  
  label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    
    .required {
      color: var(--error);
      margin-left: 2px;
    }
  }
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 14px;
  font-size: 14px;
  font-family: var(--font-sans);
  color: var(--text-primary);
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  outline: none;
  transition: all 0.2s;
  
  &::placeholder {
    color: var(--text-muted);
  }
  
  &:hover:not(:disabled) {
    border-color: #cbd5e1;
  }
  
  &:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-light);
    background: white;
  }
  
  &.error {
    border-color: var(--error);
    
    &:focus {
      box-shadow: 0 0 0 3px var(--error-light);
    }
  }
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.6;
  
  &.description-textarea {
    min-height: 180px;
    font-family: var(--font-mono, 'SF Mono', 'Monaco', 'Consolas', monospace);
    font-size: 13px;
  }
}

.field-hint {
  font-size: 12px;
  color: var(--text-muted);
  
  &.error {
    color: var(--error);
  }
}

.label-hint {
  font-weight: 400;
  color: var(--text-muted);
  font-size: 12px;
  margin-left: 8px;
}

.field-help {
  margin-top: 8px;
}

.help-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
  &:hover {
    background: var(--bg-subtle);
    color: var(--primary);
  }
}

.help-content {
  margin-top: 12px;
  padding: 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  
  p {
    margin: 0 0 12px 0;
    font-size: 13px;
    color: var(--text-secondary);
  }
  
  pre {
    margin: 0;
    padding: 12px;
    background: var(--bg-subtle);
    border-radius: 8px;
    font-size: 12px;
    font-family: var(--font-mono, 'SF Mono', 'Monaco', 'Consolas', monospace);
    color: var(--text-primary);
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-x: auto;
  }
}

.list-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-item {
  display: flex;
  gap: 10px;
  align-items: center;
  
  .form-input {
    flex: 1;
  }
}

.remove-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: var(--error-light);
    border-color: var(--error);
    color: var(--error);
  }
}

.add-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
  background: var(--bg-elevated);
  border: 1px dashed var(--primary);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: var(--primary-light);
  }
}
</style>
