# 流式输出功能说明

## 概述

为了解决图片识别等待时间过长的问题，我们已将模型的输出改为流式输出(Server-Sent Events, SSE)。用户现在可以实时看到 AI 的响应内容，而不需要等待整个响应完成。

## 改进内容

### 1. 后端改进

#### VL 模型服务 (`backend/app/services/vl_model_service.py`)
- 新增 `parse_image_stream()` 方法：支持流式解析图片
- 新增 `clarify_stream()` 方法：支持流式澄清对话
- 新增 `_parse_accumulated_content()` 辅助方法：解析流式累积的内容

#### 图片解析 API (`backend/app/api/v1/page_config.py`)
- 新增 `/api/v1/pages/parse-stream` 端点：流式图片解析
- 返回 SSE 格式的实时响应
- 支持以下事件类型：
  - `start`: 开始解析
  - `content`: 内容片段
  - `complete`: 解析完成
  - `error`: 错误信息

#### 澄清对话 API (`backend/app/api/v1/clarify.py`)
- 新增 `/api/v1/clarify/{session_id}/chat-stream` 端点：流式聊天
- 实时返回 AI 的修改建议
- 自动更新数据库中的会话状态

### 2. 前端改进

#### API 层 (`frontend/src/api/index.js`)
- 新增 `pageConfigApi.parseStream()` 方法：调用流式解析 API
- 新增 `clarifyApi.chatStream()` 方法：调用流式聊天 API
- 使用 Fetch API 的 ReadableStream 处理 SSE 响应

#### 页面编辑器 (`frontend/src/views/PageEditor.vue`)
- 更新 `handleAIParse()` 方法使用流式解析
- 移除轮询机制，改为实时接收响应
- 支持取消流式请求

#### AI 助手面板 (`frontend/src/components/AIAssistant/ClarifyPanel.vue`)
- 更新 `sendMessage()` 方法使用流式聊天
- 实时显示 AI 响应内容
- 添加流式输入光标动画
- 支持流式消息的视觉反馈

## 使用方式

### 流式图片解析

前端调用示例：
```javascript
const eventSource = pageConfigApi.parseStream(
  imageUrl,
  // 消息回调
  (data) => {
    if (data.type === 'content') {
      console.log('收到内容:', data.content)
    }
  },
  // 完成回调
  (result) => {
    console.log('解析完成:', result)
  },
  // 错误回调
  (error) => {
    console.error('解析失败:', error)
  }
)

// 取消请求
eventSource.close()
```

### 流式聊天

前端调用示例：
```javascript
const stream = clarifyApi.chatStream(
  sessionId,
  message,
  currentConfig,
  // 消息回调
  (data) => {
    if (data.type === 'content') {
      // 实时显示内容
      updateMessage(data.content)
    }
  },
  // 完成回调
  (result) => {
    console.log('配置已更新:', result)
  },
  // 错误回调
  (error) => {
    console.error('请求失败:', error)
  }
)
```

## SSE 消息格式

### 事件类型

1. **start** - 开始处理
```json
{
  "type": "start",
  "message": "正在分析图片..."
}
```

2. **content** - 内容片段
```json
{
  "type": "content",
  "content": "部分响应内容"
}
```

3. **complete** - 处理完成
```json
{
  "type": "complete",
  "result": {
    "page_name": {...},
    "elements": [...],
    ...
  }
}
```

4. **error** - 错误信息
```json
{
  "type": "error",
  "message": "错误描述"
}
```

## 技术细节

### 后端实现

1. **流式生成器**: 使用 Python 的 `AsyncGenerator` 生成 SSE 流
2. **FastAPI StreamingResponse**: 返回 `text/event-stream` 类型响应
3. **数据库更新**: 在流式完成后自动更新会话状态

### 前端实现

1. **Fetch ReadableStream**: 使用现代浏览器的 Fetch API 读取流
2. **实时渲染**: 累积内容并实时更新 DOM
3. **视觉反馈**: 流式输入光标动画提供更好的用户体验

## 兼容性

- 后端保留了原有的非流式 API，确保向后兼容
- 前端可以选择使用流式或非流式 API
- 流式 API 端点：
  - `/api/v1/pages/parse-stream` (流式)
  - `/api/v1/pages/parse` (原有非流式)
  - `/api/v1/clarify/{session_id}/chat-stream` (流式)
  - `/api/v1/clarify/{session_id}/chat` (原有非流式)

## 性能优势

1. **更快的首字节时间**: 用户无需等待完整响应即可看到内容
2. **更好的用户体验**: 实时反馈让用户感知到系统正在工作
3. **降低超时风险**: 长时间请求被拆分为多个小片段
4. **资源优化**: 减少客户端轮询请求

## 测试建议

1. 上传页面截图，点击"AI 辅助填写"按钮
2. 观察 AI 助手面板中的实时响应
3. 在聊天框中输入修改建议，查看流式响应效果
4. 检查浏览器开发者工具的网络面板，确认 SSE 连接

## 注意事项

1. SSE 连接在完成或出错后会自动关闭
2. 如果网络中断，前端会显示错误消息
3. 流式内容会被累积并最终解析为 JSON
4. 确保 VL 模型 API 支持流式输出(`stream: true`)

