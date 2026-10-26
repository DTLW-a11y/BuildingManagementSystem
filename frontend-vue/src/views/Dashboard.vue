<template>
  <div>
    <div class="page-title">📊 系统概览仪表盘</div>

    <!-- KPI 卡片 -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon">📋</div>
        <div class="kpi-value">{{ kpi.total_records != null ? fmt(kpi.total_records, 0) : '-' }}</div>
        <div class="kpi-label">总记录数</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">⚡</div>
        <div class="kpi-value">{{ kpi.total_power_kwh != null ? fmt(kpi.total_power_kwh, 0) : '-' }}</div>
        <div class="kpi-label">总电力能耗 (kWh)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">💧</div>
        <div class="kpi-value">{{ kpi.total_water_m3 != null ? fmt(kpi.total_water_m3, 0) : '-' }}</div>
        <div class="kpi-label">总水耗 (m³)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">🌡️</div>
        <div class="kpi-value">{{ kpi.avg_cop != null ? fmt(kpi.avg_cop, 3) : '-' }}</div>
        <div class="kpi-label">平均 COP</div>
      </div>
      <div class="kpi-card alert">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-value">{{ kpi.anomaly_count != null ? fmt(kpi.anomaly_count, 0) : '-' }}</div>
        <div class="kpi-label">异常记录数</div>
      </div>
      <div class="kpi-card alert">
        <div class="kpi-icon">📉</div>
        <div class="kpi-value">{{ kpi.anomaly_rate != null ? kpi.anomaly_rate + '%' : '-' }}</div>
        <div class="kpi-label">异常率 (%)</div>
      </div>
    </div>

    <!-- 图表 -->
    <div class="chart-row">
      <div class="chart-card">
        <div class="chart-title">各建筑电力能耗分布</div>
        <div ref="pieEl" class="chart-container"></div>
      </div>
      <div class="chart-card wide">
        <div class="chart-title">近期能耗趋势</div>
        <div ref="trendEl" class="chart-container"></div>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" @click="load"><img class="refresh-icon" src="/image/refresh_grey.svg" alt="Refresh">刷新数据</button>
    </div>

    <p v-if="error" class="hint" style="color:red;">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject } from 'vue'
import * as echarts from 'echarts'

const { apiFetch, formatNum, loading } = inject('api')
const fmt = formatNum

const kpi = ref({})
const error = ref('')
const pieEl = ref(null)
const trendEl = ref(null)
let pieChart = null
let trendChart = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch('/api/stats/overview')
    if (data.message) { loading.value = false; return }
    kpi.value = data.kpis
    renderPie(data.building_power_distribution)
    renderTrend(data.recent_trend)
  } catch (e) {
    error.value = '加载失败：' + e.message
  } finally {
    loading.value = false
  }
}

function renderPie(dist) {
  if (!pieChart) pieChart = echarts.init(pieEl.value)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} kWh ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle', textStyle: { fontSize: 12 } },
    color: ['#1a6fcf', '#52c41a', '#fa8c16', '#722ed1', '#f5222d'],
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['65%', '50%'],
      avoidLabelOverlap: true,
      label: { show: true, formatter: '{b}\n{d}%', fontSize: 11 },
      data: dist.map(d => ({ name: d.name, value: d.value })),
    }],
  })
}

function renderTrend(trend) {
  if (!trendChart) trendChart = echarts.init(trendEl.value)
  const times = trend.map(d => d.time.substring(5, 16))
  const powers = trend.map(d => d.total_power)
  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', name: 'kWh', nameTextStyle: { fontSize: 11 } },
    color: ['#1a6fcf'],
    series: [{
      type: 'line',
      data: powers,
      smooth: true,
      areaStyle: { opacity: 0.2 },
      symbol: 'none',
    }],
  })
}

function onResize() {
  pieChart?.resize()
  trendChart?.resize()
}

let observer = new ResizeObserver(e => {
    onResize()});

onMounted(() => {
  load()
  observer.observe(document.querySelector('.main'))
})

onUnmounted(() => {
  pieChart?.dispose()
  trendChart?.dispose()
  observer.disconnect()
})
</script>
