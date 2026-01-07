<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="visible" class="dialog-overlay" @click.self="handleCancel">
        <div class="dialog card">
          <h3 class="dialog-title">{{ title }}</h3>
          <p class="dialog-message">{{ message }}</p>
          
          <slot></slot>
          
          <div class="dialog-footer">
            <slot name="footer">
              <button class="btn btn-secondary" @click="handleCancel">
                {{ cancelText }}
              </button>
              <button :class="['btn', confirmClass]" @click="handleConfirm">
                {{ confirmText }}
              </button>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  visible: Boolean,
  title: {
    type: String,
    default: '确认'
  },
  message: {
    type: String,
    default: ''
  },
  confirmText: {
    type: String,
    default: '确认'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  confirmClass: {
    type: String,
    default: 'btn-primary'
  }
})

const emit = defineEmits(['update:visible', 'confirm', 'cancel'])

const handleConfirm = () => {
  emit('confirm')
  emit('update:visible', false)
}

const handleCancel = () => {
  emit('cancel')
  emit('update:visible', false)
}
</script>

<style lang="scss" scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  width: 400px;
  max-width: 90vw;
  
  .dialog-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 12px;
  }
  
  .dialog-message {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.6;
    margin-bottom: 24px;
  }
  
  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

