import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    const message = error.response?.data?.message || error.message || '请求失败'
    console.error('API Error:', message)
    return Promise.reject(error)
  }
)

// System Prompt API
export const systemPromptApi = {
  getCurrent: () => api.get('/system-prompt'),
  update: (data) => api.put('/system-prompt', data),
  reset: () => api.post('/system-prompt/reset'),
  getDefault: () => api.get('/system-prompt/default'),
  getStats: () => api.get('/system-prompt/stats')
}

// Page Config API
export const pageConfigApi = {
  list: (params) => api.get('/pages', { params }),
  get: (pageId) => api.get(`/pages/${pageId}`),
  create: (data) => api.post('/pages', data),
  update: (pageId, data) => api.put(`/pages/${pageId}`, data),
  delete: (pageId) => api.delete(`/pages/${pageId}`),
  
  // 图片上传
  uploadImage: (file, onProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    
    return api.post('/pages/upload-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(e.loaded / e.total)
        }
      }
    })
  },
  
  // AI 解析
  parse: (imageUrl) => api.post('/pages/parse', null, { params: { image_url: imageUrl } }),
  getParseStatus: (sessionId) => api.get(`/pages/parse/${sessionId}/status`),
  
  // AI 解析 - 流式输出 (使用 fetch 处理 SSE)
  parseStream: (imageUrl, onMessage, onComplete, onError) => {
    const controller = new AbortController()
    
    fetch(`/api/v1/pages/parse-stream?image_url=${encodeURIComponent(imageUrl)}`, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream'
      },
      signal: controller.signal
    }).then(async response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          break
        }
        
        buffer += decoder.decode(value, { stream: true })
        
        // 处理可能包含多个事件的 buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 保留未完成的行
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim()
            if (!dataStr) continue
            
            try {
              const data = JSON.parse(dataStr)
              
              if (data.type === 'start') {
                onMessage && onMessage({ type: 'start', message: data.message })
              } else if (data.type === 'content') {
                onMessage && onMessage({ type: 'content', content: data.content })
              } else if (data.type === 'complete') {
                onComplete && onComplete(data.result)
                return
              } else if (data.type === 'error') {
                onError && onError(data.message)
                return
              }
            } catch (e) {
              // 忽略解析错误
              console.debug('Parse error for line:', dataStr)
            }
          }
        }
      }
    }).catch(error => {
      if (error.name !== 'AbortError') {
        console.error('Fetch stream error:', error)
        onError && onError('连接失败，请重试')
      }
    })
    
    // 返回可以取消的对象
    return {
      close: () => controller.abort()
    }
  }
}

// Clarify API
export const clarifyApi = {
  submitResponse: (sessionId, data) => api.post(`/clarify/${sessionId}/respond`, data),
  confirm: (sessionId, data) => api.post(`/clarify/${sessionId}/confirm`, data),
  getHistory: (sessionId) => api.get(`/clarify/${sessionId}/history`),
  // 通用聊天接口 - 用于配置修改建议
  chat: (sessionId, data) => api.post(`/clarify/${sessionId}/chat`, data),
  
  // 通用聊天接口 - 流式输出 (使用 fetch 处理 SSE)
  chatStream: (sessionId, message, currentConfig, onMessage, onComplete, onError) => {
    const controller = new AbortController()
    
    fetch(`/api/v1/clarify/${sessionId}/chat-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify({
        message: message,
        current_config: currentConfig || {}
      }),
      signal: controller.signal
    }).then(async response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          break
        }
        
        buffer += decoder.decode(value, { stream: true })
        
        // 处理可能包含多个事件的 buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 保留未完成的行
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim()
            if (!dataStr) continue
            
            try {
              const data = JSON.parse(dataStr)
              
              if (data.type === 'start') {
                onMessage && onMessage({ type: 'start', message: data.message })
              } else if (data.type === 'content') {
                onMessage && onMessage({ type: 'content', content: data.content })
              } else if (data.type === 'complete') {
                onComplete && onComplete(data.result)
                return
              } else if (data.type === 'error') {
                onError && onError(data.message)
                return
              }
            } catch (e) {
              // 忽略解析错误
              console.debug('Parse error for line:', dataStr)
            }
          }
        }
      }
    }).catch(error => {
      if (error.name !== 'AbortError') {
        console.error('Fetch stream error:', error)
        onError && onError('连接失败，请重试')
      }
    })
    
    // 返回可以取消的对象
    return {
      close: () => controller.abort()
    }
  }
}

// Config Generator API
export const configApi = {
  generate: (data) => api.post('/config/generate', data),
  validate: (config) => api.post('/config/validate', config),
  save: (data) => api.post('/config/save', data),
  getSchema: () => api.get('/config/schema')
}

// MCP API
export const mcpApi = {
  list: () => api.get('/mcp'),
  toggle: (presetKey, enable) => api.post(`/mcp/${presetKey}/toggle`, null, { params: { enable } }),
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/mcp/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  addConfig: (config) => api.post('/mcp/config', config),
  update: (serverId, config) => api.put(`/mcp/${serverId}`, config),
  delete: (serverId) => api.delete(`/mcp/${serverId}`),
  test: (serverId) => api.post(`/mcp/${serverId}/test`)
}

export default api

