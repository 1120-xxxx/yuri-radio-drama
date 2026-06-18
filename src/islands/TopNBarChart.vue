<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed, type Ref } from 'vue';
import * as echarts from 'echarts';

interface Item { id: string; title: string; value: number; display: string; platform?: string; }

const props = defineProps<{
  items?: Item[];
  title?: string;
  height?: number;
  unit?: string;
  variant?: 'brand' | 'accent' | 'cyan' | 'gold' | 'emerald';
  linkPrefix?: string; // e.g. '/dramas/' or '/cvs/'
}>();

const el: Ref<HTMLDivElement | null> = ref(null);
let chart: echarts.ECharts | null = null;

const safeItems = computed(() => Array.isArray(props.items) ? props.items : []);

const variantGradients: Record<string, [string, string]> = {
  brand: ['#fda4af', '#f472b6'],
  accent: ['#c4b5fd', '#818cf8'],
  cyan: ['#67e8f9', '#06b6d4'],
  gold: ['#fcd34d', '#f59e0b'],
  emerald: ['#6ee7b7', '#10b981'],
};

function render() {
  if (!el.value || safeItems.value.length === 0) return;
  if (!chart) chart = echarts.init(el.value);
  const sorted = [...safeItems.value].slice(0, 20).reverse();
  const grad = variantGradients[props.variant ?? 'brand'];
  const prefix = props.linkPrefix ?? '/dramas/';

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1a1a2e',
      borderColor: '#2d2d44',
      textStyle: { color: '#e5e7eb' },
      formatter: (p: any) => {
        const idx = p[0].dataIndex;
        const item = sorted[idx];
        return `<span style="font-weight:600">${p[0].name}</span><br/>${p[0].value}${props.unit ?? ''}<br/><span style="color:#9ca3af;font-size:11px">点击查看详情 →</span>`;
      },
    },
    grid: { left: '3%', right: '8%', bottom: '8%', top: 10, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: {
        color: '#9ca3af',
        // 格式化：>=10000 显示为 x.xw，>=1000 显示为 xk
        formatter: (v: number) => {
          if (v >= 10000) {
            const w = v / 10000;
            // 整数则不带小数
            return (Number.isInteger(w) ? w.toFixed(0) : w.toFixed(1)) + 'w';
          }
          if (v >= 1000) {
            const k = v / 1000;
            return (Number.isInteger(k) ? k.toFixed(0) : k.toFixed(1)) + 'k';
          }
          return String(v);
        },
        // 防止标签互相重叠：限制标签数量
        interval: 'auto',
        hideOverlap: true,
        fontSize: 11,
      },
      splitLine: { lineStyle: { color: '#2d2d44' } },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((d) => d.title),
      axisLabel: {
        width: 180,
        overflow: 'truncate',
        color: '#c8cad0',
        fontSize: 12,
      },
      axisLine: { lineStyle: { color: '#2d2d44' } },
      axisTick: { show: false },
      triggerEvent: true,
    },
    series: [
      {
        name: '数值',
        type: 'bar',
        barWidth: '60%',
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: grad[0] },
            { offset: 1, color: grad[1] },
          ]),
        },
        data: sorted.map((d) => d.value),
        emphasis: {
          itemStyle: { shadowBlur: 12, shadowColor: 'rgba(244, 114, 182, 0.4)' },
        },
      },
    ],
  }, true);

  chart.off('click');
  chart.on('click', (params: any) => {
    const idx = params.dataIndex;
    if (idx == null) return;
    const item = sorted[idx];
    if (!item) return;
    const url = `${prefix}${item.id}/`;
    window.location.href = url;
  });

  chart.resize();
}

function handleResize() { chart?.resize(); }

onMounted(() => { render(); window.addEventListener('resize', handleResize); });
onBeforeUnmount(() => { window.removeEventListener('resize', handleResize); chart?.dispose(); chart = null; });
watch(() => [safeItems.value, props.variant], render, { deep: true });
</script>

<template>
  <div ref="el" :style="{ width: '100%', height: (props.height ?? 360) + 'px', cursor: 'pointer' }"></div>
</template>
