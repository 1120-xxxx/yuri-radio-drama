# 百合广播剧数据可视化平台 - The Implementation Plan (Decomposed and Prioritized Task List)

## [ ] Task 1: Astro 项目脚手架与基础配置
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 初始化 Astro 项目（`npm create astro@latest`），配置 `astro.config.mjs` 启用 SSG 与 Vue 组件支持 (`@astrojs/vue`)。
  - 集成 UnoCSS：`@unocss/astro`，设置主题色与设计 token。
  - 集成 `@supabase/supabase-js` 客户端与 SSR 工具（`@supabase/ssr`）。
  - 配置 `src/env.d.ts` 与 `import.meta.env` 类型（`PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`）。
  - 建立目录结构：`src/pages`, `src/components`, `src/layouts`, `src/islands`, `src/lib`, `src/styles`, `public/`。
- **Acceptance Criteria Addressed**: AC-1, AC-10, AC-11
- **Test Requirements**:
  - `programmatic` TR-1.1: `npm run build` 在空内容下能成功产出 `dist/` 静态文件。
  - `programmatic` TR-1.2: 运行 `npm run dev` 能在 `http://localhost:4321` 返回基础页。
  - `human-judgement` TR-1.3: 项目目录结构清晰，可扩展；package.json 包含必要依赖。
- **Notes**: 使用 Node 18+；UnoCSS 预设 `@unocss/preset-uno` + `@unocss/preset-icons`。

## [ ] Task 2: Supabase 数据库 Schema 与 RLS 策略
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 在 Supabase 项目中执行 SQL 创建以下表：
    - `dramas` (id, title, original_work, platform, year, total_episodes, play_count, rating_avg, rating_count, cover_url, description, studio, director, source_url, created_at, updated_at)
    - `cvs` (id, name, avatar_url, bio, gender, created_at)
    - `drama_cv_roles` (drama_id, cv_id, role_type: 'main' | 'support' | 'director', character_name, created_at)  — 同时承担主役/协役/配音导演的关联
    - `ratings` (id, drama_id, score, comment, ip_hash, device_fingerprint, created_at)
  - 添加唯一约束：`ratings(drama_id, ip_hash, device_fingerprint)`，同时建立必要索引（dramas(title)、drama_cv_roles(drama_id, cv_id) 等）。
  - 开启 RLS 并编写策略：
    - `dramas`: anon 仅 SELECT
    - `cvs`: anon 仅 SELECT
    - `drama_cv_roles`: anon 仅 SELECT
    - `ratings`: anon SELECT + INSERT，禁止 UPDATE/DELETE
  - 保存 SQL 脚本至 `supabase/schema.sql`，作为项目部署可复现脚本。
- **Acceptance Criteria Addressed**: AC-6, AC-7, AC-8, AC-11
- **Test Requirements**:
  - `programmatic` TR-2.1: 在 Supabase SQL Editor 执行 schema.sql 无报错，并能看到所有表与策略。
  - `programmatic` TR-2.2: 使用 anon key 通过 JS SDK 对 `dramas` 做 SELECT 成功；做 UPDATE/DELETE 返回 403。
  - `programmatic` TR-2.3: 使用 anon key 两次 `INSERT` 同一条 ratings（相同 drama_id + ip_hash + device_fingerprint）第二次返回唯一性冲突错误。

## [ ] Task 3: Supabase 客户端封装与数据层抽象
- **Priority**: P0
- **Depends On**: Task 1, Task 2
- **Description**:
  - 在 `src/lib/supabase.ts` 中封装：
    - 浏览器侧 `createClient`（读取 `PUBLIC_SUPABASE_URL`/`PUBLIC_SUPABASE_ANON_KEY`）
    - 构建时 `createClient`（使用 `SUPABASE_SERVICE_ROLE_KEY`，仅用于 Node/Vercel 构建环境）
  - 在 `src/lib/data.ts` 中抽象数据获取函数：
    - `getAllDramas()`、`getDramaById(id)`
    - `getAllCvs()`、`getCvById(id)`
    - `getDramaRoles(dramaId)`、`getCvRoles(cvId)`
    - `getRankings(metric)`
    - `getStatsOverview()`
  - 在 `src/lib/ratings.ts` 中封装：
    - `getRatingForDrama(dramaId)`（均分、评论列表）
    - `submitRating({ dramaId, score, comment, ipHash, deviceFingerprint })`
- **Acceptance Criteria Addressed**: AC-1, AC-4, AC-5, AC-6, AC-8
- **Test Requirements**:
  - `programmatic` TR-3.1: 通过 TypeScript 类型检查（`tsc --noEmit` 或 Astro 构建）无类型错误。
  - `programmatic` TR-3.2: 构建期从 Supabase 正确拉取样例数据并序列化。
  - `human-judgement` TR-3.3: 代码结构清晰，错误处理与空值兜底合理。

## [ ] Task 4: 全局布局、导航与 UnoCSS 设计令牌
- **Priority**: P1
- **Depends On**: Task 1
- **Description**:
  - 编写 `src/layouts/BaseLayout.astro`：header 导航（首页 / 剧集库 / 排行榜 / CV 榜），footer，移动端 hamburger 菜单。
  - 在 `src/styles/global.css` 定义 CSS 变量（颜色、圆角、阴影、字体栈），供 UnoCSS 使用。
  - 封装基础组件：`Card`, `Badge`, `Button`, `Tag`, `Container` 等 Astro 组件。
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `human-judgement` TR-4.1: 主要页面在 1920/1024/375px 视口下导航可用、无明显错位。
  - `programmatic` TR-4.2: UnoCSS 编译产出正常，无缺失样式类。

## [ ] Task 5: ECharts 图表岛屿组件封装
- **Priority**: P1
- **Depends On**: Task 1, Task 4
- **Description**:
  - 在 `src/islands/` 下创建 Vue 3 岛屿组件，统一封装 ECharts：
    - `PlatformPieChart.vue`：平台分布饼图
    - `YearBarChart.vue`：年份分布柱状图
    - `RatingTrendChart.vue`：评分/数量趋势折线图
    - `TopNBarChart.vue`：Top N 横向柱状图
  - 组件通过 props 接收数据；监听窗口 resize 自适应；SSR 时输出占位骨架。
  - 导出统一工具：`src/lib/echarts.ts`（懒加载 ECharts 核心与主题）。
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-10
- **Test Requirements**:
  - `human-judgement` TR-5.1: 图表在 PC 与移动端均可见并自适应尺寸。
  - `programmatic` TR-5.2: 首次访问核心页图表 JS < 150KB（启用 Astro 岛屿按需加载）。

## [ ] Task 6: 首页页面实现
- **Priority**: P0
- **Depends On**: Task 3, Task 4, Task 5
- **Description**:
  - `src/pages/index.astro`：构建期通过 `getStatsOverview()`、`getRankings('play_count')` 等拉取数据并预渲染指标卡片、平台分布图、Top10 榜单。
  - 动态图表采用 `<ClientOnly>` 或岛屿 `client:visible` 指令。
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-6.1: `npm run build` 构建首页成功，产出 `dist/index.html` 包含关键指标数字。
  - `human-judgement` TR-6.2: 视觉层级清晰，卡片/图表排版合理。

## [ ] Task 7: 排行榜专区实现
- **Priority**: P1
- **Depends On**: Task 3, Task 5, Task 6
- **Description**:
  - `src/pages/rank.astro`：构建期导出四种维度榜单数据，注入到 Vue 岛屿 `RankSwitcher.vue`。
  - 岛屿内切换 Tab 仅更新 props 绑定的数据，无网络请求。
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-7.1: 四种榜单数据均已序列化至 HTML 中，可被 JS 读取。
  - `human-judgement` TR-7.2: Tab 切换顺滑，表格/图表更新同步。

## [ ] Task 8: 剧集库页面（列表 + 搜索 + 筛选）
- **Priority**: P1
- **Depends On**: Task 3, Task 4
- **Description**:
  - `src/pages/dramas/index.astro`：预渲染全部剧集基本信息，注入至岛屿 `DramaList.vue`。
  - 岛屿组件实现客户端模糊搜索（按标题/CV 名/平台）与筛选（年份、类型、平台）。
- **Acceptance Criteria Addressed**: AC-3, AC-9
- **Test Requirements**:
  - `programmatic` TR-8.1: 输入关键字可正确过滤结果；切换筛选条件列表实时更新。
  - `human-judgement` TR-8.2: 搜索体验流畅，移动端键盘交互友好。

## [ ] Task 9: Astro 动态路由 - 剧集详情页 & CV 详情页
- **Priority**: P0
- **Depends On**: Task 3, Task 5
- **Description**:
  - `src/pages/dramas/[id].astro`：
    - `getStaticPaths()` 通过 `getAllDramas()` 预生成全部剧集详情页；
    - 预渲染基础信息 + 关联 CV 列表 + 制作信息；
    - 底部挂载 `RatingIsland.vue`（评分组件 + 评论列表）。
  - `src/pages/cvs/[id].astro`：
    - `getStaticPaths()` 通过 `getAllCvs()` 预生成全部 CV 详情页；
    - 预渲染 CV 基本信息 + 参演作品列表 + 相关统计卡片。
- **Acceptance Criteria Addressed**: AC-4, AC-5
- **Test Requirements**:
  - `programmatic` TR-9.1: 构建成功为每个 drama/cv 生成静态 HTML。
  - `programmatic` TR-9.2: 任一剧集详情页 HTML 内包含剧名与基础信息文本。
  - `human-judgement` TR-9.3: 详情页排版美观，信息分区清晰。

## [ ] Task 10: 匿名评分评论岛屿组件
- **Priority**: P0
- **Depends On**: Task 3, Task 9
- **Description**:
  - 实现 `src/islands/RatingIsland.vue`：
    - 5 星评分 UI；
    - 评论输入（可选，限 ≤ 200 字）；
    - 提交前检查浏览器端 localStorage 是否已评分；
    - 调用 `submitRating()`；服务端唯一性冲突时友好提示；
    - 提交后自动刷新均分与评论列表，按时间倒序展示。
  - 设备指纹：使用 `fingerprintjs` 免费包或本地哈希实现（见 spec.md open-question，暂定 fingerprintjs free）。
  - IP 哈希：由服务端（可选 Supabase Edge Function 或简单 Vercel Edge Function）读取 `x-forwarded-for` 做 sha256 后写入，浏览器侧仅提供 fingerprint。
- **Acceptance Criteria Addressed**: AC-6, AC-7, AC-8
- **Test Requirements**:
  - `programmatic` TR-10.1: 提交一次评分后，按钮禁用/隐藏，且同一浏览器刷新后保持「已评分」状态。
  - `programmatic` TR-10.2: 对同一剧集模拟两次提交，第二次写入失败并提示。
  - `human-judgement` TR-10.3: 评分组件在移动端布局合理。

## [ ] Task 11: Python 爬虫与数据清洗脚本
- **Priority**: P1
- **Depends On**: Task 2
- **Description**:
  - 在 `scripts/` 目录编写 Python 脚本：
    - `crawler_main.py`：基于 `requests` + `BeautifulSoup` 或平台公开 API（若有）抓取剧集与 CV 元数据。
    - `cleaners.py`：去重（基于 URL/平台 ID）、别名归一化（别名映射表 `aliases.json`）、空值/字段标准化。
    - `writer.py`：通过 `supabase` Python SDK 批量 upsert 写入数据库。
    - `pipeline.sh`：组合脚本，失败时退出码非 0。
  - 脚本支持 `--dry-run` 预览写入内容。
- **Acceptance Criteria Addressed**: AC-9
- **Test Requirements**:
  - `programmatic` TR-11.1: `python scripts/crawler_main.py --dry-run` 成功输出待写入数据摘要。
  - `programmatic` TR-11.2: 去重与别名映射逻辑通过单元测试（`pytest` 小套）。

## [ ] Task 12: GitHub Actions 定时更新与 Vercel Deploy Hook
- **Priority**: P1
- **Depends On**: Task 11
- **Description**:
  - 新增 `.github/workflows/sync-data.yml`：
    - `cron: '0 2 * * 0'` 每周一 UTC 02:00 运行；
    - 安装 Python 依赖并执行 `pipeline.sh`；
    - 成功后 `curl -X POST $VERCEL_DEPLOY_HOOK` 触发重建；
    - 失败时通过 GitHub Actions 通知；
  - 配置仓库 Secrets：`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `VERCEL_DEPLOY_HOOK`。
- **Acceptance Criteria Addressed**: AC-9, AC-11
- **Test Requirements**:
  - `programmatic` TR-12.1: 手动 `workflow_dispatch` 能成功运行并触发 Vercel 构建。
  - `programmatic` TR-12.2: cron 配置在仓库 Settings→Actions 可见且启用。

## [ ] Task 13: 部署配置与文档化
- **Priority**: P1
- **Depends On**: Task 1, Task 2, Task 12
- **Description**:
  - Vercel 配置（`vercel.json`，如需要）：框架识别 Astro；输出目录 `dist/`。
  - 在 `README.md`（或项目内说明文件）记录部署步骤：Supabase 配置→Vercel 导入→Cloudflare CDN→环境变量→Secrets→首次运行爬虫。
  - Cloudflare 接入建议（非强制脚本化）：添加 CNAME → 开启 HTTPS → 中国大陆优化线路。
- **Acceptance Criteria Addressed**: AC-11
- **Test Requirements**:
  - `human-judgement` TR-13.1: 依据说明文档可在空白账号上完成一次可复现部署。

## [ ] Task 14: 视觉走查与响应式调优
- **Priority**: P2
- **Depends On**: Task 6, Task 7, Task 8, Task 9
- **Description**:
  - 在 1920/1024/375px 视口对首页、排行榜、剧集库、详情页进行走查，修正间距、字号、溢出、图表比例等。
  - 微调 UnoCSS 主题，确保风格统一。
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `human-judgement` TR-14.1: 主要页面在三档视口下均无错位、无溢出。
  - `programmatic` TR-14.2: Lighthouse Performance/Accessibility/Best Practices 分数达标（如 ≥ 90/90/90）。
