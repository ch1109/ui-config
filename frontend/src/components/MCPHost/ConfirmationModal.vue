<template>
  <div class="confirmation-overlay" @click.self="$emit('close')">
    <div class="confirmation-modal" :class="riskClass">
      <!-- 头部 -->
      <div class="modal-header">
        <div class="risk-badge" :class="riskClass">
          {{ riskIcon }} {{ riskLabel }}
        </div>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <!-- 内容 -->
      <div class="modal-body">
        <h2 class="title">🔐 需要确认操作</h2>
        <p class="description">{{ request.risk_description }}</p>
        
        <div v-if="request.warning_message" class="warning-box">
          {{ request.warning_message }}
        </div>

        <!-- 工具信息 -->
        <div class="tool-info">
          <div class="info-row">
            <span class="label">工具名称</span>
            <span class="value">{{ request.tool }}</span>
          </div>
          <div class="info-row">
            <span class="label">服务器</span>
            <span class="value">{{ request.server_key || '未知' }}</span>
          </div>
        </div>

        <!-- 参数编辑 -->
        <div class="arguments-section">
          <div class="section-header">
            <span>📝 调用参数</span>
            <button
              v-if="allowModification"
              class="edit-btn"
              @click="isEditing = !isEditing"
            >
              {{ isEditing ? '取消编辑' : '✏️ 编辑' }}
            </button>
          </div>
          
          <div v-if="!isEditing" class="arguments-view">
            <pre>{{ JSON.stringify(displayArguments, null, 2) }}</pre>
          </div>
          
          <div v-else class="arguments-edit">
            <textarea
              v-model="editedArgumentsText"
              :class="{ error: parseError }"
              rows="8"
            ></textarea>
            <div v-if="parseError" class="parse-error">
              ❌ JSON 格式错误: {{ parseError }}
            </div>
          </div>
        </div>

        <!-- 倒计时 -->
        <div v-if="timeRemaining > 0" class="countdown">
          <div class="countdown-bar">
            <div
              class="countdown-progress"
              :style="{ width: `${(timeRemaining / totalTime) * 100}%` }"
            ></div>
          </div>
          <span class="countdown-text">
            {{ Math.ceil(timeRemaining) }}秒后自动取消
          </span>
        </div>

        <!-- 拒绝原因 -->
        <div v-if="showRejectInput" class="reject-reason">
          <label>拒绝原因（可选）</label>
          <input
            v-model="rejectReason"
            placeholder="请说明拒绝的原因..."
          />
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="modal-footer">
        <button
          v-if="!showRejectInput"
          class="btn btn-danger"
          @click="showRejectInput = true"
        >
          🚫 拒绝
        </button>
        <button
          v-else
          class="btn btn-danger"
          @click="handleReject"
        >
          确认拒绝
        </button>
        
        <button
          class="btn btn-success"
          :disabled="isEditing && !!parseError"
          @click="handleConfirm"
        >
          ✅ 确认执行
        </button>
      </div>

      <!-- 二次确认（CRITICAL 级别） -->
      <div v-if="showDoubleConfirm" class="double-confirm-overlay">
        <div class="double-confirm-modal">
          <div class="double-confirm-icon">🚨</div>
          <h3>危险操作二次确认</h3>
          <p>此操作具有极高风险，请再次确认您要执行：</p>
          <p class="tool-highlight">{{ request.tool }}</p>
          <div class="double-confirm-actions">
            <button class="btn btn-outline" @click="showDoubleConfirm = false">
              取消
            </button>
            <button class="btn btn-danger" @click="finalConfirm">
              我确认要执行
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  request: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['confirm', 'reject', 'close'])

// 状态
const isEditing = ref(false)
const editedArgumentsText = ref('')
const parseError = ref('')
const showRejectInput = ref(false)
const rejectReason = ref('')
const showDoubleConfirm = ref(false)
const timeRemaining = ref(0)
const totalTime = ref(300) // 5分钟

// 计算属性
const riskClass = computed(() => {
  return props.request.risk_level || 'medium'
})

const riskIcon = computed(() => {
  const icons = {
    low: '🟢',
    medium: '🟡',
    high: '🟠',
    critical: '🔴'
  }
  return icons[props.request.risk_level] || '🟡'
})

const riskLabel = computed(() => {
  const labels = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '极高风险'
  }
  return labels[props.request.risk_level] || '中风险'
})

const allowModification = computed(() => {
  return props.request.allow_modification !== false
})

const displayArguments = computed(() => {
  return props.request.arguments || {}
})

const parsedEditedArguments = computed(() => {
  if (!isEditing.value) return null
  try {
    parseError.value = ''
    return JSON.parse(editedArgumentsText.value)
  } catch (e) {
    parseError.value = e.message
    return null
  }
})

// 初始化
onMounted(() => {
  editedArgumentsText.value = JSON.stringify(props.request.arguments || {}, null, 2)
  
  // 设置倒计时
  if (props.request.time_remaining_seconds > 0) {
    timeRemaining.value = props.request.time_remaining_seconds
    totalTime.value = props.request.time_remaining_seconds
    startCountdown()
  }
})

// 倒计时
let countdownInterval = null

function startCountdown() {
  countdownInterval = setInterval(() => {
    timeRemaining.value -= 1
    if (timeRemaining.value <= 0) {
      clearInterval(countdownInterval)
      emit('reject', '超时自动取消')
    }
  }, 1000)
}

onUnmounted(() => {
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }
})

// 处理确认
function handleConfirm() {
  // CRITICAL 级别需要二次确认
  if (props.request.risk_level === 'critical' && props.request.require_double_confirmation) {
    showDoubleConfirm.value = true
    return
  }
  
  finalConfirm()
}

function finalConfirm() {
  showDoubleConfirm.value = false
  
  // 如果编辑了参数，传递修改后的参数
  if (isEditing.value && parsedEditedArguments.value) {
    emit('confirm', parsedEditedArguments.value)
  } else {
    emit('confirm', null)
  }
}

// 处理拒绝
function handleReject() {
  emit('reject', rejectReason.value)
}

// 监听编辑状态
watch(isEditing, (newVal) => {
  if (newVal) {
    editedArgumentsText.value = JSON.stringify(props.request.arguments || {}, null, 2)
  }
})
</script>

<style scoped>
.confirmation-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.confirmation-modal {
  background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
  border-radius: 20px;
  width: 500px;
  max-width: 90%;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
  animation: slideUp 0.3s ease-out;
  position: relative;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* 风险边框 */
.confirmation-modal.low {
  border: 2px solid rgba(16, 185, 129, 0.3);
}

.confirmation-modal.medium {
  border: 2px solid rgba(245, 158, 11, 0.3);
}

.confirmation-modal.high {
  border: 2px solid rgba(249, 115, 22, 0.3);
}

.confirmation-modal.critical {
  border: 2px solid rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 40px rgba(239, 68, 68, 0.2);
}

/* 头部 */
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.risk-badge {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.risk-badge.low {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.risk-badge.medium {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.risk-badge.high {
  background: rgba(249, 115, 22, 0.2);
  color: #f97316;
}

.risk-badge.critical {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* 内容 */
.modal-body {
  padding: 20px;
  max-height: 60vh;
  overflow-y: auto;
}

.title {
  margin: 0 0 12px;
  font-size: 20px;
  color: #fff;
}

.description {
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin-bottom: 16px;
}

.warning-box {
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 10px;
  padding: 12px 16px;
  color: #f59e0b;
  font-size: 14px;
  margin-bottom: 20px;
}

/* 工具信息 */
.tool-info {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 20px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
}

.info-row:not(:last-child) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.label {
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}

.value {
  color: #fff;
  font-weight: 500;
  font-family: 'JetBrains Mono', monospace;
}

/* 参数区域 */
.arguments-section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  color: #fff;
  font-weight: 500;
}

.edit-btn {
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.edit-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.arguments-view pre {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 10px;
  padding: 16px;
  margin: 0;
  color: rgba(255, 255, 255, 0.9);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  overflow-x: auto;
  max-height: 200px;
}

.arguments-edit textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  padding: 16px;
  color: #fff;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  resize: vertical;
}

.arguments-edit textarea.error {
  border-color: #ef4444;
}

.arguments-edit textarea:focus {
  outline: none;
  border-color: #667eea;
}

.parse-error {
  color: #ef4444;
  font-size: 12px;
  margin-top: 8px;
}

/* 倒计时 */
.countdown {
  margin-bottom: 20px;
}

.countdown-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.countdown-progress {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b 0%, #ef4444 100%);
  border-radius: 2px;
  transition: width 1s linear;
}

.countdown-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

/* 拒绝原因 */
.reject-reason {
  margin-bottom: 16px;
}

.reject-reason label {
  display: block;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  margin-bottom: 8px;
}

.reject-reason input {
  width: 100%;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
}

.reject-reason input:focus {
  outline: none;
  border-color: #667eea;
}

/* 底部按钮 */
.modal-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.btn {
  flex: 1;
  padding: 12px 20px;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-danger {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: #fff;
}

.btn-danger:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
}

.btn-success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #fff;
}

.btn-success:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

.btn-success:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
}

.btn-outline:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* 二次确认 */
.double-confirm-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.double-confirm-modal {
  background: linear-gradient(135deg, #2d1f1f 0%, #1e1e2e 100%);
  border: 2px solid rgba(239, 68, 68, 0.5);
  border-radius: 16px;
  padding: 24px;
  text-align: center;
  max-width: 360px;
}

.double-confirm-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.double-confirm-modal h3 {
  color: #fff;
  margin: 0 0 12px;
}

.double-confirm-modal p {
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8px;
}

.tool-highlight {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  padding: 8px 16px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 20px !important;
}

.double-confirm-actions {
  display: flex;
  gap: 12px;
}

.double-confirm-actions .btn {
  flex: 1;
}

/* 滚动条 */
.modal-body::-webkit-scrollbar {
  width: 6px;
}

.modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.modal-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}
</style>

