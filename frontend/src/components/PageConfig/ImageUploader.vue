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
  >
    <!-- Has Image -->
    <template v-if="modelValue">
      <img :src="modelValue" alt="页面截图" class="preview-image" />
      <div class="overlay">
        <label class="btn-action">
          <input 
            type="file" 
            accept="image/png,image/jpeg,.png,.jpg,.jpeg"
            :disabled="disabled || isUploading"
            @change="handleFileSelect"
            class="hidden-input"
          />
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 4v6h6M23 20v-6h-6"/>
            <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/>
          </svg>
          更换
        </label>
        <button class="btn-action danger" type="button" @click.stop="handleRemove">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
          </svg>
          移除
        </button>
      </div>
    </template>
    
    <!-- Uploading -->
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
    
    <!-- Default: Click to upload (input nested inside label for reliability) -->
    <template v-else>
      <label class="upload-placeholder">
        <input 
          type="file" 
          accept="image/png,image/jpeg,.png,.jpg,.jpeg"
          :disabled="disabled || isUploading"
          @change="handleFileSelect"
          class="hidden-input"
        />
        <div class="upload-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
          </svg>
        </div>
        <p class="upload-text">拖拽图片到此处</p>
        <p class="upload-hint">或点击上传</p>
        <p class="upload-formats">支持 PNG, JPG (最大 10MB)</p>
      </label>
    </template>
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

const isDragover = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)

const handleDragover = () => {
  if (!props.disabled) isDragover.value = true
}

const handleDragleave = () => {
  isDragover.value = false
}

const handleDrop = (e) => {
  isDragover.value = false
  if (props.disabled || isUploading.value) return
  
  const files = e.dataTransfer.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const handleFileSelect = async (e) => {
  const inputEl = e.target
  const files = inputEl.files
  try {
    if (files && files.length > 0) {
      // 注意：processFile 是异步的；不要在其完成前就清空 input.value，
      // 否则部分浏览器会撤销文件读取权限，导致 NotReadableError。
      await processFile(files[0])
    }
  } finally {
    // 重置 input 以允许选择相同文件
    inputEl.value = ''
  }
}

const processFile = async (file) => {
  if (!file) return
  
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg']
  if (!allowedTypes.includes(file.type)) {
    emit('upload-error', {
      code: 'INVALID_FILE_TYPE',
      message: '仅支持 PNG、JPG 格式的图片'
    })
    return
  }
  
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    emit('upload-error', {
      code: 'FILE_TOO_LARGE',
      message: '图片大小不能超过 10MB'
    })
    return
  }
  
  isUploading.value = true
  uploadProgress.value = 0
  
  try {
    const result = await pageConfigApi.uploadImage(file, (progress) => {
      uploadProgress.value = progress
    })
    
    emit('update:modelValue', result.file_url)
    emit('upload-success', result)
  } catch (error) {
    console.error('Upload error:', error)
    
    // 构建友好的错误信息
    let errorMessage = '上传失败，请重试'
    let errorCode = 'UPLOAD_FAILED'
    
    if (error.code === 'UPLOAD_FAILED' || error.name === 'NotReadableError') {
      errorMessage = error.message
      errorCode = 'FILE_READ_ERROR'
    } else if (error.message?.includes('Network Error') || error.code === 'ERR_NETWORK') {
      errorMessage = '网络连接失败，请检查后端服务是否正常运行'
      errorCode = 'NETWORK_ERROR'
    } else if (error.response?.data?.message) {
      errorMessage = error.response.data.message
      errorCode = error.response.data.error || 'SERVER_ERROR'
    } else if (error.message) {
      errorMessage = error.message
    }
    
    emit('upload-error', {
      code: errorCode,
      message: errorMessage
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
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
  background: var(--bg-subtle);
  
  &:hover:not(.is-disabled):not(.has-image) {
    border-color: var(--primary);
    background: var(--primary-light);
    
    .upload-icon {
      transform: translateY(-4px);
    }
  }
  
  &:hover:not(.is-disabled).has-image {
    .overlay {
      opacity: 1;
    }
  }
  
  &.is-dragover {
    border-color: var(--primary);
    background: var(--primary-light);
    border-style: solid;
    
    .upload-icon {
      transform: scale(1.1) translateY(-4px);
    }
  }
  
  &.has-image {
    border-style: solid;
    border-color: transparent;
    background: #0f172a;
  }
  
  &.is-disabled {
    opacity: 0.6;
    cursor: not-allowed;
    
    .upload-placeholder {
      cursor: not-allowed;
    }
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
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.3s;
}

.btn-action {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: rgba(255, 255, 255, 0.95);
  border: none;
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: white;
    transform: translateY(-2px);
  }
  
  &.danger:hover {
    background: var(--error-light);
    color: var(--error);
  }
}

.upload-placeholder {
  text-align: center;
  padding: 32px;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  position: relative;
  
  .upload-icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 20px;
    background: var(--bg-elevated);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s;
    box-shadow: var(--shadow-sm);
    
    svg {
      width: 32px;
      height: 32px;
      color: var(--primary);
    }
  }
  
  .upload-text {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-heading);
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

.hidden-input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  margin: 0;
  border: 0;
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
