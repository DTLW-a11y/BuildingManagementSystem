<template>
  <div>
    <div class="page-title">📁 数据管理</div>

    <div class="card">
      <div class="card-title">导入能耗数据</div>
      <p class="hint">支持 CSV 格式，包含标准字段的能耗数据文件。</p>
      <div
        class="upload-area"
        :class="{ dragover: dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
        @click="fileInput.click()"
      >
        <div class="upload-icon">📂</div>
        <p style="margin-bottom: 26px;">点击选择 CSV 文件或拖拽到此处</p>
        <button class="btn btn-primary" @click.stop="fileInput.click()">选择文件</button>
        <input ref="fileInput" type="file" accept=".csv" style="display:none" @change="onFileChange" />
      </div>
      <div v-if="uploadMsg" class="status-msg" :class="uploadMsgType" v-html="uploadMsg"></div>
    </div>

    <div class="card">
      <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
        <span>数据集统计信息</span>
        <div class="btn-row" style="margin-top:0;">
          <button class="btn btn-secondary" @click="loadStats"><img class="refresh-icon" src="/image/refresh_blue.svg" alt="Refresh">刷新统计</button>
          <button class="btn" style="background:#f5222d;color:#fff;" @click="openClearConfirm">🗑 清空数据库</button>
        </div>
      </div>
      <div class="table-wrapper" style="margin-top:12px;">
        <p v-if="!stats" class="hint">点击刷新统计以加载数据。</p>
        <template v-else-if="stats.total_records === 0">
          <p class="hint">数据库为空，请先导入 CSV 数据文件。</p>
        </template>
        <template v-else>
          <div style="margin-bottom:12px;font-size:14px;">
            <strong>总记录数：</strong>{{ stats.total_records }} 条 &nbsp;|&nbsp;
            <strong>时间范围：</strong>{{ stats.time_range.start }} ~ {{ stats.time_range.end }} &nbsp;|&nbsp;
            <strong>异常率：</strong><span style="color:#fa8c16;">{{ stats.anomaly_rate }}%</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>建筑编号</th><th>建筑名称</th><th>建筑类型</th><th>记录数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in stats.buildings" :key="b.building_id">
                <td>{{ b.building_id }}</td>
                <td>{{ b.building_name }}</td>
                <td>{{ b.building_type }}</td>
                <td>{{ b.record_count }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <div v-if="showClearConfirm" class="loading-overlay" @click.self="showClearConfirm = false">
      <div class="loading-spinner" style="min-width:360px;max-width:520px;text-align:left;">
        <div style="font-size:18px;font-weight:600;margin-bottom:10px;">⚠️ 确认清空数据库</div>
        <div style="font-size:14px;line-height:1.8;margin-bottom:12px;">
          此操作会永久删除当前数据库中的全部记录，且不可恢复。<br>
          请确认是否继续。
        </div>
        <div class="btn-row" style="justify-content:flex-end;margin-top:0;">
          <button class="btn btn-secondary" :disabled="clearing" @click="showClearConfirm = false">取消</button>
          <button class="btn" :disabled="clearing" style="background:#f5222d;color:#fff;" @click="confirmClearData">
            {{ clearing ? '清空中...' : '确认清空' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'

const { apiFetch, loading } = inject('api')

const dragging = ref(false)
const uploadMsg = ref('')
const uploadMsgType = ref('')
const stats = ref(null)
const fileInput = ref(null)
const showClearConfirm = ref(false)
const clearing = ref(false)

function onFileChange(e) {
  const file = e.target.files[0]
  if (file) uploadCsv(file)
}

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.name.endsWith('.csv')) uploadCsv(file)
}

async function uploadCsv(file) {
  uploadMsg.value = '⏳ 正在上传并导入数据，请稍候...'
  uploadMsgType.value = 'info'
  loading.value = true
  const form = new FormData()
  form.append('file', file)
  try {
    const data = await fetch('/api/data/import', { method: 'POST', body: form }).then(r => r.json())
    uploadMsgType.value = 'success'
    uploadMsg.value = `✅ 导入完成！<br>新增：${data.inserted} 条 | 跳过（重复）：${data.skipped} 条` +
      (data.errors?.length ? `<br>⚠️ 错误：${data.errors.slice(0, 3).join(' | ')}` : '')
    loadStats()
  } catch (e) {
    uploadMsgType.value = 'error'
    uploadMsg.value = '❌ 导入失败：' + e.message
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await apiFetch('/api/data/stats')
  } catch (e) {
    stats.value = null
  }
}

function openClearConfirm() {
  if (loading.value || clearing.value) return
  if (stats.value && stats.value.total_records === 0) {
    uploadMsgType.value = 'info'
    uploadMsg.value = 'ℹ️ 当前数据库已为空，无需清空。'
    return
  }
  showClearConfirm.value = true
}

async function confirmClearData() {
  if (clearing.value) return
  clearing.value = true
  loading.value = true
  try {
    const data = await apiFetch('/api/data/clear', { method: 'DELETE' })
    uploadMsgType.value = 'success'
    uploadMsg.value = `✅ ${data.message}`
    await loadStats()
    window.dispatchEvent(new CustomEvent('dataset-updated'))
  } catch (e) {
    uploadMsgType.value = 'error'
    uploadMsg.value = '❌ 清空失败：' + e.message
  } finally {
    clearing.value = false
    loading.value = false
    showClearConfirm.value = false
  }
}

onMounted(loadStats)
</script>
