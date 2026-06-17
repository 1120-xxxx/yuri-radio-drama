-- Supabase 数据库 schema（在 Supabase SQL Editor 中执行一次即可）
-- 包含剧集、CV、关联表、匿名评分表与行级安全策略

-- ==================== 剧集基础信息表 ====================
create table if not exists public.dramas (
  id text primary key,
  title text not null,
  original_work text,
  platform text,
  year int,
  total_episodes int default 0,
  play_count bigint default 0,
  rating_avg numeric(3, 2) default 0,
  rating_count int default 0,
  cover_url text,
  description text,
  studio text,
  director text,
  source_url text,
  tags text[] default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ==================== CV 信息表 ====================
create table if not exists public.cvs (
  id text primary key,
  name text not null,
  avatar_url text,
  bio text,
  created_at timestamptz default now()
);

-- ==================== 剧集-CV 关联表 ====================
-- role_type: main / support / director
create table if not exists public.drama_cv_roles (
  drama_id text references public.dramas(id) on delete cascade,
  cv_id text references public.cvs(id) on delete cascade,
  role_type text not null check (role_type in ('main', 'support', 'director')),
  character_name text,
  created_at timestamptz default now(),
  primary key (drama_id, cv_id, role_type)
);

-- ==================== 匿名评分/评论表 ====================
create table if not exists public.ratings (
  id uuid primary key default gen_random_uuid(),
  drama_id text references public.dramas(id) on delete cascade not null,
  score int not null check (score between 1 and 5),
  comment text,
  ip_hash text,
  device_fingerprint text,
  created_at timestamptz default now()
);

-- 防重复评分唯一约束（同一 IP + 设备对同一剧集只能评一次）
create unique index if not exists ratings_drama_ip_fingerprint_unique
  on public.ratings (drama_id, ip_hash, device_fingerprint);

-- 常用索引
create index if not exists dramas_title_idx on public.dramas (title);
create index if not exists dramas_platform_idx on public.dramas (platform);
create index if not exists dramas_year_idx on public.dramas (year);
create index if not exists dramas_play_count_idx on public.dramas (play_count desc);
create index if not exists ratings_drama_id_idx on public.ratings (drama_id);
create index if not exists ratings_created_at_idx on public.ratings (created_at desc);

-- ==================== RLS 行级安全策略 ====================
alter table public.dramas enable row level security;
alter table public.cvs enable row level security;
alter table public.drama_cv_roles enable row level security;
alter table public.ratings enable row level security;

-- 匿名/登录用户对 dramas/cvs/roles 只可读
drop policy if exists "dramas are readable by anon" on public.dramas;
create policy "dramas are readable by anon" on public.dramas for select using (true);

drop policy if exists "cvs are readable by anon" on public.cvs;
create policy "cvs are readable by anon" on public.cvs for select using (true);

drop policy if exists "drama_cv_roles are readable by anon" on public.drama_cv_roles;
create policy "drama_cv_roles are readable by anon" on public.drama_cv_roles for select using (true);

-- 匿名用户可写入评分，但不得修改/删除
drop policy if exists "ratings are readable by anon" on public.ratings;
create policy "ratings are readable by anon" on public.ratings for select using (true);

drop policy if exists "ratings are insertable by anon" on public.ratings;
create policy "ratings are insertable by anon" on public.ratings for insert
  with check (
    score between 1 and 5
    and (comment is null or char_length(comment) <= 200)
  );

-- ==================== 自动更新 drama.rating_avg / rating_count 的触发器 ====================
create or replace function public.update_drama_rating_summary() returns trigger
language plpgsql as $$
begin
  update public.dramas
  set rating_avg = (
        select round(coalesce(avg(score), 0), 2)
        from public.ratings
        where drama_id = new.drama_id
      ),
      rating_count = (
        select count(*)
        from public.ratings
        where drama_id = new.drama_id
      ),
      updated_at = now()
  where id = new.drama_id;
  return new;
end;
$$;

drop trigger if exists update_drama_rating_on_insert on public.ratings;
create trigger update_drama_rating_on_insert
  after insert on public.ratings
  for each row execute function public.update_drama_rating_summary();
