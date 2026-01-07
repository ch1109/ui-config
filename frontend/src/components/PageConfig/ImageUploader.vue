<template>
  <div 
    class="image-uploader"
    :class="{ 
      'is-dragover': isDragover,
      'has-image': modelValue,
      'is-disabled': disabled || isUploading
    }"
    @dragover.prevent="handleDragover"
    @dragleave="handleDragleave"
    @drop.prevent="handleDrop"
    @click="triggerFileInput"
  >
    <!-- 已上传状态 -->
    <template v-if="modelValue">
      <img :src="modelValue" alt="页面截图" class="preview-image" />
      <div class="overlay">
        <button class="btn-action" @click.stop="triggerFileInput">
          🔄 更换
        </button>
        <button class="btn-action danger" @click.stop="handleRemove">
          🗑️ 移除
        </button>
      </div>
    </template>
    
    <!-- 上传中状态 -->
    <template v-else-if="isUploading">
      <div class="upload-progress">
        <div class="progress-ring">
          <svg viewBox="0 0 100 100">
            <circle class="bg" cx="50" cy="50" r="45" />
            <circle 
              class="progress" 
              cx="50" 
              cy="50" 
              r="45"
              :stroke-dasharray="`${uploadProgress * 283} 283`"
            />
          </svg>
          <span class="percent">{{ Math.round(uploadProgress * 100) }}%</span>
        </div>
        <p>上传中...</p>
      </div>
    </template>
    
    <!-- 默认状态 -->
    <template v-else>
      <div class="upload-placeholder">
        <div class="upload-icon">📤</div>
        <p class="upload-text">拖拽图片到此处</p>
        <p class="upload-hint">或点击上传</p>
        <p class="upload-formats">支持 PNG, JPG (最大 10MB)</p>
      </div>
    </template>
    
    <input
      ref="fileInput"
      type="file"
      accept=".png,.jpg,.jpeg"
      class="file-input"
      @change="handleFileSelect"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { pageConfigApi } from '@/api'

const props = defineProps({
  modelValue: String,
  disabled: Boolean
})

const emit = defineEmits(['update:modelValue', 'upload-success', 'upload-error'])

const fileInput = ref(null)
const isDragover = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)

const triggerFileInput = () => {
  console.log('triggerFileInput called', { disabled: props.disabled, isUploading: isUploading.value, fileInput: fileInput.value })
  if (!props.disabled && !isUploading.value) {
    if (fileInput.value) {
      fileInput.value.click()
    } else {
      // 备用方案：直接查找 DOM
      const input = document.querySelector('.image-uploader .file-input')
      if (input) input.click()
    }
  }
}

const handleDragover = () => {
  if (!props.disabled) isDragover.value = true
}

const handleDragleave = () => {
  isDragover.value = false
}

const handleDrop = (e) => {
  isDragover.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files.length > 0) {
    processFile(files[0])
  }
  // 清空 input 以支持重复选择同一文件
  e.target.value = ''
}

const processFile = async (file) => {
  // 验证文件类型 (REQ-M2-010)
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg']
  if (!allowedTypes.includes(file.type)) {
    emit('upload-error', {
      code: 'INVALID_FILE_TYPE',
      message: '仅支持 PNG、JPG 格式的图片'
    })
    return
  }
  
  // 验证文件大小 (REQ-M2-011)
  const maxSize = 10 * 1024 * 1024 // 10MB
  if (file.size > maxSize) {
    emit('upload-error', {
      code: 'FILE_TOO_LARGE',
      message: '图片大小不能超过 10MB'
    })
    return
  }
  
  // 上传文件
  isUploading.value = true
  uploadProgress.value = 0
  
  try {
    const result = await pageConfigApi.uploadImage(file, (progress) => {
      uploadProgress.value = progress
    })
    
    emit('update:modelValue', result.file_url)
    emit('upload-success', result)
  } catch (error) {
    emit('upload-error', {
      code: error.response?.data?.error || 'UPLOAD_FAILED',
      message: error.response?.data?.message || '上传失败'
    })
  } finally {
    isUploading.value = false
  }
}

const handleRemove = () => {
  emit('update:modelValue', null)
}
</script>

<style lang="scss" scoped>
.image-uploader {
  width: 100%;
  aspect-ratio: 4 / 3;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
  background: var(--bg-secondary);
  
  &:hover:not(.is-disabled) {
    border-color: var(--primary);
    
    .overlay {
      opacity: 1;
    }
  }
  
  &.is-dragover {
    border-color: var(--primary);
    background: var(--primary-light);
    
    .upload-icon {
      transform: scale(1.1);
    }
  }
  
  &.has-image {
    border-style: solid;
    border-color: transparent;
  }
  
  &.is-disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.3s;
}

.btn-action {
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: var(--bg-hover);
    border-color: var(--text-muted);
  }
  
  &.danger:hover {
    border-color: var(--error);
    color: var(--error);
  }
}

.upload-placeholder {
  text-align: center;
  padding: 24px;
  
  .upload-icon {
    font-size: 48px;
    margin-bottom: 16px;
    transition: transform 0.3s;
  }
  
  .upload-text {
    font-size: 15px;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 4px;
  }
  
  .upload-hint {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }
  
  .upload-formats {
    font-size: 11px;
    color: var(--text-muted);
  }
}

.file-input {
  display: none;
}

.upload-progress {
  text-align: center;
  
  .progress-ring {
    position: relative;
    width: 80px;
    height: 80px;
    margin: 0 auto 16px;
    
    svg {
      transform: rotate(-90deg);
      width: 100%;
      height: 100%;
    }
    
    circle {
      fill: none;
      stroke-width: 6;
      
      &.bg {
        stroke: var(--border-color);
      }
      
      &.progress {
        stroke: var(--primary);
        stroke-linecap: round;
        transition: stroke-dasharray 0.3s;
      }
    }
    
    .percent {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 14px;
      font-weight: 600;
      color: var(--primary);
    }
  }
  
  p {
    color: var(--text-secondary);
    font-size: 13px;
  }
}
</style>

