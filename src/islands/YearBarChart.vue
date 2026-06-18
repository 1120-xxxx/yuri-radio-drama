<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed, type Ref } from 'vue';
import * as echarts from 'echarts';

const props = defineProps<{
  data?: { name: string; value: number }[];
  title?: string;
  height?: number;
}>();

const el: Ref<HTMLDivElement | null> = ref(null);
let chart: echarts.ECharts | null = null;
const safeData = computed(() => (Array.isArray(props.data) ? props.data : []));

const gradients: [string, string][] = [
  ['#ACEDFF', '#5D9FFF'],
  ['#6BBBFF', '#4A9EF0'],
  ['#FFD68A', '#FFC04E'],
  ['#89BBFE', '#5D9FFF'],
];

function render() {
  if (!el.value || safeData.value.length === 0) return;
  if (!chart) chart = echarts.init(el.value);
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#FFFFFF',
      borderColor: '#89BBFE',
      textStyle: { color: '#615D6C' },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 30, containLabel: true },
    xAxis: {
      type: 'category',
      data: safeData.value.map((d) => d.name),
      axisLabel: { color: '#6F8AB7', interval: 0 },
      axisLine: { lineStyle: { color: '#89BBFE' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6F8AB7' },
      splitLine: { lineStyle: { color: '#ACEDFF' } },
    },
    series: [
      {
        name: '数量',
        type: 'bar',
        barMaxWidth: 50,
        barWidth: '50%',
        itemStyle: {
          borderRadius: [10, 10, 0, 0],
          color: (p: any) => {
            const grad = gradients[p.dataIndex % gradients.length];
            return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: grad[0] },
              { offset: 1, color: grad[1] },
            ]);
          },
        },
        data: safeData.value.map((d) => d.value),
        emphasis: {
          itemStyle: { shadowBlur: 15, shadowColor: 'rgba(244, 114, 182, 0.4)' },
        },
      },
    ],
  });
  chart.resize();
}

function handleResize() { chart?.resize(); }

onMounted(() => { render(); window.addEventListener('resize', handleResize); });
onBeforeUnmount(() => { window.removeEventListener('resize', handleResize); chart?.dispose(); chart = null; });
watch(() => safeData.value, render, { deep: true });
</script>

<template>
  <div ref="el" :style="{ width: '100%', height: (props.height ?? 340) + 'px' }"></div>
</template>
