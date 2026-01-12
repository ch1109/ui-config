# MCP (Model Context Protocol) 功能文档

> **版本**: v1.0.0  
> **更新日期**: 2026-01-12  
> **适用对象**: 产品经理、技术开发人员

---

## 目录

1. [产品概述](#1-产品概述)
2. [核心概念](#2-核心概念)
3. [功能模块](#3-功能模块)
4. [API 接口文档](#4-api-接口文档)
5. [使用流程](#5-使用流程)
6. [技术架构](#6-技术架构)
7. [快速接入指南](#7-快速接入指南)
8. [预置服务器](#8-预置服务器)
9. [常见问题](#9-常见问题)

---

## 1. 产品概述

### 1.1 什么是 MCP？

**MCP (Model Context Protocol)** 是 Anthropic 发布的开放标准协议，用于连接 AI 模型与外部工具/服务。通过 MCP，AI 可以：

- 🔧 **调用工具**: 执行搜索、计算、API 调用等操作
- 📦 **访问资源**: 读取文件、数据库、配置等
- 📝 **使用提示模板**: 调用预定义的提示词模板

### 1.2 本系统 MCP 功能架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ MCP 服务器  │  │  MCP Host   │  │     MCP 测试页面        │ │
│  │   管理页    │  │   对话页    │  │   (工具测试/调试)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        后端服务层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ MCP 管理    │  │  MCP Host   │  │   ReAct 引擎            │ │
│  │   API       │  │   Service   │  │   (推理-行动循环)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Stdio MCP   │  │  SSE MCP    │  │   人机回环服务           │ │
│  │   Manager   │  │   Client    │  │   (Human-in-the-Loop)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      外部 MCP 服务器                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Context7   │  │ Everything  │  │     和风天气             │ │
│  │  (文档搜索) │  │  (测试服务) │  │   (天气查询)            │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 核心价值

| 价值点 | 描述 |
|--------|------|
| **能力扩展** | 让 AI 能够执行实际操作，而不仅仅是文本生成 |
| **安全可控** | 高风险操作需要人工确认，防止 AI 误操作 |
| **灵活接入** | 支持预置服务器和自定义服务器，满足不同场景 |
| **标准协议** | 遵循 MCP 开放标准，兼容生态内所有服务 |

---

## 2. 核心概念

### 2.1 关键术语

| 术语 | 英文 | 说明 |
|------|------|------|
| **MCP Server** | MCP 服务器 | 提供工具、资源、提示模板的服务端 |
| **MCP Client** | MCP 客户端 | 连接和调用 MCP Server 的客户端 |
| **MCP Host** | MCP 宿主 | 管理多个 MCP Server 并与 LLM 交互的中间层 |
| **Tool** | 工具 | MCP Server 提供的可执行功能 |
| **Resource** | 资源 | MCP Server 提供的可读取数据 |
| **Prompt** | 提示模板 | MCP Server 提供的预定义提示词 |
| **ReAct 循环** | 推理-行动循环 | LLM 推理 → 调用工具 → 获取结果 → 继续推理的循环 |
| **人机回环** | Human-in-the-Loop | 高风险操作需要人工确认的安全机制 |

### 2.2 传输协议

本系统支持两种 MCP 传输协议：

#### STDIO (标准输入输出)

```
后端 ←────────→ 子进程 (MCP Server)
      stdin/stdout
```

- **适用场景**: 本地运行的 MCP 服务器
- **启动方式**: `npx -y package-name` 或 `node script.js`
- **优点**: 无网络延迟，适合本地工具
- **代表服务**: Context7, Everything Server, 和风天气

#### SSE (Server-Sent Events)

```
后端 ←────────→ 远程服务器
      HTTP/SSE
```

- **适用场景**: 远程部署的 MCP 服务器
- **连接方式**: HTTP URL + SSE 端点
- **优点**: 支持远程服务，可跨网络调用
- **代表服务**: 自定义 HTTP 服务器

### 2.3 风险等级

| 等级 | 英文 | 说明 | 是否需确认 |
|------|------|------|------------|
| 🟢 LOW | 低风险 | 只读操作，如查询、搜索 | ❌ |
| 🟡 MEDIUM | 中等风险 | 可能访问敏感数据 | ❌ |
| 🟠 HIGH | 高风险 | 会修改数据或产生副作用 | ✅ |
| 🔴 CRITICAL | 极高风险 | 危险操作，如删除、执行命令 | ✅ 二次确认 |

---

## 3. 功能模块

### 3.1 MCP 服务器管理 (`/mcp`)

**用途**: 管理系统中的 MCP 服务器配置

#### 功能列表

| 功能 | 说明 | 入口 |
|------|------|------|
| 查看预置服务器 | 显示系统内置的 MCP 服务器 | 预置服务器列表 |
| 启用/禁用服务器 | 切换服务器的启用状态 | 开关按钮 |
| 启动 STDIO 服务器 | 启动本地 MCP 进程 | "启动"按钮 |
| 测试工具调用 | 在侧边面板测试工具 | "测试"按钮 |
| 添加自定义服务器 | 配置自己的 MCP 服务器 | "添加服务器"按钮 |
| 查看 MCP 上下文 | 查看注入到系统提示词的内容 | "查看 MCP 上下文" |

#### 使用流程

```
1. 进入 MCP 服务器管理页面
2. 选择预置服务器或添加自定义服务器
3. 点击"启动"按钮启动 STDIO 服务器
4. 等待服务器初始化完成（显示工具数量）
5. 点击"测试"按钮验证工具调用
6. 服务器运行后，其工具可在 MCP Host 中使用
```

#### 截图功能说明

**预置服务器卡片**:
- 显示服务器名称、描述、传输类型
- 显示可用工具列表
- 状态指示：已禁用/已启用/运行中
- 操作按钮：启动/停止/测试

**添加服务器弹窗**:
- 传输类型选择：HTTP/SSE 或 STDIO
- HTTP 类型：填写 URL、健康检查路径
- STDIO 类型：填写命令、参数、环境变量
- 支持 JSON 编辑和文件上传

---

### 3.2 MCP Host 对话 (`/mcp-host`)

**用途**: 与 AI 进行对话，AI 可自动调用 MCP 工具

#### 功能列表

| 功能 | 说明 |
|------|------|
| AI 对话 | 发送消息与 AI 交互 |
| 工具调用 | AI 自动识别并调用 MCP 工具 |
| 人机回环 | 高风险操作弹出确认框 |
| 工具调用展示 | 显示调用的工具、参数、结果 |
| 审计日志 | 查看历史确认/拒绝记录 |

#### ReAct 循环流程

```
用户输入 "帮我查询北京的天气"
         │
         ▼
    ┌─────────────┐
    │  LLM 推理   │ ← 分析用户意图
    └─────────────┘
         │
         ▼ 需要调用工具
    ┌─────────────┐
    │ 准备工具调用 │ ← 评估风险等级
    └─────────────┘
         │
         ├── 低风险 ──→ 直接执行
         │
         └── 高风险 ──→ 请求确认 ──→ 用户确认/拒绝
                                          │
                                          ▼
    ┌─────────────┐                  ┌─────────────┐
    │  执行工具   │ ←─────────────── │ 执行/跳过   │
    └─────────────┘                  └─────────────┘
         │
         ▼
    ┌─────────────┐
    │  返回结果   │ ← 工具执行结果
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │ LLM 生成回复│ ← 基于结果生成最终回复
    └─────────────┘
         │
         ▼
    显示给用户
```

#### 使用示例

**用户**: 帮我查询北京的天气

**AI 执行流程**:
1. 调用 `hefeng__get_location_id` 获取北京的位置 ID
2. 调用 `hefeng__get_weather` 获取实时天气
3. 整合结果生成友好回复

**AI 回复**:
> 根据查询结果，北京当前的天气情况如下：
> - 天气: 晴
> - 温度: 3°C
> - 体感温度: 1°C
> - 风向: 西南风 2级
> - 湿度: 19%
> 
> 今天北京天气晴朗，建议您注意保暖。

---

### 3.3 MCP 测试功能 (`/mcp-test` API)

**用途**: 开发调试时测试 MCP 功能

#### 功能列表

| 功能 | API 端点 | 说明 |
|------|----------|------|
| 内置演示服务器测试 | `/api/v1/mcp-test/demo/*` | 测试内置的演示工具 |
| STDIO 服务器状态 | `/api/v1/mcp-test/stdio/status` | 查看所有 STDIO 服务器状态 |
| 启动 STDIO 服务器 | `/api/v1/mcp-test/stdio/start` | 启动预置或自定义服务器 |
| 停止 STDIO 服务器 | `/api/v1/mcp-test/stdio/stop` | 停止运行中的服务器 |
| 获取工具列表 | `/api/v1/mcp-test/stdio/{key}/tools` | 获取服务器提供的工具 |
| 调用工具 | `/api/v1/mcp-test/stdio/tools/call` | 直接调用指定工具 |
| 批量测试 | `/api/v1/mcp-test/stdio/{key}/batch-test` | 批量测试服务器所有工具 |

---

## 4. API 接口文档

### 4.1 MCP 服务器管理 API

#### 获取服务器列表

```http
GET /api/v1/mcp
```

**响应示例**:
```json
[
  {
    "id": -1,
    "name": "Context7",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp@latest"],
    "status": "disabled",
    "tools": ["resolve-library-id", "get-library-docs"],
    "is_preset": true,
    "description": "官方文档搜索 MCP 服务器"
  }
]
```

#### 启用/禁用预置服务器

```http
POST /api/v1/mcp/{preset_key}/toggle?enable=true
```

**参数**:
- `preset_key`: 预置服务器标识 (context7, everything, hefeng, wttr)
- `enable`: true 启用 / false 禁用

#### 添加自定义服务器

```http
POST /api/v1/mcp/config
Content-Type: application/json

{
  "name": "我的 MCP 服务器",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "my-mcp-server"],
  "env": {
    "API_KEY": "xxx"
  },
  "tools": ["tool1", "tool2"],
  "description": "自定义服务器描述"
}
```

---

### 4.2 MCP Host API

#### 获取服务器状态

```http
GET /api/v1/host/servers
```

**响应示例**:
```json
{
  "stdio_servers": {
    "hefeng": {
      "running": true,
      "initialized": true,
      "tools_count": 3,
      "resources_count": 0,
      "prompts_count": 0,
      "server_info": {
        "name": "hefeng-mcp-server",
        "version": "1.7.0"
      }
    }
  },
  "sse_servers": {},
  "total_stdio": 1,
  "total_sse": 0
}
```

#### 启动 STDIO 服务器

```http
POST /api/v1/host/servers/stdio/{server_key}/start
    ?command=npx
    &args=-y
    &args=hefeng-mcp-server
    &args=--apiKey=YOUR_KEY
    &args=--apiUrl=https://api.example.com
```

**参数**:
- `server_key`: 服务器标识
- `command`: 启动命令 (npx, node, python 等)
- `args`: 命令参数 (可多个)

#### 停止 STDIO 服务器

```http
POST /api/v1/host/servers/stdio/{server_key}/stop
```

#### 创建会话

```http
POST /api/v1/host/sessions
Content-Type: application/json

{
  "session_id": "optional-custom-id",
  "system_prompt": "你是一个有帮助的助手"
}
```

#### 发送消息（流式响应）

```http
POST /api/v1/host/sessions/{session_id}/chat
Content-Type: application/json

{
  "message": "帮我查询北京的天气",
  "llm_provider": "zhipu",
  "llm_model": "glm-4",
  "api_key": "YOUR_API_KEY",
  "stream": true
}
```

**流式事件类型**:
```json
// 状态更新
{"type": "state", "state": "reasoning", "message": "正在分析请求..."}

// 工具调用准备
{"type": "tool_call", "tool": "hefeng__get_weather", "arguments": {...}, "state": "preparing"}

// 工具执行结果
{"type": "tool_result", "tool": "hefeng__get_weather", "success": true, "result": {...}}

// 需要确认（高风险操作）
{"type": "confirmation_required", "request_id": "xxx", "tool": "xxx", "risk_level": "high"}

// 最终回复
{"type": "final", "content": "根据查询结果，北京当前天气..."}
```

#### 确认工具调用

```http
POST /api/v1/host/sessions/{session_id}/confirmations/{request_id}
Content-Type: application/json

{
  "approved": true,
  "modified_arguments": null,
  "reason": null
}
```

#### 获取聚合工具列表

```http
GET /api/v1/host/tools
```

**响应示例**:
```json
{
  "count": 3,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "hefeng__get_location_id",
        "description": "[hefeng] 获取城市的位置 ID",
        "parameters": {
          "type": "object",
          "properties": {
            "city_name": {"type": "string", "description": "城市名称"}
          },
          "required": ["city_name"]
        }
      }
    }
  ]
}
```

#### 获取/更新风险策略

```http
GET /api/v1/host/policy

PUT /api/v1/host/policy
    ?confirmation_levels=high
    &confirmation_levels=critical
    &confirmation_timeout=300
    &allow_modification=true
```

#### 获取审计日志

```http
GET /api/v1/host/audit-log?session_id=xxx&limit=100
```

---

### 4.3 MCP 测试 API

#### 获取 STDIO 服务器状态

```http
GET /api/v1/mcp-test/stdio/status
```

**响应示例**:
```json
{
  "success": true,
  "servers": {
    "hefeng": {
      "running": true,
      "initialized": true,
      "tools_count": 3
    }
  },
  "available_presets": ["context7", "everything", "wttr", "hefeng"]
}
```

#### 启动预置服务器

```http
POST /api/v1/mcp-test/stdio/start
Content-Type: application/json

{
  "server_key": "hefeng"
}
```

#### 调用 STDIO 工具

```http
POST /api/v1/mcp-test/stdio/tools/call
Content-Type: application/json

{
  "server_key": "hefeng",
  "tool_name": "get_weather",
  "arguments": {
    "location": "101010100",
    "days": "now"
  }
}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "content": [
      {
        "type": "text",
        "text": "地点: 101010100\n观测时间: 2026-01-12T16:48+08:00\n天气: 晴\n温度: 3°C..."
      }
    ]
  },
  "duration_ms": 245.32
}
```

---

## 5. 使用流程

### 5.1 产品经理使用流程

#### 场景 1: 启用天气查询功能

```
1. 打开 MCP 服务器管理页面
2. 找到"和风天气"预置服务器
3. 点击"启动"按钮
4. 等待状态变为"运行中"
5. 打开 MCP Host 对话页面
6. 输入"帮我查询北京的天气"
7. 查看 AI 返回的实时天气数据
```

#### 场景 2: 测试高风险操作确认

```
1. 启动支持写操作的 MCP 服务器
2. 在 MCP Host 发送可能触发写操作的请求
3. 系统弹出确认框，显示：
   - 工具名称
   - 调用参数
   - 风险等级
   - 风险描述
4. 选择"确认执行"或"拒绝"
5. 确认后 AI 继续执行
```

### 5.2 技术人员使用流程

#### 场景: 接入自定义 MCP 服务器

```bash
# 1. 启动你的 MCP 服务器（假设是 node 服务）
node my-mcp-server.js

# 2. 通过 API 添加服务器配置
curl -X POST "http://localhost:8000/api/v1/mcp/config" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的 MCP 服务器",
    "transport": "stdio",
    "command": "node",
    "args": ["my-mcp-server.js"],
    "tools": ["my_tool_1", "my_tool_2"]
  }'

# 3. 启动服务器
curl -X POST "http://localhost:8000/api/v1/mcp-test/stdio/start" \
  -H "Content-Type: application/json" \
  -d '{"server_key": "custom_1"}'

# 4. 测试工具调用
curl -X POST "http://localhost:8000/api/v1/mcp-test/stdio/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "server_key": "custom_1",
    "tool_name": "my_tool_1",
    "arguments": {"param1": "value1"}
  }'
```

---

## 6. 技术架构

### 6.1 后端架构

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── mcp.py              # MCP 服务器管理 API
│   │   ├── mcp_host.py         # MCP Host API (对话、确认)
│   │   ├── mcp_test.py         # MCP 测试 API
│   │   └── mcp_context.py      # MCP 上下文 API
│   ├── services/
│   │   ├── stdio_mcp_manager.py   # STDIO 服务器管理
│   │   ├── sse_mcp_client.py      # SSE 客户端
│   │   ├── mcp_host_service.py    # Host 核心服务
│   │   ├── react_engine.py        # ReAct 循环引擎
│   │   ├── human_in_loop.py       # 人机回环服务
│   │   └── mcp_tools_service.py   # 工具管理服务
│   └── models/
│       └── mcp_server.py       # MCP 服务器数据模型
└── requirements.txt
```

### 6.2 前端架构

```
frontend/src/
├── views/
│   ├── MCPManager.vue          # MCP 服务器管理页面
│   ├── MCPHostPage.vue         # MCP Host 对话页面
│   └── MCPTestPage.vue         # MCP 测试页面
├── components/
│   ├── MCPHost/
│   │   ├── ChatPanel.vue       # 对话面板组件
│   │   └── ConfirmationModal.vue  # 确认弹窗组件
│   └── MCPManager/
│       └── ...
└── api/
    └── index.js                # API 调用封装
```

### 6.3 核心类说明

#### StdioMCPManager

```python
class StdioMCPManager:
    """
    管理通过 stdio 传输协议运行的 MCP 服务器
    
    职责:
    - 启动/停止 MCP 服务器进程
    - 发送 JSON-RPC 请求
    - 管理会话状态
    """
    
    async def start_server(server_key, command, args, env, timeout)
    async def stop_server(server_key)
    async def list_tools(server_key)
    async def call_tool(server_key, tool_name, arguments)
    async def list_resources(server_key)
    async def read_resource(server_key, uri)
```

#### MCPHostService

```python
class MCPHostService:
    """
    MCP Host 核心服务
    
    职责:
    - 聚合多个 MCP Server 的工具
    - 评估工具调用风险
    - 管理人机回环确认
    - 执行工具调用
    """
    
    def assess_tool_risk(tool_name, arguments) -> ToolRiskLevel
    async def get_aggregated_tools() -> List[Dict]
    async def prepare_tool_call(session_id, tool_name, arguments)
    async def execute_tool_call(request, force=False)
    async def confirm_tool_call(session_id, request_id, approved)
```

#### ReActEngine

```python
class ReActEngine:
    """
    ReAct 循环引擎
    
    职责:
    - 管理对话上下文
    - 调用 LLM 进行推理
    - 解析工具调用意图
    - 协调工具执行
    """
    
    async def run_react_loop(session_id, user_input, llm_config)
    async def continue_after_confirmation(session_id, request_id, approved)
```

---

## 7. 快速接入指南

### 7.1 前端接入

#### 步骤 1: 引入 API

```javascript
// api/index.js
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

export const mcpHostApi = {
  // 获取服务器状态
  listServers: () => axios.get(`${API_BASE}/api/v1/host/servers`).then(r => r.data),
  
  // 启动服务器
  startStdioServer: (serverKey, command, args) => 
    axios.post(`${API_BASE}/api/v1/host/servers/stdio/${serverKey}/start`, null, {
      params: { command, args }
    }).then(r => r.data),
  
  // 发送消息
  chat: (sessionId, message, config) =>
    axios.post(`${API_BASE}/api/v1/host/sessions/${sessionId}/chat`, {
      message,
      ...config
    }).then(r => r.data),
  
  // 确认工具调用
  confirmTool: (sessionId, requestId, approved) =>
    axios.post(`${API_BASE}/api/v1/host/sessions/${sessionId}/confirmations/${requestId}`, {
      approved
    }).then(r => r.data)
}
```

#### 步骤 2: 使用流式响应

```javascript
async function sendMessage(message) {
  const response = await fetch(`${API_BASE}/api/v1/host/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      llm_provider: 'zhipu',
      llm_model: 'glm-4',
      api_key: 'YOUR_KEY',
      stream: true
    })
  })
  
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    
    const text = decoder.decode(value)
    const lines = text.split('\n')
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') continue
        
        const event = JSON.parse(data)
        handleEvent(event)
      }
    }
  }
}

function handleEvent(event) {
  switch (event.type) {
    case 'state':
      // 更新状态显示
      break
    case 'tool_call':
      // 显示工具调用
      break
    case 'tool_result':
      // 显示工具结果
      break
    case 'confirmation_required':
      // 弹出确认框
      showConfirmationModal(event)
      break
    case 'final':
      // 显示最终回复
      break
  }
}
```

### 7.2 后端接入

#### 步骤 1: 安装依赖

```bash
# 核心依赖
pip install fastapi uvicorn httpx

# 已包含在 requirements.txt 中
```

#### 步骤 2: 注册 API 路由

```python
from fastapi import FastAPI
from app.api.v1 import mcp, mcp_host, mcp_test

app = FastAPI()

# 注册 MCP 相关路由
app.include_router(mcp.router)
app.include_router(mcp_host.router)
app.include_router(mcp_test.router)
```

#### 步骤 3: 启动服务

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7.3 自定义 MCP 服务器开发

参考 MCP 官方文档创建服务器：

```javascript
// my-mcp-server.js (Node.js 示例)
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'

const server = new Server({
  name: 'my-mcp-server',
  version: '1.0.0'
}, {
  capabilities: {
    tools: {}
  }
})

// 定义工具
server.setRequestHandler('tools/list', async () => ({
  tools: [{
    name: 'my_tool',
    description: '我的工具描述',
    inputSchema: {
      type: 'object',
      properties: {
        param1: { type: 'string', description: '参数1' }
      },
      required: ['param1']
    }
  }]
}))

// 实现工具
server.setRequestHandler('tools/call', async (request) => {
  const { name, arguments: args } = request.params
  
  if (name === 'my_tool') {
    return {
      content: [{
        type: 'text',
        text: `工具执行结果: ${args.param1}`
      }]
    }
  }
})

// 启动服务器
const transport = new StdioServerTransport()
await server.connect(transport)
```

---

## 8. 预置服务器

### 8.1 Context7 (文档搜索)

| 属性 | 值 |
|------|-----|
| **服务器标识** | `context7` |
| **包名** | `@upstash/context7-mcp@latest` |
| **传输协议** | STDIO |
| **依赖** | Node.js |

**工具列表**:

| 工具 | 说明 |
|------|------|
| `resolve-library-id` | 解析库/框架的 Context7 ID |
| `get-library-docs` | 获取库的官方文档 |

**使用示例**:
```json
{
  "tool_name": "resolve-library-id",
  "arguments": { "libraryName": "react" }
}
```

---

### 8.2 Everything Server (测试服务)

| 属性 | 值 |
|------|-----|
| **服务器标识** | `everything` |
| **包名** | `@modelcontextprotocol/server-everything@latest` |
| **传输协议** | STDIO |
| **依赖** | Node.js |

**工具列表**:

| 工具 | 说明 |
|------|------|
| `echo` | 回显消息 |
| `add` | 两数相加 |
| `longRunningOperation` | 长时间运行操作 |
| `sampleLLM` | LLM 调用示例 |
| `getTinyImage` | 获取测试图片 |
| `printEnv` | 打印环境变量 |
| `annotatedMessage` | 带注解的消息 |

---

### 8.3 和风天气 (hefeng)

| 属性 | 值 |
|------|-----|
| **服务器标识** | `hefeng` |
| **包名** | `hefeng-mcp-server` |
| **传输协议** | STDIO |
| **依赖** | Node.js, 和风天气 API Key |

**工具列表**:

| 工具 | 说明 |
|------|------|
| `get_location_id` | 获取城市位置 ID |
| `get_weather` | 获取实时/预报天气 |
| `get_indices` | 获取生活指数 |

**配置要求**:
- 需要和风天气 API Key
- 需要配置 API Host URL

**使用示例**:
```json
// 1. 先获取位置 ID
{
  "tool_name": "get_location_id",
  "arguments": { "city_name": "beijing" }
}

// 2. 再获取天气
{
  "tool_name": "get_weather",
  "arguments": { "location": "101010100", "days": "now" }
}
```

---

### 8.4 Wttr 天气 (免费)

| 属性 | 值 |
|------|-----|
| **服务器标识** | `wttr` |
| **包名** | `wttr-mcp-server@latest` |
| **传输协议** | STDIO |
| **依赖** | Node.js |
| **API Key** | 无需 |

**工具列表**:

| 工具 | 说明 |
|------|------|
| `get_weather_wttr` | 获取天气信息 |
| `get_datetime` | 获取日期时间 |

---

## 9. 常见问题

### Q1: MCP 服务器启动失败？

**可能原因**:
1. Node.js 未安装或版本过低
2. 网络问题导致 npm 包下载失败
3. API Key 配置错误

**解决方案**:
```bash
# 检查 Node.js 版本
node --version  # 建议 v18+

# 手动安装包测试
npx -y @modelcontextprotocol/server-everything@latest

# 检查环境变量
echo $HEFENG_API_KEY
```

### Q2: 工具调用返回 403 错误？

**可能原因**:
- API Key 无效
- API Host 配置错误

**解决方案**:
检查服务器启动参数中的 `--apiKey` 和 `--apiUrl` 是否正确。

### Q3: MCP Host 显示"暂无连接服务器"？

**原因**: 服务器未通过 Host API 启动

**解决方案**:
```bash
# 通过 Host API 启动服务器
curl -X POST "http://localhost:8000/api/v1/host/servers/stdio/hefeng/start?command=npx&args=-y&args=hefeng-mcp-server&args=--apiKey=YOUR_KEY"
```

### Q4: 如何添加自定义风险规则？

编辑 `backend/app/services/mcp_host_service.py` 中的 `HIGH_RISK_KEYWORDS`:

```python
HIGH_RISK_KEYWORDS = {
    ToolRiskLevel.CRITICAL: [
        "delete", "remove", "drop",
        "my_critical_tool"  # 添加自定义
    ],
    ...
}
```

### Q5: 如何修改确认超时时间？

```http
PUT /api/v1/host/policy?confirmation_timeout=600
```

或在代码中修改默认值:
```python
# human_in_loop.py
class RiskPolicy:
    confirmation_timeout: int = 600  # 改为 10 分钟
```

---

## 附录

### A. 相关链接

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP GitHub](https://github.com/modelcontextprotocol)
- [和风天气 API](https://dev.qweather.com/)

### B. 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-01-12 | v1.0.0 | 初始版本发布 |

---

> 💡 **如有问题，请联系技术支持团队**
