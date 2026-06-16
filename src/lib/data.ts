// Unified data layer. Reads from Supabase when available, else falls back
// to local mock data so the project is always buildable without credentials.

import { SAMPLE_DRAMAS, SAMPLE_CVS, SAMPLE_ROLES } from './mock-data';
import type { Drama, Cv, DramaCvRole } from './mock-data';

export type { Drama, Cv, DramaCvRole };

const USE_SUPABASE =
  !!import.meta.env.PUBLIC_SUPABASE_URL &&
  !!import.meta.env.PUBLIC_SUPABASE_ANON_KEY &&
  import.meta.env.PUBLIC_SUPABASE_URL !== 'https://your-project.supabase.co';

function logFallback(msg: string) {
  // eslint-disable-next-line no-console
  console.warn('[data] Supabase not configured — using mock data:', msg);
}

export async function getAllDramas(): Promise<Drama[]> {
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

export type RankingMetric = 'play_count' | 'rating_avg' | 'rating_count' | 'cv_roles';

export interface RankingItem {
  id: string;
  title: string;
  platform?: string;
  value: number;
  display: string;
}

export async function getRankings(metric: RankingMetric): Promise<RankingItem[]> {
  const dramas = await getAllDramas();
  if (metric === 'cv_roles') {
    const cvs = await getAllCvs();
    const roles = SAMPLE_ROLES; // or fetch from supabase
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
