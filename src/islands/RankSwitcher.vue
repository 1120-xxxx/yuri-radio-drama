<script setup lang="ts">
import { ref, computed } from 'vue';

interface Work {
  id: string;
  title: string;
  platform?: string;
  play_count?: number;
  year?: number;
}

interface Item {
  id: string;
  title: string;
  value: number;
  display: string;
  platform?: string;
  works?: Work[];
}

const props = defineProps<{
  byPlay?: Item[];
  byRating?: Item[];
  byCv?: Item[];
  byAuthor?: Item[];
}>();

type Metric = 'play' | 'rating' | 'cv' | 'author';
const metric = ref<Metric>('play');

const tabs: { key: Metric; label: string }[] = [
  { key: 'play', label: '播放量榜' },
  { key: 'rating', label: '评分榜' },
  { key: 'cv', label: 'CV 参演榜' },
  { key: 'author', label: '作者改编榜' },
];

function safe(arr: Item[] | undefined): Item[] { return Array.isArray(arr) ? arr : []; }

const current = computed(() => {
  switch (metric.value) {
    case 'rating': return { items: safe(props.byRating), prefix: '/dramas/', kind: 'drama' as const };
    case 'cv': return { items: safe(props.byCv), prefix: '/cvs/', kind: 'cv' as const };
    case 'author': return { items: safe(props.byAuthor), prefix: '/dramas/', kind: 'author' as const };
    default: return { items: safe(props.byPlay), prefix: '/dramas/', kind: 'drama' as const };
  }
});

// 作者作品弹窗
const modalAuthor = ref<Item | null>(null);
function openAuthorWorks(item: Item) { modalAuthor.value = item; }
function closeAuthorWorks() { modalAuthor.value = null; }

function fmtPlay(n?: number): string {
  if (!n) return '0';
  if (n >= 10000) return `${(n / 10000).toFixed(1)} 万`;
  return String(n);
}

// 排名样式
function rankClass(idx: number): string {
  if (idx === 0) return 'bg-gradient-to-br from-yellow-500/20 to-amber-500/10 border-yellow-500/40';
  if (idx === 1) return 'bg-gradient-to-br from-slate-400/15 to-slate-300/10 border-slate-400/40';
  if (idx === 2) return 'bg-gradient-to-br from-orange-700/15 to-amber-700/10 border-orange-700/40';
  return 'bg-bg-darker border-border';
}
function rankBadge(idx: number): string {
  if (idx === 0) return 'from-yellow-400 to-amber-500 text-black';
  if (idx === 1) return 'from-slate-300 to-slate-400 text-black';
  if (idx === 2) return 'from-orange-500 to-amber-700 text-white';
  return 'from-brand-500/30 to-accent-500/30 text-text-soft';
}
</script>

<template>
  <div class="card">
    <!-- Tab 切换 -->
    <div class="flex flex-wrap gap-2 mb-6 pb-4 border-b border-border">
      <button v-for="t in tabs" :key="t.key" @click="metric = t.key" :class="[
        'px-4 py-2 rounded-xl text-sm font-medium transition-all',
        metric === t.key
          ? 'bg-gradient-to-r from-brand-500/25 to-accent-500/25 text-brand-200 border border-brand-500/40 shadow-lg shadow-brand-500/10'
          : 'bg-bg-darker text-text-muted border border-border hover:text-text-soft hover:border-brand-500/30',
      ]">{{ t.label }}</button>
    </div>

    <!-- 卡片列表 -->
    <div v-if="current.items.length" class="space-y-2">
      <!-- 播放量榜 / 评分榜：广播剧卡片 -->
      <template v-if="current.kind === 'drama'">
        <a
          v-for="(item, idx) in current.items"
          :key="item.id"
          :href="`${current.prefix}${item.id}/`"
          class="flex items-center gap-4 p-3 rounded-xl border transition-all hover:border-brand-500/40 hover:shadow-lg hover:shadow-brand-500/10 hover:-translate-y-0.5 group"
          :class="rankClass(idx)"
        >
          <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm bg-gradient-to-br"
            :class="rankBadge(idx)">
            {{ idx + 1 }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-text truncate group-hover:text-brand-300 transition-colors">{{ item.title }}</div>
            <div class="text-xs text-text-muted mt-0.5">
              <span v-if="item.platform" class="px-1.5 py-0.5 rounded bg-bg-soft/60 border border-border/40">{{ item.platform }}</span>
            </div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="font-bold tabular-nums bg-gradient-to-r from-brand-300 to-accent-300 bg-clip-text text-transparent">{{ item.display }}</div>
            <div class="text-[10px] text-text-faint mt-0.5">{{ metric === 'play' ? '播放量' : '评分' }}</div>
          </div>
        </a>
      </template>

      <!-- CV 参演榜：CV 卡片 -->
      <template v-else-if="current.kind === 'cv'">
        <a
          v-for="(item, idx) in current.items"
          :key="item.id"
          :href="`${current.prefix}${item.id}/`"
          class="flex items-center gap-4 p-3 rounded-xl border transition-all hover:border-brand-500/40 hover:shadow-lg hover:shadow-brand-500/10 hover:-translate-y-0.5 group"
          :class="rankClass(idx)"
        >
          <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm bg-gradient-to-br"
            :class="rankBadge(idx)">
            {{ idx + 1 }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-text truncate group-hover:text-brand-300 transition-colors">{{ item.title }}</div>
            <div class="text-xs text-text-faint mt-0.5">CV</div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="font-bold tabular-nums text-cyanx-300">{{ item.display }}</div>
            <div class="text-[10px] text-text-faint mt-0.5">参演数</div>
          </div>
        </a>
      </template>

      <!-- 作者改编榜：作者卡片（点击弹窗） -->
      <template v-else-if="current.kind === 'author'">
        <button
          v-for="(item, idx) in current.items"
          :key="item.id"
          @click="openAuthorWorks(item)"
          class="w-full flex items-center gap-4 p-3 rounded-xl border transition-all hover:border-emerald-500/40 hover:shadow-lg hover:shadow-emerald-500/10 hover:-translate-y-0.5 group text-left"
          :class="rankClass(idx)"
        >
          <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm bg-gradient-to-br"
            :class="rankBadge(idx)">
            {{ idx + 1 }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-text truncate group-hover:text-emerald-300 transition-colors">{{ item.title }}</div>
            <div class="text-xs text-text-faint mt-0.5">原作作者</div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="font-bold tabular-nums bg-gradient-to-r from-emerald-300 to-cyanx-300 bg-clip-text text-transparent">{{ item.display }}</div>
            <div class="text-[10px] text-text-faint mt-0.5">改编数</div>
          </div>
        </button>
      </template>
    </div>

    <p v-else class="text-sm text-text-muted mt-4">暂无数据。</p>

    <!-- 作者作品弹窗：Teleport 到 body 确保相对屏幕居中 -->
    <Teleport to="body">
      <div v-if="modalAuthor" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click.self="closeAuthorWorks">
        <div class="bg-bg-card border border-border rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col">
          <div class="flex items-center justify-between p-5 border-b border-border">
            <div>
              <h3 class="text-xl font-bold text-text">{{ modalAuthor.title }}</h3>
              <p class="text-sm text-text-muted mt-1">原作作者 · 共 {{ modalAuthor.works?.length ?? 0 }} 部改编作品</p>
            </div>
            <button @click="closeAuthorWorks" class="p-2 rounded-lg hover:bg-bg-darker text-text-muted hover:text-text transition-colors" aria-label="关闭">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-5 space-y-2">
            <a
              v-for="w in modalAuthor.works"
              :key="w.id"
              :href="`/dramas/${w.id}/`"
              class="flex items-center justify-between gap-3 p-3 rounded-xl bg-bg-darker border border-border hover:border-brand-500/40 hover:bg-bg-soft transition-all group"
            >
              <div class="flex-1 min-w-0">
                <div class="font-medium text-text truncate group-hover:text-brand-300 transition-colors">{{ w.title }}</div>
                <div class="text-xs text-text-muted mt-0.5 flex items-center gap-2">
                  <span v-if="w.platform" class="px-1.5 py-0.5 rounded bg-bg-soft/60 border border-border/40">{{ w.platform }}</span>
                  <span v-if="w.year">{{ w.year }}</span>
                </div>
              </div>
              <div v-if="w.play_count" class="text-sm text-text-muted tabular-nums flex-shrink-0">{{ fmtPlay(w.play_count) }} 播放</div>
            </a>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
