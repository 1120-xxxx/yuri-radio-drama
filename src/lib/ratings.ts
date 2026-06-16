// Rating helpers — Supabase-powered anonymous ratings.
// Gracefully degrades to a local storage demo when Supabase is not configured.

import { getBrowserClient } from './supabase';

export interface RatingSummary {
  avg: number;
  count: number;
}

export interface RatingComment {
  id: string;
  score: number;
  comment: string;
  created_at: string;
}

const LS_KEY_PREFIX = 'yuri_rated_drama_';

export function hasLocallyRated(dramaId: string): boolean {
  try {
    return !!localStorage.getItem(LS_KEY_PREFIX + dramaId);
  } catch {
    return false;
  }
}

function markLocallyRated(dramaId: string, score: number): void {
  try {
    localStorage.setItem(LS_KEY_PREFIX + dramaId, String(score));
  } catch {
    /* ignore */
  }
}

export async function getRatingForDrama(dramaId: string): Promise<{
  summary: RatingSummary;
  comments: RatingComment[];
  backendConnected: boolean;
}> {
  const sb = getBrowserClient();
  if (!sb) {
    // Local demo mode — 随机一个平均分与空评论
    return {
      summary: { avg: 4.5, count: 120 },
      comments: [],
      backendConnected: false,
    };
  }
  const [{ data: rows, error }, { data: avgRow }] = await Promise.all([
    sb
      .from('ratings')
      .select('id, score, comment, created_at')
      .eq('drama_id', dramaId)
      .order('created_at', { ascending: false })
      .limit(50),
    sb
      .from('dramas')
      .select('rating_avg, rating_count')
      .eq('id', dramaId)
      .single()
      .maybeSingle(),
  ]);
  if (error && error.code !== 'PGRST116') {
    // Fall back to computed avg if the table does not yet exist or has no data
  }
  const list = (rows as RatingComment[]) ?? [];
  const computed =
    list.length > 0
      ? {
          avg: list.reduce((s, r) => s + r.score, 0) / list.length,
          count: list.length,
        }
      : { avg: 0, count: 0 };
  const summary: RatingSummary =
    (avgRow as any)?.rating_avg != null
      ? {
          avg: Number((avgRow as any).rating_avg),
          count: Number((avgRow as any).rating_count ?? computed.count),
        }
      : computed;
  return { summary, comments: list, backendConnected: true };
}

export interface SubmitRatingPayload {
  dramaId: string;
  score: number; // 1-5
  comment?: string;
  deviceFingerprint?: string;
}

export async function submitRating(payload: SubmitRatingPayload): Promise<{
  ok: boolean;
  message: string;
}> {
  if (payload.score < 1 || payload.score > 5) {
    return { ok: false, message: '评分必须在 1 到 5 之间' };
  }
  if (payload.comment && payload.comment.length > 200) {
    return { ok: false, message: '短评长度不得超过 200 字' };
  }
  if (hasLocallyRated(payload.dramaId)) {
    return { ok: false, message: '您已评分过该剧集' };
  }
  const sb = getBrowserClient();
  if (!sb) {
    // Demo fallback — just remember locally
    markLocallyRated(payload.dramaId, payload.score);
    return { ok: true, message: '本地演示模式：已记录评分' };
  }
  const { error } = await sb.from('ratings').insert({
    drama_id: payload.dramaId,
    score: payload.score,
    comment: payload.comment ?? null,
    ip_hash: 'browser_placeholder', // 真实 IP 由 Edge Function 写入
    device_fingerprint: payload.deviceFingerprint ?? 'unknown',
  });
  if (error) {
    // 23505 = unique violation — 防重复评分命中
    if ((error as any).code === '23505') {
      markLocallyRated(payload.dramaId, payload.score);
      return { ok: false, message: '您已评分过该剧集' };
    }
    return { ok: false, message: `提交失败：${error.message}` };
  }
  markLocallyRated(payload.dramaId, payload.score);
  return { ok: true, message: '感谢您的评分！' };
}
