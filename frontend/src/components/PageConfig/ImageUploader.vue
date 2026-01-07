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
        <button class="btn-action" type="button" @click.stop.prevent="openFilePicker">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 4v6h6M23 20v-6h-6"/>
            <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/>
          </svg>
          更换
        </button>
        <button class="btn-action danger" type="button" @click.stop.prevent="handleRemove">
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
    
    <!-- Default: Click to upload -->
    <template v-else>
      <div class="upload-placeholder" @click.stop="openFilePicker">
        <div class="upload-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
          </svg>
        </div>
        <p class="upload-text">拖拽图片到此处</p>
        <p class="upload-hint">或点击上传</p>
        <p class="upload-formats">支持 PNG, JPG (最大 10MB)</p>
      </div>
    </template>
    
    <input
      ref="fileInputRef"
      type="file"
      accept="image/png,image/jpeg,.png,.jpg,.jpeg"
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

const fileInputRef = ref(null)
const isDragover = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const isPickerOpen = ref(false)

// 打开文件选择器
const openFilePicker = () => {
  if (props.disabled || isUploading.value || isPickerOpen.value) {
    return
  }
  
  isPickerOpen.value = true
  
  // 确保 input 存在并触发点击
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
  
  // 重置标志，允许下次打开
  setTimeout(() => {
    isPickerOpen.value = false
  }, 500)
}

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

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files && files.length > 0) {
    processFile(files[0])
  }
  // 重置 input 以允许选择相同文件
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
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
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
  background: var(--bg-subtle);
  
  &:hover:not(.is-disabled) {
    border-color: var(--primary);
    background: var(--primary-light);
    
    .overlay {
      opacity: 1;
    }
    
    .upload-icon {
      transform: translateY(-4px);
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
  cursor: pointer;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  
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
