// Unified data layer.
// 数据源优先级：1. 本地 JSON（爬虫导出）→ 2. Supabase → 3. Mock 数据
// 本地 JSON 是最可靠的来源：爬虫提交到仓库 → Vercel 检测 push 自动重建

import { SAMPLE_DRAMAS, SAMPLE_CVS, SAMPLE_ROLES } from './mock-data';
import type { Drama, Cv, DramaCvRole } from './mock-data';
import latestData from '../data/latest.json';

export type { Drama, Cv, DramaCvRole };

const USE_SUPABASE =
  !!import.meta.env.PUBLIC_SUPABASE_URL &&
  !!import.meta.env.PUBLIC_SUPABASE_ANON_KEY &&
  import.meta.env.PUBLIC_SUPABASE_URL !== 'https://your-project.supabase.co';

// 本地 JSON 是否有真实数据（dramas 数组非空）
const HAS_LOCAL_DATA = Array.isArray(latestData.dramas) && latestData.dramas.length > 0;

function logFallback(msg: string) {
  // eslint-disable-next-line no-console
  console.warn('[data] Fallback:', msg);
}

export async function getAllDramas(): Promise<Drama[]> {
  // 优先使用本地 JSON（爬虫导出的最新数据）
  if (HAS_LOCAL_DATA) {
    return latestData.dramas as unknown as Drama[];
  }
  if (USE_SUPABASE) {
    try {
      const sb = await import('./supabase');
      const client = sb.getBuildClient();
      const { data, error } = await client
        .from('dramas')
        .select('*')
        .order('play_count', { ascending: false });
      if (error) throw error;
      return (data as Drama[]) ?? [];
    } catch (err) {
      logFallback(String(err));
    }
  }
  return SAMPLE_DRAMAS;
}

export async function getDramaById(id: string): Promise<Drama | undefined> {
  const all = await getAllDramas();
  return all.find((d) => d.id === id);
}

export async function getAllCvs(): Promise<Cv[]> {
  if (HAS_LOCAL_DATA) {
    return latestData.cvs as Cv[];
  }
  if (USE_SUPABASE) {
    try {
      const sb = await import('./supabase');
      const client = sb.getBuildClient();
      const { data, error } = await client.from('cvs').select('*').order('name');
      if (error) throw error;
      return (data as Cv[]) ?? [];
    } catch (err) {
      logFallback(String(err));
    }
  }
  return SAMPLE_CVS;
}

export async function getCvById(id: string): Promise<Cv | undefined> {
  const all = await getAllCvs();
  return all.find((c) => c.id === id);
}

export async function getDramaRoles(dramaId: string): Promise<DramaCvRole[]> {
  if (HAS_LOCAL_DATA) {
    const roles = latestData.roles as DramaCvRole[];
    const cvs = latestData.cvs as Cv[];
    const cvNameMap = new Map(cvs.map((c) => [c.id, c.name]));
    return roles
      .filter((r) => r.drama_id === dramaId)
      .map((r) => ({ ...r, cv_name: cvNameMap.get(r.cv_id) }));
  }
  if (USE_SUPABASE) {
    try {
      const sb = await import('./supabase');
      const client = sb.getBuildClient();
      const { data, error } = await client
        .from('drama_cv_roles')
        .select('*, cvs(name)')
        .eq('drama_id', dramaId);
      if (error) throw error;
      return (data as any[]).map((r) => ({
        drama_id: r.drama_id,
        cv_id: r.cv_id,
        role_type: r.role_type,
        character_name: r.character_name,
        cv_name: r.cvs?.name,
      }));
    } catch (err) {
      logFallback(String(err));
    }
  }
  return SAMPLE_ROLES.filter((r) => r.drama_id === dramaId);
}

export async function getCvRoles(cvId: string): Promise<DramaCvRole[]> {
  if (HAS_LOCAL_DATA) {
    const roles = latestData.roles as DramaCvRole[];
    const dramas = latestData.dramas as unknown as Drama[];
    const dramaMap = new Map(dramas.map((d) => [d.id, d]));
    return roles
      .filter((r) => r.cv_id === cvId)
      .map((r) => ({ ...r, drama_title: dramaMap.get(r.drama_id)?.title }))
      .sort((a, b) => {
        const pa = dramaMap.get(a.drama_id)?.play_count ?? 0;
        const pb = dramaMap.get(b.drama_id)?.play_count ?? 0;
        return pb - pa;
      });
  }
  if (USE_SUPABASE) {
    try {
      const sb = await import('./supabase');
      const client = sb.getBuildClient();
      const { data, error } = await client
        .from('drama_cv_roles')
        .select('*, dramas(title, play_count, year)')
        .eq('cv_id', cvId)
        .order('dramas.play_count', { ascending: false, foreignTable: 'dramas' });
      if (error) throw error;
      return (data as any[]).map((r) => ({
        drama_id: r.drama_id,
        cv_id: r.cv_id,
        role_type: r.role_type,
        character_name: r.character_name,
        drama_title: r.dramas?.title,
      }));
    } catch (err) {
      logFallback(String(err));
    }
  }
  return SAMPLE_ROLES.filter((r) => r.cv_id === cvId);
}

export type RankingMetric = 'play_count' | 'rating_avg' | 'rating_count' | 'cv_roles' | 'author_adaptation';

export interface RankingItem {
  id: string;
  title: string;
  platform?: string;
  value: number;
  display: string;
}

async function getAllRoles(): Promise<DramaCvRole[]> {
  if (HAS_LOCAL_DATA) {
    return latestData.roles as DramaCvRole[];
  }
  if (USE_SUPABASE) {
    try {
      const sb = await import('./supabase');
      const client = sb.getBuildClient();
      const { data, error } = await client.from('drama_cv_roles').select('drama_id, cv_id');
      if (error) throw error;
      return (data as DramaCvRole[]) ?? [];
    } catch (err) {
      logFallback(String(err));
    }
  }
  return SAMPLE_ROLES;
}

export async function getRankings(metric: RankingMetric): Promise<RankingItem[]> {
  const dramas = await getAllDramas();
  if (metric === 'cv_roles') {
    const cvs = await getAllCvs();
    const roles = await getAllRoles();
    const counts = new Map<string, number>();
    for (const r of roles) counts.set(r.cv_id, (counts.get(r.cv_id) ?? 0) + 1);
    return cvs
      .map((cv) => ({
        id: cv.id,
        title: cv.name,
        value: counts.get(cv.id) ?? 0,
        display: `${counts.get(cv.id) ?? 0} 部`,
      }))
      .sort((a, b) => b.value - a.value);
  }
  if (metric === 'author_adaptation') {
    // 作者改编榜：按原作作者分组，统计其作品被改编为广播剧的数量
    // id 设为该作者播放量最高的剧集id，点击可跳转到该剧详情
    const authorMap = new Map<string, { count: number; totalPlay: number; topDramaId: string; topDramaPlay: number }>();
    for (const d of dramas) {
      const author = d.original_work?.trim();
      if (!author) continue;
      const existing = authorMap.get(author) ?? { count: 0, totalPlay: 0, topDramaId: d.id, topDramaPlay: 0 };
      existing.count += 1;
      existing.totalPlay += d.play_count ?? 0;
      if ((d.play_count ?? 0) > existing.topDramaPlay) {
        existing.topDramaPlay = d.play_count ?? 0;
        existing.topDramaId = d.id;
      }
      authorMap.set(author, existing);
    }
    return Array.from(authorMap.entries())
      .map(([author, { count, topDramaId }]) => ({
        id: topDramaId,
        title: author,
        value: count,
        display: `${count} 部`,
      }))
      .sort((a, b) => b.value - a.value);
  }
  return dramas
    .map((d) => {
      const value = (d as any)[metric] as number;
      let display = String(value);
      if (metric === 'play_count') {
        display = `${(value / 10000).toFixed(1)} 万`;
      } else if (metric === 'rating_avg') {
        display = `${value.toFixed(2)} 分`;
      } else if (metric === 'rating_count') {
        display = `${value} 条`;
      }
      return {
        id: d.id,
        title: d.title,
        platform: d.platform,
        value,
        display,
      };
    })
    .sort((a, b) => b.value - a.value);
}

// ---------------------------------------------------------------------------
// CV 宇宙：高频合作数据
// ---------------------------------------------------------------------------
export interface CvCollaboration {
  cv1_id: string;
  cv1_name: string;
  cv2_id: string;
  cv2_name: string;
  count: number;
  dramas: { id: string; title: string; platform?: string }[];
}

export async function getCvCollaborations(minCount = 2): Promise<CvCollaboration[]> {
  const roles = await getAllRoles();
  const cvs = await getAllCvs();
  const dramas = await getAllDramas();

  // cv_id -> cv_name
  const cvNameMap = new Map<string, string>();
  for (const c of cvs) cvNameMap.set(c.id, c.name);

  // drama_id -> { id, title, platform }
  const dramaMap = new Map<string, { id: string; title: string; platform?: string }>();
  for (const d of dramas) dramaMap.set(d.id, { id: d.id, title: d.title, platform: d.platform });

  // drama_id -> cv_id[] (按drama分组CV)
  const dramaCvs = new Map<string, Set<string>>();
  for (const r of roles) {
    if (!dramaCvs.has(r.drama_id)) dramaCvs.set(r.drama_id, new Set());
    dramaCvs.get(r.drama_id)!.add(r.cv_id);
  }

  // 统计CV对合作次数
  const pairMap = new Map<string, { cv1: string; cv2: string; dramaIds: Set<string> }>();
  for (const [dramaId, cvSet] of dramaCvs) {
    const cvList = Array.from(cvSet);
    for (let i = 0; i < cvList.length; i++) {
      for (let j = i + 1; j < cvList.length; j++) {
        const a = cvList[i] < cvList[j] ? cvList[i] : cvList[j];
        const b = cvList[i] < cvList[j] ? cvList[j] : cvList[i];
        const key = `${a}|${b}`;
        if (!pairMap.has(key)) pairMap.set(key, { cv1: a, cv2: b, dramaIds: new Set() });
        pairMap.get(key)!.dramaIds.add(dramaId);
      }
    }
  }

  return Array.from(pairMap.values())
    .filter((p) => p.dramaIds.size >= minCount)
    .map((p) => ({
      cv1_id: p.cv1,
      cv1_name: cvNameMap.get(p.cv1) ?? p.cv1,
      cv2_id: p.cv2,
      cv2_name: cvNameMap.get(p.cv2) ?? p.cv2,
      count: p.dramaIds.size,
      dramas: Array.from(p.dramaIds)
        .map((id) => dramaMap.get(id))
        .filter(Boolean) as { id: string; title: string; platform?: string }[],
    }))
    .sort((a, b) => b.count - a.count);
}

export interface StatsOverview {
  dramaCount: number;
  cvCount: number;
  ratingCount: number;
  platformCount: number;
  platformBreakdown: { name: string; value: number }[];
  yearBreakdown: { name: string; value: number }[];
}

export async function getStatsOverview(): Promise<StatsOverview> {
  const dramas = await getAllDramas();
  const cvs = await getAllCvs();
  const ratingCount = dramas.reduce((sum, d) => sum + (d.rating_count ?? 0), 0);
  const byPlatform = new Map<string, number>();
  const byYear = new Map<string, number>();
  for (const d of dramas) {
    byPlatform.set(d.platform, (byPlatform.get(d.platform) ?? 0) + 1);
    const y = String(d.year ?? '未知');
    byYear.set(y, (byYear.get(y) ?? 0) + 1);
  }
  return {
    dramaCount: dramas.length,
    cvCount: cvs.length,
    ratingCount,
    platformCount: byPlatform.size,
    platformBreakdown: Array.from(byPlatform.entries()).map(([name, value]) => ({ name, value })),
    yearBreakdown: Array.from(byYear.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([name, value]) => ({ name, value })),
  };
}
