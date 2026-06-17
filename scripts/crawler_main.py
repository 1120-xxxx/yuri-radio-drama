# 数据流水线：抓取 → 清洗 → 写入 Supabase → 触发 Vercel 重建
#
# 架构说明：
#   1. 基于 Python 编写定向爬虫，通过 GitHub Actions 每周定时运行
#   2. 使用 Supabase REST API 直接写入数据（不依赖 supabase-py SDK）
#   3. 数据更新完成后，调用 Vercel Deploy Hook 触发 Astro 全站重新构建
#   4. 构建完成后静态页自动上线，全程无人工干预
#
# 请勿以任何形式存储和传播受版权保护的音视频内容；仅抓取元数据。

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("pipeline")

ROOT = Path(__file__).resolve().parent.parent

# 加载 .env 文件中的环境变量（本地运行时需要）
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    # python-dotenv 未安装时手动解析 .env 文件
    _env_file = ROOT / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
ALIASES_FILE = ROOT / "scripts" / "aliases.json"

REQUEST_DELAY = 0.3  # 爬取请求间隔（秒）- 降低以提升速度（并发场景下已有限流）
MAX_WORKERS = 8  # 并发线程数（用于详情/分页并发获取，提升饭角专辑详情获取速度）
MAX_RETRIES = 3  # HTTP请求最大重试次数
_verbose = False  # 全局 verbose 标志

# 全局 Session（连接池复用，减少 TCP 握手开销，提升并发性能）
_SESSION: requests.Session | None = None


def _get_session() -> requests.Session:
    """获取全局 requests.Session（连接池复用）"""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        # 配置连接池大小，适配并发场景
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
        _SESSION.mount("https://", adapter)
        _SESSION.mount("http://", adapter)
    return _SESSION


def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """带重试的HTTP请求，遇到网络错误自动退避重试
    使用全局 Session 复用连接池，提升并发性能。
    """
    kwargs.setdefault("timeout", 15)
    session = _get_session()
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except (requests.RequestException, ConnectionError) as e:
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                wait = 0.5 * (attempt + 1)
                log.debug("请求失败(第%d次): %s，%.1fs后重试", attempt + 1, e, wait)
                time.sleep(wait)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Supabase REST API 客户端（直接用 requests，绕开 SDK 兼容性问题）
# ---------------------------------------------------------------------------
class SupabaseREST:
    """轻量 Supabase REST API 封装，不依赖 supabase-py"""

    def __init__(self, url: str, service_key: str):
        # 确保 URL 不以 / 结尾
        self.base_url = url.rstrip("/")
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates",
        }

    def _url(self, table: str) -> str:
        return f"{self.base_url}/rest/v1/{table}"

    def select(self, table: str, columns: str = "*", limit: int | None = None) -> list[dict]:
        params = {"select": columns}
        if limit:
            params["limit"] = str(limit)
        resp = requests.get(self._url(table), headers=self.headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def upsert(self, table: str, data: list[dict]) -> list[dict]:
        """Upsert 数据，返回写入的记录"""
        if not data:
            return []
        log.info("POST %s (%d records)", self._url(table), len(data))
        if _verbose:
            log.info("Payload sample: %s", json.dumps(data[0], ensure_ascii=False)[:300])
        try:
            resp = requests.post(self._url(table), headers=self.headers, json=data, timeout=30)
        except requests.exceptions.RequestException as e:
            log.error("Supabase 请求异常 [%s]: %s", table, e)
            raise
        log.info("Response: status=%d, body_len=%d", resp.status_code, len(resp.text))
        if resp.status_code >= 400:
            log.error("Supabase upsert 失败 [%s]: status=%d body=%s", table, resp.status_code, resp.text[:500])
            # 提供更具体的错误提示
            if resp.status_code == 404:
                log.error("→ 表 '%s' 不存在，请先在 Supabase SQL Editor 中执行 schema.sql", table)
            elif resp.status_code == 401:
                log.error("→ 认证失败，请检查 SUPABASE_SERVICE_ROLE_KEY 是否正确（不是 anon key）")
            elif resp.status_code == 403:
                log.error("→ 权限不足，请确认使用的是 service_role key 而非 anon key")
            elif resp.status_code == 409:
                log.error("→ 主键冲突，upsert 应该能处理此情况，请检查 Prefer header 是否生效")
            resp.raise_for_status()
        return resp.json() if resp.text.strip() else []

    def table_exists(self, table: str) -> bool:
        """检查表是否可访问"""
        try:
            self.select(table, limit=1)
            return True
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False
            # 其他错误（如空表返回 200 但 RLS 限制）可能仍表示表存在
            log.warning("表检查 '%s' 返回异常: %s", table, e)
            return True  # 假设表存在，让后续 upsert 报具体错误

    def delete_all(self, table: str, filter_column: str = "id") -> int:
        """删除表中的所有数据（通过 PostgREST DELETE + 过滤器）
        返回删除的行数（近似值）。
        注意：需要 service_role key 绕过 RLS。
        filter_column: 用于 DELETE 过滤的列名（PostgREST DELETE 需要至少一个过滤器）
        """
        # 先统计现有行数
        count_resp = requests.get(
            self._url(table),
            headers={**self.headers, "Prefer": "count=exact", "Range": "0-0"},
            timeout=15,
        )
        existing = 0
        if count_resp.status_code == 200:
            cr = count_resp.headers.get("content-range", "")
            # 格式: 0-0/123
            if "/" in cr:
                try:
                    existing = int(cr.split("/")[-1])
                except ValueError:
                    pass
        log.info("DELETE %s (现有 ~%d 行)", self._url(table), existing)
        # PostgREST DELETE 需要至少一个过滤器才能删除（防止误删）
        # 使用 filter_column.gte.0 匹配所有行（service_role 可绕过 RLS）
        # 对于 text 列使用 not.is.null 过滤
        resp = requests.delete(
            self._url(table),
            headers=self.headers,
            params={filter_column: "not.is.null"},
            timeout=30,
        )
        if resp.status_code >= 400:
            log.error("Supabase delete_all 失败 [%s]: status=%d body=%s", table, resp.status_code, resp.text[:300])
            resp.raise_for_status()
        log.info("DELETE %s 完成 (已清空)", table)
        return existing


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class Drama:
    id: str
    title: str
    original_work: str | None = None
    platform: str = "未知"
    year: int = 0
    total_episodes: int = 0
    play_count: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0
    cover_url: str | None = None
    description: str | None = None
    studio: str | None = None
    director: str | None = None
    source_url: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Cv:
    id: str
    name: str
    avatar_url: str | None = None
    bio: str | None = None


@dataclass
class Role:
    drama_id: str
    cv_id: str
    role_type: str  # main / support / director
    character_name: str | None = None


@dataclass
class CrawlResult:
    """一次爬取的完整结果，包含 dramas / cvs / roles"""
    dramas: list[Drama] = field(default_factory=list)
    cvs: list[Cv] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 猫耳FM 爬取（真实 API）
# ---------------------------------------------------------------------------
# 猫耳FM公开API：
#   搜索: https://www.missevan.com/dramaapi/search?s=关键字&page=1
#   详情: https://www.missevan.com/dramaapi/getdrama?drama_id=XXX
# 仅抓取元数据，不下载音频
# ---------------------------------------------------------------------------

MAOER_SEARCH_URL = "https://www.missevan.com/dramaapi/search"
MAOER_DETAIL_URL = "https://www.missevan.com/dramaapi/getdrama"
MAOER_HEADERS = {
    "User-Agent": "YuriDataBot/1.0 (metadata only)",
    "Referer": "https://www.missevan.com/",
}

# 只保留中文广播剧分类
MAOER_TARGET_CATALOGS = {"中文广播剧", "广播剧"}


def _strip_html(text: str | None) -> str:
    """简单去除HTML标签"""
    if not text or not isinstance(text, str):
        return ""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# 百合/GL 内容过滤
# ---------------------------------------------------------------------------
# 百合相关关键词（标题/简介/标签中包含这些词则认为是百合内容）
YURI_KEYWORDS = {"百合", "GL", "橘气", "橘向", "girls love", "girls' love", "girl's love",
                 "女生向", "女性向恋爱", "百合向", "GL向", "橘"}
# BL/非百合关键词（包含这些词则排除）
BL_KEYWORDS = {"耽美", "BL", "纯爱", "男男", "同志", "攻×受", "攻受", "男生向",
               "腐", "兄贵", "男频", "bg向", "BG向", "言情向"}


def is_yuri_content(title: str, description: str | None = None, tags: list[str] | None = None) -> bool:
    """判断一部广播剧是否属于百合/GL题材"""
    text = f"{title} {description or ''} {' '.join(tags or [])}".lower()

    # 如果包含BL关键词且不包含百合关键词，排除
    has_yuri = any(kw.lower() in text for kw in YURI_KEYWORDS)
    has_bl = any(kw.lower() in text for kw in BL_KEYWORDS)

    if has_yuri:
        return True
    if has_bl:
        return False
    # 两者都没有，无法判断，保守排除
    return False


def _parse_maoer_search_item(item: dict) -> Drama | None:
    """将猫耳FM搜索结果的一条记录转为Drama对象"""
    catalog_name = item.get("catalog_name", "")
    # 只保留中文广播剧，过滤掉音乐/有声漫画/日抓等
    if catalog_name not in MAOER_TARGET_CATALOGS:
        return None

    drama_id = str(item["id"])
    name = item.get("name", "").strip()
    if not name:
        return None

    view_count = item.get("view_count", 0) or 0
    episodes = item.get("episodes", [])
    # 统计非ED/预告的正片集数
    ep_count = len([e for e in episodes if e.get("type", 0) == 0])
    abstract = _strip_html(item.get("abstract", ""))
    author = item.get("author", "") or None

    return Drama(
        id=f"maoer_{drama_id}",
        title=name,
        original_work=author,
        platform="猫耳FM",
        year=0,  # 搜索结果无年份，详情接口才有
        total_episodes=ep_count,
        play_count=view_count,
        rating_avg=0.0,
        rating_count=0,
        description=abstract[:500] if abstract else None,
        source_url=f"https://www.missevan.com/mdrama/{drama_id}",
        tags=["百合"],
    )


def fetch_maoer_dramas() -> Iterable[Drama]:
    """爬取猫耳FM百合/GL标签下的中文广播剧元数据"""
    # 使用精确的百合搜索关键词，避免抓到BL/耽美内容
    keywords = ["百合广播剧", "GL广播剧", "百合向广播剧", "橘气广播剧", "橘向广播剧",
                "女生向广播剧", "百合向", "GL向", "橘气", "百合"]
    seen_ids: set[str] = set()

    for kw in keywords:
        page = 1
        while page <= 5:  # 每个关键词最多5页（扩大覆盖）
            try:
                params = {"s": kw, "type": 1, "page": page}
                resp = _request_with_retry("GET", MAOER_SEARCH_URL, params=params,
                                           headers=MAOER_HEADERS)
                data = resp.json()

                if not data.get("success"):
                    log.warning("猫耳FM搜索 '%s' page=%d 返回失败", kw, page)
                    break

                datas = data.get("info", {}).get("Datas", [])
                if not datas:
                    break

                count = 0
                for item in datas:
                    drama = _parse_maoer_search_item(item)
                    if drama and drama.id not in seen_ids:
                        # 二次过滤：确认是百合内容
                        if is_yuri_content(drama.title, drama.description, drama.tags):
                            seen_ids.add(drama.id)
                            count += 1
                            yield drama

                log.info("猫耳FM搜索 '%s' page=%d: 获取 %d 条百合广播剧", kw, page, count)
                time.sleep(REQUEST_DELAY)
                page += 1

            except Exception as e:
                log.warning("猫耳FM搜索 '%s' page=%d 失败: %s", kw, page, e)
                break


def _fetch_single_maoer_detail(d: Drama, result: CrawlResult) -> Drama | None:
    """获取单个猫耳FM剧集详情，返回Drama（如被过滤返回None）"""
    if not d.id.startswith("maoer_"):
        return d
    maoer_id = d.id.replace("maoer_", "")
    try:
        resp = _request_with_retry("GET", MAOER_DETAIL_URL, params={"drama_id": maoer_id},
                                   headers=MAOER_HEADERS)
        data = resp.json()
        if not data.get("success"):
            return d

        info = data.get("info", {})
        drama_info = info.get("drama", {})

        # 补充标签
        tags_raw = drama_info.get("tags", [])
        tag_names = [t.get("name", "") for t in tags_raw if t.get("name")]
        existing_tags = d.tags or []
        d.tags = list(set(existing_tags + tag_names))

        # 补充封面（先补充封面，后面年份提取需要用到封面URL中的日期路径）
        if not d.cover_url:
            cover = drama_info.get("cover", "") or drama_info.get("cover_base", "")
            if cover:
                d.cover_url = f"https://static.maoercdn.com/dramacovers/{cover}" if not cover.startswith("http") else cover

        # 补充年份（从created_at字段提取，或从封面URL路径提取如 /202109/）
        created_at = drama_info.get("created_at", "")
        if created_at and len(created_at) >= 4:
            try:
                d.year = int(created_at[:4])
            except ValueError:
                pass
        # 如果 created_at 没有，从封面 URL 提取年份（猫耳 CDN 路径含 /YYYYMM/）
        if not d.year and d.cover_url:
            m_year = _re.search(r"/(\d{4})(\d{2})/", d.cover_url)
            if m_year:
                y = int(m_year.group(1))
                if 2015 <= y <= 2026:
                    d.year = y

        # 补充播放量（详情接口更准确）
        d.play_count = drama_info.get("view_count", d.play_count) or d.play_count

        # 补充集数
        episodes = info.get("episodes", {}).get("episode", [])
        if episodes:
            d.total_episodes = len([e for e in episodes if e.get("type", 0) == 0])

        # 补充原作作者（优先用 API 字段，其次从描述解析"原著：XXX"或"XXX原著"）
        if not d.original_work:
            d.original_work = drama_info.get("author", "") or None
        if not d.original_work and d.description:
            d.original_work = _parse_fanjiao_author(d.description)

        # 补充描述（如果还没有）
        if not d.description:
            abstract = drama_info.get("abstract", "") or drama_info.get("catalog", "")
            if abstract:
                d.description = _strip_html(abstract)[:500]
        # 有描述后再次尝试解析作者（描述可能刚被补充）
        if not d.original_work and d.description:
            d.original_work = _parse_fanjiao_author(d.description)

        # 补充工作室
        if not d.studio:
            d.studio = drama_info.get("organization", "") or drama_info.get("studio", "") or None

        # 补充导演（策划/导演字段）
        if not d.director:
            d.director = drama_info.get("director", "") or drama_info.get("planner", "") or None

        # 百合内容二次验证：用详情API的完整信息再次过滤
        if not is_yuri_content(d.title, d.description, d.tags):
            log.debug("猫耳FM %s (%s) 非百合内容，跳过", maoer_id, d.title)
            return None

        # 提取CV信息
        cv_list = info.get("cvs", [])
        if isinstance(cv_list, list):
            for cv_item in cv_list:
                cv_info = cv_item.get("cv_info", {})
                cv_id_raw = str(cv_info.get("id", ""))
                cv_name = cv_info.get("name", "").strip()
                if not cv_id_raw or not cv_name:
                    continue
                cv_id = f"maoer_cv_{cv_id_raw}"
                result.cvs.append(Cv(id=cv_id, name=cv_name))
                char_name = cv_item.get("character", "") or None
                role_type = "main"
                result.roles.append(Role(
                    drama_id=d.id,
                    cv_id=cv_id,
                    role_type=role_type,
                    character_name=char_name,
                ))

        return d

    except Exception as e:
        log.warning("猫耳FM详情 %s 失败: %s", maoer_id, e)
        return d


def fetch_maoer_drama_details(dramas: list[Drama], result: CrawlResult) -> list[Drama]:
    """对猫耳FM的Drama列表补充详情（标签、年份、CV信息等），并发获取以提升速度"""
    maoer_dramas = [d for d in dramas if d.id.startswith("maoer_")]
    other_dramas = [d for d in dramas if not d.id.startswith("maoer_")]

    updated: list[Drama] = list(other_dramas)
    completed = 0
    total = len(maoer_dramas)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_drama = {
            executor.submit(_fetch_single_maoer_detail, d, result): d
            for d in maoer_dramas
        }
        for future in as_completed(future_to_drama):
            completed += 1
            try:
                result_d = future.result()
                if result_d is not None:
                    updated.append(result_d)
                if completed % 10 == 0 or completed == total:
                    log.info("猫耳FM详情进度: %d/%d", completed, total)
            except Exception as e:
                log.warning("猫耳FM详情获取异常: %s", e)

    return updated


# ---------------------------------------------------------------------------
# 喜马拉雅 爬取（真实 API）
# ---------------------------------------------------------------------------
XIMALAYA_SEARCH_URL = "https://www.ximalaya.com/revision/search/main"
XIMALAYA_HEADERS = {
    "User-Agent": "YuriDataBot/1.0 (metadata only)",
    "Referer": "https://www.ximalaya.com/",
}


def fetch_ximalaya_dramas() -> Iterable[Drama]:
    """爬取喜马拉雅百合广播剧元数据"""
    keywords = ["百合广播剧", "GL广播剧"]
    seen_ids: set[str] = set()

    for kw in keywords:
        try:
            params = {"kw": kw, "page": 1, "pageSize": 30, "condition": "radio"}
            resp = requests.get(XIMALAYA_SEARCH_URL, params=params, timeout=15,
                                headers=XIMALAYA_HEADERS)
            resp.raise_for_status()
            data = resp.json()

            albums = data.get("data", {}).get("album", {}).get("albums", [])
            if not albums:
                log.info("喜马拉雅搜索 '%s': 无结果", kw)
                time.sleep(REQUEST_DELAY)
                continue

            count = 0
            for album in albums:
                album_id = str(album.get("id", ""))
                title = album.get("title", "").strip()
                if not album_id or not title:
                    continue

                drama_id = f"xm_{album_id}"
                if drama_id in seen_ids:
                    continue
                seen_ids.add(drama_id)

                play_count = album.get("playCount", 0) or 0
                # 喜马拉雅的playCount可能是字符串
                if isinstance(play_count, str):
                    play_count = int(play_count.replace(",", "")) if play_count.replace(",", "").isdigit() else 0

                desc = album.get("intro", "") or ""
                desc = _strip_html(desc)[:500] if desc else None

                yield Drama(
                    id=drama_id,
                    title=title,
                    platform="喜马拉雅",
                    play_count=play_count,
                    description=desc or None,
                    source_url=f"https://www.ximalaya.com/album/{album_id}",
                    tags=["百合"],
                )
                count += 1

            log.info("喜马拉雅搜索 '%s': 获取 %d 条", kw, count)
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            log.warning("喜马拉雅搜索 '%s' 失败: %s", kw, e)


# ---------------------------------------------------------------------------
# 荔枝FM 爬取
# ---------------------------------------------------------------------------
LIZHI_HEADERS = {
    "User-Agent": "YuriDataBot/1.0 (metadata only)",
    "Referer": "https://www.lizhi.fm/",
}


def fetch_lizhi_dramas() -> Iterable[Drama]:
    """爬取荔枝FM百合广播剧元数据
    荔枝FM搜索接口: https://www.lizhi.fm/api/search?k=百合广播剧&type=2
    type=2 表示专辑搜索
    """
    search_url = "https://www.lizhi.fm/api/search"
    keywords = ["百合广播剧", "GL广播剧"]
    seen_ids: set[str] = set()

    for kw in keywords:
        try:
            params = {"k": kw, "type": 2, "page": 1, "pageSize": 20}
            resp = requests.get(search_url, params=params, timeout=15,
                                headers=LIZHI_HEADERS)
            resp.raise_for_status()
            data = resp.json()

            # 荔枝FM搜索返回格式: { data: { list: [...] } }
            items = data.get("data", {}).get("list", [])
            if not items:
                log.info("荔枝FM搜索 '%s': 无结果", kw)
                time.sleep(REQUEST_DELAY)
                continue

            count = 0
            for item in items:
                radio_id = str(item.get("radioId", item.get("id", "")))
                name = item.get("radioName", item.get("name", "")).strip()
                if not radio_id or not name:
                    continue

                drama_id = f"lizhi_{radio_id}"
                if drama_id in seen_ids:
                    continue
                seen_ids.add(drama_id)

                play_count = item.get("playCount", 0) or 0
                desc = item.get("radioDesc", item.get("desc", "")) or ""
                desc = _strip_html(desc)[:500] if desc else None

                yield Drama(
                    id=drama_id,
                    title=name,
                    platform="荔枝FM",
                    play_count=play_count,
                    description=desc,
                    source_url=f"https://www.lizhi.fm/radio/{radio_id}",
                    tags=["百合"],
                )
                count += 1

            log.info("荔枝FM搜索 '%s': 获取 %d 条", kw, count)
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            log.warning("荔枝FM搜索 '%s' 失败: %s", kw, e)


# ---------------------------------------------------------------------------
# 漫播 爬取
# ---------------------------------------------------------------------------
# 漫播 (manbo.hongdoulive.com) 是以App为主的平台，公开Web API有限
# 通过Web端搜索接口获取元数据
# ---------------------------------------------------------------------------
MANBO_HEADERS = {
    "User-Agent": "YuriDataBot/1.0 (metadata only)",
    "Referer": "https://manbo.hongdoulive.com/",
}


def fetch_manbo_dramas() -> Iterable[Drama]:
    """爬取漫播百合广播剧元数据
    漫播Web端搜索接口（需抓包确认，此处为已知格式）:
    https://manbo.hongdoulive.com/api/search?keyword=百合&type=1&page=1
    """
    search_url = "https://manbo.hongdoulive.com/api/search"
    keywords = ["百合", "GL"]
    seen_ids: set[str] = set()

    for kw in keywords:
        try:
            params = {"keyword": kw, "type": 1, "page": 1, "pageSize": 20}
            resp = requests.get(search_url, params=params, timeout=15,
                                headers=MANBO_HEADERS)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data", {}).get("list", data.get("data", []))
            if not items:
                log.info("漫播搜索 '%s': 无结果或接口不可用", kw)
                time.sleep(REQUEST_DELAY)
                continue

            count = 0
            for item in items:
                item_id = str(item.get("id", ""))
                name = item.get("name", item.get("title", "")).strip()
                if not item_id or not name:
                    continue

                drama_id = f"manbo_{item_id}"
                if drama_id in seen_ids:
                    continue
                seen_ids.add(drama_id)

                play_count = item.get("playCount", item.get("play_count", 0)) or 0
                desc = item.get("description", item.get("intro", "")) or ""
                desc = _strip_html(desc)[:500] if desc else None

                yield Drama(
                    id=drama_id,
                    title=name,
                    platform="漫播",
                    play_count=play_count,
                    description=desc,
                    source_url=f"https://manbo.hongdoulive.com/Activecard/radioplay?id={item_id}",
                    tags=["百合"],
                )
                count += 1

            log.info("漫播搜索 '%s': 获取 %d 条", kw, count)
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            log.warning("漫播搜索 '%s' 失败（App端API可能需要认证）: %s", kw, e)


# ---------------------------------------------------------------------------
# 饭角 爬取（真实 API - 逆向签名算法）
# ---------------------------------------------------------------------------
# 饭角API: https://api.fanjiao.co
# 签名算法: MD5(sorted("key=value").join("&") + SECRET)
# 排行榜:   /walkman/api/ranking/album?tab=2&time_type=4&page=1&size=20
# 专辑详情: /walkman/api/album/album_info?album_id=XXX&from=H5
# 参演CV:   /walkman/api/album/actor_cvs?album_id=XXX  (返回 cv_list 含真实头像)
# ---------------------------------------------------------------------------
import hashlib as _hashlib

FANJIAO_BASE = "https://api.fanjiao.co"
FANJIAO_SECRET = "879f30c4b1641142c6192acc23cfb733"
FANJIAO_HEADERS = {
    "User-Agent": "YuriDataBot/1.0 (metadata only)",
    "Origin": "https://www.fanjiao.co",
    "Referer": "https://www.fanjiao.co/",
}


def _fanjiao_sign(params: dict) -> str:
    """饭角API签名: MD5(sorted("k=v").join("&") + SECRET)
    API 服务端会对参数排序后校验签名，因此客户端必须对参数排序后签名。
    """
    pairs = [f"{k}={v}" for k, v in params.items()]
    pairs.sort()
    raw = "&".join(pairs) + FANJIAO_SECRET
    return _hashlib.md5(raw.encode()).hexdigest()


def _fanjiao_get(path: str, params: dict) -> dict:
    """调用饭角API（带重试）"""
    sig = _fanjiao_sign(params)
    url = f"{FANJIAO_BASE}{path}"
    headers = {**FANJIAO_HEADERS, "signature": sig}
    resp = _request_with_retry("GET", url, params=params, headers=headers)
    return resp.json()


# ---- 饭角音频描述解析（提取CV、作者、制作方等结构化信息） ----
import re as _re

# 匹配 "角色名：CV名 @微博handle" 或 "角色名：CV名"
_FANJIAO_CV_LINE = _re.compile(r"([^\s:：·]{1,12})\s*[:：]\s*([^\s@·]+(?:\s+[^\s@·]+)?)\s*(?:@[^\s]*)?")

# 角色类型关键词映射
_FANJIAO_ROLE_KEYWORDS = {
    "主役": "main", "主演": "main", "主角": "main", "配音": "main",
    "协役": "support", "配角": "support", "客串": "support", "嘉宾": "support",
    "导演": "director", "策划": "director", "监制": "director",
    "后期": "support", "编剧": "support", "画师": "support", "字幕": "support",
    "主持": "support", "出品": "director", "制作": "director",
}

# 原著作者匹配: "原著：晋江文学城，鱼宰" / "原著：鱼宰" / "XXX原著" / "原著：XXX（晋江）"
_FANJIAO_AUTHOR = _re.compile(r"(?:原著|原作)\s*[:：]\s*(?:[^，,，\s]*[，,])?\s*([^\s@，,（(]+)")
_FANJIAO_AUTHOR_ALT = _re.compile(r"([\u4e00-\u9fa5]{2,12})原著")
# 猫耳描述中常见的作者模式：英文/中文名 + 原著，或 @用户名 原著
_MAOER_AUTHOR_ALT = _re.compile(r"@?([\u4e00-\u9fa5A-Za-z0-9_]{2,20})\s*原著")
# 作者名后的边界词（截断用）
_AUTHOR_BOUNDARY = _re.compile(r"(现代|古风|民国|全一期|全两期|全三期|全四期|广播剧|原创|出品|制作|《|策划|编剧|导演|STAFF|Cast|CAST|staff|cast|发布|完结|连载|第一季|第二季|第三季|第四季|第一季|预告|正剧|番外)")

# 制作方匹配: "制作：极乎工作室" / "出品：八号疯球"
_FANJIAO_STUDIO = _re.compile(r"(?:制作|出品)\s*[:：]\s*([^\s@，,（(]+(?:工作室|文化|传媒|出品|工作室)?)")

# 集数匹配: "正剧共19集" / "本剧共19集" / "共XX集" / "全XX期" / "全XX集"
_FANJIAO_EPISODES = _re.compile(r"(?:正剧|本剧)?共?\s*(\d{1,3})\s*集|全\s*(\d{1,3})\s*(?:期|集)")

# 年份匹配: "2024年" / "2024.08" / "2024-08-30" / "2024/08/30"
_FANJIAO_YEAR = _re.compile(r"(20\d{2})(?:\s*年|[.\-/年]\s*\d{1,2})?")


def _parse_fanjiao_cvs_from_description(desc: str) -> list[tuple[str, str, str]]:
    """从音频描述中解析CV信息，返回 [(cv_name, role_type, character_name), ...]
    优先解析"配音组"区块下的角色-CV映射。
    """
    if not desc:
        return []
    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    # 非角色行的关键词（遇到这些关键词的行要跳过）
    non_char_keywords = {
        "音频后期", "后期", "画师", "字幕", "海报", "人设图", "Q版",
        "片头", "片尾", "音乐", "配乐", "主题曲", "原创配乐", "片头曲",
        "原著", "原作", "出品", "制作", "播出时间", "播出", "策划",
        "监制", "导演", "编剧", "特别提醒", "禁止", "版权",
        "本剧", "正剧", "追剧", "更新", "福利", "花絮", "铃声",
        "预告", "主题曲", "角色曲", "片尾曲", "宣传", "鸣谢",
    }

    # 找到"配音组"区块（更可靠）
    voice_section = ""
    if "配音组" in desc:
        parts = desc.split("配音组", 1)
        if len(parts) > 1:
            # 取配音组后到下一个空行或"原著"/"出品"等关键词
            voice_section = parts[1]
            # 截断到非角色区块开始
            for stop_kw in ["原著", "原作", "出品", "制作", "播出", "音频后期", "后期", "画师", "字幕", "海报", "人设图", "片头", "片尾", "音乐", "配乐", "特别提醒", "禁止"]:
                idx = voice_section.find(stop_kw)
                if idx > 0:
                    voice_section = voice_section[:idx]
            voice_section = voice_section[:500]
    elif "配音" in desc:
        voice_section = desc

    if voice_section:
        for line in voice_section.split("\n"):
            line = line.strip()
            if not line or line.startswith("❌") or line.startswith("⚠") or line.startswith("✨"):
                continue
            m = _FANJIAO_CV_LINE.match(line)
            if m:
                char_name = m.group(1).strip()
                cv_name = m.group(2).strip().rstrip("·")
                # 过滤非CV行
                if char_name in non_char_keywords:
                    continue
                # 跳过以这些词开头的行
                if any(char_name.startswith(kw) for kw in ["播出", "本剧", "正剧", "追剧", "更新", "福利", "禁止", "版权", "特别"]):
                    continue
                if len(cv_name) < 2 or len(cv_name) > 8:
                    continue
                # 跳过包含特殊标记的
                if any(kw in cv_name for kw in ["@", "http", "www", "工作室", "文化", "传媒", "文学", "晋江", "8月", "每周", "更新"]):
                    continue
                # 跳过cv_name是日期/数字的情况
                if any(c.isdigit() for c in cv_name):
                    continue
                key = (cv_name, char_name)
                if key not in seen:
                    seen.add(key)
                    results.append((cv_name, "main", char_name))

    # 如果配音组没解析到，尝试从嘉宾/主持人等关键词提取
    if not results:
        # 这些关键词对应的是幕后人员，不是CV，跳过
        non_cv_keywords = {"后期", "音频后期", "画师", "字幕", "海报", "人设图", "片头", "片尾", "音乐", "配乐", "编剧", "策划", "监制"}
        for line in desc.split("\n"):
            line = line.strip()
            for kw, role_type in _FANJIAO_ROLE_KEYWORDS.items():
                if kw in line and ("：" in line or ":" in line):
                    # 跳过幕后人员行
                    if kw in non_cv_keywords:
                        continue
                    # 提取冒号后的CV名
                    after_colon = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                    # 去掉@handle
                    cv_name = after_colon.split("@")[0].strip().rstrip("·")
                    if cv_name and 2 <= len(cv_name) <= 8:
                        if any(kw2 in cv_name for kw2 in ["工作室", "文化", "传媒", "文学", "晋江"]):
                            continue
                        # 跳过英文名过短或含数字的
                        if any(c.isdigit() for c in cv_name):
                            continue
                        key = (cv_name, kw)
                        if key not in seen:
                            seen.add(key)
                            results.append((cv_name, role_type, None))
                    break

    return results


def _parse_fanjiao_author(desc: str) -> str | None:
    """从描述中提取原作作者名"""
    if not desc:
        return None
    # 平台名列表（用于去除前缀，扩展更多平台）
    platforms = ["晋江文学城", "晋江文学城", "晋江", "长佩文学", "长佩", "番茄小说",
                 "起点中文网", "起点", "知乎", "豆瓣", "Lofter", "LOFTER", "豆腐阅读",
                 "话本小说", "话本", "书旗小说", "书旗", "连城读书", "连城",
                 "汤圆创作", "汤圆", "SF轻小说", "轻小说", "豆瓣阅读",
                 "17K小说网", "17K", "纵横中文网", "纵横", "3G书城", "3G"]
    # 截断作者名中的边界词（如"现代广播剧"等）
    def _truncate_author(author: str) -> str:
        m = _AUTHOR_BOUNDARY.search(author)
        if m:
            author = author[:m.start()].strip()
        return author.strip("，,。.·：:")

    # 先匹配 "原著：XXX，作者名" 或 "原著：作者名"
    m = _FANJIAO_AUTHOR.search(desc)
    if m:
        author = m.group(1).strip().rstrip("，,。.")
        author = _truncate_author(author)
        for platform in platforms:
            if author.startswith(platform):
                author = author[len(platform):].strip("，,。.·")
        if 2 <= len(author) <= 15:
            return author
    # 再匹配 "XXX原著" (如 "鱼宰原著" 或 "晋江文学城鱼宰原著")，支持英文和@前缀
    m = _MAOER_AUTHOR_ALT.search(desc)
    if m:
        author = m.group(1).strip()
        author = _truncate_author(author)
        for platform in platforms:
            if author.startswith(platform):
                author = author[len(platform):].strip("，,。.·")
        if 2 <= len(author) <= 15 and author not in ("本剧", "正剧", "原著", "原作", "原创", "个人"):
            return author
    # 兼容旧的中文名匹配
    m = _FANJIAO_AUTHOR_ALT.search(desc)
    if m:
        author = m.group(1).strip()
        author = _truncate_author(author)
        for platform in platforms:
            if author.startswith(platform):
                author = author[len(platform):].strip("，,。.·")
        if 2 <= len(author) <= 8 and author not in ("本剧", "正剧", "原著", "原作"):
            return author
    return None


def _parse_fanjiao_studio(desc: str) -> str | None:
    """从描述中提取制作方"""
    if not desc:
        return None
    # 先匹配 "制作：XXX工作室"
    m = _FANJIAO_STUDIO.search(desc)
    if m:
        studio = m.group(1).strip()
        if 2 <= len(studio) <= 20:
            return studio
    # 再匹配 "XXX工作室制作" (无冒号格式)
    m2 = _re.search(r"([\u4e00-\u9fa5]{2,15}(?:工作室|文化|传媒|出品))制作", desc)
    if m2:
        return m2.group(1).strip()
    # 匹配 "XXX出品"
    m3 = _re.search(r"([\u4e00-\u9fa5]{2,15}(?:工作室|文化|传媒))出品", desc)
    if m3:
        return m3.group(1).strip()
    return None


def _parse_fanjiao_episodes(desc: str) -> int:
    """从描述中提取集数"""
    if not desc:
        return 0
    m = _FANJIAO_EPISODES.search(desc)
    if m:
        # 支持两个捕获组："共XX集"（group 1）和"全XX期"（group 2）
        return int(m.group(1) or m.group(2) or 0)
    return 0


def _parse_fanjiao_year(desc: str, publish_date: str | None = None) -> int:
    """从描述或发布日期中提取年份"""
    if publish_date:
        try:
            return int(publish_date[:4])
        except (ValueError, IndexError):
            pass
    if desc:
        m = _FANJIAO_YEAR.search(desc)
        if m:
            year = int(m.group(1))
            if 2015 <= year <= 2026:
                return year
    return 0


def _cv_avatar_url(cv_name: str) -> str:
    """为CV生成确定性头像URL（兜底：当饭角API未返回头像时使用 DiceBear 生成）"""
    import urllib.parse
    seed = urllib.parse.quote(cv_name)
    return f"https://api.dicebear.com/7.x/initials/svg?seed={seed}&backgroundColor=ffd5dc,c9b6ff,b6c6ff"


def _fetch_fanjiao_album_detail(album_id: int, drama_id: str, result: CrawlResult | None) -> tuple[dict, list[dict]]:
    """并发获取单个专辑的详情和CV列表
    返回 (album_info_data, cv_list)
    album_info_data: album_info API 返回的 data 字段（含 author_name/cover/play/publish_date 等）
    cv_list: actor_cvs API 返回的 cv_list（含真实头像 avatar、cv_type 1=主役 2=协役）
    """
    info_data: dict = {}
    cv_list: list[dict] = []

    def _fetch_info() -> None:
        nonlocal info_data
        try:
            r = _fanjiao_get("/walkman/api/album/album_info", {"album_id": album_id, "from": "H5"})
            if r.get("code") == 0 and r.get("data"):
                info_data = r["data"]
        except Exception as e:
            log.debug("饭角 album_info album_id=%s 失败: %s", album_id, e)

    def _fetch_cvs() -> None:
        nonlocal cv_list
        try:
            r = _fanjiao_get("/walkman/api/album/actor_cvs", {"album_id": album_id})
            if r.get("code") == 0 and r.get("data"):
                cv_list = r["data"].get("cv_list", []) or []
        except Exception as e:
            log.debug("饭角 actor_cvs album_id=%s 失败: %s", album_id, e)

    # 并发获取详情和CV列表（2个请求并发）
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(_fetch_info)
        f2 = executor.submit(_fetch_cvs)
        f1.result()
        f2.result()

    # 将CV信息写入 result（使用真实头像）
    if result is not None and cv_list:
        for cv_item in cv_list:
            cv_id_raw = cv_item.get("cv_id", 0)
            cv_name = (cv_item.get("name") or "").strip()
            if not cv_id_raw or not cv_name:
                continue
            cv_id = f"fanjiao_cv_{cv_id_raw}"
            avatar = cv_item.get("avatar") or ""
            # 规范化头像域名（fanjiao.cn → fanjiao.co）
            if avatar and "fanjiao.cn" in avatar:
                avatar = avatar.replace("fanjiao.cn", "fanjiao.co")
            role_name = cv_item.get("role_name") or None
            # cv_type: 1=主役, 2=协役
            cv_type = cv_item.get("cv_type", 1)
            role_type = "main" if cv_type == 1 else "support"
            result.cvs.append(Cv(
                id=cv_id,
                name=cv_name,
                avatar_url=avatar or _cv_avatar_url(cv_name),
            ))
            result.roles.append(Role(
                drama_id=drama_id,
                cv_id=cv_id,
                role_type=role_type,
                character_name=role_name,
            ))

    return info_data, cv_list


def fetch_fanjiao_dramas(result: CrawlResult | None = None) -> Iterable[Drama]:
    """爬取饭角广播剧排行榜元数据（优化版）
    流程：
    1. 通过排行榜API获取热门专辑列表（tab=2,3,4,5 各取 size=20）
    2. 对每个专辑并发调用 album_info + actor_cvs 两个API：
       - album_info: 准确获取 author_name/cover/publish_date/play/up_name/tags
       - actor_cvs: 获取 CV 真实头像、角色名、cv_type(主役/协役)
    3. 集数从描述中"共XX集"解析，播放量优先用 album_info.play
    优化点：
    - 用 album_info API 直接获取结构化字段（作者/封面/年份/制作方），不再依赖正则解析描述
    - 用 actor_cvs API 获取真实CV头像，不再使用 DiceBear 兜底
    - 多专辑详情并发获取（MAX_WORKERS 线程），大幅提升速度
    """
    seen_ids: set[str] = set()
    all_albums: list[dict] = []  # 从排行榜收集的专辑（去重）

    # Step 1: 收集排行榜专辑ID（4个tab，每个20条）
    for tab in [2, 3, 4, 5]:
        try:
            result_data = _fanjiao_get("/walkman/api/ranking/album", {
                "tab": tab, "time_type": 4, "page": 1, "size": 20,
            })
            if result_data.get("code") != 0 or not result_data.get("data"):
                log.info("饭角排行榜 tab=%d: 无数据", tab)
                time.sleep(REQUEST_DELAY)
                continue
            albums = result_data["data"].get("list", []) or []
            for album in albums:
                album_id = album.get("album_id", 0)
                if not album_id:
                    continue
                drama_id = f"fanjiao_{album_id}"
                if drama_id in seen_ids:
                    continue
                seen_ids.add(drama_id)
                all_albums.append(album)
            log.info("饭角排行榜 tab=%d: 收集 %d 条", tab, len(albums))
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            log.warning("饭角排行榜 tab=%d 失败: %s", tab, e)

    log.info("饭角排行榜共收集 %d 个专辑（去重后），开始并发获取详情...", len(all_albums))

    # Step 2: 并发获取每个专辑的详情和CV列表
    def _process_album(album: dict) -> Drama | None:
        album_id = album.get("album_id", 0)
        name = (album.get("name") or "").strip()
        if not album_id or not name:
            return None
        drama_id = f"fanjiao_{album_id}"

        # 排行榜接口已有字段：name/description/cover/up_name/play
        album_desc = album.get("description", "") or ""
        description = _strip_html(album_desc)[:500] if album_desc else None
        cover_url = album.get("cover", "") or album.get("square", "") or None
        studio = album.get("up_name", "") or None
        play_count = int(album.get("play", 0) or 0)

        # 调用 album_info + actor_cvs 获取结构化数据
        info_data, cv_list = _fetch_fanjiao_album_detail(album_id, drama_id, result)

        # 合并 album_info 的准确字段（优先级高于排行榜接口）
        if info_data:
            # 作者：album_info.author_name 是结构化字段，比正则解析更准确
            author_name = (info_data.get("author_name") or "").strip()
            if author_name:
                original_work = author_name
            else:
                original_work = _parse_fanjiao_author(album_desc)
            # 封面：优先用 album_info.cover
            cover_url = info_data.get("cover") or cover_url
            # 播放量：album_info.play 更准确
            play_count = int(info_data.get("play", 0) or play_count)
            # 制作方：album_info.up_name
            studio = info_data.get("up_name") or studio
            # 年份：从 publish_date 提取
            publish_date = info_data.get("publish_date", "") or ""
            year = _parse_fanjiao_year("", publish_date) if publish_date else _parse_fanjiao_year(album_desc)
            # 标签：从 tags 结构化字段提取
            tags_data = info_data.get("tags", {}) or {}
            tag_names: list[str] = ["百合"]
            for style_tag in (tags_data.get("style_tag") or []):
                t = (style_tag.get("name") or "").strip()
                if t and t not in tag_names:
                    tag_names.append(t)
            for content_tag in (tags_data.get("content_tag") or []):
                t = (content_tag.get("name") or "").strip()
                if t and t not in tag_names and t != original_work:
                    tag_names.append(t)
        else:
            # album_info 失败时回退到正则解析
            original_work = _parse_fanjiao_author(album_desc)
            year = _parse_fanjiao_year(album_desc)
            tag_names = ["百合"]

        # 集数：从描述解析"共XX集"
        total_episodes = _parse_fanjiao_episodes(album_desc)

        return Drama(
            id=drama_id,
            title=name,
            original_work=original_work,
            platform="饭角",
            year=year,
            total_episodes=total_episodes,
            play_count=play_count,
            cover_url=cover_url,
            description=description,
            studio=studio,
            source_url=f"https://www.fanjiao.co/album/{album_id}",
            tags=tag_names,
        )

    completed = 0
    total = len(all_albums)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_process_album, a): a for a in all_albums}
        for future in as_completed(futures):
            completed += 1
            try:
                d = future.result()
                if d is not None:
                    yield d
                if completed % 10 == 0 or completed == total:
                    log.info("饭角详情进度: %d/%d", completed, total)
            except Exception as e:
                log.warning("饭角详情获取异常: %s", e)


# ---------------------------------------------------------------------------
# 手动维护的高质量数据
# ---------------------------------------------------------------------------
def fetch_curated_dramas() -> Iterable[Drama]:
    yield Drama(id="dr1", title="我亲爱的法医小姐", original_work="酒暖回忆",
                platform="喜马拉雅", year=2023, total_episodes=80,
                play_count=9_130_000, rating_avg=4.8, rating_count=12400,
                studio="之贝文化",
                description="口吐芬芳一点就炸狐狸精法医 × 前期内敛禁欲后期又奶又狼刑侦队长。查案，猜心，探情。年上，强强，双御姐。",
                tags=["现代", "悬疑", "刑侦", "强强", "HE", "高人气"])
    yield Drama(id="dr2", title="探虚陵现代篇", original_work="君sola",
                platform="听姬", year=2024, total_episodes=48,
                play_count=6_850_000, rating_avg=4.7, rating_count=8900,
                studio="听姬出品",
                description="师清玄与洛神，两个性格迥异的女性携手探秘，揭开一个又一个惊天谜团。",
                tags=["现代", "悬疑", "探险", "强强", "HE"])
    yield Drama(id="dr3", title="我们都要好好的",
                platform="漫播", year=2024, total_episodes=16,
                play_count=300_000, rating_avg=4.5, rating_count=3200,
                studio="壹叁贰壹工作室",
                description="漫播投喂月榜第一，漫播免费榜前5。现代百合甜宠剧。",
                tags=["现代", "都市", "甜宠", "HE", "高人气"])
    yield Drama(id="dr4", title="夏·茉",
                platform="猫耳FM", year=2022, total_episodes=3,
                play_count=76_130, rating_avg=4.6, rating_count=1560,
                studio="山海归一工作室",
                description="原创现代校园百合广播剧。是青春年少的情窦初开，是少年时期的别扭迷茫。",
                tags=["校园", "青春", "甜宠", "HE"])
    yield Drama(id="dr5", title="花期",
                platform="猫耳FM", year=2021, total_episodes=1,
                play_count=120_000, rating_avg=4.2, rating_count=980,
                studio="DL_工作室",
                description="两个身患绝症的女孩子在最好的年纪和最坏的时候遇到……",
                tags=["现代", "虐恋", "BE", "全一期"])
    yield Drama(id="dr6", title="天上掉下一只小花妖",
                platform="猫耳FM", year=2019, total_episodes=1,
                play_count=64_690, rating_avg=4.0, rating_count=640,
                description="原创现代百合广播剧，日常轻松向。",
                tags=["现代", "奇幻", "甜宠", "全一期"])
    yield Drama(id="dr7", title="依旧故人来",
                platform="喜马拉雅", year=2020, total_episodes=1,
                play_count=56_870, rating_avg=4.1, rating_count=420,
                studio="恶人谷配音组",
                description="方扉求职却巧遇多年前的爱人，牵扯出一段被时间掩埋的旧情缘。",
                tags=["现代", "破镜重圆", "甜宠", "HE", "全一期"])
    yield Drama(id="dr8", title="如诗如梦",
                platform="猫耳FM", year=2025, total_episodes=4,
                play_count=74_850, rating_avg=4.3, rating_count=580,
                description="全四期百合广播剧，古风唯美。",
                tags=["古风", "唯美", "HE"])
    yield Drama(id="dr9", title="漂亮废物", original_work="引路星",
                platform="猫耳FM", year=2023, total_episodes=14,
                play_count=350_000, rating_avg=4.4, rating_count=2800,
                studio="壹叁贰壹工作室",
                description="猫耳免费榜前10，持续占榜3个月。",
                tags=["现代", "都市", "甜宠", "HE"])
    yield Drama(id="dr10", title="探虚陵古风篇", original_work="君sola",
                platform="听姬", year=2023, total_episodes=36,
                play_count=5_200_000, rating_avg=4.6, rating_count=7600,
                studio="听姬出品",
                description="古风探秘，师清玄与洛神的前传故事，揭开千年古墓的秘密。",
                tags=["古风", "悬疑", "探险", "强强", "HE"])
    yield Drama(id="dr11", title="仙尊装逼指南",
                platform="猫耳FM", year=2024, total_episodes=12,
                play_count=100_000, rating_avg=4.1, rating_count=1200,
                studio="壹叁贰壹工作室",
                description="猫耳免费榜前30，持续霸榜2个月。",
                tags=["古风", "修仙", "搞笑", "HE"])
    yield Drama(id="dr12", title="全网都在磕我们的CP",
                platform="兔U", year=2024, total_episodes=18,
                play_count=280_000, rating_avg=4.3, rating_count=2100,
                studio="壹叁贰壹工作室",
                description="兔U投喂榜霸榜前5持续6个月。",
                tags=["现代", "娱乐圈", "甜宠", "HE", "高人气"])


def fetch_curated_cvs() -> Iterable[Cv]:
    yield Cv(id="cv1", name="水母", bio="代表作品：《我们都要好好的》《漂亮废物》等。声线温柔细腻，擅长现代甜宠角色。")
    yield Cv(id="cv2", name="金喵儿", bio="代表作品：《我们都要好好的》等。声线清亮，擅长御姐角色。")
    yield Cv(id="cv3", name="凯特caty", bio="代表作品：《夏·茉》等。声线可盐可甜，擅长校园青春角色。")
    yield Cv(id="cv4", name="慕少寻", bio="代表作品：《夏·茉》等。声线沉稳，擅长冷面角色。")
    yield Cv(id="cv5", name="殳叶", bio="代表作品：《花期》等。声线柔美，擅长悲剧角色。")
    yield Cv(id="cv6", name="白术", bio="代表作品：《花期》等。声线帅气，擅长中性角色。")
    yield Cv(id="cv7", name="阮绡绯", bio="代表作品：《天上掉下一只小花妖》等。声线甜美，擅长可爱角色。")
    yield Cv(id="cv8", name="凤梨", bio="代表作品：《依旧故人来》等。恶人谷配音组成员，声线百变。")
    yield Cv(id="cv9", name="夏觅尘", bio="代表作品：《全网都在磕我们的CP》等。声线低沉磁性。")
    yield Cv(id="cv10", name="小K", bio="代表作品：《漂亮废物》等。声线温柔。")


def fetch_curated_roles() -> Iterable[Role]:
    yield Role("dr1", "cv1", "main", "林厌")
    yield Role("dr1", "cv2", "main", "余酒")
    yield Role("dr2", "cv1", "main", "师清玄")
    yield Role("dr2", "cv2", "main", "洛神")
    yield Role("dr3", "cv1", "main", "主角A")
    yield Role("dr3", "cv2", "main", "主角B")
    yield Role("dr4", "cv3", "main", "盛夏")
    yield Role("dr4", "cv4", "main", "季茉")
    yield Role("dr5", "cv5", "main", "花漪")
    yield Role("dr5", "cv6", "main", "郁冬")
    yield Role("dr6", "cv7", "main", "林晓")
    yield Role("dr7", "cv8", "main", "易水谣")
    yield Role("dr8", "cv7", "main")
    yield Role("dr8", "cv3", "support")
    yield Role("dr9", "cv10", "main")
    yield Role("dr9", "cv1", "main")
    yield Role("dr10", "cv1", "main", "师清玄")
    yield Role("dr10", "cv2", "main", "洛神")
    yield Role("dr11", "cv9", "main")
    yield Role("dr12", "cv9", "main")
    yield Role("dr12", "cv1", "main")


# ---------------------------------------------------------------------------
# 别名归一化 + 去重
# ---------------------------------------------------------------------------
def load_aliases() -> dict[str, str]:
    if ALIASES_FILE.exists():
        with ALIASES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {k.lower(): v for k, v in data.items()}
    return {}


def normalize_name(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name.strip().lower(), name.strip())


def filter_low_quality_dramas(dramas: Iterable[Drama]) -> list[Drama]:
    """过滤低质量数据记录，确保数据库质量"""
    out: list[Drama] = []
    for d in dramas:
        # 必须有标题
        if not d.title or not d.title.strip():
            continue
        # 标题不能是纯数字或过短
        title = d.title.strip()
        if len(title) < 2:
            continue
        if title.isdigit():
            continue
        # 必须有平台信息
        if not d.platform or d.platform == "未知":
            continue
        # 播放量必须大于0（过滤无效记录）
        if d.play_count <= 0:
            continue
        out.append(d)
    return out


def dedupe(items: Iterable[Drama]) -> list[Drama]:
    seen: set[str] = set()
    out: list[Drama] = []
    for d in items:
        if d.id in seen:
            continue
        seen.add(d.id)
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# 写入 Supabase（使用 REST API）
# ---------------------------------------------------------------------------
# 注意：PostgREST 要求同一批次 upsert 的所有对象必须有完全相同的字段（key）
# 所以即使字段值为 None，也必须显式包含，不能移除
# ---------------------------------------------------------------------------

def upsert_dramas(client: SupabaseREST, dramas: list[Drama]) -> None:
    if not dramas:
        return
    # 所有对象必须有完全相同的 key（PostgREST PGRST102 约束）
    payload = [
        {
            "id": d.id,
            "title": d.title,
            "original_work": d.original_work if d.original_work else None,
            "platform": d.platform if d.platform else None,
            "year": d.year if d.year else None,
            "total_episodes": d.total_episodes if d.total_episodes else None,
            "play_count": d.play_count,
            "rating_avg": d.rating_avg,
            "rating_count": d.rating_count,
            "cover_url": d.cover_url if d.cover_url else None,
            "description": d.description if d.description else None,
            "studio": d.studio if d.studio else None,
            "director": d.director if d.director else None,
            "source_url": d.source_url if d.source_url else None,
            "tags": d.tags if d.tags else None,
        }
        for d in dramas
    ]
    log.info("upserting %d dramas...", len(payload))
    result = client.upsert("dramas", payload)
    log.info("dramas upsert OK, returned=%d", len(result))


def upsert_cvs(client: SupabaseREST, cvs: list[Cv]) -> None:
    if not cvs:
        return
    # 所有对象必须有完全相同的 key
    payload = [
        {
            "id": c.id,
            "name": c.name,
            "avatar_url": c.avatar_url if c.avatar_url else None,
            "bio": c.bio if c.bio else None,
        }
        for c in cvs
    ]
    log.info("upserting %d cvs...", len(payload))
    result = client.upsert("cvs", payload)
    log.info("cvs upsert OK, returned=%d", len(result))


def upsert_roles(client: SupabaseREST, roles: list[Role]) -> None:
    if not roles:
        return
    # 所有对象必须有完全相同的 key
    payload = [
        {
            "drama_id": r.drama_id,
            "cv_id": r.cv_id,
            "role_type": r.role_type,
            "character_name": r.character_name if r.character_name else None,
        }
        for r in roles
    ]
    log.info("upserting %d roles...", len(payload))
    result = client.upsert("drama_cv_roles", payload)
    log.info("roles upsert OK, returned=%d", len(result))


# ---------------------------------------------------------------------------
# 触发 Vercel 重建
# ---------------------------------------------------------------------------
def trigger_vercel_deploy() -> None:
    """触发 Vercel 重建（可选）。
    如果未设置 VERCEL_DEPLOY_HOOK，不影响数据更新——
    JSON 数据提交到仓库后，Vercel 会自动检测 git push 并重建。
    """
    hook = os.environ.get("VERCEL_DEPLOY_HOOK")
    if not hook:
        log.info("VERCEL_DEPLOY_HOOK 未设置（可选），跳过。JSON 提交后 Vercel 会自动重建。")
        return
    try:
        resp = requests.post(hook, timeout=15)
        log.info("Vercel deploy hook 响应: %d", resp.status_code)
    except Exception as e:
        log.warning("触发 Vercel 重建失败（不影响数据同步）: %s", e)


def export_json(cr: CrawlResult) -> Path:
    """将爬取的数据导出为 JSON 文件，供网站构建时直接读取。
    这是数据同步到网站的核心机制：JSON 提交到仓库 → Vercel 检测到 push 自动重建。
    """
    data_dir = ROOT / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / "latest.json"

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dramas": [
            {
                "id": d.id,
                "title": d.title,
                "original_work": d.original_work,
                "platform": d.platform,
                "year": d.year,
                "total_episodes": d.total_episodes,
                "play_count": d.play_count,
                "rating_avg": d.rating_avg,
                "rating_count": d.rating_count,
                "cover_url": d.cover_url,
                "description": d.description,
                "studio": d.studio,
                "director": d.director,
                "source_url": d.source_url,
                "tags": d.tags,
            }
            for d in cr.dramas
        ],
        "cvs": [
            {"id": c.id, "name": c.name, "avatar_url": c.avatar_url, "bio": c.bio}
            for c in cr.cvs
        ],
        "roles": [
            {
                "drama_id": r.drama_id,
                "cv_id": r.cv_id,
                "role_type": r.role_type,
                "character_name": r.character_name,
            }
            for r in cr.roles
        ],
    }

    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("JSON 数据已导出: %s (dramas=%d, cvs=%d, roles=%d)",
             out, len(cr.dramas), len(cr.cvs), len(cr.roles))
    return out


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="百合广播剧数据流水线")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过在线爬取，仅使用手动数据")
    parser.add_argument("--clear", action="store_true", help="写入前清空 Supabase 所有表数据（完全覆盖）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    global _verbose
    _verbose = args.verbose
    if _verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    url = os.environ.get("SUPABASE_URL", "").strip() or os.environ.get("PUBLIC_SUPABASE_URL", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    aliases = load_aliases()

    # 收集数据
    cr = CrawlResult()
    # curated 数据改为仅作为 fallback（当在线爬取失败时才使用）
    curated_dramas = list(fetch_curated_dramas())
    curated_cvs = list(fetch_curated_cvs())
    curated_roles = list(fetch_curated_roles())

    if not args.skip_crawl:
        log.info("开始在线爬取...")
        crawlers = [
            (fetch_maoer_dramas, "猫耳FM"),
            (fetch_ximalaya_dramas, "喜马拉雅"),
            (fetch_lizhi_dramas, "荔枝FM"),
            (fetch_manbo_dramas, "漫播"),
        ]
        for fn, name in crawlers:
            try:
                results = list(fn())
                cr.dramas.extend(results)
                log.info("%s 爬取完成: %d 条", name, len(results))
            except Exception as e:
                log.warning("%s 爬取异常: %s", name, e)

        # 饭角爬虫需要传入 CrawlResult 以提取CV
        try:
            fanjiao_dramas = list(fetch_fanjiao_dramas(result=cr))
            cr.dramas.extend(fanjiao_dramas)
            log.info("饭角 爬取完成: %d 条", len(fanjiao_dramas))
        except Exception as e:
            log.warning("饭角 爬取异常: %s", e)

        # 对猫耳FM的数据补充详情（同时提取CV）
        maoer_dramas = [d for d in cr.dramas if d.id.startswith("maoer_")]
        if maoer_dramas:
            log.info("补充猫耳FM详情 (%d 条)...", len(maoer_dramas))
            cr.dramas = fetch_maoer_drama_details(cr.dramas, cr)

        # 如果在线爬取全部失败，使用 curated 数据作为 fallback
        if not cr.dramas:
            log.warning("在线爬取无数据，使用 curated 数据作为 fallback")
            cr.dramas = curated_dramas
            cr.cvs = curated_cvs
            cr.roles = curated_roles
        else:
            # 合并 curated 数据中的CV和角色（补充在线爬取可能遗漏的）
            cr.cvs.extend(curated_cvs)
            cr.roles.extend(curated_roles)
    else:
        # skip_crawl 模式：直接使用 curated 数据
        cr.dramas = curated_dramas
        cr.cvs = curated_cvs
        cr.roles = curated_roles

    # 数据质量过滤 + 去重 + 归一化
    before_filter = len(cr.dramas)
    cr.dramas = filter_low_quality_dramas(cr.dramas)
    if before_filter != len(cr.dramas):
        log.info("数据质量过滤: %d -> %d (过滤 %d 条低质量记录)",
                 before_filter, len(cr.dramas), before_filter - len(cr.dramas))
    cr.dramas = dedupe(cr.dramas)

    # CV去重（同名CV合并）
    seen_cv_ids: set[str] = set()
    seen_cv_names: dict[str, str] = {}  # name_lower -> cv_id
    unique_cvs: list[Cv] = []
    for c in cr.cvs:
        c.name = normalize_name(c.name, aliases)
        name_lower = c.name.lower()
        if c.id not in seen_cv_ids:
            seen_cv_ids.add(c.id)
            seen_cv_names[name_lower] = c.id
            unique_cvs.append(c)
        elif name_lower not in seen_cv_names:
            seen_cv_names[name_lower] = c.id
    cr.cvs = unique_cvs

    # Role中的cv_id归一化（同名CV指向同一id）
    cv_name_to_id = {c.name.lower(): c.id for c in cr.cvs}
    for r in cr.roles:
        # 如果cv_id不在cvs列表中，尝试通过名称查找
        if r.cv_id not in seen_cv_ids:
            pass  # 保留原cv_id

    # Role去重
    seen_roles: set[tuple[str, str, str]] = set()
    unique_roles: list[Role] = []
    for r in cr.roles:
        key = (r.drama_id, r.cv_id, r.role_type)
        if key not in seen_roles:
            seen_roles.add(key)
            unique_roles.append(r)
    cr.roles = unique_roles

    # 过滤掉引用不存在 drama_id 或 cv_id 的 roles（避免外键约束冲突）
    valid_drama_ids = {d.id for d in cr.dramas}
    valid_cv_ids = {c.id for c in cr.cvs}
    before_role_filter = len(cr.roles)
    cr.roles = [r for r in cr.roles if r.drama_id in valid_drama_ids and r.cv_id in valid_cv_ids]
    if before_role_filter != len(cr.roles):
        log.info("Role 外键过滤: %d -> %d (移除 %d 条引用不存在记录的 role)",
                 before_role_filter, len(cr.roles), before_role_filter - len(cr.roles))

    log.info("数据汇总: dramas=%d, cvs=%d, roles=%d", len(cr.dramas), len(cr.cvs), len(cr.roles))

    if args.dry_run:
        print(json.dumps(
            [{"id": d.id, "title": d.title, "platform": d.platform, "play_count": d.play_count,
              "original_work": d.original_work, "tags": d.tags} for d in cr.dramas],
            ensure_ascii=False, indent=2,
        ))
        return 0

    # 导出 JSON 数据文件（网站构建时直接读取，不依赖 Supabase 环境变量）
    export_json(cr)

    # 写入 Supabase（如果配置了凭据）
    if not url or not service_key:
        log.warning("SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY 未设置，跳过 Supabase 写入")
        log.warning("请在 GitHub 仓库 Settings → Secrets → Actions 中添加这两个值以启用数据库同步")
        log.warning("JSON 数据已导出，网站仍可通过本地 JSON 更新")
        return 0

    log.info("Supabase URL: %s", url)
    log.info("Service key prefix: %s...", service_key[:10] if service_key else "(empty)")

    # 验证 URL 格式
    if not url.startswith("https://"):
        log.error("SUPABASE_URL 格式错误，应以 https:// 开头，当前值: %s", url[:50])
        return 1

    # 创建 REST 客户端
    client = SupabaseREST(url, service_key)

    # 验证表
    log.info("验证 Supabase 表...")
    for table in ["dramas", "cvs", "drama_cv_roles"]:
        if not client.table_exists(table):
            log.error("表 '%s' 不存在！请先在 Supabase SQL Editor 中执行 schema.sql", table)
            return 1
    log.info("所有表验证通过 ✓")

    # 写入数据到 Supabase
    log.info("开始写入 Supabase...")
    if args.clear:
        log.info("=== --clear 模式：清空所有表数据 ===")
        # 先删 roles（外键依赖 cvs 和 dramas），再删 cvs 和 dramas
        # drama_cv_roles 表没有 id 列，用 drama_id 作为过滤列
        for table, col in [("drama_cv_roles", "drama_id"), ("cvs", "id"), ("dramas", "id")]:
            try:
                client.delete_all(table, filter_column=col)
            except Exception as e:
                log.warning("清空表 %s 失败（可能为空）: %s", table, e)
        log.info("所有表已清空，开始写入新数据")
    upsert_dramas(client, cr.dramas)
    upsert_cvs(client, cr.cvs)
    upsert_roles(client, cr.roles)
    log.info("Supabase 写入完成 ✓ (dramas=%d, cvs=%d, roles=%d)", len(cr.dramas), len(cr.cvs), len(cr.roles))

    # 触发重建（可选，JSON 提交也会触发 Vercel 重建）
    trigger_vercel_deploy()

    return 0


if __name__ == "__main__":
    sys.exit(main())
