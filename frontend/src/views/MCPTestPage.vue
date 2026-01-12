<template>
  <div class="mcp-test-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="title-group">
          <h1>
            <span class="icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
              </svg>
            </span>
            MCP 功能测试
          </h1>
          <p class="subtitle">测试 Model Context Protocol 工具调用、资源读取和提示模板功能</p>
        </div>
        <div class="header-actions">
          <button class="batch-test-btn" @click="runBatchTest" :disabled="batchTesting">
            <svg v-if="!batchTesting" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            <span v-else class="spinner"></span>
            {{ batchTesting ? '测试中...' : '批量测试' }}
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <div class="page-content">
      <!-- Tabs -->
      <div class="tabs">
        <button 
          v-for="tab in tabs" 
          :key="tab.key"
          :class="['tab-btn', { active: activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >
          <component :is="tab.icon" />
          {{ tab.label }}
        </button>
      </div>

      <!-- Tools Tab -->
      <div v-show="activeTab === 'tools'" class="tab-content">
        <div class="panel-grid">
          <!-- Tools List -->
          <div class="panel">
            <div class="panel-header">
              <h3>可用工具</h3>
              <button class="refresh-btn" @click="loadTools" :disabled="loadingTools">
                <svg :class="{ spinning: loadingTools }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 4v6h-6M1 20v-6h6"/>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                </svg>
              </button>
            </div>
            <div class="panel-body">
              <div v-if="loadingTools" class="loading-state">
                <div class="loader"></div>
                <span>加载工具列表...</span>
              </div>
              <div v-else-if="tools.length === 0" class="empty-state">
                <p>暂无可用工具</p>
              </div>
              <div v-else class="tool-list">
                <div 
                  v-for="tool in tools" 
                  :key="tool.name"
                  :class="['tool-item', { selected: selectedTool?.name === tool.name }]"
                  @click="selectTool(tool)"
                >
                  <div class="tool-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                    </svg>
                  </div>
                  <div class="tool-info">
                    <span class="tool-name">{{ tool.name }}</span>
                    <span class="tool-desc">{{ tool.description }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Tool Call -->
          <div class="panel">
            <div class="panel-header">
              <h3>调用工具</h3>
            </div>
            <div class="panel-body">
              <div v-if="!selectedTool" class="empty-state">
                <p>请从左侧选择一个工具</p>
              </div>
              <div v-else class="tool-call-form">
                <div class="selected-tool-info">
                  <h4>{{ selectedTool.name }}</h4>
                  <p>{{ selectedTool.description }}</p>
                </div>
                
                <!-- Dynamic Arguments Form -->
                <div class="args-form">
                  <h5>参数配置</h5>
                  <div 
                    v-for="(prop, propName) in selectedTool.inputSchema?.properties || {}" 
                    :key="propName"
                    class="form-group"
                  >
                    <label>
                      {{ propName }}
                      <span v-if="selectedTool.inputSchema?.required?.includes(propName)" class="required">*</span>
                    </label>
                    <input 
                      v-if="prop.type === 'string'"
                      v-model="toolArgs[propName]"
                      type="text"
                      :placeholder="prop.description"
                    />
                    <input 
                      v-else-if="prop.type === 'integer' || prop.type === 'number'"
                      v-model.number="toolArgs[propName]"
                      type="number"
                      :placeholder="prop.description"
                    />
                    <textarea 
                      v-else
                      v-model="toolArgs[propName]"
                      :placeholder="prop.description"
                      rows="3"
                    ></textarea>
                    <span class="field-hint">{{ prop.description }}</span>
                  </div>
                </div>

                <button class="call-btn" @click="callTool" :disabled="callingTool">
                  <svg v-if="!callingTool" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                  <span v-else class="spinner small"></span>
                  {{ callingTool ? '执行中...' : '执行工具' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Result -->
          <div class="panel result-panel">
            <div class="panel-header">
              <h3>执行结果</h3>
              <span v-if="lastCallDuration" class="duration-badge">
                {{ lastCallDuration }}ms
              </span>
            </div>
            <div class="panel-body">
              <div v-if="!toolResult" class="empty-state">
                <p>执行工具后这里会显示结果</p>
              </div>
              <div v-else class="result-content">
                <div :class="['result-status', toolResult.success ? 'success' : 'error']">
                  <svg v-if="toolResult.success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                  </svg>
                  {{ toolResult.success ? '执行成功' : '执行失败' }}
                </div>
                <pre class="result-json">{{ formatJson(toolResult.data) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Resources Tab -->
      <div v-show="activeTab === 'resources'" class="tab-content">
        <div class="panel-grid two-cols">
          <!-- Resources List -->
          <div class="panel">
            <div class="panel-header">
              <h3>可用资源</h3>
              <button class="refresh-btn" @click="loadResources" :disabled="loadingResources">
                <svg :class="{ spinning: loadingResources }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 4v6h-6M1 20v-6h6"/>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                </svg>
              </button>
            </div>
            <div class="panel-body">
              <div v-if="loadingResources" class="loading-state">
                <div class="loader"></div>
                <span>加载资源列表...</span>
              </div>
              <div v-else-if="resources.length === 0" class="empty-state">
                <p>暂无可用资源</p>
              </div>
              <div v-else class="resource-list">
                <div 
                  v-for="resource in resources" 
                  :key="resource.uri"
                  class="resource-item"
                  @click="readResource(resource)"
                >
                  <div class="resource-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                  </div>
                  <div class="resource-info">
                    <span class="resource-name">{{ resource.name }}</span>
                    <span class="resource-uri">{{ resource.uri }}</span>
                    <span class="resource-desc">{{ resource.description }}</span>
                  </div>
                  <span class="mime-badge">{{ resource.mimeType }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Resource Content -->
          <div class="panel">
            <div class="panel-header">
              <h3>资源内容</h3>
            </div>
            <div class="panel-body">
              <div v-if="loadingResource" class="loading-state">
                <div class="loader"></div>
                <span>读取资源...</span>
              </div>
              <div v-else-if="!resourceContent" class="empty-state">
                <p>点击左侧资源查看内容</p>
              </div>
              <div v-else class="resource-content">
                <pre>{{ resourceContent }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Prompts Tab -->
      <div v-show="activeTab === 'prompts'" class="tab-content">
        <div class="panel-grid two-cols">
          <!-- Prompts List -->
          <div class="panel">
            <div class="panel-header">
              <h3>提示模板</h3>
              <button class="refresh-btn" @click="loadPrompts" :disabled="loadingPrompts">
                <svg :class="{ spinning: loadingPrompts }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 4v6h-6M1 20v-6h6"/>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                </svg>
              </button>
            </div>
            <div class="panel-body">
              <div v-if="loadingPrompts" class="loading-state">
                <div class="loader"></div>
                <span>加载提示模板...</span>
              </div>
              <div v-else-if="prompts.length === 0" class="empty-state">
                <p>暂无提示模板</p>
              </div>
              <div v-else class="prompt-list">
                <div 
                  v-for="prompt in prompts" 
                  :key="prompt.name"
                  :class="['prompt-item', { selected: selectedPrompt?.name === prompt.name }]"
                  @click="selectPrompt(prompt)"
                >
                  <div class="prompt-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                  </div>
                  <div class="prompt-info">
                    <span class="prompt-name">{{ prompt.name }}</span>
                    <span class="prompt-desc">{{ prompt.description }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Prompt Form & Result -->
          <div class="panel">
            <div class="panel-header">
              <h3>获取提示</h3>
            </div>
            <div class="panel-body">
              <div v-if="!selectedPrompt" class="empty-state">
                <p>请从左侧选择一个提示模板</p>
              </div>
              <div v-else class="prompt-form">
                <div class="selected-prompt-info">
                  <h4>{{ selectedPrompt.name }}</h4>
                  <p>{{ selectedPrompt.description }}</p>
                </div>
                
                <div class="args-form" v-if="selectedPrompt.arguments?.length > 0">
                  <h5>模板参数</h5>
                  <div 
                    v-for="arg in selectedPrompt.arguments" 
                    :key="arg.name"
                    class="form-group"
                  >
                    <label>
                      {{ arg.name }}
                      <span v-if="arg.required" class="required">*</span>
                    </label>
                    <input 
                      v-model="promptArgs[arg.name]"
                      type="text"
                      :placeholder="arg.description"
                    />
                    <span class="field-hint">{{ arg.description }}</span>
                  </div>
                </div>

                <button class="call-btn" @click="getPrompt" :disabled="gettingPrompt">
                  <svg v-if="!gettingPrompt" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                  <span v-else class="spinner small"></span>
                  {{ gettingPrompt ? '获取中...' : '获取提示' }}
                </button>

                <div v-if="promptResult" class="prompt-result">
                  <h5>生成结果</h5>
                  <pre>{{ formatJson(promptResult) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stream Test Tab -->
      <div v-show="activeTab === 'stream'" class="tab-content">
        <div class="panel full-width">
          <div class="panel-header">
            <h3>流式输出测试</h3>
            <button class="stream-btn" @click="runStreamTest" :disabled="streaming">
              <svg v-if="!streaming" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              <span v-else class="spinner small"></span>
              {{ streaming ? '测试中...' : '开始流式测试' }}
            </button>
          </div>
          <div class="panel-body stream-panel">
            <div class="stream-output" ref="streamOutput">
              <div v-for="(item, index) in streamResults" :key="index" :class="['stream-item', item.type]">
                <span class="stream-time">{{ item.time }}</span>
                <span class="stream-type">{{ item.type }}</span>
                <pre class="stream-content">{{ formatStreamItem(item) }}</pre>
              </div>
              <div v-if="streamResults.length === 0" class="empty-state">
                <p>点击"开始流式测试"查看 MCP 工具的流式调用效果</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Batch Test Results -->
      <div v-if="batchTestResults" class="batch-results-modal" @click.self="batchTestResults = null">
        <div class="modal-content">
          <div class="modal-header">
            <h3>批量测试结果</h3>
            <button class="close-btn" @click="batchTestResults = null">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <div :class="['summary', batchTestResults.success ? 'success' : 'partial']">
              {{ batchTestResults.summary }}
            </div>
            <div class="test-results-list">
              <div 
                v-for="(result, index) in batchTestResults.results" 
                :key="index"
                :class="['test-result-item', result.success ? 'success' : 'error']"
              >
                <span class="result-icon">
                  <svg v-if="result.success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                  </svg>
                </span>
                <span class="result-name">{{ result.tool || result.type }} {{ result.name || result.uri || '' }}</span>
                <span class="result-duration">{{ result.duration_ms }}ms</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { mcpTestApi } from '@/api'
import { message } from 'ant-design-vue'

// Tabs
const tabs = [
  { key: 'tools', label: '工具调用', icon: 'ToolIcon' },
  { key: 'resources', label: '资源读取', icon: 'FileIcon' },
  { key: 'prompts', label: '提示模板', icon: 'MessageIcon' },
  { key: 'stream', label: '流式测试', icon: 'StreamIcon' }
]
const activeTab = ref('tools')

// Tools
const tools = ref([])
const loadingTools = ref(false)
const selectedTool = ref(null)
const toolArgs = reactive({})
const callingTool = ref(false)
const toolResult = ref(null)
const lastCallDuration = ref(null)

// Resources
const resources = ref([])
const loadingResources = ref(false)
const loadingResource = ref(false)
const resourceContent = ref(null)

// Prompts
const prompts = ref([])
const loadingPrompts = ref(false)
const selectedPrompt = ref(null)
const promptArgs = reactive({})
const gettingPrompt = ref(false)
const promptResult = ref(null)

// Stream
const streaming = ref(false)
const streamResults = ref([])
const streamOutput = ref(null)

// Batch Test
const batchTesting = ref(false)
const batchTestResults = ref(null)

// Load functions
const loadTools = async () => {
  loadingTools.value = true
  try {
    const res = await mcpTestApi.getDemoTools()
    tools.value = res.tools || []
  } catch (e) {
    message.error('加载工具列表失败')
  } finally {
    loadingTools.value = false
  }
}

const loadResources = async () => {
  loadingResources.value = true
  try {
    const res = await mcpTestApi.getDemoResources()
    resources.value = res.resources || []
  } catch (e) {
    message.error('加载资源列表失败')
  } finally {
    loadingResources.value = false
  }
}

const loadPrompts = async () => {
  loadingPrompts.value = true
  try {
    const res = await mcpTestApi.getDemoPrompts()
    prompts.value = res.prompts || []
  } catch (e) {
    message.error('加载提示模板失败')
  } finally {
    loadingPrompts.value = false
  }
}

// Tool functions
const selectTool = (tool) => {
  selectedTool.value = tool
  // Reset args
  Object.keys(toolArgs).forEach(key => delete toolArgs[key])
  // Set default values
  const props = tool.inputSchema?.properties || {}
  Object.entries(props).forEach(([key, prop]) => {
    if (prop.default !== undefined) {
      toolArgs[key] = prop.default
    }
  })
}

const callTool = async () => {
  if (!selectedTool.value) return
  
  callingTool.value = true
  toolResult.value = null
  
  try {
    const res = await mcpTestApi.callDemoTool(selectedTool.value.name, toolArgs)
    toolResult.value = res
    lastCallDuration.value = res.duration_ms
    
    if (res.success) {
      message.success('工具执行成功')
    } else {
      message.error('工具执行失败: ' + (res.error || '未知错误'))
    }
  } catch (e) {
    toolResult.value = { success: false, error: e.message }
    message.error('调用失败: ' + e.message)
  } finally {
    callingTool.value = false
  }
}

// Resource functions
const readResource = async (resource) => {
  loadingResource.value = true
  resourceContent.value = null
  
  try {
    const res = await mcpTestApi.readDemoResource(resource.uri)
    if (res.success && res.data?.contents?.length > 0) {
      resourceContent.value = res.data.contents[0].text
    } else {
      resourceContent.value = res.error || '无法读取资源内容'
    }
  } catch (e) {
    resourceContent.value = '读取失败: ' + e.message
    message.error('读取资源失败')
  } finally {
    loadingResource.value = false
  }
}

// Prompt functions
const selectPrompt = (prompt) => {
  selectedPrompt.value = prompt
  promptResult.value = null
  // Reset args
  Object.keys(promptArgs).forEach(key => delete promptArgs[key])
}

const getPrompt = async () => {
  if (!selectedPrompt.value) return
  
  gettingPrompt.value = true
  promptResult.value = null
  
  try {
    const res = await mcpTestApi.getDemoPrompt(selectedPrompt.value.name, promptArgs)
    if (res.success) {
      promptResult.value = res.data
      message.success('获取提示成功')
    } else {
      message.error('获取提示失败: ' + (res.error || '未知错误'))
    }
  } catch (e) {
    message.error('获取失败: ' + e.message)
  } finally {
    gettingPrompt.value = false
  }
}

// Stream test
const runStreamTest = () => {
  streaming.value = true
  streamResults.value = []
  
  const stream = mcpTestApi.streamTest(
    (data) => {
      streamResults.value.push({
        ...data,
        time: new Date().toLocaleTimeString()
      })
      nextTick(() => {
        if (streamOutput.value) {
          streamOutput.value.scrollTop = streamOutput.value.scrollHeight
        }
      })
    },
    (data) => {
      streamResults.value.push({
        ...data,
        time: new Date().toLocaleTimeString()
      })
      streaming.value = false
      message.success('流式测试完成')
    },
    (error) => {
      streaming.value = false
      message.error('流式测试失败: ' + error)
    }
  )
}

// Batch test
const runBatchTest = async () => {
  batchTesting.value = true
  try {
    const res = await mcpTestApi.batchTest()
    batchTestResults.value = res
    if (res.success) {
      message.success('所有测试通过')
    } else {
      message.warning('部分测试未通过')
    }
  } catch (e) {
    message.error('批量测试失败: ' + e.message)
  } finally {
    batchTesting.value = false
  }
}

// Helpers
const formatJson = (obj) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

const formatStreamItem = (item) => {
  if (item.type === 'tool_result') {
    return formatJson(item.result)
  }
  return item.message || ''
}

// Init
onMounted(() => {
  loadTools()
  loadResources()
  loadPrompts()
})
</script>

<style lang="scss" scoped>
.mcp-test-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
}

.page-header {
  padding: 40px 48px 32px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  
  .title-group {
    h1 {
      font-size: 28px;
      font-weight: 700;
      color: #fff;
      margin: 0 0 8px 0;
      display: flex;
      align-items: center;
      gap: 14px;
      letter-spacing: -0.02em;
    }
    
    .icon-wrapper {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      
      svg {
        width: 24px;
        height: 24px;
        color: white;
      }
    }
    
    .subtitle {
      color: rgba(255, 255, 255, 0.5);
      font-size: 15px;
      margin: 0;
      padding-left: 58px;
    }
  }
}

.batch-test-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 24px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
}

.page-content {
  padding: 32px 48px;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.8);
  }
  
  &.active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-color: transparent;
  }
}

.panel-grid {
  display: grid;
  grid-template-columns: 300px 1fr 1fr;
  gap: 20px;
  
  &.two-cols {
    grid-template-columns: 1fr 1fr;
  }
}

.panel {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  overflow: hidden;
  
  &.full-width {
    grid-column: 1 / -1;
  }
  
  &.result-panel {
    .panel-body {
      max-height: 500px;
      overflow-y: auto;
    }
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  
  h3 {
    font-size: 15px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    margin: 0;
  }
}

.panel-body {
  padding: 16px 20px;
  min-height: 200px;
}

.refresh-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
    
    &.spinning {
      animation: spin 1s linear infinite;
    }
  }
  
  &:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: rgba(255, 255, 255, 0.4);
  gap: 12px;
}

.loader {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.tool-list, .resource-list, .prompt-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-item, .resource-item, .prompt-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(102, 126, 234, 0.3);
  }
  
  &.selected {
    background: rgba(102, 126, 234, 0.15);
    border-color: rgba(102, 126, 234, 0.5);
  }
}

.tool-icon, .resource-icon, .prompt-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(102, 126, 234, 0.15);
  border-radius: 8px;
  
  svg {
    width: 18px;
    height: 18px;
    color: #667eea;
  }
}

.tool-info, .resource-info, .prompt-info {
  flex: 1;
  min-width: 0;
  
  .tool-name, .resource-name, .prompt-name {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 2px;
  }
  
  .tool-desc, .resource-desc, .prompt-desc {
    display: block;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.4);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .resource-uri {
    display: block;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    color: rgba(102, 126, 234, 0.8);
    margin-bottom: 2px;
  }
}

.mime-badge {
  font-size: 10px;
  padding: 4px 8px;
  background: rgba(102, 126, 234, 0.15);
  color: #667eea;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.tool-call-form, .prompt-form {
  .selected-tool-info, .selected-prompt-info {
    margin-bottom: 20px;
    
    h4 {
      font-size: 16px;
      font-weight: 600;
      color: white;
      margin: 0 0 8px 0;
    }
    
    p {
      font-size: 13px;
      color: rgba(255, 255, 255, 0.5);
      margin: 0;
    }
  }
}

.args-form {
  margin-bottom: 20px;
  
  h5 {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.7);
    margin: 0 0 12px 0;
  }
}

.form-group {
  margin-bottom: 16px;
  
  label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 6px;
    
    .required {
      color: #ef4444;
      margin-left: 4px;
    }
  }
  
  input, textarea {
    width: 100%;
    padding: 10px 14px;
    font-size: 14px;
    color: white;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    outline: none;
    transition: all 0.2s;
    
    &::placeholder {
      color: rgba(255, 255, 255, 0.3);
    }
    
    &:focus {
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
    }
  }
  
  .field-hint {
    display: block;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.3);
    margin-top: 4px;
  }
}

.call-btn, .stream-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 44px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
}

.result-content {
  .result-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
    
    svg {
      width: 18px;
      height: 18px;
    }
    
    &.success {
      background: rgba(34, 197, 94, 0.15);
      color: #22c55e;
    }
    
    &.error {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
    }
  }
  
  .result-json {
    padding: 16px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.8);
    overflow-x: auto;
    white-space: pre-wrap;
    margin: 0;
  }
}

.resource-content, .prompt-result {
  pre {
    padding: 16px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.8);
    overflow-x: auto;
    white-space: pre-wrap;
    margin: 0;
  }
}

.prompt-result {
  margin-top: 20px;
  
  h5 {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.7);
    margin: 0 0 12px 0;
  }
}

.duration-badge {
  font-size: 12px;
  padding: 4px 10px;
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
}

.stream-panel {
  min-height: 400px;
}

.stream-output {
  height: 400px;
  overflow-y: auto;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.stream-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  border-left: 3px solid transparent;
  
  &.start {
    border-left-color: #3b82f6;
  }
  
  &.tool_result {
    border-left-color: #22c55e;
  }
  
  &.complete {
    border-left-color: #a855f7;
  }
  
  .stream-time {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.4);
    font-family: 'JetBrains Mono', monospace;
    min-width: 70px;
  }
  
  .stream-type {
    font-size: 11px;
    padding: 2px 8px;
    background: rgba(102, 126, 234, 0.2);
    color: #667eea;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    min-width: 80px;
    text-align: center;
  }
  
  .stream-content {
    flex: 1;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.8);
    font-family: 'JetBrains Mono', monospace;
    margin: 0;
    white-space: pre-wrap;
  }
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  
  &.small {
    width: 14px;
    height: 14px;
  }
}

// Batch Test Modal
.batch-results-modal {
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

.modal-content {
  width: 90%;
  max-width: 600px;
  background: #1a1a2e;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  
  h3 {
    font-size: 18px;
    font-weight: 600;
    color: white;
    margin: 0;
  }
}

.close-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: none;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }
}

.modal-body {
  padding: 24px;
}

.summary {
  padding: 16px 20px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 20px;
  
  &.success {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }
  
  &.partial {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
  }
}

.test-results-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.test-result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  
  .result-icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 18px;
      height: 18px;
    }
  }
  
  &.success .result-icon {
    color: #22c55e;
  }
  
  &.error .result-icon {
    color: #ef4444;
  }
  
  .result-name {
    flex: 1;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.8);
  }
  
  .result-duration {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.4);
    font-family: 'JetBrains Mono', monospace;
  }
}
</style>

