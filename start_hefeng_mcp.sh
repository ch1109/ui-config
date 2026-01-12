#!/bin/bash

# 和风天气 MCP 服务器启动脚本
# 使用方法: ./start_hefeng_mcp.sh

# 配置区域 - 请修改以下变量
HEFENG_API_KEY="${HEFENG_API_KEY:-your_hefeng_api_key_here}"  # 请替换为你的和风天气 API Key
HEFENG_API_URL="${HEFENG_API_URL:-https://devapi.qweather.com}" # 和风天气 API Host（需与你的 Key 授权一致）
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"         # 后端 API 地址

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🌤️  启动和风天气 MCP 服务器${NC}"
echo "================================"

# 检查 API Key 是否配置
if [ "$HEFENG_API_KEY" = "your_hefeng_api_key_here" ]; then
    echo -e "${RED}❌ 错误: 请先配置 HEFENG_API_KEY${NC}"
    echo "编辑此脚本，将 HEFENG_API_KEY 替换为你的和风天气 API Key"
    echo "获取地址: https://dev.qweather.com/"
    exit 1
fi

# 检查后端是否运行
echo -n "检查后端服务..."
if ! curl -s "$BACKEND_URL/health" > /dev/null; then
    echo -e "${RED}失败${NC}"
    echo "后端服务未运行，请先启动后端"
    exit 1
fi
echo -e "${GREEN}成功${NC}"

# 启动和风天气 MCP 服务器
echo -n "正在启动和风天气 MCP 服务器..."

RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/v1/host/servers/stdio/hefeng/start?command=npx&args=-y&args=hefeng-mcp-server&args=--apiKey=$HEFENG_API_KEY&args=--apiUrl=$HEFENG_API_URL")

# 检查结果
if echo "$RESPONSE" | grep -q '"success": true'; then
    echo -e "${GREEN}成功${NC}"
    echo ""
    echo -e "${GREEN}✅ 和风天气 MCP 服务器已启动！${NC}"
    echo ""
    echo "📍 后续步骤:"
    echo "  1. 访问 http://localhost:5173/mcp-host"
    echo "  2. 在左侧边栏查看连接状态"
    echo "  3. 发送消息测试: '帮我查询北京今天的天气'"
    echo ""
else
    echo -e "${RED}失败${NC}"
    echo "错误信息: $RESPONSE"
    exit 1
fi
