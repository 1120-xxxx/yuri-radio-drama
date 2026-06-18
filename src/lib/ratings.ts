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
const LS_FINGERPRINT_KEY = 'yuri_device_fp';

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

// 稳定的设备指纹：首次生成后存入 localStorage，后续复用
export function getDeviceFingerprint(): string {
  try {
    let fp = localStorage.getItem(LS_FINGERPRINT_KEY);
    if (!fp) {
      fp = 'fp_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(LS_FINGERPRINT_KEY, fp);
    }
    return fp;
  } catch {
    return 'fp_fallback_' + Date.now().toString(36);
  }
}

export async function getRatingForDrama(
  dramaId: string,
  fallback?: { fallbackAvg?: number; fallbackCount?: number }
): Promise<{
  summary: RatingSummary;
  comments: RatingComment[];
  backendConnected: boolean;
}> {
  const sb = getBrowserClient();
  // 兜底实际数据：优先用剧集自身爬取的评分（来自饭角等平台）
  const fbAvg = fallback?.fallbackAvg ?? 0;
  const fbCount = fallback?.fallbackCount ?? 0;
  if (!sb) {
    // 未配置 Supabase：显示剧集自身爬取的实际评分数据
    return {
      summary: { avg: fbAvg, count: fbCount },
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
  // 优先级：dramas表 > 用户评论计算 > 剧集爬取兜底
  const dramaAvg = (avgRow as any)?.rating_avg;
  const dramaCount = (avgRow as any)?.rating_count;
  let summary: RatingSummary;
  if (dramaAvg != null && Number(dramaAvg) > 0) {
    summary = { avg: Number(dramaAvg), count: Number(dramaCount ?? computed.count) };
  } else if (computed.count > 0) {
    summary = computed;
  } else {
    summary = { avg: fbAvg, count: fbCount };
  }
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
  const sb = getBrowserClient();
  if (!sb) {
    // Supabase 未配置：无法保存评分
    return { ok: false, message: '评分服务未配置，无法保存评分' };
  }
  // 使用稳定设备指纹，让数据库唯一约束防重复
  const fingerprint = payload.deviceFingerprint || getDeviceFingerprint();
  const { error } = await sb.from('ratings').insert([{
    drama_id: payload.dramaId,
    score: payload.score,
    comment: payload.comment ?? null,
    ip_hash: 'browser_placeholder', // 真实 IP 由 Edge Function 写入
    device_fingerprint: fingerprint,
  }]);
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
