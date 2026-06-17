<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { getBrowserClient } from '../lib/supabase';

interface RatingRow {
  id: string;
  drama_id: string;
  score: number;
  comment: string | null;
  ip_hash: string | null;
  device_fingerprint: string | null;
  created_at: string;
}

interface DramaInfo {
  id: string;
  title: string;
  rating_avg: number;
  rating_count: number;
}

const ratings = ref<RatingRow[]>([]);
const dramas = ref<Map<string, DramaInfo>>(new Map());
const loading = ref(true);
const errorMsg = ref('');
const filterScore = ref<number>(0); // 0 = 全部
const searchKeyword = ref('');

const filteredRatings = computed(() => {
  let list = ratings.value;
  if (filterScore.value > 0) {
    list = list.filter((r) => r.score === filterScore.value);
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase();
    list = list.filter((r) => {
      const title = dramas.value.get(r.drama_id)?.title ?? r.drama_id;
      return title.toLowerCase().includes(kw) || (r.comment ?? '').toLowerCase().includes(kw);
    });
  }
  return list;
});

const stats = computed(() => {
  const total = ratings.value.length;
  const avg = total > 0 ? ratings.value.reduce((s, r) => s + r.score, 0) / total : 0;
  const withComment = ratings.value.filter((r) => r.comment && r.comment.trim()).length;
  return { total, avg, withComment };
});

async function loadData() {
  loading.value = true;
  errorMsg.value = '';
  const sb = getBrowserClient();
  if (!sb) {
    errorMsg.value = '未配置 Supabase。请在 .env 中设置 PUBLIC_SUPABASE_URL 和 PUBLIC_SUPABASE_ANON_KEY。';
    loading.value = false;
    return;
  }
  try {
    // 加载所有剧集（用于显示标题）
    const { data: dramaRows } = await sb
      .from('dramas')
      .select('id, title, rating_avg, rating_count')
      .order('rating_count', { ascending: false });
    const dramaMap = new Map<string, DramaInfo>();
    for (const d of (dramaRows as DramaInfo[]) ?? []) {
      dramaMap.set(d.id, d);
    }
    dramas.value = dramaMap;

    // 加载所有评分（最多 1000 条）
    const { data: ratingRows, error } = await sb
      .from('ratings')
      .select('id, drama_id, score, comment, ip_hash, device_fingerprint, created_at')
      .order('created_at', { ascending: false })
      .limit(1000);
    if (error) throw error;
    ratings.value = (ratingRows as RatingRow[]) ?? [];
  } catch (e: any) {
    errorMsg.value = `加载失败：${e.message ?? String(e)}`;
  } finally {
    loading.value = false;
  }
}

function dramaTitle(id: string): string {
  return dramas.value.get(id)?.title ?? id;
}

function dramaRating(id: string): { avg: number; count: number } | null {
  const d = dramas.value.get(id);
  if (!d) return null;
  return { avg: d.rating_avg, count: d.rating_count };
}

function formatTime(s: string): string {
  try {
    return new Date(s).toLocaleString('zh-CN');
  } catch {
    return s;
  }
}

onMounted(loadData);
</script>

<template>
  <div>
    <!-- 统计概览 -->
    <div class="grid grid-cols-3 gap-4 mb-6">
      <div class="card text-center">
        <div class="text-xs text-text-muted mb-1">总评分数</div>
        <div class="text-2xl font-bold bg-gradient-to-r from-brand-400 to-accent-400 bg-clip-text text-transparent tabular-nums">{{ stats.total }}</div>
      </div>
      <div class="card text-center">
        <div class="text-xs text-text-muted mb-1">平均分</div>
        <div class="text-2xl font-bold text-text-soft tabular-nums">{{ stats.avg.toFixed(2) }}</div>
      </div>
      <div class="card text-center">
        <div class="text-xs text-text-muted mb-1">含短评数</div>
        <div class="text-2xl font-bold text-text-soft tabular-nums">{{ stats.withComment }}</div>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="card mb-6">
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2">
          <span class="text-sm text-text-muted">评分筛选：</span>
          <button
            v-for="s in [0, 1, 2, 3, 4, 5]"
            :key="s"
            @click="filterScore = s"
            :class="[
              'px-3 py-1 rounded-lg text-sm transition-all',
              filterScore === s
                ? 'bg-brand-500/25 text-brand-200 border border-brand-500/40'
                : 'bg-bg-darker text-text-muted border border-border hover:text-text-soft',
            ]"
          >{{ s === 0 ? '全部' : `${s} 星` }}</button>
        </div>
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="搜索剧集名或短评内容..."
            class="w-full px-4 py-2 rounded-xl bg-bg-darker border border-border text-text text-sm focus:outline-none focus:border-brand-500/50"
          />
        </div>
        <button @click="loadData" class="px-4 py-2 rounded-xl bg-bg-darker border border-border text-text-soft text-sm hover:border-brand-500/30 transition-all">
          刷新
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="card mb-6 border-gold-500/30">
      <p class="text-sm text-gold-300">{{ errorMsg }}</p>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card text-center py-12">
      <p class="text-text-muted">加载中...</p>
    </div>

    <!-- 评分列表 -->
    <div v-else-if="filteredRatings.length" class="card">
      <h2 class="section-title mb-4">评分与短评（{{ filteredRatings.length }} / {{ ratings.length }}）</h2>
      <ul class="space-y-2">
        <li
          v-for="r in filteredRatings"
          :key="r.id"
          class="py-3 px-4 rounded-xl bg-bg-darker border border-border/60"
        >
          <div class="flex items-start gap-3">
            <div class="flex-shrink-0">
              <span class="text-brand-300 text-sm font-medium">{{ '★'.repeat(r.score) }}</span>
              <span class="text-text-faint text-sm">{{ '★'.repeat(5 - r.score) }}</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <a :href="`/dramas/${r.drama_id}/`" class="font-medium text-text-soft hover:text-brand-300 transition-colors truncate">
                  {{ dramaTitle(r.drama_id) }}
                </a>
                <span class="text-xs text-text-faint">·</span>
                <span class="text-xs text-text-muted">{{ formatTime(r.created_at) }}</span>
              </div>
              <div v-if="r.comment" class="text-sm text-text leading-relaxed mt-1">{{ r.comment }}</div>
              <div v-else class="text-xs text-text-faint italic mt-1">（未留评论）</div>
              <div class="text-xs text-text-faint mt-2">
                ID: {{ r.id.slice(0, 8) }} · IP哈希: {{ r.ip_hash ?? '-' }} · 设备: {{ r.device_fingerprint ?? '-' }}
              </div>
            </div>
            <div v-if="dramaRating(r.drama_id)" class="text-right text-xs text-text-muted flex-shrink-0">
              <div>该剧聚合</div>
              <div class="font-semibold text-text-soft">{{ dramaRating(r.drama_id)!.avg.toFixed(2) }} 分</div>
              <div>{{ dramaRating(r.drama_id)!.count }} 条</div>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <div v-else class="card text-center py-12">
      <p class="text-text-muted">暂无评分数据。</p>
    </div>
  </div>
</template>
