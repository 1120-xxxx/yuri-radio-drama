<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

interface DramaSummary {
  id: string;
  title: string;
  platform: string;
  year: number;
  play_count: number;
  rating_avg: number;
  rating_count: number;
  tags?: string[];
  cover_url?: string;
  is_completed?: boolean;
}

const props = defineProps<{ dramas?: DramaSummary[] }>();

const q = ref('');
const selectedPlatforms = ref<string[]>([]);
const selectedYears = ref<string[]>([]);
const selectedTags = ref<string[]>([]);
const sort = ref<'play' | 'rating'>('play');

const platformDropdownOpen = ref(false);
const yearDropdownOpen = ref(false);
const sortDropdownOpen = ref(false);

const safe = computed(() => (Array.isArray(props.dramas) ? props.dramas : []));

const allPlatforms = computed(() => Array.from(new Set(safe.value.map((d) => d.platform))));
const allYears = computed(() => Array.from(new Set(safe.value.map((d) => String(d.year)))).sort((a, b) => Number(b) - Number(a)));
const allTags = computed(() => {
  // 统计每个标签的出现次数，只保留高频标签（>=2部剧使用），取前25个
  const counts = new Map<string, number>();
  for (const d of safe.value) {
    if (d.tags) for (const t of d.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .filter(([, c]) => c >= 2) // 至少2部剧使用
    .sort((a, b) => b[1] - a[1]) // 按频次降序
    .slice(0, 25) // 只展示前25个
    .map(([t]) => t);
});

const filtered = computed(() => {
  const kw = q.value.trim().toLowerCase();
  let list = safe.value.filter((d) => {
    const matchKw = !kw || d.title.toLowerCase().includes(kw) || d.platform.toLowerCase().includes(kw);
    const matchP = selectedPlatforms.value.length === 0 || selectedPlatforms.value.includes(d.platform);
    const matchY = selectedYears.value.length === 0 || selectedYears.value.includes(String(d.year));
    const matchT = selectedTags.value.length === 0 || (d.tags && selectedTags.value.every((t) => d.tags!.includes(t)));
    return matchKw && matchP && matchY && matchT;
  });
  list = list.slice().sort((a, b) => sort.value === 'play' ? b.play_count - a.play_count : b.rating_avg - a.rating_avg);
  return list;
});

function fmt(n: number) {
  return n >= 10000 ? `${(n / 10000).toFixed(1)} 万` : String(n);
}

function togglePlatform(p: string) {
  const i = selectedPlatforms.value.indexOf(p);
  if (i >= 0) selectedPlatforms.value.splice(i, 1);
  else selectedPlatforms.value.push(p);
}
function toggleYear(y: string) {
  const i = selectedYears.value.indexOf(y);
  if (i >= 0) selectedYears.value.splice(i, 1);
  else selectedYears.value.push(y);
}
function toggleTag(t: string) {
  const i = selectedTags.value.indexOf(t);
  if (i >= 0) selectedTags.value.splice(i, 1);
  else selectedTags.value.push(t);
}
function clearAll() {
  selectedPlatforms.value = [];
  selectedYears.value = [];
  selectedTags.value = [];
  q.value = '';
}

function closeDropdowns(e: Event) {
  const target = e.target as HTMLElement;
  if (!target.closest('[data-dropdown]')) {
    platformDropdownOpen.value = false;
    yearDropdownOpen.value = false;
    sortDropdownOpen.value = false;
  }
}

onMounted(() => document.addEventListener('click', closeDropdowns));
onBeforeUnmount(() => document.removeEventListener('click', closeDropdowns));
</script>

<template>
  <div class="card">
    <!-- 搜索 + 筛选按钮 -->
    <div class="relative mb-5" data-dropdown>
      <div class="flex items-center gap-3 px-5 py-4 rounded-2xl bg-gradient-to-r from-bg-darker to-bg-soft border border-border hover:border-brand-500/30 transition-colors">
        <span class="text-text-muted text-lg">🔍</span>
        <input
          v-model="q"
          placeholder="搜索剧名、平台或关键词…"
          class="flex-1 bg-transparent text-text placeholder:text-text-faint outline-none text-sm"
        />
        <button
          v-if="q || selectedPlatforms.length || selectedYears.length || selectedTags.length"
          @click.stop="clearAll"
          class="px-3 py-1.5 rounded-lg text-xs text-text-muted hover:text-brand-300 hover:bg-brand-500/10 transition-colors"
        >清空</button>
      </div>
    </div>

    <!-- 自定义下拉框组 -->
    <div class="flex flex-wrap gap-3 mb-5">
      <!-- 平台下拉 -->
      <div class="relative" data-dropdown>
        <button
          @click.stop="platformDropdownOpen = !platformDropdownOpen; yearDropdownOpen = false; sortDropdownOpen = false"
          class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-bg-darker border border-border hover:border-brand-500/40 hover:bg-bg-soft transition-all text-sm"
          :class="{ 'border-brand-500/60 bg-bg-soft': platformDropdownOpen || selectedPlatforms.length > 0 }"
        >
          <span class="text-text-muted">📻</span>
          <span class="text-text-soft">平台</span>
          <span v-if="selectedPlatforms.length" class="px-2 py-0.5 rounded-full text-xs bg-gradient-to-r from-brand-500 to-accent-500 text-white font-semibold">{{ selectedPlatforms.length }}</span>
          <span class="text-text-faint transition-transform" :class="{ 'rotate-180': platformDropdownOpen }">▾</span>
        </button>
        <div
          v-if="platformDropdownOpen"
          class="absolute top-full left-0 mt-2 w-48 p-2 rounded-2xl bg-bg-darker border border-border shadow-2xl shadow-black/40 backdrop-blur-xl z-30 origin-top"
        >
          <div class="px-2 py-1.5 text-xs text-text-faint uppercase tracking-wider">选择平台</div>
          <button
            v-for="p in allPlatforms"
            :key="p"
            @click.stop="togglePlatform(p)"
            class="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-sm hover:bg-bg-soft transition-colors"
            :class="selectedPlatforms.includes(p) ? 'text-brand-300 bg-brand-500/10' : 'text-text-soft'"
          >
            <span>{{ p }}</span>
            <span v-if="selectedPlatforms.includes(p)" class="text-brand-300 font-bold">✓</span>
          </button>
        </div>
      </div>

      <!-- 年份下拉 -->
      <div class="relative" data-dropdown>
        <button
          @click.stop="yearDropdownOpen = !yearDropdownOpen; platformDropdownOpen = false; sortDropdownOpen = false"
          class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-bg-darker border border-border hover:border-brand-500/40 hover:bg-bg-soft transition-all text-sm"
          :class="{ 'border-brand-500/60 bg-bg-soft': yearDropdownOpen || selectedYears.length > 0 }"
        >
          <span class="text-text-muted">📅</span>
          <span class="text-text-soft">年份</span>
          <span v-if="selectedYears.length" class="px-2 py-0.5 rounded-full text-xs bg-gradient-to-r from-accent-500 to-brand-500 text-white font-semibold">{{ selectedYears.length }}</span>
          <span class="text-text-faint transition-transform" :class="{ 'rotate-180': yearDropdownOpen }">▾</span>
        </button>
        <div
          v-if="yearDropdownOpen"
          class="absolute top-full left-0 mt-2 w-36 p-2 rounded-2xl bg-bg-darker border border-border shadow-2xl shadow-black/40 backdrop-blur-xl z-30 origin-top"
        >
          <div class="px-2 py-1.5 text-xs text-text-faint uppercase tracking-wider">选择年份</div>
          <button
            v-for="y in allYears"
            :key="y"
            @click.stop="toggleYear(y)"
            class="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-sm hover:bg-bg-soft transition-colors"
            :class="selectedYears.includes(y) ? 'text-accent-300 bg-accent-500/10' : 'text-text-soft'"
          >
            <span>{{ y }}</span>
            <span v-if="selectedYears.includes(y)" class="text-accent-300 font-bold">✓</span>
          </button>
        </div>
      </div>

      <!-- 排序下拉 -->
      <div class="relative" data-dropdown>
        <button
          @click.stop="sortDropdownOpen = !sortDropdownOpen; platformDropdownOpen = false; yearDropdownOpen = false"
          class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-bg-darker border border-border hover:border-brand-500/40 hover:bg-bg-soft transition-all text-sm"
          :class="{ 'border-brand-500/60 bg-bg-soft': sortDropdownOpen }"
        >
          <span class="text-text-muted">↕️</span>
          <span class="text-text-soft">{{ sort === 'play' ? '按播放量' : '按评分' }}</span>
          <span class="text-text-faint transition-transform" :class="{ 'rotate-180': sortDropdownOpen }">▾</span>
        </button>
        <div
          v-if="sortDropdownOpen"
          class="absolute top-full left-0 mt-2 w-36 p-2 rounded-2xl bg-bg-darker border border-border shadow-2xl shadow-black/40 backdrop-blur-xl z-30 origin-top"
        >
          <div class="px-2 py-1.5 text-xs text-text-faint uppercase tracking-wider">排序方式</div>
          <button
            v-for="opt in [{ key: 'play', label: '按播放量' }, { key: 'rating', label: '按评分' }]"
            :key="opt.key"
            @click.stop="sort = opt.key as any; sortDropdownOpen = false"
            class="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-sm hover:bg-bg-soft transition-colors"
            :class="sort === opt.key ? 'text-cyanx-400 bg-cyanx-500/10' : 'text-text-soft'"
          >
            <span>{{ opt.label }}</span>
            <span v-if="sort === opt.key" class="text-cyanx-400 font-bold">✓</span>
          </button>
        </div>
      </div>

      <!-- 结果统计 -->
      <div class="flex-1 min-w-[120px] flex items-center justify-end gap-2 px-4 py-2.5 rounded-xl bg-bg-darker/50 border border-border/50 text-sm text-text-muted">
        共 <span class="text-text-soft font-bold tabular-nums">{{ filtered.length }}</span> 部
      </div>
    </div>

    <!-- 标签云 -->
    <div v-if="allTags.length > 0" class="mb-6 p-4 rounded-2xl bg-gradient-to-br from-bg-darker/80 to-bg-soft/40 border border-border/60">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2 text-sm text-text-muted">
          <span class="text-text-soft">🏷️</span>
          <span>风格标签</span>
          <span v-if="selectedTags.length" class="px-2 py-0.5 rounded-full text-xs bg-gradient-to-r from-gold-400 to-brand-500 text-white font-semibold">已选 {{ selectedTags.length }}</span>
        </div>
        <button
          v-if="selectedTags.length"
          @click="selectedTags = []"
          class="text-xs text-text-faint hover:text-brand-300 transition-colors"
        >清除</button>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in allTags"
          :key="t"
          @click="toggleTag(t)"
          class="px-3.5 py-1.5 rounded-full text-xs font-medium transition-all hover:scale-105"
          :class="[
            selectedTags.includes(t)
              ? 'bg-gradient-to-r from-brand-500 to-accent-500 text-white shadow-md shadow-brand-500/30 border border-transparent'
              : 'bg-bg-darker text-text-muted border border-border hover:text-text-soft hover:border-brand-500/50',
          ]"
        ># {{ t }}</button>
      </div>
    </div>

    <!-- 已选筛选条件摘要 -->
    <div
      v-if="selectedPlatforms.length || selectedYears.length || selectedTags.length"
      class="mb-5 flex flex-wrap gap-2"
    >
      <span class="text-xs text-text-faint self-center">已选：</span>
      <button
        v-for="p in selectedPlatforms"
        :key="'p-' + p"
        @click="togglePlatform(p)"
        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-brand-500/10 text-brand-300 border border-brand-500/30 hover:bg-brand-500/20 transition-colors"
      >📻 {{ p }} <span class="text-brand-400">×</span></button>
      <button
        v-for="y in selectedYears"
        :key="'y-' + y"
        @click="toggleYear(y)"
        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-accent-500/10 text-accent-300 border border-accent-500/30 hover:bg-accent-500/20 transition-colors"
      >📅 {{ y }} <span class="text-accent-400">×</span></button>
      <button
        v-for="t in selectedTags"
        :key="'t-' + t"
        @click="toggleTag(t)"
        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-gold-400/10 text-gold-400 border border-gold-400/30 hover:bg-gold-400/20 transition-colors"
      ># {{ t }} <span class="text-gold-500">×</span></button>
    </div>

    <!-- 剧集卡片列表 -->
    <div v-if="filtered.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <a
        v-for="d in filtered"
        :key="d.id"
        :href="`/dramas/${d.id}/`"
        class="block p-4 rounded-2xl bg-bg-darker border border-border hover:border-brand-500/40 hover:shadow-xl hover:shadow-brand-500/10 hover:-translate-y-0.5 transition-all group overflow-hidden"
      >
        <div class="flex gap-3">
          <div class="flex-shrink-0 w-16 h-20 rounded-lg overflow-hidden bg-bg-soft border border-border/60">
            <img v-if="d.cover_url" :src="d.cover_url" :alt="d.title" loading="lazy" referrerpolicy="no-referrer"
              class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex items-center justify-center text-2xl opacity-50">🎙️</div>
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-text truncate group-hover:text-brand-300 transition-colors mb-1">{{ d.title }}</div>
            <div class="flex items-center gap-1.5 text-xs text-text-muted mb-2 flex-wrap">
              <span class="px-1.5 py-0.5 rounded-md bg-bg-soft border border-border/60">{{ d.platform }}</span>
              <span class="text-text-faint">·</span>
              <span>{{ d.year }}</span>
              <span v-if="d.is_completed" class="px-1.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">已完结</span>
            </div>
            <div v-if="d.tags && d.tags.length" class="flex flex-wrap gap-1 mb-2">
              <span v-for="t in d.tags.slice(0, 3)" :key="t" class="text-[10px] px-1.5 py-0.5 rounded bg-bg-soft/60 text-text-faint border border-border/40">{{ t }}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center justify-between pt-2 mt-1 border-t border-border/40">
          <span class="bg-gradient-to-r from-brand-400 to-accent-400 bg-clip-text text-transparent font-bold tabular-nums">★ {{ d.rating_avg.toFixed(2) }}</span>
          <span class="text-xs text-text-muted tabular-nums">{{ fmt(d.play_count) }} 次</span>
        </div>
      </a>
    </div>
    <div v-else class="text-center py-16 rounded-2xl border border-dashed border-border/50 bg-bg-darker/30">
      <div class="text-5xl mb-4 opacity-40">🔍</div>
      <div class="text-text-soft font-semibold mb-2">暂无匹配的剧集</div>
      <div class="text-sm text-text-muted">试试调整搜索关键词或筛选条件</div>
    </div>
  </div>
</template>
