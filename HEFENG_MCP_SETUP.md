# 和风天气 MCP 服务器配置指南

通过 MCP Host 功能直接使用和风天气服务器，无需修改代码。

## 📋 前置条件

- ✅ Node.js 和 npm/npx 已安装
- ✅ 后端服务已启动 (http://localhost:8000)
- ✅ 已获取和风天气 API Key

## 🔑 获取和风天气 API Key

1. 访问 https://dev.qweather.com/
2. 注册并登录账号
3. 创建应用（选择"Web API"类型）
4. 复制 API Key

## 🚀 快速启动

### 方法一：使用启动脚本（推荐）

**macOS / Linux:**

```bash
# 1. 赋予执行权限
chmod +x start_hefeng_mcp.sh

# 2. 编辑脚本，填入你的 API Key
nano start_hefeng_mcp.sh
# 修改 HEFENG_API_KEY="your_hefeng_api_key_here"
# 如需切换 API Host，同步修改 HEFENG_API_URL

# 3. 运行脚本
./start_hefeng_mcp.sh
```

**Windows:**

```bash
# 1. 编辑脚本，填入你的 API Key
notepad start_hefeng_mcp.bat
# 修改 set HEFENG_API_KEY=your_hefeng_api_key_here
# 如需切换 API Host，同步修改 HEFENG_API_URL

# 2. 运行脚本
start_hefeng_mcp.bat
```

### 方法二：使用 curl 命令

**macOS / Linux:**

```bash
curl -X POST "http://localhost:8000/api/v1/host/servers/stdio/hefeng/start?command=npx&args=-y&args=hefeng-mcp-server&args=--apiKey=你的API密钥&args=--apiUrl=https://devapi.qweather.com"
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/host/servers/stdio/hefeng/start?command=npx&args=-y&args=hefeng-mcp-server&args=--apiKey=你的API密钥&args=--apiUrl=https://devapi.qweather.com" `
  -Method POST
```

## ✅ 验证启动

### 1. 检查服务器状态

```bash
curl http://localhost:8000/api/v1/host/servers
```

应该看到 `stdio_servers` 中包含 `hefeng`，状态为 `running`。

### 2. 访问 MCP Host 页面

1. 打开浏览器访问: http://localhost:5173/mcp-host
2. 查看左侧边栏"连接状态"
3. 应该看到"和风天气"服务器及其工具数量

### 3. 测试天气查询

在 MCP Host 对话框中发送：

```
帮我查询北京今天的天气
```

AI 应该会自动调用和风天气工具并返回结果。

## 🛑 停止服务器

**使用脚本：**

```bash
# macOS / Linux
chmod +x stop_hefeng_mcp.sh
./stop_hefeng_mcp.sh

# Windows
stop_hefeng_mcp.bat
```

**使用 curl：**

```bash
curl -X POST "http://localhost:8000/api/v1/host/servers/stdio/hefeng/stop"
```

## 🔧 故障排查

### 问题 1: 启动失败

**检查 Node.js 是否安装：**

```bash
npx --version
```

**检查后端是否运行：**

```bash
curl http://localhost:8000/health
```

### 问题 2: 工具调用失败

**检查 API Key 是否正确：**

```bash
# 使用脚本时，确认已修改 HEFENG_API_KEY 和 HEFENG_API_URL
# 或直接测试 API Key
curl --compressed -H "X-QW-Api-Key: 你的API密钥" "https://devapi.qweather.com/v7/weather/now?location=101010100"

如果返回 Invalid Host，说明 API Host 与 Key 的授权不匹配，请使用与你的 Key 授权一致的 Host。
```

### 问题 3: 服务器未在 MCP Host 显示

**刷新服务器列表：**

访问 MCP Host 页面，点击左侧边栏的"🔄 刷新状态"按钮。

## 📚 可用工具

和风天气 MCP 服务器提供以下工具：

- `get_weather` - 获取天气预报（支持实时/小时/天）
- `get_location_id` - 查询位置 ID
- `get_datetime` - 获取当前日期时间

## 🆘 需要帮助？

如果遇到问题，可以：

1. 查看后端日志
2. 检查 API 响应
3. 确认和风天气 API 配额未用完

## 📝 配置参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `command` | 启动命令 | `npx` |
| `args` | 命令参数 | `["-y", "hefeng-mcp-server", "--apiKey=你的API密钥", "--apiUrl=https://devapi.qweather.com"]` |

## 🎯 完整 API 参考

### 启动服务器

```http
POST /api/v1/host/servers/stdio/{server_key}/start
Query Parameters:
- command: npx
- args: -y
- args: hefeng-mcp-server
- args: --apiKey=your_api_key
- args: --apiUrl=https://devapi.qweather.com
```

### 停止服务器

```http
POST /api/v1/host/servers/stdio/{server_key}/stop
```

### 查看服务器状态

```http
GET /api/v1/host/servers
```

响应示例：

```json
{
  "stdio_servers": {
    "hefeng": {
      "running": true,
      "initialized": true,
      "tools_count": 3,
      "resources_count": 0,
      "prompts_count": 0
    }
  },
  "total_stdio": 1,
  "total_sse": 0
}
```
