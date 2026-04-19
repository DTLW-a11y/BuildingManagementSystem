<template>
  <div class="empty-import-overlay">
    <div class="empty-import-box">
      <div class="empty-import-icon">📂</div>
      <div class="empty-import-title">暂无能耗数据</div>
      <div class="empty-import-desc">
        系统数据库中尚未导入任何数据。<br>
        请上传包含能耗记录的 CSV 文件以开始使用系统。
      </div>

      <div
        class="empty-upload-area"
        :class="{ dragover: dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
        @click="fileInput.click()"
      >
        <div class="upload-icon">⬆️</div>
        <p>点击选择 CSV 文件，或拖拽到此处</p>
        <button class="btn btn-primary" @click.stop="fileInput.click()">选择 CSV 文件</button>
        <input ref="fileInput" type="file" accept=".csv" style="display:none" @change="onFileChange" />
      </div>

      <div v-if="uploadMsg" class="empty-status-msg" :class="uploadMsgType" v-html="uploadMsg"></div>

      <p class="hint" style="margin-top:16px;">
        支持标准能耗 CSV 格式，包含建筑编号、时间戳、电力、水耗等字段。
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, inject } from 'vue'

const { loading } = inject('api')
const emit = defineEmits(['imported'])

const dragging = ref(false)
const uploadMsg = ref('')
const uploadMsgType = ref('')
const fileInput = ref(null)

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
    uploadMsg.value = `✅ 导入完成！新增：${data.inserted} 条 | 跳过（重复）：${data.skipped} 条` +
      (data.errors?.length ? `<br>⚠️ 错误：${data.errors.slice(0, 3).join(' | ')}` : '')
    if (data.inserted > 0) {
      const REDIRECT_DELAY_MS = 1200
      setTimeout(() => emit('imported'), REDIRECT_DELAY_MS)
    }
  } catch (e) {
    uploadMsgType.value = 'error'
    uploadMsg.value = '❌ 导入失败：' + e.message
  } finally {
    loading.value = false
  }
}
</script>
