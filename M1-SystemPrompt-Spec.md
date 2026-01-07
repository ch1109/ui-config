# Spec Coding: M1 - System Prompt 配置管理

## 模块概述

| 项目 | 内容 |
|------|------|
| 模块编号 | M1 |
| 模块名称 | System Prompt 配置管理 |
| 优先级 | P0 (核心功能) |
| 预估工时 | 2 人天 |

说明：本版本为 Demo，不包含登录与鉴权机制，接口默认在可信环境下使用。

---

## 技术架构

### 技术栈
- 后端: Python 3.10+, FastAPI
- 数据库: PostgreSQL / SQLite (开发环境)
- 前端: Vue 3 / React (根据现有后台技术选型)

### 文件结构
```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── system_prompt.py      # API 路由
│   ├── models/
│   │   └── system_prompt.py          # 数据模型
│   ├── schemas/
│   │   └── system_prompt.py          # Pydantic Schema
│   ├── services/
│   │   └── system_prompt_service.py  # 业务逻辑
│   └── core/
│       └── default_prompts.py        # 默认提示词模板
```

---

## 数据模型设计

### 数据库表: system_prompts

```sql
CREATE TABLE system_prompts (
    id SERIAL PRIMARY KEY,
    prompt_key VARCHAR(50) UNIQUE NOT NULL DEFAULT 'global_ui_config',
    prompt_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- 索引
CREATE INDEX idx_system_prompts_key ON system_prompts(prompt_key);
```

### SQLAlchemy Model

```python
# app/models/system_prompt.py

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class SystemPrompt(Base):
    __tablename__ = "system_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_key = Column(String(50), unique=True, nullable=False, default="global_ui_config")
    prompt_content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
```

### Pydantic Schema

```python
# app/schemas/system_prompt.py

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional

class SystemPromptBase(BaseModel):
    prompt_content: str = Field(
        ..., 
        max_length=10000,
        description="System Prompt 内容，建议不少于 100 字符，最大 10000 字符"
    )

class SystemPromptCreate(SystemPromptBase):
    pass

class SystemPromptUpdate(SystemPromptBase):
    # Demo 版本为单用户场景，移除并发检测
    pass

class SystemPromptResponse(SystemPromptBase):
    id: int
    prompt_key: str
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool
    char_count: int = Field(description="当前字符数")
    
    class Config:
        from_attributes = True
    
    @validator('char_count', pre=True, always=True)
    def calc_char_count(cls, v, values):
        return len(values.get('prompt_content', ''))

class SystemPromptStats(BaseModel):
    current_length: int
    max_length: int = 10000
    recommended_min_length: int = 100
    is_valid: bool
```

---

## API 接口设计

### 接口列表

| 方法 | 路径 | 描述 | 对应需求 |
|------|------|------|----------|
| GET | /api/v1/system-prompt | 获取当前 System Prompt | REQ-M1-004 |
| PUT | /api/v1/system-prompt | 更新 System Prompt | REQ-M1-006 |
| POST | /api/v1/system-prompt/reset | 恢复默认 System Prompt | REQ-M1-007 |
| GET | /api/v1/system-prompt/default | 获取默认 System Prompt | REQ-M1-004 |

### API 实现

```python
# app/api/v1/system_prompt.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.system_prompt import (
    SystemPromptCreate, 
    SystemPromptUpdate, 
    SystemPromptResponse,
    SystemPromptStats
)
from app.services.system_prompt_service import SystemPromptService

router = APIRouter(prefix="/api/v1/system-prompt", tags=["System Prompt"])

@router.get("", response_model=SystemPromptResponse)
async def get_system_prompt(db: Session = Depends(get_db)):
    """
    获取当前 System Prompt
    
    - 若数据库中存在配置，返回该配置
    - 若不存在，返回默认模板
    
    对应需求: REQ-M1-004
    """
    service = SystemPromptService(db)
    prompt = service.get_current_prompt()
    return prompt

@router.put("", response_model=SystemPromptResponse)
async def update_system_prompt(
    prompt_data: SystemPromptUpdate,
    db: Session = Depends(get_db)
):
    """
    更新 System Prompt
    
    - 验证内容最大长度 (<=10000 字符)
    - 持久化存储至数据库
    - 返回更新后的配置
    
    对应需求: REQ-M1-006, REQ-M1-008
    
    注: Demo 版本为单用户场景，不做并发冲突检测
    """
    service = SystemPromptService(db)
    
    # 长度验证 (仅最大长度校验)
    content_length = len(prompt_data.prompt_content)
    if content_length > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "CONTENT_TOO_LONG",
                "message": "已达到最大字符限制",
                "max_length": 10000,
                "current_length": content_length
            }
        )
    
    try:
        updated_prompt = service.update_prompt(prompt_data.prompt_content)
        return updated_prompt
    except Exception as e:
        # 对应 REQ-M1-009: 数据库连接失败处理
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SAVE_FAILED",
                "message": "保存失败，请检查网络后重试",
                "retry": True
            }
        )

@router.post("/reset", response_model=SystemPromptResponse)
async def reset_system_prompt(db: Session = Depends(get_db)):
    """
    恢复默认 System Prompt
    
    对应需求: REQ-M1-007
    """
    service = SystemPromptService(db)
    reset_prompt = service.reset_to_default()
    return reset_prompt

@router.get("/default", response_model=SystemPromptResponse)
async def get_default_prompt():
    """
    获取默认 System Prompt 模板 (不保存)
    """
    from app.core.default_prompts import DEFAULT_UI_CONFIG_PROMPT
    return {
        "id": 0,
        "prompt_key": "default",
        "prompt_content": DEFAULT_UI_CONFIG_PROMPT,
        "created_at": None,
        "updated_at": None,
        "is_active": True,
        "char_count": len(DEFAULT_UI_CONFIG_PROMPT)
    }

@router.get("/stats", response_model=SystemPromptStats)
async def get_prompt_stats(db: Session = Depends(get_db)):
    """
    获取当前 Prompt 统计信息 (用于前端实时显示)
    
    对应需求: REQ-M1-005
    """
    service = SystemPromptService(db)
    prompt = service.get_current_prompt()
    return {
        "current_length": len(prompt.prompt_content),
        "max_length": 10000,
        "recommended_min_length": 100,
        "is_valid": len(prompt.prompt_content) <= 10000
    }
```

---

## 业务逻辑实现

```python
# app/services/system_prompt_service.py

from sqlalchemy.orm import Session
from app.models.system_prompt import SystemPrompt
from app.core.default_prompts import DEFAULT_UI_CONFIG_PROMPT
from datetime import datetime

class SystemPromptService:
    PROMPT_KEY = "global_ui_config"
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_current_prompt(self) -> SystemPrompt:
        """获取当前配置，不存在则返回默认"""
        prompt = self.db.query(SystemPrompt).filter(
            SystemPrompt.prompt_key == self.PROMPT_KEY,
            SystemPrompt.is_active == True
        ).first()
        
        if not prompt:
            # 创建默认配置
            prompt = SystemPrompt(
                prompt_key=self.PROMPT_KEY,
                prompt_content=DEFAULT_UI_CONFIG_PROMPT
            )
            self.db.add(prompt)
            self.db.commit()
            self.db.refresh(prompt)
        
        return prompt
    
    def update_prompt(self, content: str) -> SystemPrompt:
        """更新 System Prompt (Demo 版本，单用户场景)"""
        prompt = self.get_current_prompt()
        prompt.prompt_content = content
        prompt.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(prompt)
        return prompt
    
    def reset_to_default(self) -> SystemPrompt:
        """恢复为默认 Prompt"""
        return self.update_prompt(DEFAULT_UI_CONFIG_PROMPT)
```

---

## 默认 Prompt 模板

```python
# app/core/default_prompts.py

DEFAULT_UI_CONFIG_PROMPT = """你是一个专业的 UI 页面分析助手，负责从页面截图中提取结构化的配置信息。

## 你的任务
1. 识别页面中的所有可交互元素（按钮、输入框、链接等）
2. 推断每个元素的业务含义和交互意图
3. 生成标准化的 UI Config JSON 配置

## 输出格式要求
请按照以下 JSON Schema 格式输出：
```json
{
  "name": {
    "zh-CN": "页面中文名称",
    "en": "Page English Name"
  },
  "description": {
    "zh-CN": "页面功能描述",
    "en": "Page function description"
  },
  "buttonList": ["按钮ID列表"],
  "optionalActions": ["可选操作列表"]
}
```

## 识别规则
1. 按钮 ID 使用 snake_case 格式，如 "submit_button", "return_home"
2. 页面描述应包含用户可执行的主要操作
3. 如有不确定的元素，请提出澄清问题

## 注意事项
- 保持 ID 命名的语义化和一致性
- 优先识别主要业务流程相关的元素
- 忽略装饰性、非交互性元素
"""
```

---

## 前端组件设计

### 组件结构

```
frontend/
├── components/
│   └── SystemPromptConfig/
│       ├── index.vue                 # 主组件
│       ├── PromptEditor.vue          # 编辑器组件
│       └── CharacterCounter.vue      # 字符计数器
```

### 核心组件实现 (Vue 3 示例)

```vue
<!-- components/SystemPromptConfig/index.vue -->
<template>
  <div class="system-prompt-config">
    <div class="header">
      <h2>UI Config 提示词配置</h2>
      <div class="actions">
        <button 
          class="btn-secondary" 
          @click="handleReset"
          :disabled="isLoading"
        >
          恢复默认
        </button>
        <button 
          class="btn-primary" 
          @click="handleSave"
          :disabled="!hasChanges || isLoading || !isValid"
        >
          {{ isLoading ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
    
    <div class="editor-container">
      <PromptEditor
        v-model="promptContent"
        :disabled="isLoading"
        @input="handleInput"
      />
      
      <CharacterCounter
        :current="promptContent.length"
        :recommended-min="100"
        :max="10000"
        @validity-change="isValid = $event"
      />
    </div>
    
    <!-- 保存成功提示 -->
    <Transition name="fade">
      <div v-if="showSuccess" class="success-toast">
        保存成功
      </div>
    </Transition>
    
    <!-- 离开确认弹窗 -->
    <ConfirmDialog
      v-model:visible="showLeaveConfirm"
      title="未保存的更改"
      message="您有未保存的更改，确定要离开吗？"
      @confirm="confirmLeave"
      @cancel="cancelLeave"
    />
    
    <!-- 恢复默认确认弹窗 -->
    <ConfirmDialog
      v-model:visible="showResetConfirm"
      title="恢复默认"
      message="确定要恢复为默认模板吗？当前内容将被覆盖。"
      @confirm="confirmReset"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { systemPromptApi } from '@/api/systemPrompt'
import PromptEditor from './PromptEditor.vue'
import CharacterCounter from './CharacterCounter.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const router = useRouter()

// 状态
const promptContent = ref('')
const originalContent = ref('')
const isLoading = ref(false)
const isValid = ref(true)
const showSuccess = ref(false)
const showLeaveConfirm = ref(false)
const showResetConfirm = ref(false)
const pendingNavigation = ref(null)

// 计算属性
const hasChanges = computed(() => promptContent.value !== originalContent.value)

// 加载数据 (REQ-M1-004)
onMounted(async () => {
  isLoading.value = true
  try {
    const response = await systemPromptApi.getCurrent()
    promptContent.value = response.prompt_content
    originalContent.value = response.prompt_content
  } catch (error) {
    console.error('Failed to load prompt:', error)
  } finally {
    isLoading.value = false
  }
})

// 保存处理 (REQ-M1-006)
const handleSave = async () => {
  if (!isValid.value) return
  
  isLoading.value = true
  try {
    await systemPromptApi.update({
      prompt_content: promptContent.value
    })
    originalContent.value = promptContent.value
    
    // 显示成功提示 3 秒
    showSuccess.value = true
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)
  } catch (error) {
    // REQ-M1-009: 保存失败处理
    const message = error.response?.data?.message
    alert(message || '保存失败，请检查网络后重试')
  } finally {
    isLoading.value = false
  }
}

// 恢复默认处理 (REQ-M1-007)
const handleReset = () => {
  showResetConfirm.value = true
}

const confirmReset = async () => {
  showResetConfirm.value = false
  isLoading.value = true
  try {
    const response = await systemPromptApi.reset()
    promptContent.value = response.prompt_content
    originalContent.value = response.prompt_content
  } catch (error) {
    alert('恢复失败，请重试')
  } finally {
    isLoading.value = false
  }
}

// 离开页面确认 (REQ-M1-010)
onBeforeRouteLeave((to, from, next) => {
  if (hasChanges.value) {
    pendingNavigation.value = next
    showLeaveConfirm.value = true
    return false
  }
  next()
})

const confirmLeave = () => {
  showLeaveConfirm.value = false
  if (pendingNavigation.value) {
    pendingNavigation.value()
  }
}

const cancelLeave = () => {
  showLeaveConfirm.value = false
  pendingNavigation.value = null
}

// 浏览器刷新/关闭提示
onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

const handleBeforeUnload = (e) => {
  if (hasChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
</script>

<style scoped>
.system-prompt-config {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 12px;
}

.editor-container {
  position: relative;
}

.success-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  background: #52c41a;
  color: white;
  padding: 12px 24px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

---

## 测试用例

### 单元测试

```python
# tests/test_system_prompt.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestSystemPromptAPI:
    """System Prompt API 测试"""
    
    def test_get_prompt_returns_default_when_empty(self):
        """REQ-M1-004: 无配置时返回默认模板"""
        response = client.get("/api/v1/system-prompt")
        assert response.status_code == 200
        data = response.json()
        assert "prompt_content" in data
    
    def test_update_prompt_success(self):
        """REQ-M1-006: 正常更新 Prompt"""
        new_content = "A" * 500  # 有效长度
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": new_content}
        )
        assert response.status_code == 200
        assert response.json()["prompt_content"] == new_content
    
    def test_update_prompt_too_long(self):
        """REQ-M1-008: 超出字符限制"""
        long_content = "A" * 10001
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": long_content}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "CONTENT_TOO_LONG"
    
    def test_update_prompt_too_short(self):
        """REQ-M1-012: 低于推荐字符数仍可保存"""
        short_content = "A" * 50
        response = client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": short_content}
        )
        assert response.status_code == 200
        assert response.json()["prompt_content"] == short_content
    
    # 注: REQ-M1-013 并发冲突检测在 Demo 版本不实现，跳过相关测试
    
    def test_reset_prompt(self):
        """REQ-M1-007: 恢复默认"""
        # 先更新为其他内容
        client.put(
            "/api/v1/system-prompt",
            json={"prompt_content": "B" * 500}
        )
        
        # 恢复默认
        response = client.post("/api/v1/system-prompt/reset")
        assert response.status_code == 200
        
        # 验证已恢复
        get_response = client.get("/api/v1/system-prompt")
        from app.core.default_prompts import DEFAULT_UI_CONFIG_PROMPT
        assert get_response.json()["prompt_content"] == DEFAULT_UI_CONFIG_PROMPT
    
    def test_get_stats(self):
        """REQ-M1-005: 获取统计信息"""
        response = client.get("/api/v1/system-prompt/stats")
        assert response.status_code == 200
        data = response.json()
        assert "current_length" in data
        assert "max_length" in data
        assert data["max_length"] == 10000
```

---

## 验收清单

| 需求编号 | 验收标准 | 测试方法 |
|----------|----------|----------|
| REQ-M1-001 | 全局唯一配置可正常保存和读取 | 单元测试 |
| REQ-M1-002 | 输入框字符限制 <=10000，建议 >=100 | 单元测试 + E2E |
| REQ-M1-003 | 页面加载 <1s | 性能测试 |
| REQ-M1-004 | 加载已保存配置或默认模板 | E2E 测试 |
| REQ-M1-005 | 实时显示字符计数 | E2E 测试 |
| REQ-M1-006 | 保存成功并显示提示 3 秒 | E2E 测试 |
| REQ-M1-007 | 确认后恢复默认模板 | E2E 测试 |
| REQ-M1-008 | 超限时阻止输入并提示 | E2E 测试 |
| REQ-M1-012 | 长度不足时提示建议但允许保存 | E2E 测试 |
| REQ-M1-009 | 保存失败时显示错误提示 | 模拟测试 |
| REQ-M1-010 | 未保存离开时弹出确认 | E2E 测试 |
| REQ-M1-011 | 完整流程可正常执行 | E2E 测试 |
| ~~REQ-M1-013~~ | ~~并发更新冲突提示~~ | *Demo 版本不实现* |
