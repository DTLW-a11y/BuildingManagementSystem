<template>
  <div class="startup-screen" id="StartupHeader">
    <div class="header-logo">
      <img class="logo-icon" src="/image/building.svg" alt="ICON">
      <span class="logo-text">建筑能源智能管理系统</span>
    </div>
    <div class="header-nav">
      <span class="nav-link" @click="Clicked('/dashboard', 0)"><img class="startup-card-logo" src="/image/panel.svg" alt="PanelIcon">概览仪表盘</span>
      <span class="nav-link" @click="Clicked('/statistics', 1)"><img class="startup-card-logo" src="/image/data.svg" alt="DataIcon">数据分析</span>
      <span class="nav-link" @click="Clicked('/query', 2)"><img class="startup-card-logo" src="/image/define.svg" alt="SearchIcon">多条件查询</span>
      <span class="nav-link" @click="Clicked('/data', 3)"><img class="startup-card-logo" src="/image/folder.svg" alt="ManageIcon">数据管理</span>
    </div>
    <div v-show="isClicked" style="display:flex;align-items:center;gap:12px;">
      <div class="header-status" style="margin-right: 16px;">
        <span>白天模式</span>
      </div>
      <toggle-button class="theme-toggle" size="1.08" value="light"></toggle-button>
    </div>
    <!-- <div v-show="!isClicked" class="startup-tip">点击对应卡片进入系统功能</div> -->
    <img src="/background/background_1.svg" alt="Background" class="startup-background-building-1">
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const emit = defineEmits(['select'])
const router = useRouter()
let isClicked = ref(false);

function Clicked(path, index) {
  if (isClicked.value) return
  isClicked.value = true;
  const startupHeader = document.getElementById('StartupHeader');
  let completed = false
  const finalize = () => {
    if (completed) return
    completed = true
    router.push(path)
    emit('select', index)
  }

  if (startupHeader) {
    const onTransitionEnd = (event) => {
      if (event.target !== startupHeader) return
      startupHeader.removeEventListener('transitionend', onTransitionEnd)
      clearTimeout(timeoutId)
      finalize()
    }

    startupHeader.addEventListener('transitionend', onTransitionEnd)
    startupHeader.className = 'header'
    const timeoutId = setTimeout(() => {
      startupHeader.removeEventListener('transitionend', onTransitionEnd)
      finalize()
    }, 1000)
  } else {
    finalize()
  }
}
</script>
