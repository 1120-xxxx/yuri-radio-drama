<script setup lang="ts">
import { ref, computed } from 'vue';
import TopNBarChart from './TopNBarChart.vue';

interface Item { id: string; title: string; value: number; display: string; platform?: string; }

const props = defineProps<{
  byPlay?: Item[];
  byRating?: Item[];
  byCount?: Item[];
  byCv?: Item[];
}>();

type Metric = 'play' | 'rating' | 'count' | 'cv';
const metric = ref<Metric>('play');

const tabs: { key: Metric; label: string; variant: 'brand' | 'accent' | 'gold' | 'cyan' }[] = [
  { key: 'play', label: '播放量榜', variant: 'brand' },
  { key: 'rating', label: '评分榜', variant: 'accent' },
  { key: 'count', label: '评分人数榜', variant: 'gold' },
  { key: 'cv', label: 'CV 参演榜', variant: 'cyan' },
];

function safe(arr: Item[] | undefined): Item[] { return Array.isArray(arr) ? arr : []; }

const current = computed(() => {
  switch (metric.value) {
    case 'rating': return { items: safe(props.byRating), unit: ' 分', title: '评分 Top', variant: 'accent' as const, prefix: '/dramas/' };
    case 'count': return { items: safe(props.byCount), unit: ' 条', title: '评分人数 Top', variant: 'gold' as const, prefix: '/dramas/' };
    case 'cv': return { items: safe(props.byCv), unit: ' 部', title: 'CV 参演数 Top', variant: 'cyan' as const, prefix: '/cvs/' };
    default: return { items: safe(props.byPlay), unit: ' 次', title: '播放量 Top', variant: 'brand' as const, prefix: '/dramas/' };
  }
});
</script>

<template>
  <div class="card">
    <div class="flex flex-wrap gap-2 mb-6 pb-4 border-b border-border">
      <button
        v-for="t in tabs"
        :key="t.key"
        @click="metric = t.key"
        :class="[
          'px-4 py-2 rounded-xl text-sm font-medium transition-all',
          metric === t.key
            ? 'bg-gradient-to-r from-brand-500/25 to-accent-500/25 text-brand-200 border border-brand-500/40 shadow-lg shadow-brand-500/10'
            : 'bg-bg-darker text-text-muted border border-border hover:text-text-soft hover:border-brand-500/30',
        ]"
      >{{ t.label }}</button>
    </div>
    <TopNBarChart v-if="current.items.length" :items="current.items" :unit="current.unit" :variant="current.variant" :link-prefix="current.prefix" height={400} />
    <p v-if="!current.items.length" class="text-sm text-text-muted mt-4">暂无数据。</p>
  </div>
</template>
