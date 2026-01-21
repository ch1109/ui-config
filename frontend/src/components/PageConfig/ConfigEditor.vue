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
        <!-- 页面 ID -->
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
        
        <!-- 语言选择器（多选） -->
        <div class="form-field full-width">
          <label>
            语言 / Language
            <span class="required">*</span>
          </label>
          <div class="language-select-wrapper">
            <a-select
              v-model:value="selectedLanguages"
              mode="multiple"
              class="language-select"
              :options="languageOptions"
              placeholder="选择支持的语言..."
              @change="handleLanguageSelect"
            >
              <template #dropdownRender="{ menuNode }">
                <div class="language-dropdown">
                  <div class="select-all-option" @click="handleSelectAllLanguages">
                    <a-checkbox :checked="isAllLanguagesSelected" />
                    <span>全选</span>
                  </div>
                  <a-divider style="margin: 4px 0" />
                  <component :is="menuNode" />
                </div>
              </template>
            </a-select>
          </div>
        </div>
        
        <!-- 当前编辑语言切换 -->
        <div v-if="selectedLanguages.length > 1" class="form-field full-width">
          <label>当前编辑语言</label>
          <a-radio-group v-model:value="currentLanguage" button-style="solid" class="language-tabs">
            <a-radio-button 
              v-for="lang in selectedLanguages" 
              :key="lang" 
              :value="lang"
            >
              {{ getLanguageLabel(lang) }}
            </a-radio-button>
          </a-radio-group>
        </div>
        
        <!-- 页面名称（动态语言） -->
        <div class="form-field full-width">
          <label>
            {{ currentLanguageLabel.nameLabel }}
            <span class="required">*</span>
          </label>
          <input 
            v-model="localConfig.name[currentLanguage]"
            type="text"
            class="form-input"
            :class="{ error: currentLanguage === 'zh-CN' ? errors.name_zh : errors.name_en }"
            :placeholder="currentLanguageLabel.namePlaceholder"
            @input="handleChange"
          />
          <span v-if="currentLanguage === 'zh-CN' && errors.name_zh" class="field-hint error">{{ errors.name_zh }}</span>
          <span v-if="currentLanguage === 'en' && errors.name_en" class="field-hint error">{{ errors.name_en }}</span>
        </div>
        
        <!-- 页面描述（动态语言） -->
        <div class="form-field full-width">
          <label>
            {{ currentLanguageLabel.descLabel }}
            <span class="label-hint">{{ currentLanguageLabel.descHint }}</span>
          </label>
          <textarea 
            v-model="localConfig.description[currentLanguage]"
            class="form-textarea description-textarea"
            rows="8"
            :placeholder="currentLanguageLabel.descPlaceholder"
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
              <pre>{{ descriptionHelpText }}</pre>
            </div>
          </div>
        </div>
        
        <!-- 一键翻译按钮 -->
        <div class="form-field full-width">
          <button type="button" class="translate-btn" @click="handleTranslate">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>
            </svg>
            一键翻译
          </button>
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
      
      <!-- 可点击按钮 -->
      <div class="form-field">
        <label>可点击按钮</label>
        <a-select
          v-model:value="localConfig.button_list"
          mode="multiple"
          class="button-select"
          placeholder="选择按钮..."
          :options="buttonOptions"
          option-filter-prop="label"
          show-search
          allow-clear
          @change="handleButtonChange"
        >
          <template #option="{ value, label }">
            <span class="option-item">
              <span class="option-label">{{ label }}</span>
              <span class="option-id">{{ value }}</span>
            </span>
          </template>
          <template #tagRender="{ value, closable, onClose }">
            <a-tag :closable="closable" class="button-tag" @close="onClose">
              {{ getButtonLabel(value) }}
            </a-tag>
          </template>
        </a-select>
        <span v-if="errors.button_list" class="field-hint error">{{ errors.button_list }}</span>
      </div>
      
      <!-- 可选意图 -->
      <div class="form-field">
        <label>可选意图</label>
        <a-select
          v-model:value="localConfig.optional_actions"
          mode="multiple"
          class="intent-select"
          placeholder="搜索意图名称..."
          :options="intentOptions"
          option-filter-prop="label"
          show-search
          allow-clear
          @change="handleActionChange"
        >
          <template #option="{ value, label }">
            <span class="option-item">
              <span class="option-label">{{ label }}</span>
            </span>
          </template>
          <template #tagRender="{ value, closable, onClose }">
            <a-tag :closable="closable" class="intent-tag" @close="onClose">
              {{ getIntentLabel(value) }}
            </a-tag>
          </template>
        </a-select>
      </div>
    </section>
    
  </div>
</template>

<script setup>
import { reactive, watch, onMounted, ref, computed } from 'vue'
import { message } from 'ant-design-vue'

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

// 已选语言列表（多选，默认中文和英文）
const selectedLanguages = ref(['zh-CN', 'en'])

// 当前编辑语言（用于切换显示）
const currentLanguage = ref('zh-CN')

// 语言选项
const languageOptions = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
  { value: 'ms', label: 'Bahasa Melayu' },
  { value: 'zh-TW', label: '繁體中文' }
]

// 全选状态
const isAllLanguagesSelected = computed(() => {
  return selectedLanguages.value.length === languageOptions.length
})

// 处理语言选择变更
const handleLanguageSelect = (values) => {
  selectedLanguages.value = values
  // 如果当前编辑语言不在已选列表中，切换到第一个已选语言
  if (values.length > 0 && !values.includes(currentLanguage.value)) {
    currentLanguage.value = values[0]
  }
}

// 全选/取消全选
const handleSelectAllLanguages = () => {
  if (isAllLanguagesSelected.value) {
    // 至少保留中文
    selectedLanguages.value = ['zh-CN']
    currentLanguage.value = 'zh-CN'
  } else {
    selectedLanguages.value = languageOptions.map(opt => opt.value)
  }
}

// 根据当前语言动态生成标签和占位符
const currentLanguageLabel = computed(() => {
  const labels = {
    'zh-CN': {
      nameLabel: '页面名称（简体中文）',
      namePlaceholder: '例如: 首页、用户中心',
      descLabel: '页面描述（简体中文）',
      descHint: '包含功能说明、行为规则和页面目标',
      descPlaceholder: '描述此页面的功能和用户可执行的操作...'
    },
    'en': {
      nameLabel: 'Page Name (English)',
      namePlaceholder: 'e.g. Home Page, User Profile',
      descLabel: 'Page Description (English)',
      descHint: 'Include features, behavior rules and goals',
      descPlaceholder: 'Describe the page features and available user actions...'
    },
    'ja': {
      nameLabel: 'ページ名（日本語）',
      namePlaceholder: '例: ホームページ、ユーザーセンター',
      descLabel: 'ページの説明（日本語）',
      descHint: '機能説明、行動規則、目標を含む',
      descPlaceholder: 'このページの機能とユーザーが実行できる操作を説明してください...'
    },
    'ms': {
      nameLabel: 'Nama Halaman (Bahasa Melayu)',
      namePlaceholder: 'cth: Halaman Utama, Pusat Pengguna',
      descLabel: 'Penerangan Halaman (Bahasa Melayu)',
      descHint: 'Termasuk ciri, peraturan dan matlamat',
      descPlaceholder: 'Terangkan ciri halaman dan tindakan pengguna yang tersedia...'
    },
    'zh-TW': {
      nameLabel: '頁面名稱（繁體中文）',
      namePlaceholder: '例如: 首頁、用戶中心',
      descLabel: '頁面描述（繁體中文）',
      descHint: '包含功能說明、行為規則和頁面目標',
      descPlaceholder: '描述此頁面的功能和用戶可執行的操作...'
    }
  }
  return labels[currentLanguage.value] || labels['zh-CN']
})

// 描述帮助文本
const descriptionHelpText = computed(() => {
  if (currentLanguage.value === 'en') {
    return `Page feature overview...

Actions available to users:
- Action 1
- Action 2

## Behavior Rules
Constraints the AI should follow on this page...

## Page Goal
The main goal for users on this page...`
  }
  return `页面功能概述...

用户可执行的操作：
- 操作1
- 操作2

## 行为规则
AI 在此页面应遵循的约束...

## 页面目标
用户在此页面的主要目标...`
})

// 按钮选项（分组）
const buttonOptions = [
  // 操作按钮
  { value: 'confirm', label: '确认 (confirm)' },
  { value: 'cancel', label: '取消 (cancel)' },
  { value: 'previous_page', label: '上一页 (previous_page)' },
  { value: 'next_page', label: '下一页 (next_page)' },
  { value: 'print', label: '打印 (print)' },
  { value: 'exit', label: '退出 (exit)' },
  // 功能按钮
  { value: 'take_photo', label: '拍照 (take_photo)' },
  { value: 'retake', label: '重拍 (retake)' },
  { value: 'search', label: '搜索 (search)' },
  { value: 'check_authorization', label: '勾选授权 (check_authorization)' },
  { value: 'fingerprint_authorization', label: '指纹授权 (fingerprint_authorization)' },
  { value: 'forgot_password', label: '忘记密码 (forgot_password)' },
  { value: 'correct_password', label: '更正密码 (correct_password)' },
  // 导航按钮
  { value: 'return_home', label: '返回首页 (return_home)' },
  { value: 'next_step', label: '下一步 (next_step)' },
  { value: 'previous_step', label: '上一步 (previous_step)' },
  // 输入触发按钮
  { value: 'input_password', label: '输入密码 (input_password)' },
  { value: 'click_signature', label: '点击签名 (click_signature)' },
  { value: 'signature_modify_confirm', label: '签名修改/确认 (signature_modify_confirm)' },
  { value: 'click_search', label: '点击搜索 (click_search)' },
  { value: 'click_authorization', label: '点击授权 (click_authorization)' }
]

// 意图选项（硬编码，后续对接 API）
const intentOptions = [
  { value: 'knowledge', label: '知识问答 (knowledge)' },
  { value: 'chat', label: '闲聊模式 (chat)' },
  { value: 'comprehension', label: '阅读理解 (comprehension)' },
  { value: 'Dir-read-agreement', label: '朗读协议 (Dir-read-agreement)' },
  { value: 'UpdateFormLossReason', label: '更新挂失原因 (UpdateFormLossReason)' },
  { value: 'UpdateFormCancelAccount', label: '更新转账表单 (UpdateFormCancelAccount)' }
]

// 按钮 ID 到中文标签的映射
const buttonLabelMap = buttonOptions.reduce((acc, opt) => {
  acc[opt.value] = opt.label.split(' (')[0]
  return acc
}, {})

// 意图 ID 到中文标签的映射
const intentLabelMap = intentOptions.reduce((acc, opt) => {
  acc[opt.value] = opt.label.split(' (')[0]
  return acc
}, {})

// 获取按钮标签
const getButtonLabel = (value) => {
  return buttonLabelMap[value] || value
}

// 获取意图标签
const getIntentLabel = (value) => {
  return intentLabelMap[value] || value
}

// 本地配置副本
const localConfig = reactive({
  page_id: '',
  name: { 'zh-CN': '', en: '', ja: '', ms: '', 'zh-TW': '' },
  description: { 'zh-CN': '', en: '', ja: '', ms: '', 'zh-TW': '' },
  button_list: [],
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
      en: props.config.name?.en || '',
      ja: props.config.name?.ja || '',
      ms: props.config.name?.ms || '',
      'zh-TW': props.config.name?.['zh-TW'] || ''
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
      en: descEn.trim(),
      ja: props.config.description?.ja || '',
      ms: props.config.description?.ms || '',
      'zh-TW': props.config.description?.['zh-TW'] || ''
    }
    // 过滤空字符串
    localConfig.button_list = (props.config.button_list || []).filter(b => b && b.trim())
    localConfig.optional_actions = (props.config.optional_actions || []).filter(a => a && a.trim())
  }
}

// 获取语言标签
const getLanguageLabel = (langCode) => {
  const option = languageOptions.find(opt => opt.value === langCode)
  return option ? option.label : langCode
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

// 按钮选择变更
const handleButtonChange = (value) => {
  localConfig.button_list = value
  handleChange()
}

// 意图选择变更
const handleActionChange = (value) => {
  localConfig.optional_actions = value
  handleChange()
}

// 一键翻译（占位）
const handleTranslate = () => {
  message.info('翻译功能开发中...')
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

// 语言选择器样式
.language-select-wrapper {
  width: 100%;
}

.language-select {
  width: 100%;
  
  :deep(.ant-select-selector) {
    min-height: 42px !important;
    padding: 4px 8px !important;
    border-radius: 10px !important;
    border-color: var(--border-color) !important;
    background: var(--bg-elevated) !important;
  }
  
  :deep(.ant-select-selection-overflow) {
    gap: 6px;
  }
  
  :deep(.ant-select-selection-item) {
    height: 28px;
    line-height: 26px;
    margin: 0;
    padding: 0 8px;
    border-radius: 6px;
    background: var(--primary-light);
    border: none;
    
    .ant-select-selection-item-content {
      color: var(--primary);
      font-size: 13px;
      font-weight: 500;
    }
    
    .ant-select-selection-item-remove {
      color: var(--primary);
      
      &:hover {
        color: var(--error);
      }
    }
  }
  
  :deep(.ant-select-arrow) {
    color: var(--text-muted);
  }
  
  &:hover :deep(.ant-select-selector) {
    border-color: #cbd5e1 !important;
  }
  
  :deep(.ant-select-focused .ant-select-selector) {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-light) !important;
  }
}

// 全选下拉选项
.language-dropdown {
  .select-all-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 14px;
    color: var(--text-primary);
    
    &:hover {
      background: var(--bg-subtle);
    }
  }
}

// 当前编辑语言切换标签
.language-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  
  :deep(.ant-radio-button-wrapper) {
    height: 36px;
    line-height: 34px;
    padding: 0 16px;
    border-radius: 8px !important;
    border: 1px solid var(--border-color);
    font-size: 13px;
    font-weight: 500;
    
    &::before {
      display: none;
    }
    
    &:not(.ant-radio-button-wrapper-checked) {
      background: var(--bg-elevated);
      color: var(--text-secondary);
      
      &:hover {
        color: var(--primary);
        border-color: var(--primary);
      }
    }
    
    &.ant-radio-button-wrapper-checked {
      background: var(--primary);
      border-color: var(--primary);
      color: white;
    }
  }
}

// 一键翻译按钮
.translate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 44px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, var(--primary) 0%, #818cf8 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  }
  
  &:active {
    transform: translateY(0);
  }
}

// 按钮和意图多选下拉样式
.button-select,
.intent-select {
  width: 100%;
  
  :deep(.ant-select-selector) {
    min-height: 42px !important;
    padding: 4px 8px !important;
    border-radius: 10px !important;
    border-color: var(--border-color) !important;
    background: var(--bg-elevated) !important;
  }
  
  :deep(.ant-select-selection-overflow) {
    gap: 6px;
  }
  
  :deep(.ant-select-selection-placeholder) {
    color: var(--text-muted);
  }
  
  &:hover :deep(.ant-select-selector) {
    border-color: #cbd5e1 !important;
  }
  
  :deep(.ant-select-focused .ant-select-selector) {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-light) !important;
  }
}

// 自定义标签样式
.button-tag,
.intent-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0 !important;
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 6px;
  border: none;
  
  :deep(.ant-tag-close-icon) {
    margin-left: 4px;
    font-size: 10px;
  }
}

.button-tag {
  background: var(--primary-light);
  color: var(--primary);
}

.intent-tag {
  background: var(--accent-light);
  color: var(--accent);
}

// 下拉选项样式
.option-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  
  .option-label {
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .option-id {
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono, monospace);
  }
}
</style>
