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
  getParseStatus: (sessionId) => api.get(`/pages/parse/${sessionId}/status`)
}

// Clarify API
export const clarifyApi = {
  submitResponse: (sessionId, data) => api.post(`/clarify/${sessionId}/respond`, data),
  confirm: (sessionId, data) => api.post(`/clarify/${sessionId}/confirm`, data),
  getHistory: (sessionId) => api.get(`/clarify/${sessionId}/history`),
  // 通用聊天接口 - 用于配置修改建议
  chat: (sessionId, data) => api.post(`/clarify/${sessionId}/chat`, data)
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

