<template>
  <div class="config-editor card">
    <!-- 基本信息区 -->
    <section class="section">
      <h3 class="section-title">📝 基本信息</h3>
      
      <div class="form-row">
        <div class="form-group">
          <label>页面 ID (英文标识) <span class="required">*</span></label>
          <input 
            v-model="localConfig.page_id"
            class="input"
            :class="{ error: errors.page_id }"
            placeholder="例如: home_page, user_profile"
            @input="handleChange"
          />
          <p v-if="errors.page_id" class="error-text">{{ errors.page_id }}</p>
          <p class="hint">格式: snake_case 或 dot.notation</p>
        </div>
      </div>
      
      <div class="form-row">
        <div class="form-group">
          <label>页面名称 (中文) <span class="required">*</span></label>
          <input 
            v-model="localConfig.name['zh-CN']"
            class="input"
            :class="{ error: errors.name_zh }"
            placeholder="例如: 首页、用户中心"
            @input="handleChange"
          />
          <p v-if="errors.name_zh" class="error-text">{{ errors.name_zh }}</p>
        </div>
        
        <div class="form-group">
          <label>Page Name (EN) <span class="required">*</span></label>
          <input 
            v-model="localConfig.name.en"
            class="input"
            :class="{ error: errors.name_en }"
            placeholder="e.g. Home Page, User Profile"
            @input="handleChange"
          />
          <p v-if="errors.name_en" class="error-text">{{ errors.name_en }}</p>
        </div>
      </div>
      
      <div class="form-row">
        <div class="form-group full">
          <label>页面描述 (中文)</label>
          <textarea 
            v-model="localConfig.description['zh-CN']"
            class="textarea"
            rows="3"
            placeholder="描述此页面的功能和用户可执行的操作..."
            @input="handleChange"
          ></textarea>
        </div>
      </div>
      
      <div class="form-row">
        <div class="form-group full">
          <label>Page Description (EN)</label>
          <textarea 
            v-model="localConfig.description.en"
            class="textarea"
            rows="3"
            placeholder="Describe the page features and available user actions..."
            @input="handleChange"
          ></textarea>
        </div>
      </div>
    </section>
    
    <!-- 页面能力区 -->
    <section class="section">
      <h3 class="section-title">🎯 页面能力</h3>
      
      <div class="form-group">
        <label>可点击按钮 <span class="required">*</span></label>
        <div class="list-editor">
          <div 
            v-for="(btn, index) in localConfig.button_list" 
            :key="index"
            class="list-item"
          >
            <input 
              v-model="localConfig.button_list[index]"
              class="input"
              placeholder="按钮 ID (snake_case)"
              @input="handleChange"
            />
            <button 
              class="btn-icon"
              @click="removeButton(index)"
              :disabled="localConfig.button_list.length <= 1"
              :title="localConfig.button_list.length <= 1 ? '至少保留一个按钮' : '删除'"
            >
              ✕
            </button>
          </div>
          
          <button class="btn-add" @click="addButton">
            + 添加按钮
          </button>
        </div>
        <p v-if="errors.button_list" class="error-text">{{ errors.button_list }}</p>
      </div>
      
      <div class="form-group">
        <label>可选操作</label>
        <div class="list-editor">
          <div 
            v-for="(action, index) in localConfig.optional_actions" 
            :key="index"
            class="list-item"
          >
            <input 
              v-model="localConfig.optional_actions[index]"
              class="input"
              placeholder="操作 ID"
              @input="handleChange"
            />
            <button class="btn-icon" @click="removeAction(index)">
              ✕
            </button>
          </div>
          
          <button class="btn-add" @click="addAction">
            + 添加操作
          </button>
        </div>
      </div>
    </section>
    
    <!-- AI 上下文区 -->
    <section class="section">
      <h3 class="section-title">🤖 AI 上下文</h3>
      
      <div class="form-group">
        <label>行为规则</label>
        <textarea 
          v-model="localConfig.ai_context.behavior_rules"
          class="textarea"
          rows="3"
          placeholder="定义 AI 在此页面的行为规则..."
          @input="handleChange"
        ></textarea>
      </div>
      
      <div class="form-group">
        <label>页面目标</label>
        <textarea 
          v-model="localConfig.ai_context.page_goal"
          class="textarea"
          rows="2"
          placeholder="定义 AI 应该帮助用户达成的目标..."
          @input="handleChange"
        ></textarea>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, watch, onMounted } from 'vue'

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

// 本地配置副本
const localConfig = reactive({
  page_id: '',
  name: { 'zh-CN': '', en: '' },
  description: { 'zh-CN': '', en: '' },
  button_list: [''],
  optional_actions: [],
  ai_context: { behavior_rules: '', page_goal: '' }
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
    localConfig.description = {
      'zh-CN': props.config.description?.['zh-CN'] || '',
      en: props.config.description?.en || ''
    }
    localConfig.button_list = props.config.button_list?.length 
      ? [...props.config.button_list] 
      : ['']
    localConfig.optional_actions = props.config.optional_actions 
      ? [...props.config.optional_actions] 
      : []
    localConfig.ai_context = {
      behavior_rules: props.config.ai_context?.behavior_rules || '',
      page_goal: props.config.ai_context?.page_goal || ''
    }
  }
}

// 处理变更
const handleChange = () => {
  emit('config-changed', {
    page_id: localConfig.page_id,
    name: { ...localConfig.name },
    description: { ...localConfig.description },
    button_list: [...localConfig.button_list],
    optional_actions: [...localConfig.optional_actions],
    ai_context: { ...localConfig.ai_context }
  })
}

// 添加/删除按钮 (REQ-M5-005, REQ-M5-006, REQ-M5-009)
const addButton = () => {
  localConfig.button_list.push('')
  handleChange()
}

const removeButton = (index) => {
  // REQ-M5-009: 至少保留一个按钮
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
  .section {
    margin-bottom: 32px;
    padding-bottom: 32px;
    border-bottom: 1px solid var(--border-color);
    
    &:last-child {
      margin-bottom: 0;
      padding-bottom: 0;
      border-bottom: none;
    }
  }
  
  .section-title {
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.form-row {
  display: flex;
  gap: 16px;
  
  .form-group {
    flex: 1;
    
    &.full {
      flex: 1 1 100%;
    }
  }
}

.list-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-item {
  display: flex;
  gap: 8px;
  
  .input {
    flex: 1;
  }
}

.btn-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    border-color: var(--error);
    color: var(--error);
    background: rgba(239, 68, 68, 0.1);
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.btn-add {
  padding: 10px;
  background: transparent;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--primary);
    background: var(--primary-light);
  }
}
</style>

