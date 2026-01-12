@echo off
REM 和风天气 MCP 服务器启动脚本 (Windows)
REM 使用方法: start_hefeng_mcp.bat

REM 配置区域 - 请修改以下变量
set HEFENG_API_KEY=your_hefeng_api_key_here
set HEFENG_API_URL=https://devapi.qweather.com
set BACKEND_URL=http://localhost:8000

echo ================================
echo 启动和风天气 MCP 服务器
echo ================================
echo.

REM 检查 API Key 是否配置
if "%HEFENG_API_KEY%"=="your_hefeng_api_key_here" (
    echo [错误] 请先配置 HEFENG_API_KEY
    echo 编辑此脚本，将 HEFENG_API_KEY 替换为你的和风天气 API Key
    echo 获取地址: https://dev.qweather.com/
    pause
    exit /b 1
)

REM 启动和风天气 MCP 服务器
echo 正在启动和风天气 MCP 服务器...
echo.

curl -X POST "%BACKEND_URL%/api/v1/host/servers/stdio/hefeng/start?command=npx^&args=-y^&args=hefeng-mcp-server^&args=--apiKey=%HEFENG_API_KEY%^&args=--apiUrl=%HEFENG_API_URL%"

echo.
echo ================================
echo 启动完成！
echo ================================
echo.
echo 后续步骤:
echo   1. 访问 http://localhost:5173/mcp-host
echo   2. 在左侧边栏查看连接状态
echo   3. 发送消息测试: "帮我查询北京今天的天气"
echo.
pause
