# UI Config 后端配置指南

## 🤖 VL 模型配置 (重要!)

要使用 AI 解析图片功能，需要配置 VL (Vision-Language) 模型 API。

系统支持两种 VL 模型提供商：
- **智谱 GLM-4V** (默认推荐)
- **阿里云 DashScope Qwen-VL**

---

### 方式一: 使用智谱 GLM-4V (默认)

1. 注册智谱开放平台账户: https://open.bigmodel.cn/

2. 在控制台获取 API Key

3. 在 `backend/` 目录下创建 `.env` 文件:

```bash
# .env - 智谱 GLM-4V 配置
VL_PROVIDER=zhipu
ZHIPU_API_KEY=你的智谱API密钥
ZHIPU_MODEL_NAME=glm-4v-flash
```

**可选模型:**
- `glm-4v-flash` - 快速版 (推荐，速度快)
- `glm-4v` - 标准版
- `glm-4v-plus` - 增强版 (效果最好)

---

### 方式二: 使用阿里云 DashScope Qwen-VL

1. 注册阿里云账户并开通 DashScope 服务: https://dashscope.console.aliyun.com

2. 获取 API Key

3. 在 `backend/` 目录下创建 `.env` 文件:

```bash
# .env - 阿里云 Qwen-VL 配置
VL_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-你的DashScope密钥
DASHSCOPE_MODEL_NAME=qwen-vl-max
```

**可选模型:**
- `qwen-vl-max` - 最强版本
- `qwen-vl-plus` - 平衡版本

---

## 📁 完整配置选项

创建 `.env` 文件，包含以下配置:

```bash
# ========================================
# VL 模型配置 (二选一)
# ========================================

# 选择模型提供商: "zhipu" 或 "dashscope"
VL_PROVIDER=zhipu

# 智谱 GLM-4V 配置 (如果 VL_PROVIDER=zhipu)
ZHIPU_API_KEY=你的API密钥
ZHIPU_MODEL_NAME=glm-4v-flash

# 阿里云 Qwen-VL 配置 (如果 VL_PROVIDER=dashscope)
# DASHSCOPE_API_KEY=你的API密钥
# DASHSCOPE_MODEL_NAME=qwen-vl-max

# 通用配置
VL_TIMEOUT=60.0

# ========================================
# 其他配置
# ========================================

# 文件上传配置
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760

# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./ui_config.db

# 应用配置
DEBUG=True
CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]

# 澄清对话配置
CLARIFY_CONFIDENCE_THRESHOLD=0.85
CLARIFY_MAX_ROUNDS=5
CLARIFY_TIMEOUT=15.0
```

---

## 📍 API Key 填写位置

**文件位置:** `backend/.env`

1. 在 `backend/` 目录下创建一个名为 `.env` 的文件
2. 根据你选择的模型提供商，填入对应的 API Key
3. 重启后端服务使配置生效

**示例 (使用智谱 GLM-4V):**
```bash
# backend/.env
VL_PROVIDER=zhipu
ZHIPU_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
ZHIPU_MODEL_NAME=glm-4v-flash
VL_TIMEOUT=60.0
```

---

## 🚀 启动服务

```bash
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或者直接使用:
```bash
cd backend
./venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔌 MCP 服务器

Context7 MCP 服务器已预置配置，在 MCP 服务器管理页面中可以启用/禁用。

如需添加自定义 MCP 服务器，可以:
1. 通过表单填写配置
2. 上传 JSON 配置文件
3. 直接编辑 JSON 配置

