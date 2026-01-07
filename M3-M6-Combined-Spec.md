# Spec Coding: M3-M6 - 澄清对话、配置生成、可视化编辑、MCP管理

> **Demo 版本说明**：
> - 本文档覆盖 M3-M6 四个模块的实现规范
> - 采用单用户场景设计，简化冲突处理逻辑
> - MCP 功能为预留扩展，当前不强依赖

---

# 模块 M3: 多轮澄清对话

## 模块概述

| 项目 | 内容 |
|------|------|
| 模块编号 | M3 |
| 模块名称 | 多轮澄清对话 |
| 优先级 | P0 (核心功能) |
| 预估工时 | 3 人天 |
| 置信度阈值 | 85% |
| 最大澄清轮次 | 5 轮 |

---

## 实体关系说明

```
┌──────────────────┐         ┌──────────────────┐
│   ParseSession   │────────▶│   PageConfig     │
└──────────────────┘  1:0..1 └──────────────────┘
        │
        │ 1:1
        ▼
┌──────────────────┐
│  uploads/图片    │
└──────────────────┘
```

**关联时机**：
- `ParseSession` 创建时不关联 `PageConfig`（page_config_id 为空）
- 用户点击"保存配置"时，创建 `PageConfig` 并关联到 `ParseSession`
- 图片清理策略：未关联 PageConfig 且超过 24h 的 session 图片会被清理

---

## API 接口设计

### 接口列表

| 方法 | 路径 | 描述 | 对应需求 |
|------|------|------|----------|
| POST | /api/v1/clarify/{session_id}/respond | 提交澄清回答 | REQ-M3-006 |
| POST | /api/v1/clarify/{session_id}/confirm | 确认完成配置 | REQ-M3-008 |
| GET | /api/v1/clarify/{session_id}/history | 获取澄清历史 | REQ-M3-003 |

### 请求/响应结构示例

#### POST /api/v1/clarify/{session_id}/respond

请求：
```json
{
  "user_response": "这是提交按钮",
  "question_id": "q1"
}
```

响应（继续澄清）：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "clarifying",
  "confidence": 0.78,
  "message": "请继续回答澄清问题",
  "updated_config": {
    "page_name": {"zh-CN": "测试页", "en": "Test Page"},
    "page_description": {"zh-CN": "说明", "en": "Desc"},
    "elements": [],
    "button_list": ["btn_submit"],
    "optional_actions": [],
    "ai_context": {},
    "overall_confidence": 0.78,
    "clarification_needed": true
  },
  "next_questions": [
    {
      "question_id": "q2",
      "question_text": "是否需要返回按钮？",
      "context": "button_list",
      "options": ["需要", "不需要"]
    }
  ]
}
```

响应（完成）：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "completed",
  "confidence": 0.91,
  "message": "配置已生成，请查看右侧表单",
  "updated_config": {
    "page_name": {"zh-CN": "测试页", "en": "Test Page"},
    "page_description": {"zh-CN": "说明", "en": "Desc"},
    "elements": [],
    "button_list": ["btn_submit"],
    "optional_actions": [],
    "ai_context": {},
    "overall_confidence": 0.91,
    "clarification_needed": false
  },
  "next_questions": null
}
```

#### POST /api/v1/clarify/{session_id}/confirm

请求：
```json
{
  "confirm": true
}
```

响应：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "status": "completed",
  "message": "配置已确认完成",
  "final_config": {
    "page_name": {"zh-CN": "测试页", "en": "Test Page"},
    "page_description": {"zh-CN": "说明", "en": "Desc"},
    "elements": [],
    "button_list": ["btn_submit"],
    "optional_actions": [],
    "ai_context": {},
    "overall_confidence": 0.91,
    "clarification_needed": false
  }
}
```

#### GET /api/v1/clarify/{session_id}/history

响应：
```json
{
  "session_id": "e7b3c3b5-3b6d-4e3f-9b1e-3b0c2c9b1b2a",
  "history": [
    {
      "question": "确认按钮用途？",
      "answer": "提交",
      "timestamp": "2026-01-06T12:00:00Z"
    }
  ],
  "current_questions": [
    {
      "question_id": "q2",
      "question_text": "是否需要返回按钮？",
      "context": "button_list",
      "options": ["需要", "不需要"]
    }
  ]
}
```

### API 实现

```python
# app/api/v1/clarify.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.parse_session import ParseSession
from app.services.vl_model_service import VLModelService
from app.services.system_prompt_service import SystemPromptService
import asyncio
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/clarify", tags=["Clarification"])

class ClarifyRequest(BaseModel):
    user_response: str
    question_id: Optional[str] = None

class ConfirmRequest(BaseModel):
    confirm: bool = True

CONFIDENCE_THRESHOLD = 0.85  # REQ-M3-001
RESPONSE_TIMEOUT = 15.0  # REQ-M3-002
IDLE_TIMEOUT_MINUTES = 5  # REQ-M3-011
MAX_CLARIFY_ROUNDS = 5  # 最大澄清轮次

@router.post("/{session_id}/respond")
async def submit_clarify_response(
    session_id: str,
    request: ClarifyRequest,
    db: Session = Depends(get_db)
):
    """
    提交澄清回答
    
    - 将用户回答发送至模型
    - 更新配置草稿
    - 判断是否需要继续澄清
    
    对应需求: REQ-M3-006, REQ-M3-007, REQ-M3-010
    """
    session = db.query(ParseSession).filter(
        ParseSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status not in ["clarifying", "pending"]:
        raise HTTPException(status_code=400, detail="当前状态不支持澄清")
    
    # 获取系统提示词和 VL 服务
    prompt_service = SystemPromptService(db)
    system_prompt = prompt_service.get_current_prompt()
    vl_service = VLModelService()
    
    # 更新澄清历史
    clarify_history = session.clarify_history or []
    current_questions = session.current_questions or []
    
    if current_questions:
        clarify_history.append({
            "question": current_questions[0] if isinstance(current_questions[0], str) 
                       else current_questions[0].get("question_text", ""),
            "answer": request.user_response,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    try:
        # REQ-M3-002: 15秒超时
        # REQ-M3-010: 超时重试
        retry_count = 0
        max_retries = 1
        
        while retry_count <= max_retries:
            try:
                updated_result = await asyncio.wait_for(
                    vl_service.clarify(
                        image_url=session.image_path,
                        previous_result=session.parse_result,
                        clarify_history=clarify_history,
                        user_response=request.user_response,
                        system_prompt=system_prompt.prompt_content
                    ),
                    timeout=RESPONSE_TIMEOUT
                )
                break
            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count > max_retries:
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": "CLARIFY_TIMEOUT",
                            "message": "请手动完善配置或稍后重试",
                            "retry": False
                        }
                    )
        
        # 更新会话
        session.current_questions = updated_result.clarification_questions or []
        session.parse_result = updated_result.dict(exclude={"clarification_questions"})
        session.clarify_history = clarify_history
        session.confidence = updated_result.overall_confidence
        
        # REQ-M3-001/007: 判断是否结束澄清
        clarify_rounds = len(clarify_history)
        
        if updated_result.overall_confidence >= CONFIDENCE_THRESHOLD:
            session.status = "completed"
            message = "配置已生成，请查看右侧表单"
        elif clarify_rounds >= MAX_CLARIFY_ROUNDS:
            # 达到最大轮次，强制结束
            session.status = "completed"
            message = f"已达到最大澄清轮次({MAX_CLARIFY_ROUNDS}轮)，请手动完善配置"
        elif not updated_result.clarification_needed:
            session.status = "completed"
            message = "配置已生成"
        else:
            session.status = "clarifying"
            message = f"请继续回答澄清问题 (第{clarify_rounds + 1}/{MAX_CLARIFY_ROUNDS}轮)"
        
        db.commit()
        
        return {
            "session_id": session_id,
            "status": session.status,
            "confidence": float(session.confidence),
            "message": message,
            "updated_config": updated_result.dict(),
            "next_questions": session.current_questions if session.status == "clarifying" else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"澄清处理失败: {str(e)}"
        )

@router.post("/{session_id}/confirm")
async def confirm_configuration(
    session_id: str,
    request: ConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    确认完成配置
    
    对应需求: REQ-M3-008
    """
    session = db.query(ParseSession).filter(
        ParseSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if request.confirm:
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "session_id": session_id,
            "status": "completed",
            "message": "配置已确认完成",
            "final_config": session.parse_result
        }
    else:
        return {
            "session_id": session_id,
            "status": session.status,
            "message": "继续编辑"
        }

@router.get("/{session_id}/history")
async def get_clarify_history(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    获取澄清对话历史
    
    - 前端刷新后清空展示，但服务端保留当前会话内历史
    对应需求: REQ-M3-003
    """
    session = db.query(ParseSession).filter(
        ParseSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return {
        "session_id": session_id,
        "history": session.clarify_history or [],
        "current_questions": session.current_questions if session.status == "clarifying" else None
    }
```

---

## 前端 AI 助手面板组件

```vue
<!-- components/AIAssistant/ClarifyPanel.vue -->
<template>
  <div class="clarify-panel">
    <div class="panel-header">
      <div class="assistant-info">
        <img src="@/assets/ai-avatar.png" alt="AI" class="avatar" />
        <span class="name">AI 助手</span>
        <span class="status-badge" :class="statusClass">
          {{ statusText }}
        </span>
      </div>
    </div>
    
    <div class="chat-container" ref="chatContainer">
      <!-- 初始问候 -->
      <div class="message assistant">
        <div class="bubble">
          👋 你好！我是 UI 配置助手。上传页面截图，我来帮你识别页面元素并生成配置。
        </div>
      </div>
      
      <!-- 对话历史 -->
      <template v-for="(item, index) in chatHistory" :key="index">
        <div class="message" :class="item.role">
          <div class="bubble">{{ item.content }}</div>
          <span class="timestamp">{{ formatTime(item.timestamp) }}</span>
        </div>
      </template>
      
      <!-- 当前澄清问题 -->
      <template v-if="currentQuestion">
        <div class="message assistant">
          <div class="bubble">
            {{ currentQuestion.question_text || currentQuestion }}
          </div>
          
          <!-- 快捷选项 -->
          <div v-if="currentQuestion.options" class="quick-options">
            <button
              v-for="opt in currentQuestion.options"
              :key="opt"
              class="option-btn"
              @click="selectOption(opt)"
            >
              {{ opt }}
            </button>
          </div>
        </div>
      </template>
      
      <!-- 加载状态 -->
      <div v-if="isLoading" class="message assistant">
        <div class="bubble loading">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </div>
      
      <!-- 完成提示 -->
      <div v-if="isCompleted" class="message assistant">
        <div class="bubble success">
          ✅ 配置已生成，请查看右侧表单
        </div>
      </div>
    </div>
    
    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-wrapper">
        <button class="attach-btn" title="上传图片">
          <svg viewBox="0 0 24 24"><path d="M16 6v12c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v11c0 .55-.45 1-1 1s-1-.45-1-1V6H9v10c0 1.65 1.35 3 3 3s3-1.35 3-3V5c0-2.48-2.02-4.5-4.5-4.5S6 2.52 6 5v13c0 3.31 2.69 6 6 6s6-2.69 6-6V6h-2z"/></svg>
        </button>
        <input
          ref="inputRef"
          v-model="inputText"
          type="text"
          placeholder="描述页面或上传截图..."
          :disabled="isLoading"
          @keyup.enter="sendMessage"
        />
        <button 
          class="send-btn" 
          :disabled="!inputText.trim() || isLoading"
          @click="sendMessage"
        >
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
      <div class="input-hint">
        按 Enter 发送，Shift + Enter 换行
      </div>
    </div>
    
    <!-- 操作按钮 -->
    <div v-if="showActions" class="action-buttons">
      <button 
        class="btn-complete"
        @click="confirmComplete"
        :disabled="isLoading"
      >
        完成配置
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { clarifyApi } from '@/api/clarify'

const props = defineProps({
  sessionId: String,
  parseResult: Object,
  status: String
})

const emit = defineEmits(['config-updated', 'completed'])

// 状态
const chatHistory = ref([])
const currentQuestion = ref(null)
const inputText = ref('')
const isLoading = ref(false)
const chatContainer = ref(null)

// 计算属性
const isCompleted = computed(() => props.status === 'completed')
const showActions = computed(() => props.status === 'clarifying' && !isLoading.value)

const statusClass = computed(() => ({
  'status-pending': props.status === 'pending',
  'status-parsing': props.status === 'parsing',
  'status-clarifying': props.status === 'clarifying',
  'status-completed': props.status === 'completed'
}))

const statusText = computed(() => {
  const map = {
    pending: '等待中',
    parsing: '分析中',
    clarifying: '澄清中',
    completed: '已完成'
  }
  return map[props.status] || ''
})

// 监听解析结果变化
watch(() => props.parseResult, (newResult) => {
  if (newResult?.clarification_questions?.length > 0) {
    currentQuestion.value = newResult.clarification_questions[0]
  } else {
    currentQuestion.value = null
  }
}, { immediate: true })

// 发送消息
const sendMessage = async () => {
  if (!inputText.value.trim() || isLoading.value) return
  
  const userMessage = inputText.value.trim()
  inputText.value = ''
  
  // 添加用户消息到历史
  chatHistory.value.push({
    role: 'user',
    content: userMessage,
    timestamp: new Date()
  })
  
  scrollToBottom()
  isLoading.value = true
  
  try {
    const response = await clarifyApi.submitResponse(props.sessionId, {
      user_response: userMessage
    })
    
    // 添加 AI 响应
    if (response.message) {
      chatHistory.value.push({
        role: 'assistant',
        content: response.message,
        timestamp: new Date()
      })
    }
    
    // 更新当前问题
    if (response.next_questions?.length > 0) {
      currentQuestion.value = response.next_questions[0]
    } else {
      currentQuestion.value = null
    }
    
    // 通知配置更新
    emit('config-updated', response.updated_config)
    
    if (response.status === 'completed') {
      emit('completed')
    }
    
  } catch (error) {
    chatHistory.value.push({
      role: 'assistant',
      content: `❌ ${error.response?.data?.message || '请求失败，请重试'}`,
      timestamp: new Date()
    })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

// 选择快捷选项
const selectOption = (option) => {
  inputText.value = option
  sendMessage()
}

// 确认完成
const confirmComplete = async () => {
  isLoading.value = true
  try {
    await clarifyApi.confirm(props.sessionId, { confirm: true })
    emit('completed')
  } catch (error) {
    alert('确认失败，请重试')
  } finally {
    isLoading.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// 格式化时间
const formatTime = (date) => {
  return new Date(date).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.clarify-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-left: 1px solid #e8e8e8;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
}

.assistant-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
}

.status-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}

.status-clarifying {
  background: #fff7e6;
  color: #fa8c16;
}

.status-completed {
  background: #f6ffed;
  color: #52c41a;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message {
  margin-bottom: 16px;
}

.message.user {
  text-align: right;
}

.bubble {
  display: inline-block;
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f5f5f5;
}

.message.user .bubble {
  background: #1890ff;
  color: white;
}

.bubble.loading {
  display: flex;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.quick-options {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-btn {
  padding: 6px 12px;
  border: 1px solid #1890ff;
  border-radius: 16px;
  background: white;
  color: #1890ff;
  cursor: pointer;
  font-size: 13px;
}

.option-btn:hover {
  background: #e6f7ff;
}

.input-area {
  padding: 12px 16px;
  border-top: 1px solid #e8e8e8;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f5f5;
  border-radius: 20px;
  padding: 8px 12px;
}

.input-wrapper input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
}

.send-btn, .attach-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn svg {
  width: 20px;
  height: 20px;
  fill: #1890ff;
}

.send-btn:disabled svg {
  fill: #ccc;
}

.input-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  text-align: center;
}

.action-buttons {
  padding: 12px 16px;
  border-top: 1px solid #e8e8e8;
}

.btn-complete {
  width: 100%;
  padding: 10px;
  background: #1890ff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn-complete:hover {
  background: #40a9ff;
}
</style>
```

### 冲突处理示例 (M3 ⇄ M5) - Demo 简化版

Demo 版本采用简单的 `isDirty` 标记判断冲突，当 AI 更新时若用户有未保存修改，弹窗提示选择：

```ts
// store/uiConfig.ts (Pinia 示例)
const useUiConfigStore = defineStore('uiConfig', {
  state: () => ({
    draftConfig: {},
    isDirty: false  // 标记用户是否有未保存的修改
  }),
  actions: {
    applyUserEdit(patch) {
      this.draftConfig = { ...this.draftConfig, ...patch }
      this.isDirty = true
    },
    
    // 尝试应用 AI 更新
    tryApplyAiUpdate(aiConfig): { conflict: boolean } {
      if (this.isDirty) {
        // 有冲突，返回让 UI 层处理
        return { conflict: true }
      }
      // 无冲突，直接应用
      this.draftConfig = aiConfig
      return { conflict: false }
    },
    
    // 用户选择应用 AI 更新（覆盖手动修改）
    forceApplyAiUpdate(aiConfig) {
      this.draftConfig = aiConfig
      this.isDirty = false
    },
    
    // 用户选择保留手动修改
    keepUserEdit() {
      // 不做任何操作，保持 isDirty 状态
    }
  }
})
```

```vue
<!-- 父组件中处理 AI 更新 -->
<script setup>
import { ref } from 'vue'
import { useUiConfigStore } from '@/stores/uiConfig'

const store = useUiConfigStore()
const showConflictDialog = ref(false)
const pendingAiConfig = ref(null)

const onConfigUpdated = (aiConfig) => {
  const result = store.tryApplyAiUpdate(aiConfig)
  if (result.conflict) {
    // 保存待应用的配置，弹窗让用户选择
    pendingAiConfig.value = aiConfig
    showConflictDialog.value = true
  }
}

const handleApplyAi = () => {
  store.forceApplyAiUpdate(pendingAiConfig.value)
  showConflictDialog.value = false
}

const handleKeepMine = () => {
  store.keepUserEdit()
  showConflictDialog.value = false
}
</script>

<template>
  <!-- 冲突提示弹窗 -->
  <ConfirmDialog
    v-model:visible="showConflictDialog"
    title="配置冲突"
    message="AI 已更新配置，但您有未保存的修改。请选择："
  >
    <template #footer>
      <button @click="handleKeepMine">保留我的修改</button>
      <button @click="handleApplyAi" class="primary">应用 AI 更新</button>
    </template>
  </ConfirmDialog>
</template>
```

---

# 模块 M4: JSON Config 生成

## API 接口设计

```python
# app/api/v1/config_generator.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.database import get_db
from app.services.config_service import ConfigService
import jsonschema

router = APIRouter(prefix="/api/v1/config", tags=["Config Generator"])

# REQ-M4-001: Schema 定义
UI_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["pages"],
    "properties": {
        "pages": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_\\.]+$": {
                    "type": "object",
                    "required": ["name", "description", "buttonList"],
                    "properties": {
                        "name": {
                            "type": "object",
                            "required": ["zh-CN", "en"],
                            "properties": {
                                "zh-CN": {"type": "string"},
                                "en": {"type": "string"}
                            }
                        },
                        "description": {
                            "type": "object",
                            "required": ["zh-CN", "en"],
                            "properties": {
                                "zh-CN": {"type": "string"},
                                "en": {"type": "string"}
                            }
                        },
                        "buttonList": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1
                        },
                        "optionalActions": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            }
        }
    }
}

# REQ-M4-010: optionalActions 不做枚举限制，允许任意字符串

class GenerateConfigRequest(BaseModel):
    session_id: Optional[str] = None
    page_data: Optional[Dict[str, Any]] = None

class ValidationError(BaseModel):
    field: str
    message: str

class ConfigResponse(BaseModel):
    success: bool
    config: Optional[Dict[str, Any]] = None
    errors: Optional[List[ValidationError]] = None

@router.post("/generate", response_model=ConfigResponse)
async def generate_config(
    request: GenerateConfigRequest,
    db: Session = Depends(get_db)
):
    """
    生成 JSON Config
    
    对应需求: REQ-M4-003, REQ-M4-004, REQ-M4-007, REQ-M4-008
    """
    service = ConfigService(db)
    
    # 获取页面数据
    if request.session_id:
        page_data = service.get_from_session(request.session_id)
    else:
        page_data = request.page_data
    
    if not page_data:
        raise HTTPException(status_code=400, detail="缺少配置数据")
    
    # 构建配置
    config = service.build_config(page_data)
    
    # REQ-M4-004, REQ-M4-007: Schema 验证
    errors = service.validate_config(config)
    
    if errors:
        return ConfigResponse(
            success=False,
            config=config,
            errors=errors
        )
    
    return ConfigResponse(
        success=True,
        config=config,
        errors=None
    )

@router.post("/validate")
async def validate_config(config: Dict[str, Any]):
    """
    验证 JSON Config 格式
    
    对应需求: REQ-M4-007
    """
    try:
        jsonschema.validate(config, UI_CONFIG_SCHEMA)
        return {"valid": True, "errors": []}
    except jsonschema.ValidationError as e:
        return {
            "valid": False,
            "errors": [{
                "field": ".".join(str(p) for p in e.path),
                "message": e.message
            }]
        }
```

---

# 模块 M5: 可视化配置编辑

## 前端编辑器组件

```vue
<!-- components/PageConfig/ConfigEditor.vue -->
<template>
  <div class="config-editor">
    <!-- 基本信息区 -->
    <section class="section">
      <h3 class="section-title">基本信息</h3>
      
      <div class="form-row">
        <div class="form-item">
          <label>页面名称 (中文) <span class="required">*</span></label>
          <input 
            v-model="localConfig.name['zh-CN']"
            type="text"
            :class="{ error: errors.name_zh }"
            @input="markDirty"
          />
          <span v-if="errors.name_zh" class="error-text">{{ errors.name_zh }}</span>
        </div>
        
        <div class="form-item">
          <label>Page Name (EN) <span class="required">*</span></label>
          <input 
            v-model="localConfig.name.en"
            type="text"
            :class="{ error: errors.name_en }"
            @input="markDirty"
          />
          <span v-if="errors.name_en" class="error-text">{{ errors.name_en }}</span>
        </div>
      </div>
      
      <div class="form-item">
        <label>英文标识 <span class="required">*</span></label>
        <input 
          v-model="localConfig.page_id"
          type="text"
          pattern="[a-zA-Z0-9_\.]+"
          :class="{ error: errors.page_id }"
          @input="markDirty"
        />
        <span class="hint">格式: snake_case 或 dot.notation</span>
      </div>
      
      <div class="form-row">
        <div class="form-item full">
          <label>页面描述 (中文)</label>
          <textarea 
            v-model="localConfig.description['zh-CN']"
            rows="3"
            @input="markDirty"
          ></textarea>
        </div>
      </div>
    </section>
    
    <!-- 页面能力区 -->
    <section class="section">
      <h3 class="section-title">页面能力</h3>
      
      <div class="form-item">
        <label>可点击按钮</label>
        <div class="list-editor">
          <div 
            v-for="(btn, index) in localConfig.buttonList" 
            :key="index"
            class="list-item"
          >
            <input 
              v-model="localConfig.buttonList[index]"
              type="text"
              placeholder="按钮 ID"
              @input="markDirty"
            />
            <button 
              class="btn-remove"
              @click="removeButton(index)"
              :disabled="localConfig.buttonList.length <= 1"
              :title="localConfig.buttonList.length <= 1 ? '至少保留一个按钮' : '删除'"
            >
              ✕
            </button>
          </div>
          
          <button class="btn-add" @click="addButton">
            + 添加按钮
          </button>
        </div>
        <span v-if="errors.buttonList" class="error-text">{{ errors.buttonList }}</span>
      </div>
      
      <div class="form-item">
        <label>可选操作</label>
        <div class="list-editor">
          <div 
            v-for="(action, index) in localConfig.optionalActions" 
            :key="index"
            class="list-item"
          >
            <input 
              v-model="localConfig.optionalActions[index]"
              type="text"
              placeholder="操作 ID"
              @input="markDirty"
            />
            <button class="btn-remove" @click="removeAction(index)">✕</button>
          </div>
          
          <button class="btn-add" @click="addAction">
            + 添加操作
          </button>
        </div>
      </div>
    </section>
    
    <!-- AI 上下文区 -->
    <section class="section">
      <h3 class="section-title">AI 上下文</h3>
      
      <div class="form-item">
        <label>行为规则</label>
        <textarea 
          v-model="localConfig.ai_context.behavior_rules"
          rows="3"
          placeholder="定义 AI 在此页面的行为规则..."
          @input="markDirty"
        ></textarea>
      </div>
      
      <div class="form-item">
        <label>页面目标</label>
        <textarea 
          v-model="localConfig.ai_context.page_goal"
          rows="2"
          placeholder="定义 AI 应该达成的目标..."
          @input="markDirty"
        ></textarea>
      </div>
    </section>
    
    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="status">
        <span v-if="isDirty" class="unsaved-badge">未保存</span>
        <span v-if="lastSaved" class="last-saved">
          距上次保存: {{ formatTimeAgo(lastSaved) }}
        </span>
      </div>
      
      <div class="actions">
        <button class="btn-secondary" @click="resetForm" :disabled="!isDirty">
          重置
        </button>
        <button 
          class="btn-primary" 
          @click="saveConfig"
          :disabled="!isDirty || hasErrors || isSaving"
        >
          {{ isSaving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { configApi } from '@/api/config'
import { cloneDeep, isEqual } from 'lodash'

const props = defineProps({
  config: Object,
  sessionId: String
})

const emit = defineEmits(['saved', 'config-changed'])

// 状态
const localConfig = reactive({
  page_id: '',
  name: { 'zh-CN': '', en: '' },
  description: { 'zh-CN': '', en: '' },
  buttonList: [''],
  optionalActions: [],
  ai_context: { behavior_rules: '', page_goal: '' }
})

const originalConfig = ref(null)
const errors = reactive({})
const isDirty = ref(false)
const isSaving = ref(false)
const lastSaved = ref(null)

// 计算属性
const hasErrors = computed(() => Object.keys(errors).length > 0)

// 初始化
onMounted(() => {
  if (props.config) {
    Object.assign(localConfig, cloneDeep(props.config))
    originalConfig.value = cloneDeep(props.config)
  }
})

// 监听配置变化
watch(() => props.config, (newConfig) => {
  if (newConfig && !isDirty.value) {
    Object.assign(localConfig, cloneDeep(newConfig))
    originalConfig.value = cloneDeep(newConfig)
  }
}, { deep: true })

// 标记为已修改
const markDirty = () => {
  isDirty.value = !isEqual(localConfig, originalConfig.value)
  validateForm()
  emit('config-changed', localConfig)
}

// 验证表单 (REQ-M4-008)
const validateForm = () => {
  Object.keys(errors).forEach(key => delete errors[key])
  
  if (!localConfig.name['zh-CN']?.trim()) {
    errors.name_zh = '此字段为必填项'
  }
  if (!localConfig.name.en?.trim()) {
    errors.name_en = '此字段为必填项'
  }
  if (!localConfig.page_id?.trim()) {
    errors.page_id = '此字段为必填项'
  } else if (!/^[a-zA-Z0-9_\.]+$/.test(localConfig.page_id)) {
    errors.page_id = '只能包含字母、数字、下划线和点'
  }
}

// 添加/删除按钮 (REQ-M5-005, REQ-M5-006, REQ-M5-009)
const addButton = () => {
  localConfig.buttonList.push('')
  markDirty()
}

const removeButton = (index) => {
  // REQ-M5-009: 至少保留一个按钮
  if (localConfig.buttonList.length <= 1) {
    alert('至少保留一个按钮配置')
    return
  }
  localConfig.buttonList.splice(index, 1)
  markDirty()
}

const addAction = () => {
  localConfig.optionalActions.push('')
  markDirty()
}

const removeAction = (index) => {
  localConfig.optionalActions.splice(index, 1)
  markDirty()
}

// 保存配置 (REQ-M5-007)
const saveConfig = async () => {
  validateForm()
  if (hasErrors.value) return
  
  isSaving.value = true
  
  try {
    const response = await configApi.generate({
      session_id: props.sessionId,
      page_data: localConfig
    })
    
    if (response.success) {
      originalConfig.value = cloneDeep(localConfig)
      isDirty.value = false
      lastSaved.value = new Date()
      emit('saved', response.config)
    } else {
      // 显示验证错误
      response.errors?.forEach(err => {
        errors[err.field] = err.message
      })
    }
  } catch (error) {
    alert('保存失败，请重试')
  } finally {
    isSaving.value = false
  }
}

// 重置表单
const resetForm = () => {
  if (originalConfig.value) {
    Object.assign(localConfig, cloneDeep(originalConfig.value))
    isDirty.value = false
    Object.keys(errors).forEach(key => delete errors[key])
  }
}

// 格式化时间
const formatTimeAgo = (date) => {
  const seconds = Math.floor((new Date() - date) / 1000)
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}分钟`
  const hours = Math.floor(minutes / 60)
  return `${hours}小时`
}
</script>

<style scoped>
.config-editor {
  padding: 20px;
}

.section {
  margin-bottom: 32px;
  padding: 20px;
  background: #fafafa;
  border-radius: 8px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #333;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-item {
  flex: 1;
  margin-bottom: 16px;
}

.form-item.full {
  flex: 1 1 100%;
}

.form-item label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #666;
}

.required {
  color: #ff4d4f;
}

.form-item input,
.form-item textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-size: 14px;
}

.form-item input:focus,
.form-item textarea:focus {
  border-color: #1890ff;
  outline: none;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.form-item input.error {
  border-color: #ff4d4f;
}

.error-text {
  color: #ff4d4f;
  font-size: 12px;
  margin-top: 4px;
}

.hint {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}

.list-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-item {
  display: flex;
  gap: 8px;
}

.list-item input {
  flex: 1;
}

.btn-remove {
  width: 32px;
  height: 32px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  color: #ff4d4f;
}

.btn-remove:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-add {
  padding: 8px 16px;
  border: 1px dashed #d9d9d9;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  color: #1890ff;
}

.btn-add:hover {
  border-color: #1890ff;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 20px;
  border-top: 1px solid #e8e8e8;
}

.status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.unsaved-badge {
  padding: 4px 8px;
  background: #fff7e6;
  color: #fa8c16;
  border-radius: 4px;
  font-size: 12px;
}

.last-saved {
  color: #999;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 12px;
}

.btn-primary,
.btn-secondary {
  padding: 8px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background: #1890ff;
  color: white;
  border: none;
}

.btn-primary:hover {
  background: #40a9ff;
}

.btn-primary:disabled {
  background: #d9d9d9;
  cursor: not-allowed;
}

.btn-secondary {
  background: white;
  border: 1px solid #d9d9d9;
}

.btn-secondary:hover {
  border-color: #1890ff;
  color: #1890ff;
}
</style>
```

---

# 模块 M6: MCP 服务器管理

## 模块定位

MCP（Model Context Protocol）是模型上下文协议，用于扩展 AI 模型的能力。

**在本系统中的作用**：
- 预留扩展接口，后续可对接外部知识库、工具调用等
- Context7 预置服务器可用于获取页面相关的业务文档，增强解析准确性

**Demo 版本说明**：
- MCP 功能为预留扩展，VL 解析流程当前不强依赖 MCP
- 权限不做额外控制，默认用户均可管理 MCP 配置
- 后续可在 VL 模型调用时集成 MCP 工具调用

## API 接口设计

```python
# app/api/v1/mcp.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from app.database import get_db
from app.models.mcp_server import MCPServer
import json
import httpx
import asyncio

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Server"])

# REQ-M6-001: 预制 Context7 配置
PRESET_MCP_SERVERS = {
    "context7": {
        "name": "Context7",
        "description": "通用上下文管理 MCP 服务器",
        "server_url": "https://mcp.context7.io",
        "tools": ["search", "retrieve", "store"],
        "is_preset": True
    }
}

class MCPServerConfig(BaseModel):
    name: str
    server_url: str
    health_check_path: Optional[str] = "/health"
    auth_type: Optional[str] = "none"  # none, api_key, oauth
    auth_config: Optional[Dict[str, str]] = None
    tools: List[str] = []
    description: Optional[str] = None

class MCPServerResponse(BaseModel):
    id: int
    name: str
    server_url: str
    status: str  # enabled, disabled, error
    tools: List[str]
    is_preset: bool
    last_check: Optional[str]

@router.get("", response_model=List[MCPServerResponse])
async def list_mcp_servers(db: Session = Depends(get_db)):
    """
    获取 MCP 服务器列表
    
    对应需求: REQ-M6-004
    """
    servers = db.query(MCPServer).all()
    
    # 添加预制服务器
    result = []
    for key, preset in PRESET_MCP_SERVERS.items():
        # 检查是否已有用户配置
        existing = next((s for s in servers if s.preset_key == key), None)
        if existing:
            result.append(MCPServerResponse(
                id=existing.id,
                name=preset["name"],
                server_url=preset["server_url"],
                status=existing.status,
                tools=preset["tools"],
                is_preset=True,
                last_check=existing.last_check.isoformat() if existing.last_check else None
            ))
        else:
            result.append(MCPServerResponse(
                id=0,
                name=preset["name"],
                server_url=preset["server_url"],
                status="disabled",
                tools=preset["tools"],
                is_preset=True,
                last_check=None
            ))
    
    # 添加自定义服务器
    for server in servers:
        if not server.preset_key:
            result.append(MCPServerResponse(
                id=server.id,
                name=server.name,
                server_url=server.server_url,
                status=server.status,
                tools=server.tools or [],
                is_preset=False,
                last_check=server.last_check.isoformat() if server.last_check else None
            ))
    
    return result

@router.post("/{preset_key}/toggle")
async def toggle_preset_server(
    preset_key: str,
    enable: bool,
    db: Session = Depends(get_db)
):
    """
    启用/禁用预制 MCP 服务器
    
    对应需求: REQ-M6-005
    """
    if preset_key not in PRESET_MCP_SERVERS:
        raise HTTPException(status_code=404, detail="预制服务器不存在")
    
    existing = db.query(MCPServer).filter(
        MCPServer.preset_key == preset_key
    ).first()
    
    if not existing:
        # 创建配置记录
        existing = MCPServer(
            preset_key=preset_key,
            name=PRESET_MCP_SERVERS[preset_key]["name"],
            server_url=PRESET_MCP_SERVERS[preset_key]["server_url"],
            tools=PRESET_MCP_SERVERS[preset_key]["tools"],
            status="enabled" if enable else "disabled"
        )
        db.add(existing)
    else:
        existing.status = "enabled" if enable else "disabled"
    
    db.commit()
    
    return {"success": True, "status": existing.status}

@router.post("/upload")
async def upload_mcp_config(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传 MCP 配置文件
    
    对应需求: REQ-M6-006, REQ-M6-007, REQ-M6-011, REQ-M6-012
    """
    # REQ-M6-003: 文件大小限制
    content = await file.read()
    if len(content) > 1 * 1024 * 1024:  # 1MB
        raise HTTPException(status_code=400, detail="配置文件不能超过 1MB")
    
    # REQ-M6-011: JSON 格式验证
    try:
        config = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_JSON",
                "message": "文件格式错误，请上传有效的 JSON 文件"
            }
        )
    
    # 验证必需字段
    if "server_url" not in config:
        raise HTTPException(status_code=400, detail="缺少 server_url 字段")
    if "tools" not in config:
        raise HTTPException(status_code=400, detail="缺少 tools 字段")
    
    # REQ-M6-013: 检查是否重复
    existing = db.query(MCPServer).filter(
        MCPServer.server_url == config["server_url"],
        MCPServer.preset_key == None
    ).first()
    
    if existing:
        return {
            "warning": "duplicate",
            "message": "该服务器已存在，是否覆盖现有配置？",
            "existing_id": existing.id
        }
    
    # REQ-M6-012: 连通性测试
    connectivity_ok = await test_server_connectivity(
        config["server_url"],
        config.get("health_check_path") or "/health"
    )
    
    # 保存配置
    server = MCPServer(
        name=config.get("name", "自定义 MCP"),
        server_url=config["server_url"],
        tools=config["tools"],
        auth_type=config.get("auth_type", "none"),
        auth_config=config.get("auth_config"),
        status="enabled" if connectivity_ok else "error"
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    
    response = {
        "success": True,
        "id": server.id,
        "connectivity": connectivity_ok
    }
    
    if not connectivity_ok:
        response["warning"] = "服务器连接失败，配置已保存但可能无法正常使用"
    
    return response

async def test_server_connectivity(url: str, health_check_path: str) -> bool:
    """
    测试 MCP 服务器连通性
    
    对应需求: REQ-M6-012, REQ-M6-015
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url}{health_check_path}")
            return response.status_code == 200
    except Exception:
        return False

@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: int,
    db: Session = Depends(get_db)
):
    """
    删除自定义 MCP 服务器
    
    对应需求: REQ-M6-010
    """
    server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
    
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    
    if server.preset_key:
        raise HTTPException(status_code=400, detail="不能删除预制服务器")
    
    db.delete(server)
    db.commit()
    
    return {"success": True}
```

---

## 验收清单汇总

### M3 验收清单

| 需求编号 | 验收标准 | 测试方法 |
|----------|----------|----------|
| REQ-M3-001 | 置信度≥85%或达到5轮时自动结束澄清 | 单元测试 |
| REQ-M3-002 | 单轮响应≤15秒 | 性能测试 |
| REQ-M3-003 | 对话历史正确保存 | E2E 测试 |
| REQ-M3-004 | 自动触发澄清流程 | E2E 测试 |
| REQ-M3-006 | 用户回答正确处理 | 集成测试 |
| REQ-M3-007 | 置信度阈值判断正确 | 单元测试 |
| REQ-M3-008 | 确认后锁定配置 | E2E 测试 |
| REQ-M3-010 | 超时重试机制生效 | 模拟测试 |
| ~~REQ-M3-012~~ | ~~字段修改触发上下文更新~~ | *Demo 简化* |
| REQ-M3-013 | 冲突时提示并选择（isDirty 标记） | E2E 测试 |
| REQ-M3-014 | 澄清历史作为单一事实来源 | 单元测试 |

### M4 验收清单

| 需求编号 | 验收标准 | 测试方法 |
|----------|----------|----------|
| REQ-M4-001 | JSON 符合 Schema 结构 | 单元测试 |
| REQ-M4-003 | 正确生成 JSON Config | 单元测试 |
| REQ-M4-004 | Schema 验证通过后显示预览 | E2E 测试 |
| REQ-M4-007 | 验证失败高亮错误字段 | E2E 测试 |
| REQ-M4-008 | 必填字段为空时显示提示 | E2E 测试 |
| REQ-M4-009 | buttonList 至少 1 项 | E2E 测试 |
| REQ-M4-010 | optionalActions 允许任意字符串 | 单元测试 |

### M5 验收清单

| 需求编号 | 验收标准 | 测试方法 |
|----------|----------|----------|
| REQ-M5-001 | 表格+列表形式展示 | E2E 测试 |
| REQ-M5-002 | 手动保存模式 | E2E 测试 |
| REQ-M5-003 | 所有字段正确展示 | E2E 测试 |
| REQ-M5-005 | 添加按钮功能正常 | E2E 测试 |
| REQ-M5-006 | 删除按钮功能正常 | E2E 测试 |
| REQ-M5-007 | 保存后重新生成 JSON | E2E 测试 |
| REQ-M5-008 | 未保存标记正确显示 | E2E 测试 |
| REQ-M5-009 | 最后一个按钮不可删除 | E2E 测试 |

### M6 验收清单

| 需求编号 | 验收标准 | 测试方法 |
|----------|----------|----------|
| REQ-M6-001 | Context7 预制配置可用 | E2E 测试 |
| REQ-M6-002 | JSON 上传和代码编辑均支持 | E2E 测试 |
| REQ-M6-003 | 文件大小限制 1MB | 单元测试 |
| REQ-M6-004 | 列表正确展示预制和自定义 | E2E 测试 |
| REQ-M6-005 | 启用/禁用开关生效 | E2E 测试 |
| REQ-M6-007 | 上传验证流程正确 | 集成测试 |
| REQ-M6-011 | 非法 JSON 拒绝上传 | 单元测试 |
| REQ-M6-012 | 连通性测试正确执行 | 模拟测试 |
| REQ-M6-013 | 重复服务器提示覆盖 | E2E 测试 |
| REQ-M6-015 | 自定义健康检查路径 | 单元测试 |
