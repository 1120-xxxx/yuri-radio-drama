<script setup lang="ts">
import { ref, computed } from 'vue';

interface CollabDrama { id: string; title: string; platform?: string; }
interface Collaboration {
  cv1_id: string; cv1_name: string;
  cv2_id: string; cv2_name: string;
  count: number;
  dramas: CollabDrama[];
}

const props = defineProps<{
  collaborations: Collaboration[];
}>();

const selected = ref<Collaboration | null>(null);

const sorted = computed(() =>
  [...props.collaborations].sort((a, b) => b.count - a.count)
);

const topPairs = computed(() => sorted.value.slice(0, 30));

function tagSize(count: number) {
  // 根据合作次数返回不同的样式类
  if (count >= 5) return 'text-base px-4 py-2';
  if (count >= 3) return 'text-sm px-3 py-1.5';
  return 'text-xs px-2.5 py-1';
}

function tagColor(count: number) {
  if (count >= 5) return 'from-brand-500/30 to-accent-500/30 border-brand-400/50 text-brand-200 shadow-lg shadow-brand-500/10';
  if (count >= 3) return 'from-cyanx-500/25 to-brand-500/25 border-cyanx-400/40 text-cyanx-200';
  return 'from-bg-darker to-bg-soft border-border text-text-soft';
}

function openDetail(collab: Collaboration) {
  selected.value = collab;
}

function closeDetail() {
  selected.value = null;
}
</script>

<template>
  <div>
    <!-- 高频CP标签云 -->
    <div class="card mb-6">
      <h2 class="section-title mb-4">高频 CP</h2>
      <p class="text-sm text-text-muted mb-5">展示高频合作的CV组合，标签越大合作越多。点击查看合作详情。</p>
      <div class="flex flex-wrap gap-3">
        <button
          v-for="pair in topPairs"
          :key="`${pair.cv1_id}-${pair.cv2_id}`"
          @click="openDetail(pair)"
          :class="[
            'rounded-xl border bg-gradient-to-r transition-all hover:scale-105 hover:shadow-brand-500/20 cursor-pointer font-medium',
            tagSize(pair.count),
            tagColor(pair.count),
          ]"
        >
          {{ pair.cv1_name }} × {{ pair.cv2_name }}
          <span class="ml-1 opacity-70">{{ pair.count }}部</span>
        </button>
      </div>
      <p v-if="!topPairs.length" class="text-sm text-text-muted mt-4">暂无CV合作数据，需要更多CV关联信息。</p>
    </div>

    <!-- 高频合作CP榜单 -->
    <div class="card">
      <h2 class="section-title mb-4">高频合作 CP 榜</h2>
      <div class="space-y-2">
        <div
          v-for="(pair, idx) in sorted.slice(0, 20)"
          :key="`${pair.cv1_id}-${pair.cv2_id}`"
          @click="openDetail(pair)"
          class="flex items-center gap-4 py-3 px-4 rounded-xl hover:bg-bg-darker hover:border-brand-500/20 border border-transparent transition-all cursor-pointer"
        >
          <span
            :class="[
              'w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold',
              idx < 3 ? 'bg-gradient-to-br from-brand-500 to-accent-500 text-white shadow-lg shadow-brand-500/20' : 'bg-bg-darker text-text-muted border border-border',
            ]"
          >{{ idx + 1 }}</span>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-text-soft">
              <a :href="`/cvs/${pair.cv1_id}/`" class="hover:text-brand-300 transition-colors" @click.stop>{{ pair.cv1_name }}</a>
              <span class="text-brand-400 mx-1">×</span>
              <a :href="`/cvs/${pair.cv2_id}/`" class="hover:text-brand-300 transition-colors" @click.stop>{{ pair.cv2_name }}</a>
            </div>
          </div>
          <div class="text-right">
            <span class="text-lg font-bold bg-gradient-to-r from-brand-400 to-accent-400 bg-clip-text text-transparent">{{ pair.count }}</span>
            <span class="text-xs text-text-muted ml-1">部合作</span>
          </div>
          <svg class="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        </div>
      </div>
      <p v-if="!sorted.length" class="text-sm text-text-muted mt-4">暂无CV合作数据。</p>
    </div>

    <!-- 弹窗：合作详情 -->
    <Teleport to="body">
      <div
        v-if="selected"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="closeDetail"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="closeDetail"></div>
        <div class="relative bg-bg-card border border-border rounded-2xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto p-6">
          <button @click="closeDetail" class="absolute top-4 right-4 text-text-muted hover:text-text transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>

          <h3 class="text-xl font-bold text-text mb-1">
            <a :href="`/cvs/${selected.cv1_id}/`" class="hover:text-brand-300 transition-colors">{{ selected.cv1_name }}</a>
            <span class="text-brand-400 mx-2">×</span>
            <a :href="`/cvs/${selected.cv2_id}/`" class="hover:text-brand-300 transition-colors">{{ selected.cv2_name }}</a>
          </h3>
          <p class="text-sm text-text-muted mb-5">合作 {{ selected.count }} 部作品</p>

          <div class="space-y-2">
            <div
              v-for="drama in selected.dramas"
              :key="drama.id"
              class="flex items-center gap-3 py-2.5 px-3 rounded-xl bg-bg-darker border border-border/60 hover:border-brand-500/30 transition-all"
            >
              <span class="text-lg">🎙️</span>
              <a :href="`/dramas/${drama.id}/`" class="flex-1 font-medium text-text-soft hover:text-brand-300 transition-colors truncate">{{ drama.title }}</a>
              <span v-if="drama.platform" class="text-xs px-2 py-0.5 rounded-full bg-bg-soft text-text-muted border border-border">{{ drama.platform }}</span>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
