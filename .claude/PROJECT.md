# UI Config 项目文档

## 技术栈

- **后端**: Python 3.9+, FastAPI, SQLAlchemy, httpx
- **前端**: Vue 3, Ant Design Vue, Vite
- **MCP 协议版本**: 2024-11-05

## 关键依赖

- `fastapi` - 异步 Web 框架
- `httpx` - 异步 HTTP 客户端
- `sqlalchemy` - 异步 ORM
- `pydantic` - 数据验证

## 开发约定

### MCP 相关
- 工具名称使用命名空间格式: `{server_key}__{tool_name}`
- 根目录 URI 使用 `file://` 协议
- JSON-RPC 2.0 协议通信

### 代码风格
- 使用 async/await 进行异步操作
- 使用 dataclass 定义数据结构
- 日志使用 logging 模块

## 踩坑记录

### 2026-01-19: MCP Roots 功能实现

**问题**: 如何在工具调用时安全地验证文件路径？

**解决方案**:
1. 创建 `roots_service.py` 统一管理根目录
2. 从工具参数中自动提取可能的文件路径
3. 在 `prepare_tool_call` 和 `execute_tool_call` 中进行双重验证
4. 路径验证失败时自动提升风险等级到 CRITICAL

**注意事项**:
- 路径验证使用 `pathlib.Path` 的 `parents` 属性检查
- 支持 URL 编码的路径
- 严格模式下未配置根目录会拒绝所有路径

## 功能模块

### MCP Roots 能力（2026-01-19 实现）

**文件清单**:
- `backend/app/services/roots_service.py` - Roots 管理服务（新建）
- `backend/app/services/stdio_mcp_manager.py` - STDIO 管理器（修改）
- `backend/app/services/sse_mcp_client.py` - SSE 客户端（修改）
- `backend/app/services/mcp_host_service.py` - Host 服务（修改）
- `backend/app/api/v1/mcp_host.py` - Host API（修改）

**API 端点**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/host/servers/{server_key}/roots` | GET | 获取服务器根目录 |
| `/api/v1/host/servers/{server_key}/roots` | PUT | 配置服务器根目录 |
| `/api/v1/host/servers/{server_key}/roots` | POST | 添加根目录 |
| `/api/v1/host/servers/{server_key}/roots` | DELETE | 移除根目录 |
| `/api/v1/host/servers/{server_key}/validate-path` | POST | 验证路径权限 |
| `/api/v1/host/roots/global` | GET | 获取全局根目录 |
| `/api/v1/host/roots/global` | POST | 添加全局根目录 |
| `/api/v1/host/roots/global` | DELETE | 移除全局根目录 |
| `/api/v1/host/roots/status` | GET | 获取 Roots 服务状态 |

**核心功能**:
1. 在 MCP initialize 时声明 roots 能力
2. 动态管理工作区根目录（会话级 + 全局级）
3. 工具调用时自动验证文件路径权限
4. 支持 roots/list_changed 通知

### MCP Sampling 能力（2026-01-19 实现）

**功能描述**: 允许 MCP Server 请求 Host 调用 LLM，实现"反向"的 AI 能力调用。

**文件清单**:
- `backend/app/services/sampling_service.py` - Sampling 服务核心（新建）
- `backend/app/services/stdio_mcp_manager.py` - STDIO 管理器（修改，添加 sampling 支持）
- `backend/app/services/mcp_host_service.py` - Host 服务（修改，集成 sampling）
- `backend/app/api/v1/mcp_host.py` - Host API（修改，添加 sampling 端点）
- `backend/tests/test_sampling.py` - 单元测试（新建）

**API 端点**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/host/sampling/config` | GET | 获取 Sampling 安全配置 |
| `/api/v1/host/sampling/config` | PUT | 更新 Sampling 安全配置 |
| `/api/v1/host/sampling/status` | GET | 获取 Sampling 服务状态 |
| `/api/v1/host/sampling/requests` | GET | 获取待审核的请求列表 |
| `/api/v1/host/sampling/requests/{id}/approve` | POST | 批准 Sampling 请求 |
| `/api/v1/host/sampling/requests/{id}/reject` | POST | 拒绝 Sampling 请求 |
| `/api/v1/host/sampling/cleanup` | POST | 清理过期请求 |
| `/api/v1/host/sampling/servers` | GET | 获取支持 Sampling 的服务器 |

**核心功能**:
1. 在 MCP initialize 时声明 sampling 能力
2. 后台监听 MCP Server 的 sampling/createMessage 请求
3. 安全策略：Token 限制、速率限制、内容过滤、Server 黑白名单
4. 人机回环审核：高 Token 请求需要人工批准
5. 多 LLM 提供商支持（OpenAI、Anthropic、智谱）

**安全配置说明**:
- `max_tokens_limit`: 单次请求允许的最大 token 数（默认 4096）
- `rate_limit_per_minute`: 全局每分钟最大请求数（默认 60）
- `rate_limit_per_server`: 每个 Server 每分钟最大请求数（默认 10）
- `require_approval`: 是否需要人工审核（默认 false）
- `auto_approve_threshold`: 自动批准的 token 阈值（默认 100）
- `blocked_keywords`: 内容过滤关键词列表
- `allowed_servers` / `blocked_servers`: Server 白名单/黑名单

### MCP Sampling 前端 UI（2026-01-19 实现）

**文件清单**:
- `frontend/src/views/SamplingPage.vue` - Sampling 管理页面（新建）
- `frontend/src/api/index.js` - API 模块（修改，添加 Sampling 接口）
- `frontend/src/router/index.js` - 路由配置（修改，添加 /sampling 路由）
- `frontend/src/App.vue` - 主应用（修改，添加导航入口）

**功能特性**:
- 状态概览（待审核数、服务器数、速率限制、审核开关）
- 安全配置管理（Token 限制、速率限制、审核策略、内容过滤、Server 权限）
- 待审核请求列表（批准、拒绝、查看详情）
- 支持 Sampling 的服务器展示
- 实时刷新（每 10 秒自动刷新待审核请求）

**路由**: `/sampling`

## 待办清单

- [ ] 前端 UI 集成 Roots 管理
- [ ] 性能优化（路径验证缓存）
