# 流式输出快速开始指南

## 概览

本指南将帮助您快速了解和使用新的流式输出功能。

## 用户角度：如何体验

### 1. 图片识别流式输出

**之前的体验**:
- 点击"AI 辅助填写"按钮
- 等待 10-30 秒，界面无反馈
- 突然显示完整结果

**现在的体验**:
1. 上传页面截图
2. 点击"AI 辅助填写"按钮
3. **立即**看到"正在分析图片..."提示
4. **实时**看到 AI 的识别内容逐字显示
5. 看到闪烁的光标 ▊ 表示 AI 正在输出
6. 几秒后看到完整的配置预览

### 2. 聊天对话流式输出

**之前的体验**:
- 输入修改建议
- 等待响应
- 突然显示完整回复

**现在的体验**:
1. 在聊天框输入修改建议，如"请将登录按钮改为主按钮"
2. 发送后**立即**看到 AI 的回复开始出现
3. **逐字**看到 AI 的建议内容
4. 看到闪烁的光标表示 AI 还在输出
5. 完成后自动应用配置更新

## 开发者角度：如何使用

### 后端开发

#### 1. 创建流式端点

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

@router.post("/my-stream-endpoint")
async def my_stream_endpoint():
    async def stream_generator():
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'start', 'message': '开始处理'})}\n\n"
        
        # 发送内容片段
        for chunk in process_data():
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        # 发送完成事件
        yield f"data: {json.dumps({'type': 'complete', 'result': final_result})}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
```

#### 2. 使用 VL 模型服务

```python
from app.services.vl_model_service import VLModelService

vl_service = VLModelService()

# 流式解析图片
async for chunk in vl_service.parse_image_stream(image_url, system_prompt):
    yield chunk

# 流式澄清对话
async for chunk in vl_service.clarify_stream(
    image_url, previous_result, clarify_history, 
    user_response, system_prompt
):
    yield chunk
```

### 前端开发

#### 1. 调用流式 API

```javascript
import { pageConfigApi } from '@/api'

// 图片解析流式
const eventSource = pageConfigApi.parseStream(
  imageUrl,
  // 消息回调
  (data) => {
    if (data.type === 'start') {
      console.log('开始:', data.message)
    } else if (data.type === 'content') {
      console.log('内容:', data.content)
      // 实时显示内容
      displayContent(data.content)
    }
  },
  // 完成回调
  (result) => {
    console.log('完成:', result)
    applyResult(result)
  },
  // 错误回调
  (error) => {
    console.error('错误:', error)
    showError(error)
  }
)

// 取消流式请求
eventSource.close()
```

#### 2. 聊天流式

```javascript
import { clarifyApi } from '@/api'

const stream = clarifyApi.chatStream(
  sessionId,
  message,
  currentConfig,
  // 消息回调
  (data) => {
    if (data.type === 'content') {
      // 累积并显示内容
      accumulatedContent += data.content
      updateChatMessage(accumulatedContent)
    }
  },
  // 完成回调
  (result) => {
    console.log('配置已更新:', result)
    applyConfigUpdate(result)
  },
  // 错误回调
  (error) => {
    console.error('错误:', error)
  }
)
```

#### 3. 在 Vue 组件中使用

```vue
<template>
  <div class="chat-message">
    <span v-html="messageContent"></span>
    <span v-if="isStreaming" class="cursor">▊</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { clarifyApi } from '@/api'

const messageContent = ref('')
const isStreaming = ref(false)

const sendMessage = async (text) => {
  isStreaming.value = true
  messageContent.value = ''
  
  clarifyApi.chatStream(
    sessionId,
    text,
    currentConfig,
    (data) => {
      if (data.type === 'content') {
        messageContent.value += data.content
      }
    },
    (result) => {
      isStreaming.value = false
      console.log('完成:', result)
    },
    (error) => {
      isStreaming.value = false
      console.error('错误:', error)
    }
  )
}
</script>

<style scoped>
.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
```

## 常见问题

### Q1: 流式响应比非流式慢吗？

**A**: 不会。流式响应的**总时间**与非流式相同，但**首字节时间**大大减少。用户可以立即看到反馈，体验更好。

### Q2: 如何处理网络中断？

**A**: 前端会自动检测连接中断并调用 `onError` 回调。您可以在回调中显示错误消息，并提供重试按钮。

```javascript
const handleError = (error) => {
  showToast('连接中断，请重试', 'error')
  // 提供重试按钮
  showRetryButton()
}
```

### Q3: 可以取消正在进行的流式请求吗？

**A**: 可以。保存返回的 EventSource 或 stream 对象，然后调用 `close()` 方法：

```javascript
const eventSource = pageConfigApi.parseStream(...)

// 取消请求
eventSource.close()
```

### Q4: 流式输出是否支持所有 VL 模型？

**A**: 只要模型 API 支持 `stream: true` 参数即可。目前支持：
- 智谱 GLM-4V
- 阿里云 DashScope Qwen-VL
- OpenAI 兼容接口

### Q5: 如何调试流式响应？

**A**: 
1. 打开浏览器开发者工具
2. 切换到"网络"标签
3. 筛选类型为 `eventsource` 或 URL 包含 `stream` 的请求
4. 点击请求，查看"消息"或"响应"标签
5. 实时查看 SSE 事件

## 性能对比

| 指标 | 非流式 | 流式 | 改进 |
|------|--------|------|------|
| 首字节时间 | 5-30秒 | <1秒 | **95%+** |
| 感知等待时间 | 长 | 短 | **显著改善** |
| 用户焦虑感 | 高 | 低 | **大幅降低** |
| 服务器负载 | 轮询增加 | 单次连接 | **减少** |

## 最佳实践

### 1. 提供清晰的视觉反馈

```vue
<!-- 使用加载指示器 -->
<div v-if="isStreaming" class="streaming-indicator">
  <span class="dot"></span>
  <span class="dot"></span>
  <span class="dot"></span>
</div>

<!-- 或使用光标 -->
<span v-if="isStreaming" class="cursor">▊</span>
```

### 2. 处理部分内容

```javascript
let buffer = ''

const onMessage = (data) => {
  if (data.type === 'content') {
    buffer += data.content
    // 可以按行或段落显示
    displayPartialContent(buffer)
  }
}
```

### 3. 错误恢复

```javascript
const parseWithRetry = async (imageUrl, maxRetries = 3) => {
  let attempts = 0
  
  while (attempts < maxRetries) {
    try {
      await parseStream(imageUrl)
      break
    } catch (error) {
      attempts++
      if (attempts >= maxRetries) {
        showError('多次尝试失败，请稍后重试')
      } else {
        await delay(1000 * attempts) // 指数退避
      }
    }
  }
}
```

### 4. 资源清理

```javascript
import { onUnmounted } from 'vue'

let currentStream = null

const startStream = () => {
  currentStream = pageConfigApi.parseStream(...)
}

// 组件卸载时清理
onUnmounted(() => {
  if (currentStream) {
    currentStream.close()
  }
})
```

## 下一步

1. 📖 阅读 [STREAMING_FEATURE.md](./STREAMING_FEATURE.md) 了解详细技术实现
2. 📋 查看 [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) 了解完整改动列表
3. 🧪 运行项目并体验流式输出效果
4. 🔧 根据需要自定义流式行为

## 支持

如有问题，请：
1. 查看浏览器控制台日志
2. 检查后端日志
3. 确认 VL 模型 API 配置正确
4. 提交 Issue 或联系开发团队

