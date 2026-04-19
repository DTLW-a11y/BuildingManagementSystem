<template>
  <div>
    <div class="page-title">🔍 多条件数据查询</div>

    <div class="card">
      <div class="card-title">查询条件</div>
      <div class="form-grid">
        <div class="form-group">
          <label>建筑编号</label>
          <select v-model="form.building_id">
            <option value="">全部建筑</option>
            <option value="B001">B001 - 教学楼A</option>
            <option value="B002">B002 - 教学楼B</option>
            <option value="B003">B003 - 办公楼</option>
            <option value="B004">B004 - 图书馆</option>
            <option value="B005">B005 - 实验楼</option>
          </select>
        </div>
        <div class="form-group">
          <label>建筑类型</label>
          <select v-model="form.building_type">
            <option value="">全部类型</option>
            <option>教学楼</option>
            <option>办公楼</option>
            <option>图书馆</option>
            <option>实验楼</option>
          </select>
        </div>
        <div class="form-group">
          <label>开始时间</label>
          <input type="datetime-local" v-model="form.start_time" />
        </div>
        <div class="form-group">
          <label>结束时间</label>
          <input type="datetime-local" v-model="form.end_time" />
        </div>
        <div class="form-group">
          <label>年份</label>
          <select v-model="form.year">
            <option value="">全部年份</option>
            <option value="2024">2024</option>
          </select>
        </div>
        <div class="form-group">
          <label>月份</label>
          <select v-model="form.month">
            <option value="">全部月份</option>
            <option v-for="m in 12" :key="m" :value="String(m)">{{ m }}月</option>
          </select>
        </div>
        <div class="form-group">
          <label>设备状态</label>
          <select v-model="form.device_status">
            <option value="">全部状态</option>
            <option>正常</option>
            <option>异常</option>
          </select>
        </div>
        <div class="form-group">
          <label>仅显示异常</label>
          <select v-model="form.anomaly_only">
            <option value="false">否</option>
            <option value="true">是</option>
          </select>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" @click="doQuery(1)">🔍 查询</button>
        <button class="btn btn-secondary" @click="exportData">📥 导出 CSV</button>
        <button class="btn btn-secondary" @click="reset">↩️ 重置</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        查询结果
        <span v-if="total !== null" class="badge">共 {{ total }} 条</span>
      </div>
      <p v-if="queryError" class="hint" style="color:red;">{{ queryError }}</p>
      <p v-else-if="records === null" class="hint">请设置查询条件后点击查询按钮。</p>
      <p v-else-if="records.length === 0" class="hint">未找到符合条件的记录。</p>
      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>记录编号</th><th>建筑</th><th>监测时间</th>
              <th>电力能耗(kWh)</th><th>水耗(m³)</th>
              <th>空调能耗(kWh)</th><th>COP</th>
              <th>环境温度(°C)</th><th>设备状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.record_id">
              <td>{{ r.record_id }}</td>
              <td>{{ r.building_name }}</td>
              <td>{{ r.monitor_time ? r.monitor_time.substring(0, 16) : '' }}</td>
              <td>{{ r.power_consumption }}</td>
              <td>{{ r.water_consumption }}</td>
              <td>{{ r.ac_power_consumption }}</td>
              <td>{{ r.cop }}</td>
              <td>{{ r.env_temperature }}</td>
              <td>
                <span :class="r.anomaly_flag ? 'tag-anomaly' : 'tag-normal'">
                  {{ r.anomaly_flag ? '异常' : '正常' }}
                </span>
                <small v-if="r.anomaly_reason" style="color:#8c8c8c;"> {{ r.anomaly_reason }}</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button :disabled="page <= 1" @click="doQuery(page - 1)">«</button>
        <template v-for="p in pageRange" :key="p">
          <span v-if="p === '...'" style="color:#8c8c8c;">...</span>
          <button v-else :class="{ active: p === page }" @click="doQuery(p)">{{ p }}</button>
        </template>
        <button :disabled="page >= totalPages" @click="doQuery(page + 1)">»</button>
        <span>{{ page }} / {{ totalPages }} 页</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'

const { apiFetch, loading } = inject('api')

const form = ref({
  building_id: '', building_type: '', start_time: '', end_time: '',
  year: '', month: '', device_status: '', anomaly_only: 'false',
})
const records = ref(null)
const total = ref(null)
const page = ref(1)
const totalPages = ref(1)
const queryError = ref('')

const pageRange = computed(() => {
  const tp = totalPages.value
  const cp = page.value
  const pages = []
  const start = Math.max(1, cp - 3)
  const end = Math.min(tp, cp + 3)
  if (start > 1) { pages.push(1); if (start > 2) pages.push('...') }
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < tp) { if (end < tp - 1) pages.push('...'); pages.push(tp) }
  return pages
})

function buildParams(pg = 1) {
  const p = new URLSearchParams()
  const f = form.value
  if (f.building_id) p.set('building_id', f.building_id)
  if (f.building_type) p.set('building_type', f.building_type)
  if (f.start_time) p.set('start_time', f.start_time.replace('T', ' ') + ':00')
  if (f.end_time) p.set('end_time', f.end_time.replace('T', ' ') + ':00')
  if (f.year) p.set('year', f.year)
  if (f.month) p.set('month', f.month)
  if (f.device_status) p.set('device_status', f.device_status)
  if (f.anomaly_only === 'true') p.set('anomaly_only', 'true')
  p.set('page', pg)
  p.set('page_size', '20')
  return p
}

async function doQuery(pg = 1) {
  page.value = pg
  loading.value = true
  queryError.value = ''
  try {
    const data = await apiFetch('/api/query/records?' + buildParams(pg).toString())
    records.value = data.records
    total.value = data.total
    totalPages.value = data.total_pages
  } catch (e) {
    queryError.value = '查询失败：' + e.message
    records.value = []
  } finally {
    loading.value = false
  }
}

function exportData() {
  const p = buildParams(1)
  p.delete('page')
  p.delete('page_size')
  window.location.href = '/api/query/export?' + p.toString()
}

function reset() {
  form.value = { building_id: '', building_type: '', start_time: '', end_time: '', year: '', month: '', device_status: '', anomaly_only: 'false' }
  records.value = null
  total.value = null
  queryError.value = ''
}
</script>
