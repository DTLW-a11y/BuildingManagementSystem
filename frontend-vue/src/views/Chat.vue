<template>
  <div class="chat-back">
    <div class="page-title" style="margin:0 16px 10px 16px; display: flex; justify-content: space-between;">&nbsp;🤖 智能运维助手
      <!-- <span style="opacity: 0.26; font-size: 12px; position: relative; white-space: nowrap;">云端大模型 由 阿里千问Qwen 提供</span> -->
    </div>

    <div class="chat-layout">
      <!-- 聊天主区域 -->
      <div class="chat-main">
        <div ref="messagesEl" class="chat-messages">
          <!-- 欢迎消息 -->
          <div class="chat-message bot">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
              <p>您好！我是建筑能源智能运维助手。</p>
              <p>我可以帮您：</p>
              <ul>
                <li>📊 查询建筑能耗数据与统计</li>
                <li>🔍 分析能耗异常原因</li>
                <li>⚡ 评估空调系统 COP 能效</li>
                <li>🔧 提供设备维护保养建议</li>
                <li>💡 给出节能优化方案</li>
              </ul>
              <p>请输入您的问题，开始智能运维对话！</p>
            </div>
          </div>

          <!-- 动态消息 -->
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="chat-message"
            :class="msg.role"
          >
            <div class="message-avatar">{{ msg.role === 'bot' ? '🤖' : '👤' }}</div>
            <div class="message-content" v-html="msg.html"></div>
          </div>
        </div>

        <div class="chat-input-row">
          <input
            v-model="inputText"
            type="text"
            placeholder="请输入您的运维问题，如：查询教学楼本月能耗异常..."
            @keydown.enter="send"
          />
          <button class="btn btn-primary" :disabled="sending" @click="send">
            {{ sending ? '分析中...' : '发送 ▶' }}
          </button>
          <button @click="showSuggestions = !showSuggestions">
            {{ showSuggestions ? '▶️ 收起' : '💡 快捷问题' }}
          </button>
        </div>

        <div class="chat-sidebar" :class="{ active: showSuggestions }">
          <div class="sidebar-title">💡 快捷问题</div>
          <div class="suggestions-list">
            <button
              v-for="q in suggestions"
              :key="q"
              class="suggestion-btn"
              @click="ask(q)"
            >{{ q }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, inject, onMounted, onUnmounted } from 'vue'
import { AI_CONTEXT_EVENT } from '../utils/aiLink'

const { loading } = inject('api')

const inputText = ref('')
const filter = ref({ building: '', startDate: '', endDate: '' })
const messages = ref([])
const sending = ref(false)
const messagesEl = ref(null)
const showSuggestions = ref(false)

const suggestions = [
  '查询本系统所有建筑的能耗情况',
  '分析空调系统COP能效是否正常',
  '最近有哪些能耗异常记录？',
  '提供建筑节能优化建议',
  '空调设备日常维护保养规范是什么？',
  '供回水温差异常怎么处理？',
  '深夜用电异常的原因和处理方法',
]

const quickQuestionSet = new Set(suggestions)

function isPresetQuestion(question) {
  return quickQuestionSet.has(question)
}

function buildRequestBody(question, context = null, queryMode = 'ai') {
  const body = { question }
  body.query_mode = queryMode

  if (context?.building_id) body.building_id = context.building_id
  else if (filter.value.building) body.building_id = filter.value.building

  if (context?.start_time) body.start_time = context.start_time
  else if (filter.value.startDate) body.start_time = filter.value.startDate + ' 00:00:00'

  if (context?.end_time) body.end_time = context.end_time
  else if (filter.value.endDate) body.end_time = filter.value.endDate + ' 23:59:59'

  return body
}

async function backendChatRequest(question, context = null, queryMode = 'ai') {
  const body = buildRequestBody(question, context, queryMode)
  const response = await fetch('/api/chat/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseApiResponse(response)
}

async function modelApiRequest(question, context = null) {
  return backendChatRequest(question, context, 'ai')
}

async function parseApiResponse(response) {
  const text = await response.text()
  let data = {}

  try {
    data = text ? JSON.parse(text) : {}
  } catch (_) {
    throw new Error(`服务返回非JSON响应（HTTP ${response.status}）：${text.slice(0, 120)}`)
  }

  if (!response.ok) {
    const message = data.detail || data.message || data.error || `HTTP ${response.status}`
    throw new Error(message)
  }

  return data
}

function mdToHtml(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- /g, '\n• ')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

async function scrollBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

async function ask(question, options = {}) {
  showSuggestions.value = false

  const context = options.context || null
  const forceBackend = !!options.forceBackend
  const useRuleMode = isPresetQuestion(question)

  if (!question.trim() || sending.value) return
  inputText.value = ''
  sending.value = true
  loading.value = true

  messages.value.push({ role: 'user', html: mdToHtml(question) })
  const loadingIdx = messages.value.length
  messages.value.push({ role: 'bot', html: '⏳ 正在分析中...' })
  await scrollBottom()

  try {
    let answer
    if (useRuleMode) {
      const data = await backendChatRequest(question, context, 'rule')
      answer = data.answer || '后端问答接口未返回内容。'
    } else if (forceBackend) {
      const data = await backendChatRequest(question, context, 'ai')
      answer = data.answer || '后端问答接口未返回内容。'
    } else {
      const data = await modelApiRequest(question, context)
      answer = data.answer || '模型API暂无返回结果，请稍后重试。'
    }

    messages.value[loadingIdx] = { role: 'bot', html: mdToHtml(answer) }
  } catch (e) {
    messages.value[loadingIdx] = { role: 'bot', html: '❌ 请求失败：' + e.message }
  } finally {
    sending.value = false
    loading.value = false
    await scrollBottom()
  }
}

function send() {
  ask(inputText.value.trim())
}

function toDateInput(v) {
  if (!v) return ''
  return String(v).slice(0, 10)
}

function handleAiContext(event) {
  const detail = event.detail || {}
  if (!detail.question) return

  if (detail.building_id) filter.value.building = detail.building_id
  if (detail.start_time) filter.value.startDate = toDateInput(detail.start_time)
  if (detail.end_time) filter.value.endDate = toDateInput(detail.end_time)

  ask(detail.question, { context: detail, forceBackend: true })
}

onMounted(() => {
  window.addEventListener(AI_CONTEXT_EVENT, handleAiContext)
})

onUnmounted(() => {
  window.removeEventListener(AI_CONTEXT_EVENT, handleAiContext)
})
</script>
