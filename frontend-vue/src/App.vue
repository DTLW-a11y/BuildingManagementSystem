<template>
  <div>

    <StartupScreen
      v-if="showStartup"
      :activeIndex="selectedIndex"
      :hasSelected="startupAnimating"
      @select="handleStartupSelect"
    />

    <div v-show="!showStartup || startupAnimating">
      <header class="header">
        <div class="header-logo">
          <img class="logo-icon" src="/image/building.svg" alt="ICON">
          <span class="logo-text">建筑能源智能管理系统</span>
        </div>
        <nav class="header-nav">
          <RouterLink to="/dashboard" class="nav-link"><img class="startup-card-logo" src="/image/panel.svg" alt="PanelIcon">首页 | 仪表盘</RouterLink>
          <RouterLink to="/statistics" class="nav-link"><img class="startup-card-logo" src="/image/data.svg" alt="DataIcon">数据分析</RouterLink>
          <RouterLink to="/query" class="nav-link"><img class="startup-card-logo" src="/image/define.svg" alt="SearchIcon">多条件查询</RouterLink>
          <RouterLink to="/data" class="nav-link"><img class="startup-card-logo" src="/image/folder.svg" alt="ManageIcon">数据管理</RouterLink>
          <div id="nav-marker"></div>
        </nav>
        <div style="display:flex;align-items:center;gap:12px;">
          <div class="header-status" style="margin-right: 16px;">
            <span>{{ !isDark ? '白天模式' : '夜间模式' }}</span>
          </div>
          <toggle-button class="theme-toggle" size="1.08" value="light" @click="toggleTheme"></toggle-button>
        </div>
      </header>

      <main class="main">
        <transition name="route" mode="out-in">
          <RouterView :key="route.path" />
        </transition>
      </main>

      <aside class="aside hide">
        <button class="show-chat" @click="showChatAI">
          <p class="chat-title hide">🤖 智能运维助手 </p>
          <p class="chat-btn-back left">V</p>
        </button>
        <ChatAI />
      </aside>

      <footer class="footer">
        <div class="header-status">
          <span class="status-dot" :class="{ error: !healthy }"></span>
          <span style="color: var(--text-secondary);">{{ healthy ? '系统正常' : '连接失败' }}</span>
        </div>
      </footer>

      <!-- 空数据导入遮罩：仅在空库且当前路由非数据管理时显示 -->
      <EmptyImport v-if="isEmpty && route.path !== '/data'" @imported="onImported" />

      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner">⏳ 数据加载中...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, provide, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmptyImport from './components/EmptyImport.vue'
import ChatAI from './views/Chat.vue'
import StartupScreen from './components/StartupScreen.vue'

const healthy = ref(true)
const loading = ref(false)
const isDark = ref(false)
const isEmpty = ref(false)
const route = useRoute()
const router = useRouter()
const showStartup = ref(true)
const selectedIndex = ref(-1)
const startupAnimating = ref(false)
let showAI = false
let sidebar, mainContainer, ChatTitle, BtnArrow
let navMarker, navItem
let targetMAIN
let MAINobserver = new ResizeObserver(e => {
  moveMarker();
})

const API_BASE = ''

async function apiFetch(path, options = {}) {
  const resp = await fetch(API_BASE + path, options)
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  return resp.json()
}

function formatNum(n, dec = 2) {
  if (n == null || isNaN(n)) return '-'
  return Number(n).toLocaleString('zh-CN', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  })
}

async function checkHealth() {
  try {
    await apiFetch('/health')
    healthy.value = true
  } catch {
    healthy.value = false
  }
}

async function checkEmpty() {
  try {
    const data = await apiFetch('/api/data/stats')
    isEmpty.value = data.total_records === 0
  } catch {
    isEmpty.value = false
  }
}

function onImported() {
  isEmpty.value = false
}

function toggleTheme() {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.body.classList.add('dark')
  } else {
    document.body.classList.remove('dark')
  }
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function handleStartupSelect(index) {
  selectedIndex.value = index
  showStartup.value = false
  targetMAIN = document.querySelectorAll('nav .nav-link')[index]
  moveMarker()
}

function showChatAI() {
  showAI = !showAI
  if (showAI) {
    sidebar.classList.remove('hide')
    sidebar.classList.add('show')
    mainContainer.classList.add('small')
    ChatTitle.classList.remove('hide')
    ChatTitle.classList.add('show')
    BtnArrow.classList.remove('left')
    BtnArrow.classList.add('right')
  } else {
    sidebar.classList.remove('show')
    sidebar.classList.add('hide')
    mainContainer.classList.remove('small')
    ChatTitle.classList.remove('show')
    ChatTitle.classList.add('hide')
    BtnArrow.classList.remove('right')
    BtnArrow.classList.add('left')
  }
}

function moveMarker() {
  navMarker.style.left = targetMAIN.offsetLeft + 'px';
}

function Init() {
  sidebar = document.querySelector('.aside')
  mainContainer = document.querySelector('.main')
  ChatTitle = document.querySelector('.chat-title')
  BtnArrow = document.querySelector('.chat-btn-back')
  MAINobserver.observe(document.querySelector('.main'))
  navMarker = document.querySelector('#nav-marker')
  navItem = document.querySelectorAll('.nav-link')
  targetMAIN = document.querySelector('.nav-link')
  navItem.forEach(link => {
    link.addEventListener('click', (e) => {
      targetMAIN = e.target;
      moveMarker();
    })
  })
}


provide('api', { apiFetch, formatNum, loading })

onMounted(() => {
  checkHealth()
  checkEmpty()
  Init()
})
</script>
