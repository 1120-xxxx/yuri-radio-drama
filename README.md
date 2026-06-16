# 百合广播剧数据可视化平台

Astro SSG + Supabase Serverless + Vue 3 岛屿组件 + ECharts 可视化。全静态站点，匿名评分评论，零运维成本。

## 功能模块

- 首页：核心指标卡片、平台分布图、Top10 榜单
- 排行榜：播放量 / 评分 / 评分人数 / CV 参演数 四个维度切换
- 剧集库：搜索、按平台与年份筛选
- 剧集详情页：基础信息预渲染 + 动态评分评论组件
- CV 名录：CV 列表与详情，展示参演作品
- 评分评论：匿名 1-5 星，可选短评，自动计算均分

## 目录结构

```
src/
├─ pages/              # 路由与静态页面 (Astro .astro)
│  ├─ index.astro         # 首页
│  ├─ rank.astro          # 排行榜
│  ├─ dramas/index.astro  # 剧集库
│  ├─ dramas/[id].astro   # 剧集详情
│  ├─ cvs/index.astro     # CV 名录
│  └─ cvs/[id].astro      # CV 详情
├─ layouts/            # 全局布局 (BaseLayout)
├─ components/         # 基础 UI 组件 (Card / Badge / Stat)
├─ islands/            # Vue 3 岛屿：图表 + 搜索筛选 + 评分组件
├─ lib/                # 数据层与 Supabase 客户端
└─ styles/             # 全局样式与设计令牌
scripts/               # Python 爬虫与数据流水线
supabase/schema.sql    # 数据库结构与 RLS 策略
.github/workflows/     # 定时更新 + Vercel 部署钩子
```

## 本地开发

```bash
npm install
npm run dev         # http://127.0.0.1:4321
npm run build       # 生成静态站点到 dist/
npm run preview     # 预览构建产物
```

首次运行无需 Supabase 配置，会自动使用 `src/lib/mock-data.ts` 中内置的示例数据，方便样式调试与纯前端开发。

## 接入 Supabase（可选，用于真实评分写入）

1. 在 [supabase.com](https://supabase.com) 新建项目
2. 复制 `supabase/schema.sql` 到 SQL Editor 执行（会自动创建 dramas/cvs/roles/ratings 四张表与 RLS 策略）
3. 在项目根目录新建 `.env`：

```
PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
PUBLIC_SUPABASE_ANON_KEY=eyJhbG...（匿名可读）
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...（仅 Node 构建与数据流水线使用，不提交到仓库）
```

4. 通过 `scripts/crawler_main.py` 抓取或手动插入剧集与 CV 数据

## 部署到 Vercel（免费）

1. 把项目推送到 GitHub 公开仓库
2. 在 Vercel 导入仓库，框架识别为 `Astro`，构建命令 `npm run build`，输出 `dist`
3. 在 Vercel 后台配置 `PUBLIC_SUPABASE_URL`、`PUBLIC_SUPABASE_ANON_KEY` 两个环境变量
4. Vercel 会自动签发 HTTPS 证书，分配 `*.vercel.app` 子域；绑定自定义域名只需在域名商添加 CNAME
5. 在 GitHub 仓库 Secrets 配置 `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`VERCEL_DEPLOY_HOOK`
6. `.github/workflows/sync-data.yml` 每周一 UTC 02:00 自动跑爬虫并调用 Deploy Hook 重建站点

## 加速优化（Cloudflare，免费）

1. 域名 NS 指向 Cloudflare
2. 开启 CDN + 中国大陆优化线路
3. Vercel → Cloudflare 之间流量走 HTTPS，加速国内访问静态页面

## 数据流水线

`scripts/crawler_main.py` 是一个最小骨架：
- 内置示例数据（`fetch_sample_dramas()` / `fetch_sample_cvs()` / `fetch_sample_roles()`）
- `aliases.json` 用于名称归一化
- `--dry-run` 仅预览 JSON 输出；无该参数时通过 Supabase Python SDK 写入
- 实际抓取时按需扩展（例如从猫耳 FM API、喜马拉雅搜索页提取）

```bash
pip install -r scripts/requirements.txt
python scripts/crawler_main.py --dry-run
```

## 安全说明

- Supabase `anon key` 仅具备 `dramas / cvs / drama_cv_roles` 的 `SELECT` 权限，以及 `ratings` 的 `SELECT + INSERT` 权限；`UPDATE / DELETE` 被 RLS 策略阻止
- `SUPABASE_SERVICE_ROLE_KEY` 仅限在 GitHub Actions 与 Vercel 构建环境使用，不得提交到仓库
- 评分通过 `(drama_id, ip_hash, device_fingerprint)` 唯一约束防刷分，设备指纹在浏览器侧计算，IP 在服务端哈希处理（不可逆）

## License

MIT — 仅供爱好者学习与交流使用。所聚合的公开元数据版权归原平台所有。
