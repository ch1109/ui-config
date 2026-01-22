import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,  // 增加到 120 秒以适应 npx 下载包
})

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Chrome/Edge 在上传本地文件时，如果文件在上传过程中被系统写入/修改（常见于刚保存的截图），
 * 会直接中断请求并报 net::ERR_UPLOAD_FILE_CHANGED，Axios 会表现为 Network Error。
 *
 * 这里把 File/Blob 先读入内存，生成稳定的 Blob（并保留 filename），避免依赖磁盘文件句柄。
 */
async function toStableUploadPayload(file, options = {}) {
  const {
    // 给系统/同步盘一点时间把文件写完（常见于截图刚落盘）
    initialDelayMs = 200,
    // 总重试次数（含第一次）
    maxAttempts = 5,
    // 指数退避基准
    retryBaseDelayMs = 200,
  } = options

  // 兼容：如果不是 Blob/File（极少见），直接返回让后续报错更清晰
  if (!(file instanceof Blob)) return { blob: file, filename: undefined }

  if (initialDelayMs > 0) await sleep(initialDelayMs)

  let lastErr
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const ab = await file.arrayBuffer()
      const blob = new Blob([ab], { type: file.type || 'application/octet-stream' })

      // File 有 name；Blob 可能没有。FormData.append 第三个参数可强制 filename
      const filename = typeof file.name === 'string' && file.name ? file.name : 'upload'
      return { blob, filename }
    } catch (e) {
      lastErr = e

      // NotReadableError：常见于文件仍在写入/被占用/权限瞬态问题，等一等重试往往就好了
      const name = e?.name || e?.constructor?.name
      if (name === 'NotReadableError' || name === 'AbortError') {
        const delay = retryBaseDelayMs * Math.pow(2, attempt - 1)
        await sleep(delay)
        continue
      }

      // 其他错误直接抛出
      throw e
    }
  }

  // 重试耗尽：抛出更明确的信息，便于 UI 提示
  const err = new Error('读取图片失败：文件可能仍在保存/被占用/权限受限，请稍等 1-2 秒后重试，或将图片复制到本地桌面再上传。')
  err.cause = lastErr
  err.name = 'NotReadableError'
  throw err
}

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
  getStats: () => api.get('/system-prompt/stats'),
  // 获取可用模型列表
  getModels: () => api.get('/system-prompt/models'),
  // 更新选择的模型
  updateModel: (model) => api.put('/system-prompt', { selected_model: model }),
  // 获取带有 MCP 工具信息的完整系统提示词
  getWithMcpTools: (includeUnavailable = false) => 
    api.get('/system-prompt/with-mcp-tools', { params: { include_unavailable: includeUnavailable } })
}

// Project API
export const projectApi = {
  list: () => api.get('/projects'),
  get: (projectId) => api.get(`/projects/${projectId}`),
  create: (data) => api.post('/projects', data),
  update: (projectId, data) => api.put(`/projects/${projectId}`, data),
  delete: (projectId) => api.delete(`/projects/${projectId}`)
}

// Button API - 按钮管理
export const buttonApi = {
  // 获取按钮列表（包含选项格式）
  list: (category = null) => api.get('/buttons', { params: { category } }),
  // 获取单个按钮
  get: (buttonId) => api.get(`/buttons/${buttonId}`),
  // 创建新按钮
  create: (data) => api.post('/buttons', data),
  // 更新按钮
  update: (buttonId, data) => api.put(`/buttons/${buttonId}`, data),
  // 删除按钮
  delete: (buttonId) => api.delete(`/buttons/${buttonId}`),
  // 获取下拉选项列表（简化格式）
  getOptions: () => api.get('/buttons/options/list')
}

// Page Config API
export const pageConfigApi = {
  list: (params) => api.get('/pages', { params }),
  get: (pageId) => api.get(`/pages/${pageId}`),
  create: (data) => api.post('/pages', data),
  update: (pageId, data) => api.put(`/pages/${pageId}`, data),
  saveDraft: (data) => api.post('/pages/draft', data),
  delete: (pageId) => api.delete(`/pages/${pageId}`),
  
  // 图片上传
  uploadImage: async (file, onProgress) => {
    // 先尝试稳定化读取文件到内存，避免后续上传时文件被系统修改
    // 这对于刚保存的截图或从其他应用粘贴的图片特别重要
    let stableBlob = null
    let stableFilename = null
    
    try {
      const stable = await toStableUploadPayload(file, {
        initialDelayMs: 100,  // 给系统一点时间完成文件写入
        maxAttempts: 5,
        retryBaseDelayMs: 300
      })
      stableBlob = stable.blob
      stableFilename = stable.filename
    } catch (readError) {
      // 如果稳定化读取失败，尝试直接上传原始文件（最后的手段）
      console.warn('稳定化读取失败，尝试直接上传:', readError.message)
      try {
        const directForm = new FormData()
        directForm.append('file', file)
        return await api.post('/pages/upload-image', directForm, {
          onUploadProgress: (e) => {
            if (onProgress && e.total) onProgress(e.loaded / e.total)
          }
        })
      } catch (uploadError) {
        // 两种方式都失败了，抛出更友好的错误
        const friendlyError = new Error(
          readError.name === 'NotReadableError'
            ? '读取图片失败：文件可能仍在保存中或被其他程序占用，请稍等 1-2 秒后重试，或将图片复制到桌面后上传。'
            : uploadError.response?.data?.message || uploadError.message || '图片上传失败，请重试'
        )
        friendlyError.code = 'UPLOAD_FAILED'
        throw friendlyError
      }
    }
    
    // 使用稳定化后的 Blob 上传
    const formData = new FormData()
    formData.append('file', stableBlob, stableFilename)
    
    return api.post('/pages/upload-image', formData, {
      onUploadProgress: (ev) => {
        if (onProgress && ev.total) onProgress(ev.loaded / ev.total)
      }
    })
  },
  
  // AI 解析
  parse: (imageUrl) => api.post('/pages/parse', null, { params: { image_url: imageUrl } }),
  getParseStatus: (sessionId) => api.get(`/pages/parse/${sessionId}/status`),
  
  // AI 解析 - 流式输出 (使用 fetch 处理 SSE)
  // 支持两阶段工作流程：
  // - 第一阶段：AI 输出分析总结（自然语言），触发 onSummary 回调
  // - 第二阶段：AI 输出 JSON 配置，触发 onComplete 回调
  // 回调参数:
  // - onMessage: 流式消息 { type, content/message }
  // - onComplete: 第二阶段完成 (result)
  // - onError: 错误 (message)
  // - onSummary: 第一阶段完成 (content, sessionId)
  parseStream: (imageUrl, onMessage, onComplete, onError, onSummary) => {
    const controller = new AbortController()
    let sessionId = null  // 保存从 init 事件获取的 session_id
    
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
              
              if (data.type === 'init') {
                // 初始化事件，保存 session_id
                sessionId = data.session_id
              } else if (data.type === 'start') {
                onMessage && onMessage({ type: 'start', message: data.message })
              } else if (data.type === 'content') {
                onMessage && onMessage({ type: 'content', content: data.content })
              } else if (data.type === 'summary') {
                // 第一阶段完成：分析总结（自然语言）
                onSummary && onSummary(data.content, sessionId)
                return
              } else if (data.type === 'complete') {
                // 第二阶段完成：JSON 配置
                onComplete && onComplete(data.result, sessionId)
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
  upload: async (file) => {
    // 同样采用"直传优先，失败再稳定化读取"
    try {
      const directForm = new FormData()
      directForm.append('file', file)
      return await api.post('/mcp/upload', directForm)
    } catch (e) {
      const formData = new FormData()
      const { blob, filename } = await toStableUploadPayload(file)
      formData.append('file', blob, filename)
      return api.post('/mcp/upload', formData)
    }
  },
  // 添加配置（支持 HTTP 和 STDIO 两种类型）
  // HTTP: { name, transport: 'http', server_url, health_check_path, ... }
  // STDIO: { name, transport: 'stdio', command, args, env, ... }
  addConfig: (config) => api.post('/mcp/config', config),
  update: (serverId, config) => api.put(`/mcp/${serverId}`, config),
  delete: (serverId) => api.delete(`/mcp/${serverId}`),
  test: (serverId) => api.post(`/mcp/${serverId}/test`)
}

// MCP Context API - 获取 MCP 工具上下文信息
export const mcpContextApi = {
  // 获取完整的 MCP 上下文（包含系统提示词片段、工具列表等）
  getContext: () => api.get('/mcp-context'),
  
  // 获取系统提示词片段
  getSystemPromptSnippet: (includeUnavailable = false) => 
    api.get('/mcp-context/system-prompt', { params: { include_unavailable: includeUnavailable } }),
  
  // 获取可用工具列表
  getTools: (format = 'list') => api.get('/mcp-context/tools', { params: { format } }),
  
  // 获取已启用的服务器列表
  getServers: () => api.get('/mcp-context/servers')
}

// MCP Host API - 完整的 Host 功能
export const mcpHostApi = {
  // ========== 会话管理 ==========
  createSession: (systemPrompt = '') => api.post('/host/sessions', { system_prompt: systemPrompt }),
  getSession: (sessionId) => api.get(`/host/sessions/${sessionId}`),
  deleteSession: (sessionId) => api.delete(`/host/sessions/${sessionId}`),
  
  // ========== Roots 管理（工作区目录）==========
  // 获取服务器的根目录列表
  getServerRoots: (serverKey) => api.get(`/host/servers/${serverKey}/roots`),
  
  // 配置服务器的根目录（替换所有）
  configureServerRoots: (serverKey, roots, strictMode = true) => 
    api.put(`/host/servers/${serverKey}/roots`, { roots, strict_mode: strictMode }),
  
  // 添加根目录
  addServerRoot: (serverKey, path, name = null, type = 'custom') => 
    api.post(`/host/servers/${serverKey}/roots`, { path, name, type }),
  
  // 移除根目录
  removeServerRoot: (serverKey, path) => 
    api.delete(`/host/servers/${serverKey}/roots`, { params: { path } }),
  
  // 验证文件路径
  validatePath: (serverKey, path) => 
    api.post(`/host/servers/${serverKey}/validate-path`, { path }),
  
  // 获取 Roots 服务状态
  getRootsStatus: () => api.get('/host/roots/status'),
  
  // 全局根目录管理
  getGlobalRoots: () => api.get('/host/roots/global'),
  addGlobalRoot: (path, name = null, type = 'custom') => 
    api.post('/host/roots/global', { path, name, type }),
  removeGlobalRoot: (path) => 
    api.delete('/host/roots/global', { params: { path } }),
  
  // ========== 对话（ReAct 循环）==========
  // 流式对话
  chatStream: (sessionId, message, config, onEvent, onComplete, onError) => {
    const controller = new AbortController()
    
    fetch(`/api/v1/host/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify({
        message,
        llm_provider: config.provider || 'openai',
        llm_model: config.model || 'gpt-4o',
        api_key: config.apiKey,
        base_url: config.baseUrl,
        temperature: config.temperature || 0.7,
        max_tokens: config.maxTokens || 4096,
        max_iterations: config.maxIterations || 10,
        stream: true
      }),
      signal: controller.signal
    }).then(async response => {
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim()
            if (dataStr === '[DONE]') {
              onComplete && onComplete()
              return
            }
            if (!dataStr) continue
            
            try {
              const event = JSON.parse(dataStr)
              onEvent && onEvent(event)
              
              // 如果需要确认，暂停
              if (event.type === 'confirmation_required') {
                return
              }
            } catch (e) {
              console.debug('Parse error:', dataStr)
            }
          }
        }
      }
    }).catch(error => {
      if (error.name !== 'AbortError') {
        console.error('Chat stream error:', error)
        onError && onError(error.message || '连接失败')
      }
    })
    
    return { close: () => controller.abort() }
  },
  
  // 非流式对话
  chat: (sessionId, message, config) => api.post(`/host/sessions/${sessionId}/chat`, {
    message,
    llm_provider: config.provider || 'openai',
    llm_model: config.model || 'gpt-4o',
    api_key: config.apiKey,
    base_url: config.baseUrl,
    temperature: config.temperature || 0.7,
    max_tokens: config.maxTokens || 4096,
    stream: false
  }),
  
  // ========== 人机回环确认 ==========
  getPendingConfirmations: (sessionId) => api.get(`/host/sessions/${sessionId}/confirmations`),
  confirmToolCall: (sessionId, requestId, approved, modifiedArgs = null, reason = '') => 
    api.post(`/host/sessions/${sessionId}/confirmations/${requestId}`, {
      approved,
      modified_arguments: modifiedArgs,
      reason
    }),
  
  // 确认并继续 ReAct 循环（流式）
  confirmAndContinueStream: (sessionId, requestId, approved, modifiedArgs, config, onEvent, onComplete, onError) => {
    const controller = new AbortController()
    
    fetch(`/api/v1/host/sessions/${sessionId}/confirmations/${requestId}/continue`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify({
        approved,
        modified_arguments: modifiedArgs,
        llm_provider: config?.provider || 'openai',
        llm_model: config?.model || 'gpt-4o',
        api_key: config?.apiKey,
        base_url: config?.baseUrl,
        temperature: config?.temperature || 0.7,
        max_tokens: config?.maxTokens || 4096,
        stream: true
      }),
      signal: controller.signal
    }).then(async response => {
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim()
            if (dataStr === '[DONE]') {
              onComplete && onComplete()
              return
            }
            if (!dataStr) continue
            
            try {
              const event = JSON.parse(dataStr)
              onEvent && onEvent(event)
            } catch (e) {
              console.debug('Parse error:', dataStr)
            }
          }
        }
      }
    }).catch(error => {
      if (error.name !== 'AbortError') {
        onError && onError(error.message || '连接失败')
      }
    })
    
    return { close: () => controller.abort() }
  },
  
  // ========== 工具管理 ==========
  listTools: () => api.get('/host/tools'),
  callTool: (serverKey, toolName, args, skipConfirmation = false) => 
    api.post('/host/tools/call', {
      server_key: serverKey,
      tool_name: toolName,
      arguments: args,
      skip_confirmation: skipConfirmation
    }),
  
  // ========== 服务器管理 ==========
  listServers: () => api.get('/host/servers'),
  startStdioServer: (serverKey, command, args = [], env = {}) => 
    api.post(`/host/servers/stdio/${serverKey}/start`, null, { 
      params: { command, args: args.join(','), ...env } 
    }),
  stopStdioServer: (serverKey) => api.post(`/host/servers/stdio/${serverKey}/stop`),
  connectSseServer: (config) => api.post('/host/servers/sse/connect', config),
  disconnectSseServer: (serverKey) => api.post(`/host/servers/sse/${serverKey}/disconnect`),
  
  // ========== 风险策略 ==========
  getPolicy: () => api.get('/host/policy'),
  updatePolicy: (policy) => api.put('/host/policy', null, { params: policy }),
  
  // ========== 审计日志 ==========
  getAuditLog: (sessionId = null, limit = 100) => 
    api.get('/host/audit-log', { params: { session_id: sessionId, limit } }),
  
  // ========== 健康检查 ==========
  health: () => api.get('/host/health'),
  
  // ========== Sampling 管理（服务端请求 LLM）==========
  // 获取 Sampling 安全配置
  getSamplingConfig: () => api.get('/host/sampling/config'),
  
  // 更新 Sampling 安全配置
  updateSamplingConfig: (config) => api.put('/host/sampling/config', config),
  
  // 获取 Sampling 服务状态
  getSamplingStatus: () => api.get('/host/sampling/status'),
  
  // 获取待审核的 Sampling 请求列表
  getSamplingRequests: () => api.get('/host/sampling/requests'),
  
  // 批准 Sampling 请求
  approveSamplingRequest: (requestId, modifiedParams = null, llmConfig = null) => 
    api.post(`/host/sampling/requests/${requestId}/approve`, { 
      modified_params: modifiedParams,
      llm_config: llmConfig
    }),
  
  // 拒绝 Sampling 请求
  rejectSamplingRequest: (requestId, reason = '用户拒绝了此请求') => 
    api.post(`/host/sampling/requests/${requestId}/reject`, { reason }),
  
  // 清理过期的 Sampling 请求
  cleanupSamplingRequests: () => api.post('/host/sampling/cleanup'),
  
  // 获取支持 Sampling 的服务器列表
  getSamplingServers: () => api.get('/host/sampling/servers')
}

// MCP Test API - 用于测试 MCP 功能
export const mcpTestApi = {
  // 演示服务器 API
  getDemoTools: () => api.get('/mcp-test/demo/tools'),
  callDemoTool: (toolName, args) => api.post('/mcp-test/demo/tools/call', { tool_name: toolName, arguments: args }),
  getDemoResources: () => api.get('/mcp-test/demo/resources'),
  readDemoResource: (uri) => api.post('/mcp-test/demo/resources/read', { uri }),
  getDemoPrompts: () => api.get('/mcp-test/demo/prompts'),
  getDemoPrompt: (name, args) => api.post('/mcp-test/demo/prompts/get', { name, arguments: args }),
  batchTest: () => api.post('/mcp-test/demo/batch-test'),
  
  // 流式测试 (使用 fetch 处理 SSE)
  streamTest: (onMessage, onComplete, onError) => {
    const controller = new AbortController()
    
    fetch('/api/v1/mcp-test/demo/stream-test', {
      method: 'GET',
      headers: { 'Accept': 'text/event-stream' },
      signal: controller.signal
    }).then(async response => {
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim()
            if (!dataStr) continue
            
            try {
              const data = JSON.parse(dataStr)
              if (data.type === 'complete') {
                onComplete && onComplete(data)
              } else {
                onMessage && onMessage(data)
              }
            } catch (e) {
              console.debug('Parse error:', dataStr)
            }
          }
        }
      }
    }).catch(error => {
      if (error.name !== 'AbortError') {
        console.error('Stream error:', error)
        onError && onError('连接失败，请重试')
      }
    })
    
    return { close: () => controller.abort() }
  },
  
  // 外部服务器 API (HTTP)
  getServerTools: (serverId) => api.get(`/mcp-test/servers/${serverId}/tools`),
  callServerTool: (serverId, toolName, args) => api.post(`/mcp-test/servers/${serverId}/tools/call`, { tool_name: toolName, arguments: args }),
  
  // ========== 真实 MCP 服务器 API (stdio) ==========
  
  // 获取所有 stdio 服务器状态
  getStdioStatus: () => api.get('/mcp-test/stdio/status'),
  
  // 启动 stdio 服务器 (context7, everything)
  startStdioServer: (serverKey) => api.post('/mcp-test/stdio/start', { server_key: serverKey }),
  
  // 停止 stdio 服务器
  stopStdioServer: (serverKey) => api.post('/mcp-test/stdio/stop', { server_key: serverKey }),
  
  // 获取 stdio 服务器的工具列表
  getStdioTools: (serverKey) => api.get(`/mcp-test/stdio/${serverKey}/tools`),
  
  // 调用 stdio 服务器的工具
  callStdioTool: (serverKey, toolName, args) => api.post('/mcp-test/stdio/tools/call', { 
    server_key: serverKey, 
    tool_name: toolName, 
    arguments: args 
  }),
  
  // 获取 stdio 服务器的资源列表
  getStdioResources: (serverKey) => api.get(`/mcp-test/stdio/${serverKey}/resources`),
  
  // 读取 stdio 服务器的资源
  readStdioResource: (serverKey, uri) => api.post('/mcp-test/stdio/resources/read', {
    server_key: serverKey,
    uri: uri
  }),
  
  // 获取 stdio 服务器的提示模板列表
  getStdioPrompts: (serverKey) => api.get(`/mcp-test/stdio/${serverKey}/prompts`),
  
  // 获取 stdio 服务器的提示模板内容
  getStdioPrompt: (serverKey, name, args) => api.post('/mcp-test/stdio/prompts/get', {
    server_key: serverKey,
    name: name,
    arguments: args
  }),
  
  // 批量测试 stdio 服务器
  batchTestStdio: (serverKey) => api.post(`/mcp-test/stdio/${serverKey}/batch-test`),
  
  // ========== SSE MCP 服务器 API ==========
  
  // 获取所有 SSE 服务器状态
  getSseStatus: () => api.get('/mcp-test/sse/status'),
  
  // 连接 SSE 服务器
  connectSseServer: (config) => api.post('/mcp-test/sse/connect', config),
  
  // 从数据库配置连接 SSE 服务器
  connectSseServerFromDb: (serverId) => api.post(`/mcp-test/sse/connect-db/${serverId}`),
  
  // 断开 SSE 服务器连接
  disconnectSseServer: (serverKey) => api.post(`/mcp-test/sse/disconnect/${serverKey}`),
  
  // 重新连接 SSE 服务器
  reconnectSseServer: (serverKey) => api.post(`/mcp-test/sse/reconnect/${serverKey}`),
  
  // 测试 SSE 连接健康状态
  testSseConnection: (serverKey) => api.get(`/mcp-test/sse/test/${serverKey}`),
  
  // 获取 SSE 服务器的工具列表
  getSseTools: (serverKey) => api.get(`/mcp-test/sse/${serverKey}/tools`),
  
  // 调用 SSE 服务器的工具
  callSseTool: (serverKey, toolName, args) => api.post('/mcp-test/sse/tools/call', {
    server_key: serverKey,
    tool_name: toolName,
    arguments: args
  }),
  
  // 获取 SSE 服务器的资源列表
  getSseResources: (serverKey) => api.get(`/mcp-test/sse/${serverKey}/resources`),
  
  // 读取 SSE 服务器的资源
  readSseResource: (serverKey, uri) => api.post('/mcp-test/sse/resources/read', {
    server_key: serverKey,
    uri: uri
  }),
  
  // 获取 SSE 服务器的提示模板列表
  getSsePrompts: (serverKey) => api.get(`/mcp-test/sse/${serverKey}/prompts`),
  
  // 获取 SSE 服务器的提示模板内容
  getSsePrompt: (serverKey, name, args) => api.post('/mcp-test/sse/prompts/get', {
    server_key: serverKey,
    name: name,
    arguments: args
  }),
  
  // 批量测试 SSE 服务器
  batchTestSse: (serverKey) => api.post(`/mcp-test/sse/${serverKey}/batch-test`),
  
  // 获取所有 SSE 服务器的工具（聚合）
  getAllSseTools: () => api.get('/mcp-test/sse/all-tools')
}

export default api
