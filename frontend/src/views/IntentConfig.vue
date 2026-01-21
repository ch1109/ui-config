<template>
  <div class="intent-config-container">
    <!-- 顶部右上角组织标识 -->
    <header class="top-header">
      <div class="org-badge">重庆银行</div>
    </header>

    <!-- 主体内容区 -->
    <div class="main-content">
      <!-- 页面标题栏 -->
      <div class="page-header">
        <div class="header-left">
          <div class="header-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 12h6M9 16h6M17 21H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
          </div>
          <div class="header-info">
            <h1>意图配置</h1>
            <span class="org-info">Org: 708 · {{ filteredIntents.length }}条</span>
          </div>
        </div>

        <div class="header-center">
          <div class="search-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
              <circle cx="11" cy="11" r="8"/>
              <path d="M21 21l-4.35-4.35"/>
            </svg>
            <input 
              v-model="searchQuery"
              type="text"
              placeholder="按 ID / 描述 搜索"
              class="search-input"
            />
          </div>
        </div>

        <div class="header-right">
          <button class="action-btn" @click="handleAdd">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 4v16m-8-8h16"/>
            </svg>
            新增
          </button>
          <button class="action-btn" @click="handlePull">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3v12m0 0l-4-4m4 4l4-4"/>
              <path d="M3 15v4a2 2 0 002 2h14a2 2 0 002-2v-4"/>
            </svg>
            拉取
          </button>
          <button class="action-btn primary-btn" @click="handlePush">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 19V7m0 0l-4 4m4-4l4 4"/>
              <path d="M5 12H3a2 2 0 00-2 2v5a2 2 0 002 2h18a2 2 0 002-2v-5a2 2 0 00-2-2h-2"/>
            </svg>
            推送
          </button>
        </div>
      </div>

      <!-- 意图卡片列表 -->
      <div class="intent-grid">
        <article 
          v-for="intent in filteredIntents" 
          :key="intent.id"
          class="intent-card"
          @click="handleEdit(intent)"
        >
          <div class="card-header">
            <h3 class="card-title">{{ intent.id }}</h3>
            <div class="card-actions">
              <button class="card-action-btn copy" @click.stop="handleCopy(intent)" title="复制">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
              </button>
              <button class="card-action-btn delete" @click.stop="handleDelete(intent)" title="删除">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="card-content">
            <p class="card-description">{{ intent.description }}</p>
            <span v-if="intent.hasMore" class="more-indicator">...</span>
          </div>
        </article>
      </div>
    </div>

    <!-- 新增/编辑意图弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingIntent ? '编辑意图配置' : '新建意图配置'"
      :width="640"
      :footer="null"
      :destroyOnClose="true"
      class="intent-modal"
    >
      <div class="intent-form">
        <p class="form-description">仅管理 IntentionConfig（promptId -> 描述文本），不涉及 template/tools。</p>
        
        <div class="form-group">
          <label>promptId</label>
          <a-input 
            v-model:value="intentForm.id" 
            placeholder="请输入意图 ID，例如：comprehension"
            :maxlength="100"
            :disabled="!!editingIntent"
          />
        </div>
        <div class="form-group">
          <label>描述文本</label>
          <a-textarea 
            v-model:value="intentForm.description" 
            placeholder="请输入意图的详细描述"
            :rows="14"
            :maxlength="10000"
            class="description-textarea"
          />
        </div>
        <div class="form-actions">
          <a-button @click="modalVisible = false">取消</a-button>
          <a-button type="primary" :loading="saving" @click="saveIntent">
            保存
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, createVNode } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

// 搜索
const searchQuery = ref('')

// 弹窗状态
const modalVisible = ref(false)
const editingIntent = ref(null)
const saving = ref(false)
const intentForm = ref({
  id: '',
  description: ''
})

// 意图数据（四个预设意图）
const intents = ref([
  {
    id: 'comprehension',
    description: `一、背景 用户在签署《银信通服务协议》时，需要AI助手提供即时的阅读理解帮助。 二、意图分类（10类） 1. 协议概要理解 定义：了解协议整体内容和核心要点 典型问题：这个协议讲什么？银信通是什么服务？能总结一下吗？ 关键词：总结、概括、主要、核心、是什么、讲什么 2. 费用收费查询 定义：查询收费标准、扣费时间、退费规则 典型问题：怎么收费？多少钱？什么时候扣费？可以退款吗？ 关键词：收费、费用、价格、扣费、退费、多少钱、免费 3. 权利义务查询 定义：明确用户和银行各自的权利、义务和责任 典型问题：我有什么权利？银行的责任是什么？我需要做什么？ 关键词：权利、义务、责任、甲方、乙方、双方 4. 风险提示理解 定义：了解使用服务的风险和注意事项 典型问题：有什么风险？需要注意什么？为什么加粗这些内容？ 关键词：风险、注意、损失、加粗、重点、问题 5. 服务变更操作 定义：如何修改设置、变更信息或取消服务 典型问题：怎么修改手机号？如何取消服务？可以改绑定账户吗？ 关键词：修改、变更、取消、解约、怎么操作、设置 6. 条款细节解释 定义：解释特定术语、条款或规则 典型问题：什么是通知起点金额？协议什么时候生效？ 关键词：什么是、什么意思、怎么理解、为什么 7. 场景化问题咨询 定义：基于具体使用场景的实际问题 典型问题：手机丢了怎么办？换手机号需要做什么？收不到短信找谁？ 关键词：如果、万一、怎么办、手机丢了、换号了、收不到 8. 信息安全关注 定义：关心个人信息收集、使用和安全保护 典型问题：我的信息安全吗？银行会收集哪些信息？会泄露吗？ 关键词：信息安全、隐私、个人信息、泄露、保护 9. 协议对比查询 定义：了解当前协议与其他版本的区别 典型问题：这个协议和之前的有什么不同？更新了什么？ 关键词：区别、不同、变化、之前、对比、更新 10. 投诉建议 定义：提出意见、建议或投诉 典型问题：我要投诉、有意见要反馈、怎么联系你们？ 关键词：投诉、建议、意见、反馈、不满意、客服`,
    hasMore: true
  },
  {
    id: 'Dir-read-agreement',
    description: `当用户在银信通服务签约流程的"3.2 银信通-阅读协议"页面时，用户可能会提出希望AI朗读协议内容的需求。该意图旨在识别用户的朗读请求，并通过AI语音助手以清晰、有节奏的方式为用户朗读完整的《重庆银行银信通服务协议》内容，帮助用户更好地理解协议条款，特别是对于视力不便或希望通过听觉方式获取信息的用户。 触发场景： - 用户明确表达朗读需求 典型用户话术： - "朗读协议" - "帮我读一下协议" - "念一下协议内容" - "把协议读给我听" - "我想听协议内容" - "语音播放协议"`,
    hasMore: true
  },
  {
    id: 'UpdateFormLossReason',
    description: `用户意图是修改当前挂失页面的表单内容。当前表单有挂失原因（lossReason）字段，如果用户意图是更新挂失原因，包括新增、修改、删除该字段的内容，都属于UpdateFormLossReason意图。

例子：
- 卡丢了、卡片丢失、找不到了
- 被偷了、卡被人偷走了、被盗
- 卡坏了、刷不出来、读不了
- 密码忘了、忘记密码、不记得密码了
- 被ATM吞了、机器吞卡了
- 想换新卡、卡太旧了
- 卡被洗衣机洗了（自由描述的原因）
- 修改原因为卡片损坏、把原因改成被盗
- 删除挂失原因、清空原因
表达修改意愿的用词可能有：原因是、因为、挂失原因、修改为、改成、删除、清空、清除

以下内容则不属于UpdateFormLossReason意图：
1. 纯粹的询问类语句，例如：什么是挂失？挂失有什么用？
2. 导航操作指令，例如：返回首页、取消挂失
3. 功能操作指令，例如：确认挂失、提交申请
4. 模糊的表达，不包含具体原因，例如：我要挂失、帮我办理挂失`,
    hasMore: true
  },
  {
    id: 'UpdateFormCancelAccount',
    description: `用户意图是修改当前转账页面的表单内容。当前表单有收款人账号（payeeAccount）、银行名称（bankName）、收款人姓名（payeeName）三个字段，如果用户意图是更新表单内容，包括新增、修改、删除某个字段的内容，都属于UpdateForm意图。

例子：
- 账号是6222021234567890、卡号6222开头的
- 转到工行、银行是建设银行、收款银行改成农行
- 收款人是张三、把姓名改成李明明、户名王小二
- 删除账号、清空收款人、全部清空
表达修改意愿的用词可能有：xx是xx、修改为、设置为、改成、删除、清空、清除、重置、全部清空、全部删除、转给、转到

以下内容则不属于UpdateForm意图：
1. 纯粹的询问类语句，例如：什么是收款人账号？开户行是什么意思？
2. 导航操作指令，例如：返回首页、取消转账
3. 功能操作指令，例如：确认转账、提交
4. 模糊的表达，不包含具体数据值，例如：我想修改收款信息、帮我改一下`,
    hasMore: false
  }
])

// 过滤后的意图
const filteredIntents = computed(() => {
  if (!searchQuery.value) {
    return intents.value
  }
  const query = searchQuery.value.toLowerCase()
  return intents.value.filter(intent => 
    intent.id.toLowerCase().includes(query) ||
    intent.description.toLowerCase().includes(query)
  )
})

// 新增意图
const handleAdd = () => {
  editingIntent.value = null
  intentForm.value = {
    id: '',
    description: ''
  }
  modalVisible.value = true
}

// 编辑意图（点击卡片）
const handleEdit = (intent) => {
  editingIntent.value = intent
  intentForm.value = {
    id: intent.id,
    description: intent.description
  }
  modalVisible.value = true
}

// 复制意图
const handleCopy = async (intent) => {
  try {
    const content = `意图ID: ${intent.id}\n\n${intent.description}`
    await navigator.clipboard.writeText(content)
    message.success('已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

// 删除意图
const handleDelete = (intent) => {
  Modal.confirm({
    title: '删除意图',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要删除意图「${intent.id}」吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk() {
      intents.value = intents.value.filter(i => i.id !== intent.id)
      message.success('删除成功')
    }
  })
}

// 保存意图
const saveIntent = async () => {
  if (!intentForm.value.id.trim()) {
    message.warning('请输入意图 ID')
    return
  }
  
  if (!intentForm.value.description.trim()) {
    message.warning('请输入意图描述')
    return
  }
  
  saving.value = true
  
  // 模拟保存延迟
  setTimeout(() => {
    if (editingIntent.value) {
      // 更新
      const index = intents.value.findIndex(i => i.id === editingIntent.value.id)
      if (index > -1) {
        intents.value[index] = {
          ...intents.value[index],
          description: intentForm.value.description,
          hasMore: intentForm.value.description.length > 200
        }
      }
      message.success('意图更新成功')
    } else {
      // 检查 ID 是否重复
      if (intents.value.some(i => i.id === intentForm.value.id)) {
        message.error('意图 ID 已存在')
        saving.value = false
        return
      }
      // 创建
      intents.value.unshift({
        id: intentForm.value.id,
        description: intentForm.value.description,
        hasMore: intentForm.value.description.length > 200
      })
      message.success('意图创建成功')
    }
    modalVisible.value = false
    saving.value = false
  }, 300)
}

// 拉取
const handlePull = () => {
  message.info('拉取功能开发中...')
}

// 推送
const handlePush = () => {
  message.info('推送功能开发中...')
}
</script>

<style lang="scss" scoped>
// 颜色变量
$primary: #6366f1;
$primary-light: rgba(99, 102, 241, 0.1);
$primary-dark: #4f46e5;
$success: #22c55e;
$error: #ef4444;

$text-primary: #1e293b;
$text-secondary: #475569;
$text-muted: #94a3b8;
$border-color: #e2e8f0;
$border-light: #f1f5f9;
$bg-body: #f8fafc;
$bg-elevated: #ffffff;
$bg-subtle: #f1f5f9;

.intent-config-container {
  min-height: 100vh;
  background: $bg-body;
}

// 顶部 Header
.top-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 12px 24px;
  background: $bg-elevated;
  border-bottom: 1px solid $border-color;

  .org-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
    color: $primary;
    background: transparent;

    &::before {
      content: '';
      display: inline-block;
      width: 8px;
      height: 8px;
      background: $primary;
      border-radius: 50%;
    }
  }
}

// 主体内容
.main-content {
  padding: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

// 页面标题栏
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $bg-elevated;
  border: 1px solid $border-color;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-icon {
    width: 44px;
    height: 44px;
    background: $primary-light;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 22px;
      height: 22px;
      color: $primary;
    }
  }

  .header-info {
    h1 {
      font-size: 16px;
      font-weight: 600;
      color: $text-primary;
      margin: 0 0 2px 0;
      line-height: 1.3;
    }

    .org-info {
      font-size: 12px;
      color: $text-muted;
    }
  }

  .header-center {
    flex: 1;
    max-width: 480px;
    margin: 0 24px;
  }

  .search-wrapper {
    position: relative;

    .search-icon {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      width: 16px;
      height: 16px;
      color: $text-muted;
      pointer-events: none;
    }

    .search-input {
      width: 100%;
      height: 42px;
      padding: 0 16px 0 42px;
      font-size: 14px;
      background: $bg-subtle;
      border: 1px solid transparent;
      border-radius: 10px;
      outline: none;
      transition: all 0.2s;

      &::placeholder {
        color: $text-muted;
      }

      &:focus {
        background: $bg-elevated;
        border-color: $primary;
        box-shadow: 0 0 0 3px $primary-light;
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 500;
    color: $text-secondary;
    background: $bg-elevated;
    border: 1px solid $border-color;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 16px;
      height: 16px;
    }

    &:hover {
      border-color: $primary;
      color: $primary;
      background: $primary-light;
    }

    &.primary-btn {
      background: $primary;
      border-color: $primary;
      color: white;

      &:hover {
        background: $primary-dark;
        border-color: $primary-dark;
      }
    }
  }
}

// 意图卡片网格
.intent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 20px;
}

.intent-card {
  background: $bg-elevated;
  border: 1px solid $border-color;
  border-radius: 12px;
  padding: 20px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    border-color: rgba(99, 102, 241, 0.3);

    .card-actions {
      opacity: 1;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
    margin: 0;
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  }

  .card-actions {
    display: flex;
    gap: 6px;
    opacity: 0;
    transition: opacity 0.2s;
  }

  .card-action-btn {
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 8px;
    background: $bg-subtle;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;

    svg {
      width: 15px;
      height: 15px;
      color: $text-muted;
    }

    &.copy:hover {
      background: $primary-light;
      
      svg {
        color: $primary;
      }
    }

    &.delete:hover {
      background: rgba(239, 68, 68, 0.1);
      
      svg {
        color: $error;
      }
    }
  }

  .card-content {
    position: relative;
  }

  .card-description {
    font-size: 13px;
    line-height: 1.7;
    color: $text-secondary;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .more-indicator {
    display: block;
    font-size: 13px;
    color: $text-muted;
    margin-top: 4px;
  }
}

// 弹窗表单样式
.intent-form {
  .form-description {
    font-size: 13px;
    color: $text-muted;
    margin: 0 0 20px 0;
    padding-bottom: 16px;
    border-bottom: 1px solid $border-light;
  }

  .form-group {
    margin-bottom: 18px;

    label {
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: $text-primary;
      margin-bottom: 8px;
    }

    .form-hint {
      font-size: 11px;
      color: $text-muted;
      margin: 4px 0 0 0;
    }
  }

  .description-textarea {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 24px;
    padding-top: 18px;
    border-top: 1px solid $border-light;
  }
}

// 响应式适配
@media (max-width: 960px) {
  .page-header {
    flex-wrap: wrap;
    gap: 16px;

    .header-center {
      order: 3;
      flex: 1 0 100%;
      max-width: 100%;
      margin: 0;
    }
  }

  .intent-grid {
    grid-template-columns: 1fr;
  }
}
</style>
