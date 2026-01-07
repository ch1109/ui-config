<template>
  <div class="system-prompt-page">
    <header class="page-header">
      <h1><span class="icon">💬</span>UI Config 提示词配置</h1>
      <p class="subtitle">配置 VL 模型的系统提示词，影响页面解析效果</p>
    </header>
    
    <div class="page-content">
      <div class="editor-card card">
        <div class="editor-header">
          <h3>System Prompt</h3>
          <div class="actions">
            <button 
              class="btn btn-secondary" 
              @click="handleReset"
              :disabled="isLoading"
            >
              恢复默认
            </button>
            <button 
              class="btn btn-primary" 
              @click="handleSave"
              :disabled="!hasChanges || isLoading || !isValid"
            >
              {{ isLoading ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
        
        <div class="editor-body">
          <textarea
            v-model="promptContent"
            class="textarea prompt-editor"
            :class="{ error: !isValid }"
            :disabled="isLoading"
            placeholder="请输入 System Prompt..."
            @input="handleInput"
          ></textarea>
          
          <div class="editor-footer">
            <div class="char-counter" :class="counterClass">
              <span class="current">{{ charCount }}</span>
              <span class="separator">/</span>
              <span class="max">{{ maxLength }}</span>
              <span class="unit">字符</span>
            </div>
            
            <div v-if="charCount < recommendedMin" class="hint warning">
              💡 建议不少于 {{ recommendedMin }} 字符以提升解析效果
            </div>
            
            <div v-if="!isValid" class="hint error">
              ⚠️ 已达到最大字符限制
            </div>
          </div>
        </div>
      </div>
      
      <div class="tips-card card">
        <h3>📝 编写提示</h3>
        <ul class="tips-list">
          <li>明确描述期望的输出格式（JSON Schema）</li>
          <li>列出需要识别的元素类型和命名规则</li>
          <li>说明何时需要提出澄清问题</li>
          <li>定义置信度的评估标准</li>
        </ul>
      </div>
    </div>
    
    <!-- 保存成功提示 -->
    <Transition name="slide">
      <div v-if="showSuccess" class="toast success">
        ✅ 保存成功
      </div>
    </Transition>
    
    <!-- 确认弹窗 -->
    <ConfirmDialog
      v-model:visible="showResetConfirm"
      title="恢复默认"
      message="确定要恢复为默认模板吗？当前内容将被覆盖。"
      @confirm="confirmReset"
    />
    
    <!-- 离开确认 -->
    <ConfirmDialog
      v-model:visible="showLeaveConfirm"
      title="未保存的更改"
      message="您有未保存的更改，确定要离开吗？"
      @confirm="confirmLeave"
      @cancel="cancelLeave"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { systemPromptApi } from '@/api'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

// 常量
const maxLength = 10000
const recommendedMin = 100

// 状态
const promptContent = ref('')
const originalContent = ref('')
const isLoading = ref(false)
const showSuccess = ref(false)
const showResetConfirm = ref(false)
const showLeaveConfirm = ref(false)
const pendingNavigation = ref(null)

// 计算属性
const charCount = computed(() => promptContent.value.length)
const isValid = computed(() => charCount.value <= maxLength)
const hasChanges = computed(() => promptContent.value !== originalContent.value)

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
  } catch (error) {
    console.error('Failed to load prompt:', error)
  } finally {
    isLoading.value = false
  }
})

// 输入处理
const handleInput = () => {
  // 阻止超限输入 (REQ-M1-008)
  if (promptContent.value.length > maxLength) {
    promptContent.value = promptContent.value.slice(0, maxLength)
  }
}

// 保存 (REQ-M1-006)
const handleSave = async () => {
  if (!isValid.value) return
  
  isLoading.value = true
  try {
    await systemPromptApi.update({
      prompt_content: promptContent.value
    })
    originalContent.value = promptContent.value
    
    // 显示成功提示 3 秒
    showSuccess.value = true
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)
  } catch (error) {
    alert(error.response?.data?.message || '保存失败，请检查网络后重试')
  } finally {
    isLoading.value = false
  }
}

// 恢复默认 (REQ-M1-007)
const handleReset = () => {
  showResetConfirm.value = true
}

const confirmReset = async () => {
  showResetConfirm.value = false
  isLoading.value = true
  try {
    const response = await systemPromptApi.reset()
    promptContent.value = response.prompt_content
    originalContent.value = response.prompt_content
  } catch (error) {
    alert('恢复失败，请重试')
  } finally {
    isLoading.value = false
  }
}

// 离开页面确认 (REQ-M1-010)
onBeforeRouteLeave((to, from, next) => {
  if (hasChanges.value) {
    pendingNavigation.value = next
    showLeaveConfirm.value = true
    return false
  }
  next()
})

const confirmLeave = () => {
  showLeaveConfirm.value = false
  if (pendingNavigation.value) {
    pendingNavigation.value()
  }
}

const cancelLeave = () => {
  showLeaveConfirm.value = false
  pendingNavigation.value = null
}

// 浏览器刷新/关闭提示
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
}

.page-content {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
  align-items: start;
}

.editor-card {
  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    h3 {
      font-size: 16px;
      font-weight: 600;
    }
    
    .actions {
      display: flex;
      gap: 12px;
    }
  }
  
  .prompt-editor {
    min-height: 400px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.7;
  }
  
  .editor-footer {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  
  .char-counter {
    font-size: 13px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    
    .current {
      color: var(--text-primary);
    }
    
    &.warning .current {
      color: var(--warning);
    }
    
    &.error .current {
      color: var(--error);
    }
  }
  
  .hint {
    font-size: 12px;
    
    &.warning {
      color: var(--warning);
    }
    
    &.error {
      color: var(--error);
    }
  }
}

.tips-card {
  h3 {
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 16px;
  }
  
  .tips-list {
    list-style: none;
    
    li {
      padding: 10px 0;
      padding-left: 24px;
      position: relative;
      font-size: 13px;
      color: var(--text-secondary);
      border-bottom: 1px solid var(--border-color);
      
      &:last-child {
        border-bottom: none;
      }
      
      &::before {
        content: '•';
        position: absolute;
        left: 8px;
        color: var(--primary);
      }
    }
  }
}

// Toast 动画
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

