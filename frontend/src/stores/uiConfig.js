import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 将旧的 ai_context 数据合并到中文描述中
 */
function mergeAiContextToDescriptionZh(description, aiContext) {
  if (!aiContext) return description
  
  let result = description || ''
  const { behavior_rules, page_goal } = aiContext
  
  if (behavior_rules && !result.includes('## 行为规则')) {
    result += `\n\n## 行为规则\n${behavior_rules}`
  }
  if (page_goal && !result.includes('## 页面目标')) {
    result += `\n\n## 页面目标\n${page_goal}`
  }
  
  return result.trim()
}

/**
 * 将旧的 ai_context 数据合并到英文描述中
 */
function mergeAiContextToDescriptionEn(description, aiContext) {
  if (!aiContext) return description
  
  let result = description || ''
  const { behavior_rules, page_goal } = aiContext
  
  if (behavior_rules && !result.includes('## Behavior Rules')) {
    result += `\n\n## Behavior Rules\n${behavior_rules}`
  }
  if (page_goal && !result.includes('## Page Goal')) {
    result += `\n\n## Page Goal\n${page_goal}`
  }
  
  return result.trim()
}

export const useUiConfigStore = defineStore('uiConfig', () => {
  // 当前编辑的配置（ai_context 已废弃，数据合并到 description）
  // 支持多语言：zh-CN, en, ja, ms, zh-TW
  const draftConfig = ref({
    page_id: '',
    name: { 'zh-CN': '', en: '', ja: '', ms: '', 'zh-TW': '' },
    description: { 'zh-CN': '', en: '', ja: '', ms: '', 'zh-TW': '' },
    button_list: [],
    optional_actions: []
  })
  
  // 原始配置（用于比较是否修改）
  const originalConfig = ref(null)
  
  // 用户是否有未保存的修改 (REQ-M3-013)
  const isDirty = ref(false)
  
  // 当前解析会话
  const currentSession = ref(null)
  
  // Toast 消息
  const toast = ref(null)
  
  // 计算属性
  const hasChanges = computed(() => isDirty.value)
  
  // 应用用户编辑
  function applyUserEdit(patch) {
    Object.assign(draftConfig.value, patch)
    isDirty.value = true
  }
  
  // 尝试应用 AI 更新 (REQ-M3-013)
  function tryApplyAiUpdate(aiConfig) {
    if (isDirty.value) {
      // 有冲突，返回让 UI 层处理
      return { conflict: true }
    }
    // 无冲突，直接应用
    applyAiConfig(aiConfig)
    return { conflict: false }
  }
  
  // 强制应用 AI 更新（覆盖手动修改）
  function forceApplyAiUpdate(aiConfig) {
    applyAiConfig(aiConfig)
    isDirty.value = false
  }
  
  // 应用 AI 配置
  function applyAiConfig(aiConfig) {
    // 应用 page_id（英文标识）
    if (aiConfig.page_id) {
      draftConfig.value.page_id = aiConfig.page_id
    }
    if (aiConfig.page_name) {
      draftConfig.value.name = {
        'zh-CN': aiConfig.page_name['zh-CN'] || '',
        en: aiConfig.page_name.en || '',
        ja: aiConfig.page_name.ja || '',
        ms: aiConfig.page_name.ms || '',
        'zh-TW': aiConfig.page_name['zh-TW'] || ''
      }
    }
    if (aiConfig.page_description) {
      // 如果 AI 返回了 ai_context，将其合并到中文和英文描述中
      let descZh = aiConfig.page_description['zh-CN'] || ''
      let descEn = aiConfig.page_description.en || ''
      if (aiConfig.ai_context) {
        descZh = mergeAiContextToDescriptionZh(descZh, aiConfig.ai_context)
        descEn = mergeAiContextToDescriptionEn(descEn, aiConfig.ai_context)
      }
      draftConfig.value.description = {
        'zh-CN': descZh,
        en: descEn,
        ja: aiConfig.page_description.ja || '',
        ms: aiConfig.page_description.ms || '',
        'zh-TW': aiConfig.page_description['zh-TW'] || ''
      }
    }
    if (aiConfig.button_list) {
      draftConfig.value.button_list = aiConfig.button_list
    }
    if (aiConfig.optional_actions) {
      draftConfig.value.optional_actions = aiConfig.optional_actions
    }
  }
  
  // 保留用户修改
  function keepUserEdit() {
    // 不做任何操作，保持 isDirty 状态
  }
  
  // 重置配置
  function resetConfig() {
    draftConfig.value = {
      page_id: '',
      name: { 'zh-CN': '', en: '', ja: '', ms: '', 'zh-TW': '' },
      description: { 'zh-CN': '', en: '', ja: '', ms: '', 'zh-TW': '' },
      button_list: [],
      optional_actions: []
    }
    originalConfig.value = null
    isDirty.value = false
    currentSession.value = null
  }
  
  // 设置原始配置
  function setOriginalConfig(config) {
    // 兼容旧数据：如果有 ai_context，合并到 description（中文和英文）
    const normalizedConfig = { ...config }
    
    // 确保 name 和 description 包含所有语言字段
    normalizedConfig.name = {
      'zh-CN': config.name?.['zh-CN'] || '',
      en: config.name?.en || '',
      ja: config.name?.ja || '',
      ms: config.name?.ms || '',
      'zh-TW': config.name?.['zh-TW'] || ''
    }
    
    normalizedConfig.description = {
      'zh-CN': config.description?.['zh-CN'] || '',
      en: config.description?.en || '',
      ja: config.description?.ja || '',
      ms: config.description?.ms || '',
      'zh-TW': config.description?.['zh-TW'] || ''
    }
    
    if (config.ai_context) {
      normalizedConfig.description['zh-CN'] = mergeAiContextToDescriptionZh(
        normalizedConfig.description['zh-CN'],
        config.ai_context
      )
      normalizedConfig.description.en = mergeAiContextToDescriptionEn(
        normalizedConfig.description.en,
        config.ai_context
      )
    }
    // 移除 ai_context 字段
    delete normalizedConfig.ai_context
    
    originalConfig.value = JSON.parse(JSON.stringify(normalizedConfig))
    draftConfig.value = JSON.parse(JSON.stringify(normalizedConfig))
    isDirty.value = false
  }
  
  // 设置当前会话
  function setCurrentSession(session) {
    currentSession.value = session
  }
  
  // 显示 Toast
  function showToast(message, type = 'success', duration = 3000) {
    toast.value = { message, type }
    setTimeout(() => {
      toast.value = null
    }, duration)
  }
  
  return {
    draftConfig,
    originalConfig,
    isDirty,
    currentSession,
    toast,
    hasChanges,
    applyUserEdit,
    tryApplyAiUpdate,
    forceApplyAiUpdate,
    keepUserEdit,
    resetConfig,
    setOriginalConfig,
    setCurrentSession,
    showToast
  }
})

