#!/bin/bash

# 和风天气 MCP 服务器停止脚本
# 使用方法: ./stop_hefeng_mcp.sh

BACKEND_URL="http://localhost:8000"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🛑 停止和风天气 MCP 服务器${NC}"
echo "================================"

# 停止服务器
echo -n "正在停止和风天气 MCP 服务器..."

RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/v1/host/servers/stdio/hefeng/stop")

# 检查结果
if echo "$RESPONSE" | grep -q '"success": true'; then
    echo -e "${GREEN}成功${NC}"
    echo ""
    echo -e "${GREEN}✅ 和风天气 MCP 服务器已停止${NC}"
else
    echo -e "${RED}失败${NC}"
    echo "错误信息: $RESPONSE"
    exit 1
fi
