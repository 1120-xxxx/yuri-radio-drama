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

const paletteMap: Record<string, [string, string]> = {
  '猫耳FM': ['#fda4af', '#f472b6'],
  '漫播': ['#c4b5fd', '#818cf8'],
  '喜马拉雅': ['#fcd34d', '#f59e0b'],
  'B站': ['#67e8f9', '#06b6d4'],
};

function render() {
  if (!el.value || safeData.value.length === 0) return;
  if (!chart) chart = echarts.init(el.value);
  const colors = safeData.value.map((d) => {
    const grad = paletteMap[d.name];
    if (grad) return new echarts.graphic.LinearGradient(0, 0, 1, 1, [
      { offset: 0, color: grad[0] },
      { offset: 1, color: grad[1] },
    ]);
    return '#818cf8';
  });
  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1a1a2e',
      borderColor: '#2d2d44',
      textStyle: { color: '#e5e7eb' },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      bottom: 0,
      icon: 'circle',
      textStyle: { color: '#9ca3af' },
      itemWidth: 10,
      itemHeight: 10,
    },
    color: colors,
    series: [
      {
        name: '平台分布',
        type: 'pie',
        radius: ['50%', '72%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#1e1e2f',
          borderWidth: 3,
        },
        label: {
          show: true,
          color: '#c8cad0',
          fontSize: 13,
          formatter: '{b}\n{d}%',
        },
        labelLine: {
          lineStyle: { color: '#4b5563' },
        },
        emphasis: {
          scale: true,
          scaleSize: 6,
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(244, 114, 182, 0.3)',
          },
        },
        data: safeData.value,
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
