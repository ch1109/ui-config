<template>
  <div class="mcp-manager">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="title-group">
          <h1>
            <span class="icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/>
              </svg>
            </span>
            MCP 服务器管理
          </h1>
          <p class="subtitle">管理 Model Context Protocol 服务器，扩展 AI 模型能力</p>
        </div>
        <div class="header-actions">
          <button class="context-btn" @click="showContextPanel = !showContextPanel">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            {{ showContextPanel ? '隐藏' : '查看' }} MCP 上下文
          </button>
        </div>
      </div>
    </header>
    
    <!-- Context Panel (可折叠) -->
    <transition name="slide">
      <div v-if="showContextPanel" class="context-panel">
        <div class="context-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 16v-4M12 8h.01"/>
            </svg>
            MCP 上下文信息
          </h3>
          <div class="context-stats">
            <span class="stat">
              <strong>{{ mcpContext?.total_enabled_servers || 0 }}</strong> 个已启用服务器
            </span>
            <span class="stat">
              <strong>{{ mcpContext?.total_available_tools || 0 }}</strong> 个可用工具
            </span>
          </div>
        </div>
        <div class="context-body">
          <div class="context-section">
            <h4>系统提示词片段</h4>
            <p class="hint">此内容会自动注入到 AI 的系统提示词中，让 AI 知道有哪些 MCP 工具可用</p>
            <div class="prompt-preview">
              <pre>{{ mcpContext?.system_prompt_snippet || '暂无已启用的 MCP 服务器' }}</pre>
            </div>
            <button class="copy-btn" @click="copyPromptSnippet">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              复制
            </button>
          </div>
        </div>
      </div>
    </transition>
    
    <!-- Content -->
    <div class="page-content">
      <!-- Preset Servers -->
      <section class="section">
        <div class="section-header">
          <h2>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M12 1v6m0 6v10M4.22 4.22l4.24 4.24m7.08 7.08l4.24 4.24M1 12h6m6 0h10M4.22 19.78l4.24-4.24m7.08-7.08l4.24-4.24"/>
            </svg>
            预置服务器
          </h2>
        </div>
        
        <div class="server-grid">
          <article v-for="server in presetServers" :key="server.name" class="server-card" :class="{ running: isServerRunning(server) }">
            <div class="card-header">
              <div class="server-info">
                <div class="server-icon preset">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                    <path d="M8 21h8M12 17v4"/>
                  </svg>
                </div>
                <div class="server-details">
                  <h3>{{ server.name }}</h3>
                  <span class="server-transport">{{ server.transport === 'stdio' ? 'STDIO' : 'HTTP' }}</span>
                </div>
              </div>
              <label class="toggle-switch">
                <input 
                  type="checkbox" 
                  :checked="server.status === 'enabled' || server.status === 'running'"
                  @change="toggleServer(server)"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>
            
            <div class="card-body">
              <p class="server-desc">{{ server.description }}</p>
              <div class="server-tools">
                <span class="tools-label">工具:</span>
                <div class="tools-list">
                  <span v-for="tool in server.tools.slice(0, 4)" :key="tool" class="tool-tag">
                    {{ tool }}
                  </span>
                  <span v-if="server.tools.length > 4" class="tool-tag more">
                    +{{ server.tools.length - 4 }}
                  </span>
                </div>
              </div>
            </div>
            
            <div class="card-footer">
              <div class="footer-left">
                <span :class="['status-badge', getStatusClass(server)]">
                  <span class="status-dot"></span>
                  {{ getStatusLabel(server) }}
                </span>
              </div>
              <div class="footer-actions">
                <template v-if="server.transport === 'stdio'">
                  <button 
                    v-if="!isServerRunning(server)" 
                    class="action-btn start"
                    @click="startStdioServer(server)"
                    :disabled="startingServer === getServerKey(server)"
                  >
                    <span v-if="startingServer === getServerKey(server)" class="spinner"></span>
                    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    启动
                  </button>
                  <template v-else>
                    <button class="action-btn test" @click="openTestPanel(server)">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                      </svg>
                      测试
                    </button>
                    <button 
                      class="action-btn stop"
                      @click="stopStdioServer(server)"
                      :disabled="stoppingServer === getServerKey(server)"
                    >
                      <span v-if="stoppingServer === getServerKey(server)" class="spinner small"></span>
                      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="6" y="6" width="12" height="12"/>
                      </svg>
                    </button>
                  </template>
                </template>
                <button v-else class="action-btn test" @click="testConnection(server)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                  测试
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
      
      <!-- Custom Servers -->
      <section class="section">
        <div class="section-header">
          <h2>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
            </svg>
            自定义服务器
          </h2>
          <button class="add-server-btn" @click="showAddDialog = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
            添加服务器
          </button>
        </div>
        
        <div v-if="customServers.length === 0" class="empty-state">
          <div class="empty-illustration">
            <svg viewBox="0 0 200 200" fill="none">
              <circle cx="100" cy="100" r="80" fill="#f1f5f9"/>
              <rect x="65" y="60" width="70" height="50" rx="4" fill="#e2e8f0"/>
              <circle cx="80" cy="75" r="4" fill="#cbd5e1"/>
              <circle cx="95" cy="75" r="4" fill="#cbd5e1"/>
              <rect x="65" y="120" width="70" height="30" rx="4" fill="#e2e8f0"/>
              <circle cx="80" cy="135" r="4" fill="#cbd5e1"/>
              <circle cx="95" cy="135" r="4" fill="#cbd5e1"/>
              <circle cx="100" cy="100" r="15" fill="#6366f1" opacity="0.2"/>
              <path d="M95 100h10M100 95v10" stroke="#6366f1" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <h3>暂无自定义服务器</h3>
          <p>添加您自己的 MCP 服务器来扩展 AI 能力</p>
          <button class="add-btn-primary" @click="showAddDialog = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
            添加服务器
          </button>
        </div>
        
        <div v-else class="server-grid">
          <article v-for="server in customServers" :key="server.id" class="server-card custom" :class="{ running: isCustomServerRunning(server) }">
            <div class="card-header">
              <div class="server-info">
                <div class="server-icon" :class="server.transport === 'stdio' ? 'stdio' : 'custom'">
                  <svg v-if="server.transport === 'stdio'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                    <path d="M8 21h8M12 17v4"/>
                    <path d="M7 8l3 3-3 3M12 14h5"/>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                  </svg>
                </div>
                <div class="server-details">
                  <h3>{{ server.name }}</h3>
                  <span v-if="server.transport === 'stdio'" class="server-transport">STDIO</span>
                  <span v-else class="server-url">{{ server.server_url }}</span>
                </div>
              </div>
              <div class="card-actions">
                <button class="icon-btn" @click="editServer(server)" title="编辑">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="icon-btn danger" @click="deleteServer(server)" title="删除">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                  </svg>
                </button>
              </div>
            </div>
            
            <div class="card-body">
              <p v-if="server.description" class="server-desc">{{ server.description }}</p>
              <div v-if="server.transport === 'stdio'" class="server-command">
                <span class="command-label">命令:</span>
                <code>{{ server.command }} {{ (server.args || []).join(' ') }}</code>
              </div>
              <div class="server-tools" v-if="server.tools?.length">
                <span class="tools-label">工具:</span>
                <div class="tools-list">
                  <span v-for="tool in server.tools.slice(0, 4)" :key="tool" class="tool-tag">
                    {{ tool }}
                  </span>
                  <span v-if="server.tools.length > 4" class="tool-tag more">
                    +{{ server.tools.length - 4 }}
                  </span>
                </div>
              </div>
            </div>
            
            <div class="card-footer">
              <div class="footer-left">
                <span :class="['status-badge', getCustomStatusClass(server)]">
                  <span class="status-dot"></span>
                  {{ getCustomStatusLabel(server) }}
                </span>
                <span v-if="server.last_check" class="last-check">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 6v6l4 2"/>
                  </svg>
                  {{ formatTime(server.last_check) }}
                </span>
              </div>
              <div class="footer-actions">
                <template v-if="server.transport === 'stdio'">
                  <button 
                    v-if="!isCustomServerRunning(server)" 
                    class="action-btn start"
                    @click="startCustomStdioServer(server)"
                    :disabled="startingServer === getCustomServerKey(server)"
                  >
                    <span v-if="startingServer === getCustomServerKey(server)" class="spinner"></span>
                    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    启动
                  </button>
                  <template v-else>
                    <button class="action-btn test" @click="openCustomTestPanel(server)">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                      </svg>
                      测试
                    </button>
                    <button 
                      class="action-btn stop"
                      @click="stopCustomStdioServer(server)"
                      :disabled="stoppingServer === getCustomServerKey(server)"
                    >
                      <span v-if="stoppingServer === getCustomServerKey(server)" class="spinner small"></span>
                      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="6" y="6" width="12" height="12"/>
                      </svg>
                    </button>
                  </template>
                </template>
                <button v-else class="action-btn test" @click="testConnection(server)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                  测试
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
    
    <!-- Test Panel (Drawer) -->
    <transition name="drawer">
      <div v-if="testingServer" class="test-drawer">
        <div class="drawer-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
            </svg>
            {{ testingServer.name }} 工具测试
          </h3>
          <button class="close-btn" @click="testingServer = null">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        
        <div class="drawer-content">
          <!-- Tools List -->
          <div class="tools-section">
            <h4>可用工具</h4>
            <div v-if="loadingTools" class="loading-state">
              <div class="loader"></div>
              <span>加载工具列表...</span>
            </div>
            <div v-else-if="availableTools.length === 0" class="empty-state small">
              <p>暂无可用工具</p>
            </div>
            <div v-else class="tools-list-panel">
              <div 
                v-for="tool in availableTools" 
                :key="tool.name"
                :class="['tool-item', { selected: selectedTool?.name === tool.name }]"
                @click="selectTool(tool)"
              >
                <div class="tool-name">{{ tool.name }}</div>
                <div class="tool-desc">{{ tool.description || '无描述' }}</div>
              </div>
            </div>
          </div>
          
          <!-- Tool Call Form -->
          <div class="call-section" v-if="selectedTool">
            <h4>调用 {{ selectedTool.name }}</h4>
            <div class="form-fields">
              <div 
                v-for="(prop, propName) in selectedTool.inputSchema?.properties || {}"
                :key="propName"
                class="form-field"
              >
                <label>
                  {{ propName }}
                  <span v-if="selectedTool.inputSchema?.required?.includes(propName)" class="required">*</span>
                </label>
                <input 
                  v-if="prop.type === 'string'"
                  v-model="toolArgs[propName]"
                  type="text"
                  :placeholder="prop.description || `输入 ${propName}`"
                />
                <input 
                  v-else-if="prop.type === 'integer' || prop.type === 'number'"
                  v-model.number="toolArgs[propName]"
                  type="number"
                  :placeholder="prop.description || `输入 ${propName}`"
                />
                <textarea 
                  v-else
                  v-model="toolArgs[propName]"
                  :placeholder="prop.description || `输入 ${propName}`"
                  rows="2"
                ></textarea>
              </div>
            </div>
            <button class="call-btn" @click="callTool" :disabled="callingTool">
              <span v-if="callingTool" class="spinner small"></span>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              {{ callingTool ? '执行中...' : '执行工具' }}
            </button>
          </div>
          
          <!-- Result Display -->
          <div class="result-section" v-if="toolResult">
            <h4>
              执行结果
              <span v-if="toolResult.duration_ms" class="duration">{{ toolResult.duration_ms }}ms</span>
            </h4>
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
            <pre class="result-json">{{ formatJson(toolResult.data || toolResult.error) }}</pre>
          </div>
        </div>
      </div>
    </transition>
    
    <!-- Add/Edit Modal -->
    <a-modal
      v-model:open="showAddDialog"
      :title="editingServer ? '编辑服务器' : '添加 MCP 服务器'"
      width="640px"
      :footer="null"
      @cancel="closeDialog"
      class="server-modal"
    >
      <a-tabs v-model:activeKey="activeTab" class="modal-tabs">
        <a-tab-pane key="form" tab="表单配置">
          <div class="form-section">
            <!-- 传输类型选择 -->
            <div class="form-group">
              <label>传输类型 <span class="required">*</span></label>
              <div class="transport-selector">
                <label class="transport-option" :class="{ active: formData.transport === 'http' }">
                  <input type="radio" v-model="formData.transport" value="http" />
                  <div class="option-content">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="2" y1="12" x2="22" y2="12"/>
                      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                    </svg>
                    <span>HTTP/SSE</span>
                    <small>远程服务器</small>
                  </div>
                </label>
                <label class="transport-option" :class="{ active: formData.transport === 'stdio' }">
                  <input type="radio" v-model="formData.transport" value="stdio" />
                  <div class="option-content">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="2" y="3" width="20" height="14" rx="2"/>
                      <path d="M8 21h8M12 17v4"/>
                      <path d="M7 8l3 3-3 3M12 14h5"/>
                    </svg>
                    <span>STDIO</span>
                    <small>本地进程</small>
                  </div>
                </label>
              </div>
            </div>
            
            <div class="form-group">
              <label>服务器名称 <span class="required">*</span></label>
              <input v-model="formData.name" type="text" class="form-input" placeholder="My MCP Server" />
            </div>
            
            <!-- HTTP 类型字段 -->
            <template v-if="formData.transport === 'http'">
              <div class="form-group">
                <label>服务器 URL <span class="required">*</span></label>
                <input v-model="formData.server_url" type="text" class="form-input" placeholder="https://mcp.example.com" />
              </div>
              <div class="form-group">
                <label>健康检查路径</label>
                <input v-model="formData.health_check_path" type="text" class="form-input" placeholder="/health" />
              </div>
            </template>
            
            <!-- STDIO 类型字段 -->
            <template v-else>
              <div class="form-group">
                <label>启动命令 <span class="required">*</span></label>
                <input v-model="formData.command" type="text" class="form-input" placeholder="npx" />
                <p class="form-hint">常用命令：npx, node, python, uvx</p>
              </div>
              <div class="form-group">
                <label>命令参数</label>
                <input v-model="argsInput" type="text" class="form-input" placeholder="-y wttr-mcp-server@latest" />
                <p class="form-hint">空格分隔，例如：-y wttr-mcp-server@latest</p>
              </div>
              <div class="form-group">
                <label>环境变量</label>
                <textarea v-model="envInput" class="form-textarea" rows="3" placeholder="API_KEY=your_key&#10;OTHER_VAR=value"></textarea>
                <p class="form-hint">每行一个，格式：KEY=VALUE</p>
              </div>
            </template>
            
            <div class="form-group">
              <label>工具列表 (逗号分隔)</label>
              <input v-model="toolsInput" type="text" class="form-input" placeholder="search, retrieve, store" />
              <p class="form-hint">可选，服务器启动后会自动获取</p>
            </div>
            <div class="form-group">
              <label>描述</label>
              <textarea v-model="formData.description" class="form-textarea" rows="3" placeholder="服务器描述..."></textarea>
            </div>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="json" tab="JSON 编辑">
          <div class="json-editor-section">
            <textarea 
              v-model="jsonInput"
              class="json-editor"
              :class="{ error: jsonError }"
              rows="15"
              placeholder='{"name": "...", "server_url": "...", "tools": [...]}'
            ></textarea>
            <p v-if="jsonError" class="error-text">{{ jsonError }}</p>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="upload" tab="文件上传">
          <div class="upload-section">
            <label class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
              <input type="file" accept=".json" @change="handleFileSelect" hidden />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
              </svg>
              <p class="upload-title">点击或拖拽文件到此区域上传</p>
              <p class="upload-hint">支持 .json 格式，最大 1MB</p>
            </label>
          </div>
        </a-tab-pane>
      </a-tabs>
      
      <div class="modal-footer">
        <button class="modal-btn secondary" @click="closeDialog">取消</button>
        <button class="modal-btn primary" @click="saveServer" :disabled="isSaving">
          <span v-if="isSaving" class="btn-spinner"></span>
          {{ editingServer ? '保存' : '添加' }}
        </button>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, createVNode } from 'vue'
import { mcpApi, mcpTestApi, mcpContextApi } from '@/api'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

// State
const servers = ref([])
const showAddDialog = ref(false)
const activeTab = ref('form')
const editingServer = ref(null)
const isSaving = ref(false)
const jsonError = ref('')
const showContextPanel = ref(false)
const mcpContext = ref(null)

// Stdio server state
const stdioStatus = ref({})
const startingServer = ref(null)
const stoppingServer = ref(null)

// Test panel state
const testingServer = ref(null)
const loadingTools = ref(false)
const availableTools = ref([])
const selectedTool = ref(null)
const toolArgs = reactive({})
const callingTool = ref(false)
const toolResult = ref(null)

const formData = ref({
  name: '',
  transport: 'http',  // 'http' 或 'stdio'
  // HTTP 字段
  server_url: '',
  health_check_path: '/health',
  // STDIO 字段
  command: 'npx',
  args: [],
  env: {},
  // 通用字段
  description: '',
  tools: []
})
const argsInput = ref('')  // 用于输入 args（空格分隔）
const envInput = ref('')   // 用于输入 env（KEY=VALUE 格式，每行一个）
const toolsInput = ref('')
const jsonInput = ref('')

const presetServers = computed(() => servers.value.filter(s => s.is_preset))
const customServers = computed(() => servers.value.filter(s => !s.is_preset))

// Load data
onMounted(async () => {
  await Promise.all([
    loadServers(),
    loadStdioStatus(),
    loadMcpContext()
  ])
})

const loadServers = async () => {
  try {
    servers.value = await mcpApi.list()
  } catch (error) {
    console.error('Failed to load MCP servers:', error)
    message.error('加载服务器列表失败')
  }
}

const loadStdioStatus = async () => {
  try {
    const res = await mcpTestApi.getStdioStatus()
    stdioStatus.value = res.servers || {}
  } catch (error) {
    console.error('Failed to load stdio status:', error)
  }
}

const loadMcpContext = async () => {
  try {
    mcpContext.value = await mcpContextApi.getContext()
  } catch (error) {
    console.error('Failed to load MCP context:', error)
  }
}

// Helper functions
const getServerKey = (server) => {
  if (server.is_preset) {
    return server.name.toLowerCase().replace(/\s+/g, '')
  }
  return `custom_${server.id}`
}

const getCustomServerKey = (server) => {
  return `custom_${server.id}`
}

const isServerRunning = (server) => {
  if (server.transport !== 'stdio') return false
  const key = server.name === 'Context7' ? 'context7' : (server.name === 'Everything Server' ? 'everything' : (server.name === '和风天气' ? 'hefeng' : null))
  if (!key) return false
  return stdioStatus.value[key]?.running || false
}

const isCustomServerRunning = (server) => {
  if (server.transport !== 'stdio') return false
  const key = getCustomServerKey(server)
  return stdioStatus.value[key]?.running || false
}

const getStatusClass = (server) => {
  if (isServerRunning(server)) return 'running'
  if (server.status === 'enabled') return 'success'
  if (server.status === 'error') return 'error'
  return 'warning'
}

const getStatusLabel = (server) => {
  if (isServerRunning(server)) return '运行中'
  const map = {
    enabled: '已启用',
    disabled: '已禁用',
    error: '连接失败'
  }
  return map[server.status] || server.status
}

const getCustomStatusClass = (server) => {
  if (isCustomServerRunning(server)) return 'running'
  if (server.status === 'enabled') return 'success'
  if (server.status === 'error') return 'error'
  return 'warning'
}

const getCustomStatusLabel = (server) => {
  if (isCustomServerRunning(server)) return '运行中'
  if (server.transport === 'stdio') {
    const map = {
      enabled: '已配置',
      disabled: '未启动',
      error: '启动失败'
    }
    return map[server.status] || server.status
  }
  const map = {
    enabled: '已启用',
    disabled: '已禁用',
    error: '连接失败'
  }
  return map[server.status] || server.status
}

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

// Server operations
const toggleServer = async (server) => {
  try {
    // 使用后端返回的 preset_key，预置服务器都会有这个字段
    const key = server.preset_key
    if (!key) {
      message.error('无法识别服务器标识')
      return
    }
    const enable = server.status !== 'enabled'
    await mcpApi.toggle(key, enable)
    server.status = enable ? 'enabled' : 'disabled'
    message.success(enable ? '已启用' : '已禁用')
    await loadMcpContext()
  } catch (error) {
    console.error('Failed to toggle server:', error)
    message.error('切换状态失败')
  }
}

const startStdioServer = async (server) => {
  const key = server.name === 'Context7' ? 'context7' : (server.name === 'Everything Server' ? 'everything' : 'hefeng')
  startingServer.value = key
  
  try {
    const res = await mcpTestApi.startStdioServer(key)
    if (res.success) {
      message.success(`${server.name} 启动成功！`)
      await Promise.all([loadStdioStatus(), loadMcpContext()])
    } else {
      message.error('启动失败: ' + (res.message || '未知错误'))
    }
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message
    message.error('启动失败: ' + errorMsg)
  } finally {
    startingServer.value = null
  }
}

const stopStdioServer = async (server) => {
  const key = server.name === 'Context7' ? 'context7' : (server.name === 'Everything Server' ? 'everything' : 'hefeng')
  stoppingServer.value = key
  
  try {
    const res = await mcpTestApi.stopStdioServer(key)
    if (res.success) {
      message.success('服务器已停止')
      if (testingServer.value?.name === server.name) {
        testingServer.value = null
      }
      await Promise.all([loadStdioStatus(), loadMcpContext()])
    }
  } catch (error) {
    message.error('停止失败: ' + error.message)
  } finally {
    stoppingServer.value = null
  }
}

// 自定义 STDIO 服务器操作
const startCustomStdioServer = async (server) => {
  const key = getCustomServerKey(server)
  startingServer.value = key
  
  try {
    const res = await mcpTestApi.startStdioServer(key)
    if (res.success) {
      message.success(`${server.name} 启动成功！`)
      await Promise.all([loadStdioStatus(), loadMcpContext()])
    } else {
      message.error('启动失败: ' + (res.message || '未知错误'))
    }
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message
    message.error('启动失败: ' + errorMsg)
  } finally {
    startingServer.value = null
  }
}

const stopCustomStdioServer = async (server) => {
  const key = getCustomServerKey(server)
  stoppingServer.value = key
  
  try {
    const res = await mcpTestApi.stopStdioServer(key)
    if (res.success) {
      message.success('服务器已停止')
      if (testingServer.value?.id === server.id) {
        testingServer.value = null
      }
      await Promise.all([loadStdioStatus(), loadMcpContext()])
    }
  } catch (error) {
    message.error('停止失败: ' + error.message)
  } finally {
    stoppingServer.value = null
  }
}

const openCustomTestPanel = async (server) => {
  testingServer.value = server
  selectedTool.value = null
  toolResult.value = null
  Object.keys(toolArgs).forEach(key => delete toolArgs[key])
  
  loadingTools.value = true
  try {
    const key = getCustomServerKey(server)
    const res = await mcpTestApi.getStdioTools(key)
    availableTools.value = res.tools || []
  } catch (error) {
    message.error('加载工具列表失败: ' + error.message)
    availableTools.value = []
  } finally {
    loadingTools.value = false
  }
}

const testConnection = async (server) => {
  const hide = message.loading('正在测试连接...', 0)
  try {
    const result = await mcpApi.test(server.id || 0)
    hide()
    if (result.connectivity) {
      message.success('连接成功')
    } else {
      message.error('连接失败')
    }
  } catch (error) {
    hide()
    message.error('测试失败: ' + error.message)
  }
}

// Test panel functions
const openTestPanel = async (server) => {
  testingServer.value = server
  selectedTool.value = null
  toolResult.value = null
  Object.keys(toolArgs).forEach(key => delete toolArgs[key])
  
  loadingTools.value = true
  try {
    const key = server.name === 'Context7' ? 'context7' : (server.name === 'Everything Server' ? 'everything' : 'hefeng')
    const res = await mcpTestApi.getStdioTools(key)
    availableTools.value = res.tools || []
  } catch (error) {
    message.error('加载工具列表失败: ' + error.message)
    availableTools.value = []
  } finally {
    loadingTools.value = false
  }
}

const selectTool = (tool) => {
  selectedTool.value = tool
  toolResult.value = null
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
  if (!selectedTool.value || !testingServer.value) return
  
  callingTool.value = true
  toolResult.value = null
  
  try {
    // 判断是预置服务器还是自定义服务器
    let key
    if (testingServer.value.is_preset) {
      key = testingServer.value.name === 'Context7' ? 'context7' : (testingServer.value.name === 'Everything Server' ? 'everything' : 'hefeng')
    } else {
      key = getCustomServerKey(testingServer.value)
    }
    
    const res = await mcpTestApi.callStdioTool(key, selectedTool.value.name, { ...toolArgs })
    toolResult.value = res
    
    if (res.success) {
      message.success('工具执行成功')
    } else {
      message.error('工具执行失败: ' + (res.error || '未知错误'))
    }
  } catch (error) {
    toolResult.value = { success: false, error: error.message }
    message.error('调用失败: ' + error.message)
  } finally {
    callingTool.value = false
  }
}

const formatJson = (obj) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

// Context panel
const copyPromptSnippet = async () => {
  if (!mcpContext.value?.system_prompt_snippet) {
    message.warning('暂无内容可复制')
    return
  }
  
  try {
    await navigator.clipboard.writeText(mcpContext.value.system_prompt_snippet)
    message.success('已复制到剪贴板')
  } catch {
    message.error('复制失败')
  }
}

// Custom server CRUD
const editServer = (server) => {
  editingServer.value = server
  const transport = server.transport || 'http'
  formData.value = {
    name: server.name,
    transport: transport,
    server_url: server.server_url || '',
    health_check_path: server.health_check_path || '/health',
    command: server.command || 'npx',
    args: server.args || [],
    env: server.env || {},
    description: server.description || '',
    tools: server.tools || []
  }
  toolsInput.value = server.tools?.join(', ') || ''
  argsInput.value = (server.args || []).join(' ')
  envInput.value = Object.entries(server.env || {}).map(([k, v]) => `${k}=${v}`).join('\n')
  showAddDialog.value = true
}

const deleteServer = (server) => {
  Modal.confirm({
    title: '删除服务器',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要删除「${server.name}」吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await mcpApi.delete(server.id)
        servers.value = servers.value.filter(s => s.id !== server.id)
        message.success('删除成功')
        await loadMcpContext()
      } catch (error) {
        message.error('删除失败: ' + error.message)
      }
    }
  });
}

const handleFileSelect = async (e) => {
  const file = e.target.files[0]
  if (file) await processFile(file)
}

const handleDrop = async (e) => {
  const file = e.dataTransfer.files[0]
  if (file) await processFile(file)
}

const processFile = async (file) => {
  if (!file.name.endsWith('.json')) {
    message.error('仅支持 .json 文件')
    return
  }
  
  if (file.size > 1024 * 1024) {
    message.error('文件大小不能超过 1MB')
    return
  }
  
  const text = await file.text()
  try {
    const data = JSON.parse(text)
    formData.value = {
      name: data.name || '',
      server_url: data.server_url || '',
      health_check_path: data.health_check_path || '/health',
      description: data.description || '',
      tools: data.tools || []
    }
    toolsInput.value = data.tools?.join(', ') || ''
    jsonInput.value = text
    activeTab.value = 'form'
    jsonError.value = ''
    message.success('文件解析成功')
  } catch {
    message.error('无效的 JSON 格式')
  }
}

const closeDialog = () => {
  showAddDialog.value = false
  editingServer.value = null
  formData.value = {
    name: '',
    transport: 'http',
    server_url: '',
    health_check_path: '/health',
    command: 'npx',
    args: [],
    env: {},
    description: '',
    tools: []
  }
  argsInput.value = ''
  envInput.value = ''
  toolsInput.value = ''
  jsonInput.value = ''
  jsonError.value = ''
  activeTab.value = 'form'
}

const saveServer = async () => {
  if (activeTab.value === 'json') {
    try {
      const data = JSON.parse(jsonInput.value)
      formData.value = {
        name: data.name || '',
        transport: data.transport || 'http',
        server_url: data.server_url || '',
        health_check_path: data.health_check_path || '/health',
        command: data.command || 'npx',
        args: data.args || [],
        env: data.env || {},
        description: data.description || '',
        tools: data.tools || []
      }
      // 同步输入框
      argsInput.value = (data.args || []).join(' ')
      envInput.value = Object.entries(data.env || {}).map(([k, v]) => `${k}=${v}`).join('\n')
    } catch {
      jsonError.value = '无效的 JSON 格式'
      return
    }
  }
  
  // 处理工具列表
  if (toolsInput.value) {
    formData.value.tools = toolsInput.value.split(',').map(t => t.trim()).filter(Boolean)
  }
  
  // 处理 STDIO 参数
  if (formData.value.transport === 'stdio') {
    // 解析 args
    if (argsInput.value.trim()) {
      // 简单分割，支持引号包裹的参数
      formData.value.args = argsInput.value.trim().split(/\s+/)
    } else {
      formData.value.args = []
    }
    
    // 解析 env
    const envObj = {}
    if (envInput.value.trim()) {
      envInput.value.split('\n').forEach(line => {
        const trimmed = line.trim()
        if (trimmed && trimmed.includes('=')) {
          const idx = trimmed.indexOf('=')
          const key = trimmed.substring(0, idx).trim()
          const value = trimmed.substring(idx + 1).trim()
          if (key) {
            envObj[key] = value
          }
        }
      })
    }
    formData.value.env = envObj
  }
  
  // 验证必填字段
  if (!formData.value.name) {
    message.warning('请填写服务器名称')
    return
  }
  
  if (formData.value.transport === 'http' && !formData.value.server_url) {
    message.warning('HTTP 类型需要填写服务器 URL')
    return
  }
  
  if (formData.value.transport === 'stdio' && !formData.value.command) {
    message.warning('STDIO 类型需要填写启动命令')
    return
  }
  
  isSaving.value = true
  
  try {
    const configToSave = { ...formData.value }
    
    // 根据类型清理不需要的字段
    if (configToSave.transport === 'http') {
      delete configToSave.command
      delete configToSave.args
      delete configToSave.env
    } else {
      delete configToSave.server_url
      delete configToSave.health_check_path
    }
    
    if (editingServer.value) {
      await mcpApi.update(editingServer.value.id, configToSave)
    } else {
      const result = await mcpApi.addConfig(configToSave)
      if (result.transport === 'stdio') {
        message.success('STDIO 服务器已添加，可在列表中启动')
      }
    }
    
    servers.value = await mcpApi.list()
    closeDialog()
    message.success('保存成功')
    await loadMcpContext()
  } catch (error) {
    message.error('保存失败: ' + (error.response?.data?.detail || error.response?.data?.message || error.message))
  } finally {
    isSaving.value = false
  }
}
</script>

<style lang="scss" scoped>
.mcp-manager {
  min-height: 100vh;
  background: var(--bg-body);
}

.page-header {
  padding: 40px 48px 32px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-light);
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  
  .title-group {
    h1 {
      font-size: 28px;
      font-weight: 700;
      color: var(--text-heading);
      margin: 0 0 8px 0;
      display: flex;
      align-items: center;
      gap: 14px;
      letter-spacing: -0.02em;
    }
    
    .icon-wrapper {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, var(--primary-light) 0%, rgba(99, 102, 241, 0.05) 100%);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      
      svg {
        width: 24px;
        height: 24px;
        color: var(--primary);
      }
    }
    
    .subtitle {
      color: var(--text-muted);
      font-size: 15px;
      margin: 0;
      padding-left: 58px;
    }
  }
}

.context-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--primary);
  background: var(--primary-light);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: rgba(99, 102, 241, 0.15);
  }
}

// Context Panel
.context-panel {
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-light);
  
  .context-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 48px;
    border-bottom: 1px solid var(--border-light);
    
    h3 {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 600;
      color: var(--text-heading);
      margin: 0;
      
      svg {
        width: 20px;
        height: 20px;
        color: var(--primary);
      }
    }
    
    .context-stats {
      display: flex;
      gap: 24px;
      
      .stat {
        font-size: 14px;
        color: var(--text-secondary);
        
        strong {
          color: var(--primary);
          font-weight: 600;
        }
      }
    }
  }
  
  .context-body {
    padding: 24px 48px;
    
    .context-section {
      h4 {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-heading);
        margin: 0 0 8px 0;
      }
      
      .hint {
        font-size: 13px;
        color: var(--text-muted);
        margin: 0 0 16px 0;
      }
      
      .prompt-preview {
        background: var(--bg-subtle);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        max-height: 300px;
        overflow-y: auto;
        
        pre {
          margin: 0;
          font-family: var(--font-mono);
          font-size: 12px;
          line-height: 1.6;
          color: var(--text-primary);
          white-space: pre-wrap;
        }
      }
      
      .copy-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 12px;
        padding: 8px 16px;
        font-size: 13px;
        color: var(--text-secondary);
        background: var(--bg-subtle);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
        
        svg {
          width: 14px;
          height: 14px;
        }
        
        &:hover {
          border-color: var(--primary);
          color: var(--primary);
        }
      }
    }
  }
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.page-content {
  padding: 32px 48px;
  max-width: 1600px;
}

.section {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  
  h2 {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
    
    svg {
      width: 20px;
      height: 20px;
      color: var(--primary);
    }
  }
}

.add-server-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: var(--primary-hover);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }
}

.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 20px;
}

.server-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.2s;
  
  &:hover {
    box-shadow: var(--shadow-md);
    border-color: rgba(99, 102, 241, 0.2);
  }
  
  &.running {
    border-color: rgba(34, 197, 94, 0.4);
    box-shadow: 0 0 20px rgba(34, 197, 94, 0.1);
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid var(--border-light);
    background: linear-gradient(to bottom, var(--bg-elevated) 0%, var(--bg-subtle) 100%);
  }
  
  .server-info {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  
  .server-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 22px;
      height: 22px;
    }
    
    &.preset {
      background: linear-gradient(135deg, var(--primary-light) 0%, rgba(99, 102, 241, 0.2) 100%);
      color: var(--primary);
    }
    
    &.custom {
      background: linear-gradient(135deg, var(--accent-light) 0%, rgba(245, 158, 11, 0.2) 100%);
      color: var(--accent);
    }
  }
  
  .server-details {
    h3 {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-heading);
      margin: 0 0 4px 0;
    }
    
    .server-url, .server-transport {
      font-size: 12px;
      font-family: var(--font-mono);
      color: var(--text-muted);
    }
    
    .server-transport {
      padding: 2px 8px;
      background: var(--bg-subtle);
      border-radius: 4px;
    }
  }
  
  .card-body {
    padding: 20px;
  }
  
  .server-desc {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0 0 16px 0;
  }
  
  .server-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    
    .tools-label {
      font-size: 12px;
      color: var(--text-muted);
    }
    
    .tools-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    
    .tool-tag {
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 500;
      color: var(--primary);
      background: var(--primary-light);
      border-radius: 20px;
      
      &.more {
        background: var(--bg-subtle);
        color: var(--text-muted);
      }
    }
  }
  
  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-top: 1px solid var(--border-light);
    background: var(--bg-subtle);
    
    .footer-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    
    .footer-actions {
      display: flex;
      gap: 8px;
    }
  }
  
  .card-actions {
    display: flex;
    gap: 8px;
  }
}

.toggle-switch {
  position: relative;
  width: 48px;
  height: 26px;
  
  input {
    opacity: 0;
    width: 0;
    height: 0;
    
    &:checked + .toggle-slider {
      background: var(--primary);
      
      &::before {
        transform: translateX(22px);
      }
    }
  }
  
  .toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--border-color);
    border-radius: 26px;
    transition: all 0.2s;
    
    &::before {
      content: '';
      position: absolute;
      height: 20px;
      width: 20px;
      left: 3px;
      bottom: 3px;
      background: white;
      border-radius: 50%;
      transition: transform 0.2s;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
  }
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  &.start {
    background: var(--success);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--success-hover);
    }
  }
  
  &.test {
    background: var(--primary);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--primary-hover);
    }
  }
  
  &.stop {
    width: 36px;
    padding: 0;
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
    border: 1px solid rgba(239, 68, 68, 0.3);
    
    &:hover:not(:disabled) {
      background: rgba(239, 68, 68, 0.2);
    }
  }
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-subtle);
  border: none;
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    background: var(--primary-light);
    color: var(--primary);
  }
  
  &.danger:hover {
    background: var(--error-light);
    color: var(--error);
  }
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  
  &.success {
    color: var(--success);
    .status-dot { background: var(--success); }
  }
  
  &.running {
    color: var(--success);
    .status-dot { 
      background: var(--success);
      animation: pulse 2s infinite;
    }
  }
  
  &.warning {
    color: #b45309;
    .status-dot { background: var(--warning); }
  }
  
  &.error {
    color: var(--error);
    .status-dot { background: var(--error); }
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.last-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
  
  svg {
    width: 12px;
    height: 12px;
  }
}

.empty-state {
  text-align: center;
  padding: 60px 24px;
  background: var(--bg-elevated);
  border: 2px dashed var(--border-color);
  border-radius: 16px;
  
  &.small {
    padding: 30px 16px;
    border: none;
    background: transparent;
  }
  
  .empty-illustration {
    margin-bottom: 20px;
    
    svg {
      width: 160px;
      height: 160px;
    }
  }
  
  h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-heading);
    margin-bottom: 8px;
  }
  
  p {
    font-size: 14px;
    color: var(--text-muted);
    margin-bottom: 24px;
  }
}

.add-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 24px;
  font-size: 15px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
  
  svg {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: var(--primary-hover);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
  }
}

// Test Drawer
.test-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 560px;
  height: 100vh;
  background: var(--bg-elevated);
  border-left: 1px solid var(--border-light);
  box-shadow: -10px 0 40px rgba(0, 0, 0, 0.1);
  z-index: 100;
  display: flex;
  flex-direction: column;
  
  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-light);
    
    h3 {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 600;
      color: var(--text-heading);
      margin: 0;
      
      svg {
        width: 20px;
        height: 20px;
        color: var(--primary);
      }
    }
    
    .close-btn {
      width: 36px;
      height: 36px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-subtle);
      border: none;
      border-radius: 8px;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s;
      
      svg {
        width: 18px;
        height: 18px;
      }
      
      &:hover {
        background: var(--error-light);
        color: var(--error);
      }
    }
  }
  
  .drawer-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
}

.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.3s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
}

.tools-section, .call-section, .result-section {
  h4 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0 0 12px 0;
    display: flex;
    align-items: center;
    gap: 8px;
    
    .duration {
      font-size: 12px;
      padding: 2px 8px;
      background: rgba(34, 197, 94, 0.1);
      color: var(--success);
      border-radius: 4px;
      font-family: var(--font-mono);
    }
  }
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 16px;
  color: var(--text-muted);
  gap: 12px;
}

.loader {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tools-list-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.tool-item {
  padding: 12px 16px;
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: var(--bg-elevated);
    border-color: rgba(99, 102, 241, 0.3);
  }
  
  &.selected {
    background: var(--primary-light);
    border-color: var(--primary);
  }
  
  .tool-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-heading);
    margin-bottom: 4px;
  }
  
  .tool-desc {
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 16px;
}

.form-field {
  label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 6px;
    
    .required {
      color: var(--error);
      margin-left: 4px;
    }
  }
  
  input, textarea {
    width: 100%;
    padding: 10px 14px;
    font-size: 14px;
    color: var(--text-primary);
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    outline: none;
    transition: all 0.2s;
    
    &::placeholder {
      color: var(--text-muted);
    }
    
    &:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-light);
    }
  }
}

.call-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 42px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover:not(:disabled) {
    background: var(--primary-hover);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.result-section {
  .result-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 12px;
    
    svg {
      width: 18px;
      height: 18px;
    }
    
    &.success {
      background: rgba(34, 197, 94, 0.1);
      color: var(--success);
    }
    
    &.error {
      background: rgba(239, 68, 68, 0.1);
      color: var(--error);
    }
  }
  
  .result-json {
    padding: 16px;
    background: var(--bg-subtle);
    border-radius: 8px;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-primary);
    overflow-x: auto;
    white-space: pre-wrap;
    margin: 0;
    max-height: 300px;
    overflow-y: auto;
  }
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  
  &.small {
    width: 12px;
    height: 12px;
  }
}

// Modal Styles
:deep(.server-modal) {
  .ant-modal-content {
    border-radius: 20px;
  }
  
  .ant-modal-header {
    padding: 24px 24px 16px;
    border-bottom: none;
  }
  
  .ant-modal-body {
    padding: 0 24px 24px;
  }
}

.modal-tabs {
  :deep(.ant-tabs-nav) {
    margin-bottom: 20px;
  }
}

// Transport selector
.transport-selector {
  display: flex;
  gap: 12px;
  
  .transport-option {
    flex: 1;
    position: relative;
    cursor: pointer;
    
    input {
      position: absolute;
      opacity: 0;
      width: 0;
      height: 0;
    }
    
    .option-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 16px 12px;
      background: var(--bg-subtle);
      border: 2px solid var(--border-color);
      border-radius: 12px;
      transition: all 0.2s;
      
      svg {
        width: 28px;
        height: 28px;
        color: var(--text-muted);
      }
      
      span {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-secondary);
      }
      
      small {
        font-size: 11px;
        color: var(--text-muted);
      }
    }
    
    &:hover .option-content {
      border-color: rgba(99, 102, 241, 0.3);
    }
    
    &.active .option-content {
      background: var(--primary-light);
      border-color: var(--primary);
      
      svg {
        color: var(--primary);
      }
      
      span {
        color: var(--primary);
      }
    }
  }
}

.form-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 6px 0 0 0;
}

.server-command {
  margin-bottom: 12px;
  
  .command-label {
    font-size: 12px;
    color: var(--text-muted);
    margin-right: 8px;
  }
  
  code {
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 4px 8px;
    background: var(--bg-subtle);
    border-radius: 4px;
    color: var(--text-secondary);
    word-break: break-all;
  }
}

.server-icon.stdio {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.2) 100%);
  color: var(--success);
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 8px;
    
    .required {
      color: var(--error);
    }
  }
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 14px;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  outline: none;
  transition: all 0.2s;
  
  &::placeholder {
    color: var(--text-muted);
  }
  
  &:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-light);
    background: var(--bg-elevated);
  }
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.json-editor-section {
  .json-editor {
    width: 100%;
    padding: 16px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
    color: var(--text-primary);
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    outline: none;
    resize: vertical;
    transition: all 0.2s;
    
    &:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-light);
    }
    
    &.error {
      border-color: var(--error);
    }
  }
  
  .error-text {
    margin-top: 8px;
    font-size: 13px;
    color: var(--error);
  }
}

.upload-section {
  .upload-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    background: var(--bg-subtle);
    border: 2px dashed var(--border-color);
    border-radius: 16px;
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover {
      border-color: var(--primary);
      background: var(--primary-light);
    }
    
    svg {
      width: 48px;
      height: 48px;
      color: var(--text-muted);
      margin-bottom: 16px;
    }
    
    .upload-title {
      font-size: 15px;
      font-weight: 500;
      color: var(--text-secondary);
      margin-bottom: 4px;
    }
    
    .upload-hint {
      font-size: 13px;
      color: var(--text-muted);
    }
  }
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-light);
}

.modal-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 24px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  
  &.secondary {
    background: var(--bg-subtle);
    color: var(--text-secondary);
    
    &:hover {
      background: var(--border-color);
    }
  }
  
  &.primary {
    background: var(--primary);
    color: white;
    
    &:hover:not(:disabled) {
      background: var(--primary-hover);
    }
    
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
</style>
