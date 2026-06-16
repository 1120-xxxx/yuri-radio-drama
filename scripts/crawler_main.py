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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("pipeline")

ROOT = Path(__file__).resolve().parent.parent
ALIASES_FILE = ROOT / "scripts" / "aliases.json"

REQUEST_DELAY = 1.5  # 爬取请求间隔（秒）
_verbose = False  # 全局 verbose 标志


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
    description: str | None = None
    studio: str | None = None
    director: str | None = None
    source_url: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Cv:
    id: str
    name: str
    bio: str | None = None


@dataclass
class Role:
    drama_id: str
    cv_id: str
    role_type: str  # main / support / director
    character_name: str | None = None


# ---------------------------------------------------------------------------
# 猫耳FM 爬取（框架）
# ---------------------------------------------------------------------------
def fetch_maoer_dramas() -> Iterable[Drama]:
    """爬取猫耳FM百合标签下的广播剧元数据"""
    search_url = "https://www.missevan.com/mdrama/search"
    keywords = ["百合", "GL", "橘气"]
    for kw in keywords:
        try:
            params = {"s": kw, "type": 1}
            resp = requests.get(search_url, params=params, timeout=15,
                                headers={"User-Agent": "YuriDataBot/1.0"})
            resp.raise_for_status()
            log.info("猫耳FM搜索 '%s': status=%d", kw, resp.status_code)
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            log.warning("猫耳FM搜索 '%s' 失败: %s", kw, e)


# ---------------------------------------------------------------------------
# 喜马拉雅 爬取（框架）
# ---------------------------------------------------------------------------
def fetch_ximalaya_dramas() -> Iterable[Drama]:
    """爬取喜马拉雅百合广播剧元数据"""
    search_url = "https://www.ximalaya.com/revision/search/main"
    keywords = ["百合广播剧", "GL广播剧"]
    for kw in keywords:
        try:
            params = {"kw": kw, "page": 1, "pageSize": 20, "condition": "radio"}
            resp = requests.get(search_url, params=params, timeout=15,
                                headers={"User-Agent": "YuriDataBot/1.0"})
            resp.raise_for_status()
            data = resp.json()
            albums = data.get("data", {}).get("album", {}).get("albums", [])
            for album in albums:
                log.info("喜马拉雅: %s (播放 %s)", album.get("title", ""), album.get("playCount", 0))
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            log.warning("喜马拉雅搜索 '%s' 失败: %s", kw, e)


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
def _clean(item: dict) -> dict:
    """移除 None 值和空列表"""
    return {k: v for k, v in item.items() if v is not None and v != []}


def upsert_dramas(client: SupabaseREST, dramas: list[Drama]) -> None:
    if not dramas:
        return
    payload = [
        _clean({
            "id": d.id,
            "title": d.title,
            "original_work": d.original_work or None,
            "platform": d.platform or None,
            "year": d.year or None,
            "total_episodes": d.total_episodes or None,
            "play_count": d.play_count,
            "rating_avg": d.rating_avg,
            "rating_count": d.rating_count,
            "description": d.description or None,
            "studio": d.studio or None,
            "director": d.director or None,
            "source_url": d.source_url or None,
            "tags": d.tags if d.tags else None,
        })
        for d in dramas
    ]
    log.info("upserting %d dramas...", len(payload))
    result = client.upsert("dramas", payload)
    log.info("dramas upsert OK, returned=%d", len(result))


def upsert_cvs(client: SupabaseREST, cvs: list[Cv]) -> None:
    if not cvs:
        return
    payload = [_clean({"id": c.id, "name": c.name, "bio": c.bio or None}) for c in cvs]
    log.info("upserting %d cvs...", len(payload))
    result = client.upsert("cvs", payload)
    log.info("cvs upsert OK, returned=%d", len(result))


def upsert_roles(client: SupabaseREST, roles: list[Role]) -> None:
    if not roles:
        return
    payload = [
        _clean({
            "drama_id": r.drama_id,
            "cv_id": r.cv_id,
            "role_type": r.role_type,
            "character_name": r.character_name or None,
        })
        for r in roles
    ]
    log.info("upserting %d roles...", len(payload))
    result = client.upsert("drama_cv_roles", payload)
    log.info("roles upsert OK, returned=%d", len(result))


# ---------------------------------------------------------------------------
# 触发 Vercel 重建
# ---------------------------------------------------------------------------
def trigger_vercel_deploy() -> None:
    hook = os.environ.get("VERCEL_DEPLOY_HOOK")
    if not hook:
        log.warning("VERCEL_DEPLOY_HOOK 未设置，跳过触发重建")
        return
    try:
        resp = requests.post(hook, timeout=15)
        log.info("Vercel deploy hook 响应: %d", resp.status_code)
    except Exception as e:
        log.error("触发 Vercel 重建失败: %s", e)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="百合广播剧数据流水线")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过在线爬取，仅使用手动数据")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    global _verbose
    _verbose = args.verbose
    if _verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    url = os.environ.get("SUPABASE_URL", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    aliases = load_aliases()

    # 收集数据
    all_dramas: list[Drama] = list(fetch_curated_dramas())
    all_cvs: list[Cv] = list(fetch_curated_cvs())
    all_roles: list[Role] = list(fetch_curated_roles())

    if not args.skip_crawl:
        log.info("开始在线爬取...")
        for fn, name in [(fetch_maoer_dramas, "猫耳FM"), (fetch_ximalaya_dramas, "喜马拉雅")]:
            try:
                all_dramas.extend(list(fn()))
            except Exception as e:
                log.warning("%s 爬取异常: %s", name, e)

    # 去重 + 归一化
    all_dramas = dedupe(all_dramas)
    for c in all_cvs:
        c.name = normalize_name(c.name, aliases)

    log.info("数据汇总: dramas=%d, cvs=%d, roles=%d", len(all_dramas), len(all_cvs), len(all_roles))

    if args.dry_run:
        print(json.dumps(
            [{"id": d.id, "title": d.title, "platform": d.platform, "play_count": d.play_count,
              "tags": d.tags} for d in all_dramas],
            ensure_ascii=False, indent=2,
        ))
        return 0

    # 验证环境变量
    if not url or not service_key:
        log.error("SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY 未设置")
        log.error("请在 GitHub 仓库 Settings → Secrets → Actions 中添加这两个值")
        return 1

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

    # 写入数据
    upsert_dramas(client, all_dramas)
    upsert_cvs(client, all_cvs)
    upsert_roles(client, all_roles)
    log.info("全部写入完成 ✓")

    # 触发重建
    trigger_vercel_deploy()

    return 0


if __name__ == "__main__":
    sys.exit(main())
