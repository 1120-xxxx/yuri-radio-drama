<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import {
  getRatingForDrama,
  submitRating,
  hasLocallyRated,
  getDeviceFingerprint,
  type RatingComment,
  type RatingSummary,
} from '../lib/ratings';
import { getBrowserClient } from '../lib/supabase';

const props = defineProps<{
  dramaId: string;
  dramaTitle?: string;
  fallbackAvg?: number; // 剧集自身爬取的评分（实际数据兜底）
  fallbackCount?: number; // 剧集自身爬取的评分人数
}>();

const score = ref<number>(5);
const comment = ref('');
const submitting = ref(false);
const message = ref('');
const summary = ref<RatingSummary>({ avg: 0, count: 0 });
const comments = ref<RatingComment[]>([]);
const alreadyRated = ref(false);
const backendConnected = ref(true);

function setScore(v: number) { if (!alreadyRated.value) score.value = v; }

async function refresh() {
  const data = await getRatingForDrama(props.dramaId, {
    fallbackAvg: props.fallbackAvg,
    fallbackCount: props.fallbackCount,
  });
  summary.value = data.summary;
  comments.value = data.comments;
  backendConnected.value = data.backendConnected;
  alreadyRated.value = hasLocallyRated(props.dramaId);
}

// 乐观更新：提交成功后立即在前端更新 UI，不等服务器返回
function optimisticUpdate(submittedScore: number, submittedComment: string) {
  const newComment: RatingComment = {
    id: 'local_' + Date.now(),
    score: submittedScore,
    comment: submittedComment,
    created_at: new Date().toISOString(),
  };
  // 评论列表：新评论插入到最前面
  comments.value = [newComment, ...comments.value];
  // 重新计算均分
  const totalCount = summary.value.count + 1;
  const totalScore = summary.value.avg * summary.value.count + submittedScore;
  summary.value = {
    avg: totalScore / totalCount,
    count: totalCount,
  };
}

async function handleSubmit() {
  if (submitting.value) return;
  if (alreadyRated.value) { message.value = '您已评分过该剧集'; return; }
  submitting.value = true;
  message.value = '';
  try {
    const res = await submitRating({
      dramaId: props.dramaId,
      score: score.value,
      comment: comment.value.trim(),
      deviceFingerprint: getDeviceFingerprint(),
    });
    message.value = res.message;
    if (res.ok) {
      // 乐观更新：立即在 UI 显示新评分和评论
      optimisticUpdate(score.value, comment.value.trim());
      comment.value = '';
      alreadyRated.value = true;
      // 延迟刷新：等待数据库触发器完成后再同步服务器数据
      setTimeout(refresh, 800);
    }
  } finally {
    submitting.value = false;
  }
}

// Supabase Realtime：订阅本剧集评分变更，其他用户评分也能实时更新
let channel: any = null;
function subscribeRealtime() {
  const sb = getBrowserClient();
  if (!sb) return;
  channel = sb
    .channel(`drama_${props.dramaId}_ratings`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'ratings',
        filter: `drama_id=eq.${props.dramaId}`,
      },
      () => {
        // 有新评分插入时，延迟刷新（等触发器更新 dramas 表）
        setTimeout(refresh, 500);
      }
    )
    .subscribe();
}

onMounted(() => {
  refresh();
  subscribeRealtime();
});

onUnmounted(() => {
  if (channel) {
    const sb = getBrowserClient();
    sb?.removeChannel(channel);
  }
});
</script>

<template>
  <section class="card">
    <h3 class="text-lg font-bold mb-4 text-text">匿名评分与短评</h3>
    <div v-if="!backendConnected" class="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-sm text-amber-300">
      ⚠ 评分服务未连接，评分将无法保存。请稍后再试。
    </div>
    <div class="flex flex-wrap items-start gap-6 mb-6">
      <div class="text-center px-6 py-4 rounded-2xl bg-bg-darker border border-border">
        <div class="text-xs text-text-muted mb-2">当前均分</div>
        <div
          class="text-4xl font-bold bg-gradient-to-r from-brand-400 to-accent-400 bg-clip-text text-transparent tabular-nums">
          {{ summary.avg ? summary.avg.toFixed(2) : '--' }}
        </div>
        <div class="text-xs text-text-muted mt-1">/ 5.00</div>
        <div class="text-xs text-text-faint mt-2">共 {{ summary.count }} 条评分</div>
      </div>
      <div class="flex-1 min-w-[260px]">
        <div class="flex items-center gap-2 mb-3">
          <template v-for="i in 5" :key="i">
            <button type="button" @click="setScore(i)" :disabled="alreadyRated || submitting" :class="[
              'text-2xl transition-all cursor-pointer',
              i <= score
                ? 'text-brand-300 drop-shadow-lg drop-shadow-brand-500/30 scale-110'
                : 'text-text-faint',
              (alreadyRated || submitting) ? 'cursor-not-allowed opacity-60' : 'hover:scale-115 hover:text-brand-200',
            ]" :aria-label="`打 ${i} 星`">★</button>
          </template>
          <span class="text-sm text-text-muted ml-2">{{ score }} 星</span>
        </div>
        <textarea v-model="comment" :disabled="alreadyRated || submitting" rows="2" maxlength="200"
          placeholder="写下你的感受（可选，最多 200 字）"
          class="w-full px-4 py-3 rounded-2xl bg-bg-darker border border-border text-text resize-y focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/20 transition-all text-sm" />
        <div class="flex items-center justify-between mt-3">
          <div class="text-xs text-text-faint">{{ comment.length }} / 200</div>
          <button type="button" @click="handleSubmit" :disabled="alreadyRated || submitting" :class="[
            'px-6 py-2.5 rounded-xl text-sm font-semibold transition-all',
            alreadyRated
              ? 'bg-bg-darker border border-border text-text-muted cursor-not-allowed'
              : 'bg-gradient-to-r from-brand-500 to-accent-500 text-white hover:from-brand-400 hover:to-accent-400 shadow-lg shadow-brand-500/30',
          ]">
            {{ submitting ? '提交中…' : alreadyRated ? '已评分' : '提交评分' }}
          </button>
        </div>
        <div v-if="message" class="text-sm mt-3 text-brand-300">{{ message }}</div>
      </div>
    </div>

    <div v-if="comments.length" class="mt-2">
      <h4 class="text-sm font-semibold mb-3 text-text-soft">最新评论</h4>
      <ul class="space-y-2">
        <li v-for="c in comments.slice(0, 20)" :key="c.id"
          class="py-3 px-4 rounded-2xl bg-bg-darker border border-border/60">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-brand-300 text-sm font-medium">{{ '★'.repeat(c.score) }}<span class="text-text-faint">{{
              '★'.repeat(5 - c.score) }}</span></span>
          </div>
          <div v-if="c.comment" class="text-sm text-text-soft leading-relaxed">{{ c.comment }}</div>
          <div v-else class="text-sm text-text-faint italic">（未留评论）</div>
          <div class="text-xs text-text-faint mt-2">{{ new Date(c.created_at).toLocaleString() }}</div>
        </li>
      </ul>
    </div>
    <div v-else class="text-sm text-text-muted mt-4 py-8 text-center rounded-2xl border border-dashed border-border">
      暂无评分，快来留下第一条吧 ✨
    </div>
  </section>
</template>
