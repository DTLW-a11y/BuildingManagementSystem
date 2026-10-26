<template>
  <div>
    <div class="page-title">📈 数据统计分析</div>

    <!-- 时段能耗汇总 -->
    <div class="card">
      <div class="card-title">⏱️ 时段能耗汇总</div>
      <div class="form-inline">
        <label>分组方式：</label>
        <select v-model="period.groupBy">
          <option value="month">按月</option>
          <option value="day">按天</option>
          <option value="hour">按小时</option>
          <option value="building">按建筑</option>
        </select>
        <label>年份：</label>
        <select v-model="period.year">
          <option value="">全部</option>
          <option value="2024">2024</option>
        </select>
        <label>建筑：</label>
        <select v-model="period.building">
          <option value="">全部</option>
          <option value="B001">教学楼A</option>
          <option value="B002">教学楼B</option>
          <option value="B003">办公楼</option>
          <option value="B004">图书馆</option>
          <option value="B005">实验楼</option>
        </select>
        <button class="btn btn-primary" @click="loadPeriod">📊 分析</button>
      </div>
      <p class="hint" style="margin:0 0 10px 0;">点击柱状图节点或下方表格行，可一键联动智能运维诊断。</p>
      <div ref="periodEl" class="chart-container" style="height:320px;"></div>
      <div class="table-wrapper">
        <table v-if="periodData.length">
          <thead>
            <tr>
              <th>时段/分组</th>
              <th v-for="k in periodKeys" :key="k">{{ periodKeyLabel(k) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in periodData" :key="row.period" @click="diagnosePeriodRow(row)" style="cursor:pointer;">
              <td>{{ row.period }}</td>
              <td v-for="k in periodKeys" :key="k">{{ row[k] != null ? row[k] : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="periodError" class="hint" style="color:red;">{{ periodError }}</p>
    </div>

    <!-- COP 能效分析 -->
    <div class="card">
      <div class="card-title">🌡️ COP 能效分析</div>
      <div class="form-inline">
        <label>年份：</label>
        <select v-model="cop.year">
          <option value="">全部</option>
          <option value="2024">2024</option>
        </select>
        <label>建筑：</label>
        <select v-model="cop.building">
          <option value="">全部</option>
          <option value="B001">教学楼A</option>
          <option value="B002">教学楼B</option>
          <option value="B003">办公楼</option>
          <option value="B004">图书馆</option>
          <option value="B005">实验楼</option>
        </select>
        <button class="btn btn-primary" @click="loadCop">📊 分析</button>
      </div>
      <p class="hint" style="margin:0 0 10px 0;">点击 COP 曲线节点，可将节点上下文直接注入运维助手。</p>
      <div ref="copEl" class="chart-container" style="height:320px;"></div>
      <div v-if="copSummary" class="info-box" v-html="copSummary"></div>
      <p v-if="copError" class="hint" style="color:red;">{{ copError }}</p>
    </div>

    <!-- 异常分析 -->
    <div class="card">
      <div class="card-title">⚠️ 能耗异常分析</div>
      <div class="form-inline">
        <label>年份：</label>
        <select v-model="anomaly.year">
          <option value="">全部</option>
          <option value="2024">2024</option>
        </select>
        <label>月份：</label>
        <select v-model="anomaly.month">
          <option value="">全部</option>
          <option v-for="m in 12" :key="m" :value="String(m)">{{ m }}月</option>
        </select>
        <button class="btn btn-primary" @click="loadAnomaly">📊 分析</button>
      </div>
      <p class="hint" style="margin:0 0 10px 0;">点击异常分布柱图或异常原因饼图节点，可直接获取诊断建议。</p>
      <div class="chart-row">
        <div ref="anomalyBarEl" class="chart-container" style="height:280px;flex:1;"></div>
        <div ref="anomalyPieEl" class="chart-container" style="height:280px;flex:1;"></div>
      </div>
      <div v-if="anomalySummary" class="info-box" v-html="anomalySummary"></div>
      <p v-if="anomalyError" class="hint" style="color:red;">{{ anomalyError }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import * as echarts from 'echarts'
import { emitAiContext } from '../utils/aiLink'

const { apiFetch, loading } = inject('api')

// ---- Period ----
const period = ref({ groupBy: 'month', year: '2024', building: '' })
const periodData = ref([])
const periodError = ref('')
const periodEl = ref(null)
let periodChart = null

const periodKeys = computed(() =>
  periodData.value.length ? Object.keys(periodData.value[0]).filter(k => k !== 'period') : []
)

const KEY_LABELS = {
  total_power: '总电耗(kWh)', avg_power: '均值(kWh)', max_power: '最高(kWh)',
  total_water: '总水耗(m³)', total_ac_power: '空调能耗(kWh)', record_count: '记录数',
  building_id: '建筑编号', building_type: '建筑类型',
}
function periodKeyLabel(k) { return KEY_LABELS[k] || k }

function pad2(n) {
  return String(n).padStart(2, '0')
}

function formatDateTime(dateObj) {
  return `${dateObj.getFullYear()}-${pad2(dateObj.getMonth() + 1)}-${pad2(dateObj.getDate())} ${pad2(dateObj.getHours())}:${pad2(dateObj.getMinutes())}:${pad2(dateObj.getSeconds())}`
}

function getYearRange(yearValue) {
  const year = Number(yearValue)
  if (!year) return {}
  return {
    start_time: `${year}-01-01 00:00:00`,
    end_time: `${year}-12-31 23:59:59`,
  }
}

function getMonthRange(yearValue, monthValue) {
  const year = Number(yearValue)
  const month = Number(monthValue)
  if (!year || !month) return {}

  const lastDay = new Date(year, month, 0).getDate()
  return {
    start_time: `${year}-${pad2(month)}-01 00:00:00`,
    end_time: `${year}-${pad2(month)}-${pad2(lastDay)} 23:59:59`,
  }
}

function getPeriodRange(row) {
  const mode = period.value.groupBy

  if (mode === 'month') {
    const matched = /^(\d{4})-(\d{2})$/.exec(String(row.period || ''))
    if (matched) return getMonthRange(matched[1], matched[2])
  }

  if (mode === 'day') {
    const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(row.period || ''))
    if (matched) {
      return {
        start_time: `${matched[1]}-${matched[2]}-${matched[3]} 00:00:00`,
        end_time: `${matched[1]}-${matched[2]}-${matched[3]} 23:59:59`,
      }
    }
  }

  if (mode === 'hour') {
    return getYearRange(period.value.year)
  }

  if (mode === 'building') {
    return getYearRange(period.value.year)
  }

  return {}
}

function emitDiagnosisContext(payload) {
  emitAiContext(payload)
}

function diagnosePeriodRow(row, source = 'table') {
  const metrics = periodKeys.value
    .map(k => `${periodKeyLabel(k)}=${row[k] != null ? row[k] : '-'}`)
    .join('，')
  const range = getPeriodRange(row)
  const buildingId = row.building_id || period.value.building || ''

  const question = `请对以下异常能耗节点进行诊断：来源为时段汇总${source === 'chart' ? '图表' : '表格'}，分组方式${period.value.groupBy}，节点${row.period}，${metrics}。请输出【问题】【原因】【措施】，并给出节能优化建议。`

  emitDiagnosisContext({
    source: 'stats-period',
    question,
    building_id: buildingId,
    start_time: range.start_time,
    end_time: range.end_time,
  })
}

function bindPeriodChartEvents() {
  if (!periodChart) return
  periodChart.off('click')
  periodChart.on('click', params => {
    const row = periodData.value[params.dataIndex]
    if (row) diagnosePeriodRow(row, 'chart')
  })
}

function diagnoseCopPoint(params) {
  const monthLabel = String(params.name || '')
  const monthValue = Number(monthLabel.replace('月', ''))
  const buildingName = String(params.seriesName || '')
  const point = copRawData.value.find(d => d.building_name === buildingName && d.month === monthValue)
  const buildingId = point?.building_id || cop.value.building || ''
  const copValue = params.value != null ? params.value : point?.avg_cop
  const range = getMonthRange(cop.value.year, monthValue)

  const question = `在COP分析中发现疑似异常能效节点：建筑${buildingName}，时间${monthLabel}，平均COP为${copValue}。请判断是否存在效率异常，并给出排查步骤和优化建议。`

  emitDiagnosisContext({
    source: 'stats-cop',
    question,
    building_id: buildingId,
    start_time: range.start_time,
    end_time: range.end_time,
  })
}

function bindCopChartEvents() {
  if (!copChart) return
  copChart.off('click')
  copChart.on('click', params => {
    diagnoseCopPoint(params)
  })
}

function diagnoseAnomalyBuilding(item) {
  const range = anomaly.value.month
    ? getMonthRange(anomaly.value.year, anomaly.value.month)
    : getYearRange(anomaly.value.year)

  const question = `异常分析中检测到建筑${item.building_name}出现异常记录${item.anomaly_count}条，异常率${item.anomaly_rate}%（正常${item.normal_count}条）。请给出异常原因分析与处置建议。`

  emitDiagnosisContext({
    source: 'stats-anomaly-building',
    question,
    building_id: item.building_id,
    start_time: range.start_time,
    end_time: range.end_time,
  })
}

function diagnoseAnomalyReason(params) {
  const range = anomaly.value.month
    ? getMonthRange(anomaly.value.year, anomaly.value.month)
    : getYearRange(anomaly.value.year)

  const question = `异常分析中，异常原因“${params.name}”出现${params.value}次。请说明该异常的典型诱因、排查优先级和处置建议。`

  emitDiagnosisContext({
    source: 'stats-anomaly-reason',
    question,
    start_time: range.start_time,
    end_time: range.end_time,
  })
}

function bindAnomalyChartEvents() {
  if (anomalyBarChart) {
    anomalyBarChart.off('click')
    anomalyBarChart.on('click', params => {
      const target = anomalyBuildingData.value.find(item => item.building_name === params.name)
      if (target) diagnoseAnomalyBuilding(target)
    })
  }

  if (anomalyPieChart) {
    anomalyPieChart.off('click')
    anomalyPieChart.on('click', params => {
      diagnoseAnomalyReason(params)
    })
  }
}

async function loadPeriod() {
  loading.value = true
  periodError.value = ''
  try {
    const p = new URLSearchParams({ group_by: period.value.groupBy })
    if (period.value.year) p.set('year', period.value.year)
    if (period.value.building) p.set('building_id', period.value.building)
    const data = await apiFetch('/api/stats/period_summary?' + p.toString())
    periodData.value = data.data

    const periods = data.data.map(d => d.period)
    const powers = data.data.map(d => d.total_power ?? d.avg_power)
    if (!periodChart) periodChart = echarts.init(periodEl.value)
    periodChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: periods, axisLabel: { rotate: periods.length > 12 ? 45 : 0, fontSize: 11 } },
      yAxis: { type: 'value', name: period.value.groupBy === 'hour' ? '平均kWh' : '总计kWh' },
      color: ['#1a6fcf'],
      series: [{
        type: 'bar',
        data: powers,
        label: { show: periods.length <= 14, position: 'top', fontSize: 10 },
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      }],
    })
    bindPeriodChartEvents()
  } catch (e) {
    periodError.value = '加载失败：' + e.message
  } finally {
    loading.value = false
  }
}

// ---- COP ----
const cop = ref({ year: '2024', building: '' })
const copSummary = ref('')
const copError = ref('')
const copEl = ref(null)
let copChart = null
const copRawData = ref([])

function getCopAxisRange(rows) {
  const values = rows
    .map(r => Number(r.avg_cop))
    .filter(v => Number.isFinite(v))

  if (!values.length) {
    return { min: 0, max: 1 }
  }

  const dataMin = Math.min(...values)
  const dataMax = Math.max(...values)
  const span = dataMax - dataMin

  // 当波动很小时，仍然保持最小展示跨度，避免曲线“挤在一起”
  const baseSpan = Math.max(span, 0.25)
  const padding = Math.max(baseSpan * 0.2, 0.05)

  const min = Math.max(0, dataMin - padding)
  const max = dataMax + padding

  return {
    min: Number(min.toFixed(2)),
    max: Number(max.toFixed(2)),
  }
}

async function loadCop() {
  loading.value = true
  copError.value = ''
  try {
    const p = new URLSearchParams()
    if (cop.value.year) p.set('year', cop.value.year)
    if (cop.value.building) p.set('building_id', cop.value.building)
    const data = await apiFetch('/api/stats/cop_analysis?' + p.toString())
    copRawData.value = data.data

    if (!copChart) copChart = echarts.init(copEl.value)

    if (!data.data.length) {
      copChart.setOption({
        title: {
          text: '当前筛选条件下暂无COP数据',
          left: 'center',
          top: 'middle',
          textStyle: { color: '#999', fontSize: 13, fontWeight: 'normal' },
        },
        xAxis: { type: 'category', data: [] },
        yAxis: { type: 'value' },
        series: [],
      }, { notMerge: true })
      copSummary.value = '<strong>当前筛选条件下暂无COP数据</strong>，请调整年份或建筑后重试。'
      return
    }

    const buildingNames = [...new Set(data.data.map(d => d.building_name))]
    const months = [...new Set(data.data.map(d => d.month))].sort((a, b) => a - b)
    const axisRange = getCopAxisRange(data.data)
    const series = buildingNames.map(name => ({
      name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 7,
      showSymbol: true,
      lineStyle: { width: 2.5 },
      emphasis: { focus: 'series' },
      data: months.map(m => {
        const f = data.data.find(d => d.building_name === name && d.month === m)
        return f ? f.avg_cop : null
      }),
      connectNulls: true,
    }))

    copChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, type: 'scroll' },
      grid: { left: '3%', right: '4%', bottom: '50px', containLabel: true },
      xAxis: { type: 'category', data: months.map(m => m + '月') },
      yAxis: {
        type: 'value',
        name: 'COP',
        min: axisRange.min,
        max: axisRange.max,
        scale: true,
      },
      series,
    }, { notMerge: true })
    bindCopChartEvents()

    const r = data.overall_avg_cop
    const grade = r >= 3.5 ? '优秀 ✅' : r >= 3.0 ? '良好 ✅' : r >= 2.5 ? '一般 ⚠️' : '较差 ❌'
    copSummary.value = `<strong>整体平均 COP：${r}</strong> &nbsp;|&nbsp; <strong>评级：</strong>${grade}<br>COP 越高表示空调系统能效越好。建议定期清洗冷凝器、检查冷媒量以维持高 COP。`
  } catch (e) {
    copError.value = '加载失败：' + e.message
  } finally {
    loading.value = false
  }
}

// ---- Anomaly ----
const anomaly = ref({ year: '2024', month: '' })
const anomalySummary = ref('')
const anomalyError = ref('')
const anomalyBarEl = ref(null)
const anomalyPieEl = ref(null)
let anomalyBarChart = null
let anomalyPieChart = null
const anomalyBuildingData = ref([])

async function loadAnomaly() {
  loading.value = true
  anomalyError.value = ''
  try {
    const p = new URLSearchParams()
    if (anomaly.value.year) p.set('year', anomaly.value.year)
    if (anomaly.value.month) p.set('month', anomaly.value.month)
    const data = await apiFetch('/api/stats/anomaly_analysis?' + p.toString())
    anomalyBuildingData.value = data.by_building || []

    if (!anomalyBarChart) anomalyBarChart = echarts.init(anomalyBarEl.value)
    anomalyBarChart.setOption({
      title: { text: '各建筑异常记录分布', textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '50px', containLabel: true },
      xAxis: { type: 'category', data: data.by_building.map(b => b.building_name) },
      yAxis: { type: 'value', name: '记录数' },
      series: [
        { name: '正常', type: 'bar', stack: 'total', data: data.by_building.map(b => b.normal_count), color: '#52c41a', itemStyle: { borderRadius: [0, 0, 4, 4] } },
        { name: '异常', type: 'bar', stack: 'total', data: data.by_building.map(b => b.anomaly_count), color: '#fa8c16', itemStyle: { borderRadius: [4, 4, 0, 0] } },
      ],
    })

    if (data.reason_distribution?.length) {
      if (!anomalyPieChart) anomalyPieChart = echarts.init(anomalyPieEl.value)
      anomalyPieChart.setOption({
        title: { text: '异常原因分布', textStyle: { fontSize: 13 } },
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        color: ['#fa8c16', '#f5222d', '#722ed1'],
        series: [{ type: 'pie', radius: '60%', data: data.reason_distribution.map(r => ({ name: r.reason, value: r.count })) }],
      })
    }

    bindAnomalyChartEvents()

    const s = data.summary
    const rateColor = s.overall_anomaly_rate > 10 ? '#f5222d' : '#fa8c16'
    anomalySummary.value = `<strong>汇总：</strong>总记录 ${s.total_records} 条 | 异常 ${s.total_anomalies} 条 | 异常率 <span style="color:${rateColor};">${s.overall_anomaly_rate}%</span>` +
      (s.overall_anomaly_rate > 10 ? ' ⚠️ 异常率偏高，建议排查设备故障。' : ' ✅ 异常率在正常范围内。')
  } catch (e) {
    anomalyError.value = '加载失败：' + e.message
  } finally {
    loading.value = false
  }
}

function onResize() {
  periodChart?.resize()
  copChart?.resize()
  anomalyBarChart?.resize()
  anomalyPieChart?.resize()
}

let observer = new ResizeObserver(e => {
    onResize()});

onMounted(() => {
  loadPeriod()
  observer.observe(document.querySelector('.main'))
})

onUnmounted(() => {
  periodChart?.dispose()
  copChart?.dispose()
  anomalyBarChart?.dispose()
  anomalyPieChart?.dispose()
  observer.disconnect()
})
</script>
