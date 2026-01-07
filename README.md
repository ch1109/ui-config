# UI Config 智能配置系统

基于 VL 模型的 UI 配置智能生成系统，通过页面截图自动解析生成结构化配置。

## ✨ 功能特性

- **🖼️ 智能图片解析**: 上传页面截图，AI 自动识别可交互元素
- **💬 多轮澄清对话**: 当识别不确定时，AI 主动提问澄清
- **📝 可视化配置编辑**: 表单化编辑配置，所见即所得
- **📋 JSON Config 生成**: 自动生成符合 Schema 的配置文件
- **🔌 MCP 服务器管理**: 扩展 AI 能力的 MCP 服务器配置

## 🏗️ 技术栈

### 后端
- Python 3.10+
- FastAPI
- SQLAlchemy (异步)
- SQLite (开发环境)
- Qwen3-VL-8B-Instruct (VL 模型)

### 前端
- Vue 3
- Vite
- Pinia
- Vue Router

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量 (可选)
cp .env.example .env
# 编辑 .env 设置 VL 模型地址

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173 即可使用。

## 📁 项目结构

```
.
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/v1/         # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic Schema
│   │   └── services/       # 业务逻辑
│   ├── uploads/            # 上传文件目录
│   └── requirements.txt
│
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── api/           # API 封装
│   │   ├── components/    # 组件
│   │   ├── router/        # 路由
│   │   ├── stores/        # 状态管理
│   │   └── views/         # 页面
│   └── package.json
│
├── EARS-Requirements.md    # 需求规格文档
├── M1-SystemPrompt-Spec.md # M1 模块规范
├── M2-ImageParsing-Spec.md # M2 模块规范
├── M3-M6-Combined-Spec.md  # M3-M6 模块规范
└── TASK-TRACKER.md         # 任务跟踪清单
```

## 📚 API 文档

启动后端后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🎯 主要模块

| 模块 | 功能 | 状态 |
|------|------|------|
| M1 | System Prompt 配置管理 | ✅ 完成 |
| M2 | 页面截图智能解析 | ✅ 完成 |
| M3 | 多轮澄清对话 | ✅ 完成 |
| M4 | JSON Config 生成 | ✅ 完成 |
| M5 | 可视化配置编辑 | ✅ 完成 |
| M6 | MCP 服务器管理 | ✅ 完成 |

## ⚙️ 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| VL_MODEL_ENDPOINT | VL 模型 API 地址 | http://localhost:8080 |
| VL_API_KEY | VL 模型 API 密钥 | - |
| DATABASE_URL | 数据库连接字符串 | sqlite+aiosqlite:///./ui_config.db |

### VL 模型配置

系统依赖 Qwen3-VL-8B-Instruct 模型进行图片解析。请确保:
1. 模型服务已部署并可访问
2. 正确配置 `VL_MODEL_ENDPOINT` 环境变量
3. 如需认证，配置 `VL_API_KEY`

## 📝 开发说明

### Demo 版本约定
- 单用户场景，不包含登录鉴权
- SSRF 防护为简化版本
- MCP 功能为预留扩展

### 代码规范
- 后端遵循 PEP 8
- 前端使用 ESLint + Prettier
- 提交信息遵循 Conventional Commits

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

