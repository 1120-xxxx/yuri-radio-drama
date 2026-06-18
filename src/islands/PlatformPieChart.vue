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
  '猫耳FM': ['#ACEDFF', '#5D9FFF'],
  '漫播': ['#6BBBFF', '#4A9EF0'],
  '喜马拉雅': ['#FFD68A', '#FFC04E'],
  'B站': ['#89BBFE', '#5D9FFF'],
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
    return '#5D9FFF';
  });
  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#FFFFFF',
      borderColor: '#89BBFE',
      textStyle: { color: '#615D6C' },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      bottom: 0,
      icon: 'circle',
      textStyle: { color: '#6F8AB7' },
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
          borderColor: '#FFFFFF',
          borderWidth: 3,
        },
        label: {
          show: true,
          color: '#4A4658',
          fontSize: 13,
          formatter: '{b}\n{d}%',
        },
        labelLine: {
          lineStyle: { color: '#9BAECF' },
        },
        emphasis: {
          scale: true,
          scaleSize: 6,
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(93, 159, 255, 0.3)',
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
