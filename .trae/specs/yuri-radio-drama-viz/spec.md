# 百合广播剧数据可视化平台 - Product Requirement Document

## Overview

* **Summary**: 基于 Astro SSG + Supabase Serverless 架构，构建一个全免费、零运维、免备案的百合广播剧数据可视化平台，提供剧集库浏览、CV 信息查询、匿名评分评论、数据榜单与多维度可视化图表等功能。

* **Purpose**: 解决当前百合广播剧信息分散、数据不可视化、缺乏匿名评分系统的问题，为爱好者提供一个聚合、可浏览、可持续更新的信息门户。

* **Target Users**: 百合广播剧爱好者（核心用户）、CV 粉丝、数据控/榜单控、普通浏览游客。

## Goals

* 基于 Astro 构建纯静态站点，预渲染核心内容，首屏加载极快、SEO 友好。

* 通过 Supabase Serverless 提供动态评分评论能力，免注册匿名参与。

* 建立每周自动更新的数据流水线，保障基础数据持续有效。

* 实现全免费部署链路：GitHub → Vercel → Cloudflare CDN，零运维成本。

* 海外免备案部署，可直接上线访问。

* 提供剧集库、CV 详情、榜单、多维度可视化图表四大核心模块。

## Non-Goals (Out of Scope)

* 不支持用户注册、登录体系（仅匿名评分）。

* 不提供视频/音频在线播放功能（仅元数据展示与链接），但后续需要扩展该功能。

* 不做内容版权相关的审核与存储（仅元数据聚合）。

* 不做移动端 App（仅响应式 Web 页面）。

* 不做付费订阅 / 商业化功能（保持全免费）。

* 不做大规模实时并发优化（面向中小访问量场景）。

## Background & Context

* 现有百合广播剧数据分散在猫耳 FM、漫播、喜马拉雅、放角等多个平台，缺乏统一聚合门户。

* 采用「静态预渲染 + 动态数据层」混合架构的理由：

  * 纯静态站点可获得极致加载速度，易于 SEO 与 CDN 缓存；

  * Supabase 提供 PostgreSQL + 实时 API + RLS 权限控制，可免费支撑个人项目；

  * 爬虫 + GitHub Actions 定时触发构建，数据更新后自动重建静态页。

* 国内访问优化：Cloudflare CDN（免费套餐）提供基础加速能力。

## Functional Requirements

* **FR-1 首页总览**: 展示核心指标卡片（剧集总数、CV 总数、评分总数等）、平台分布图、Top10 榜单基础信息。

* **FR-2 排行榜专区**: 预渲染默认榜单，支持客户端维度切换（CV 参演榜 / 播放量榜 / 平台作品榜 / 评分榜）。

* **FR-3 全量剧集库**: 支持剧集列表浏览与关键词搜索，可按平台/类型/年份等维度筛选。

* **FR-4 剧集详情页**: 通过 Astro 动态路由预生成每个剧集的静态详情页，内嵌基础信息（剧名、平台、CV、播放量、制作信息）；底部动态加载评分与评论。

* **FR-5 CV 详情页**: 预渲染 CV 基本信息、参演作品列表、相关数据统计；点击跳转作品无刷新。

* **FR-6 匿名评分评论**: 游客无需登录，可选择 1–5 星评分并附短评；同一 IP+设备指纹对同一剧集仅可评分一次；剧集均分实时计算并更新。

* **FR-7 数据可视化**: 提供饼图（平台分布）、柱状图（年份分布）、折线图（评分趋势）、排行榜等多种图表（ECharts）。

* **FR-8 数据自动更新流水线**: 基于 Python 爬虫 + GitHub Actions 每周定时抓取，数据清洗后写入 Supabase，调用 Vercel Deploy Hook 触发重建。

* **FR-9 搜索与筛选**: 支持客户端模糊搜索剧集名/CV 名，支持多条件组合筛选。

* **FR-10 响应式布局**: 在 PC、Pad、Mobile 三端均有良好的布局与加载体验。

## Non-Functional Requirements

* **NFR-1 性能**: 首页首屏 LCP < 2.5s（国内访问），核心页面构建后 HTML ≤ 50KB（不含图片/JS）；交互岛屿按需加载 JS。

* **NFR-2 安全**: Supabase 开启 RLS，匿名用户仅能 SELECT/INSERT ratings/comments；爬虫密钥通过 GitHub Secrets 管理，不得硬编码；IP 哈希存储不可逆。

* **NFR-3 免费可部署**: 所有依赖服务（GitHub、Vercel、Supabase、Cloudflare）均有可满足项目需求的免费套餐；部署链路完全自动化，零运维成本。

* **NFR-4 可访问性**: 主要页面语义化 HTML；关键交互组件有键盘可达性；图表有文本摘要。

* **NFR-5 代码可维护性**: 使用 Astro 岛屿架构，样式方案统一（UnoCSS），图表组件（ECharts）封装独立；目录结构清晰可扩展。

* **NFR-6 数据时效性**: 基础元数据每周至少更新一次（爬虫 + GitHub Actions cron）；评分评论数据实时写入并回显。

## Constraints

* **Technical**: 前端 Astro + Vue 3 岛屿组件；可视化 ECharts；样式 UnoCSS；后端 Supabase PostgreSQL + RLS；爬虫 Python + GitHub Actions；部署 Vercel；CDN Cloudflare 免费套餐。

* **Business**: 全程免费使用，匿名用户无门槛；无用户体系；不可存储或播放原始音频/视频。

* **Dependencies**: 外部平台数据抓取受其站点结构变化影响；需在 Supabase/Vercel/Cloudflare 分别注册账号并完成配置；需在 GitHub 配置 Secrets 与定时任务。

## Assumptions

* Supabase 免费套餐在项目访问量下够用（500MB 数据库存储）。

* Vercel 免费套餐构建额度与带宽够用（个人项目，每周一次重建）。

* 用户浏览器支持现代 JS（ES2020）与 HTTPS。

* 抓取目标平台的公开元数据在技术与合规上可行（仅抓取公开可访问信息，遵守 robots 合理约束）。

* 匿名用户可稳定写入 Supabase，RLS 配置能避免恶意越权修改。

## Acceptance Criteria

### AC-1: 首页预渲染与关键指标展示

* **Given**: 项目已构建并部署上线

* **When**: 用户访问首页 `/`

* **Then**: 页面直接返回预渲染 HTML，关键指标卡片（剧集总数、CV 总数、评分总数、平台数量）与默认榜单 Top10 列表可见；ECharts 图表在岛屿 JS 加载完成后渲染

* **Verification**: `programmatic`

* **Notes**: 指标数据来源于构建时从 Supabase 读取（或本地数据快照），首屏不依赖接口返回即可展示核心信息。

### AC-2: 排行榜多维度切换（客户端）

* **Given**: 用户在排行榜页 `/rank`

* **When**: 点击 CV 参演榜 / 播放量榜 / 平台作品榜 / 评分榜 Tab

* **Then**: 榜单在客户端无刷新切换，表格/图表数据相应更新，无需请求后端接口

* **Verification**: `programmatic`

### AC-3: 剧集库浏览与搜索筛选

* **Given**: 用户在剧集库 `/dramas`

* **When**: 输入关键词搜索或切换筛选条件

* **Then**: 列表在客户端进行过滤，匹配剧集名/CV 名/平台，结果列表实时更新

* **Verification**: `programmatic`

### AC-4: 剧集详情静态页 + 动态评分评论区

* **Given**: 用户访问任一剧集详情页 `/dramas/[id]`

* **When**: 页面加载完成

* **Then**: 基础信息（剧名、平台、CV、播放量、制作信息、封面等）直接内嵌 HTML；底部评分组件与评论区在岛屿组件中从 Supabase 实时拉取最新均分与评论列表并渲染

* **Verification**: `programmatic`

### AC-5: CV 详情预渲染

* **Given**: 用户访问任一 CV 详情页 `/cvs/[id]`

* **When**: 页面加载完成

* **Then**: CV 基本信息、参演作品列表、数据统计卡片全部预渲染完成；点击作品可跳转到剧集详情页

* **Verification**: `programmatic`

### AC-6: 匿名评分提交

* **Given**: 用户在剧集详情页底部评分组件，未提交过评分

* **When**: 选择 1–5 星并填写（可选）短评后点击提交

* **Then**: 数据通过 Supabase anonymous key 写入 ratings 表；前端即时刷新均分与评论列表；该用户此后对同一剧集不可再次提交评分

* **Verification**: `programmatic`

### AC-7: IP+设备指纹防刷分

* **Given**: 用户尝试对同一剧集多次提交评分

* **When**: 第二次及以后点击提交

* **Then**: 前端提示「您已评分过该剧集」；服务端（Supabase RLS 或触发器）对 `(drama_id, ip_hash, device_fingerprint)` 做唯一约束，拒绝重复写入

* **Verification**: `programmatic`

### AC-8: 数据安全与 RLS 权限

* **Given**: 用户在浏览器端持有 anon key

* **When**: 尝试通过脚本直接修改/删除他人评分或剧集信息

* **Then**: Supabase 返回 403 权限错误；匿名用户仅具备：ratings SELECT/INSERT、comments SELECT/INSERT、dramas/cvs/joins SELECT，不具备 UPDATE/DELETE

* **Verification**: `programmatic`

### AC-9: 数据自动更新流水线

* **Given**: GitHub Actions 定时任务配置完成

* **When**: 每周定时时间到达

* **Then**: 爬虫脚本运行，完成数据抓取→清洗→写入 Supabase，并调用 Vercel Deploy Hook 触发站点重建；构建成功后静态页自动上线

* **Verification**: `programmatic`

### AC-10: 响应式与整体视觉质量

* **Given**: 站点在主流浏览器、不同视口下访问

* **When**: 浏览首页、剧集库、详情页、CV 页

* **Then**: 布局不发生错位、内容不溢出、关键图表在移动端可横向滑动查看、整体视觉风格统一美观

* **Verification**: `human-judgment`

* **Notes**: 由人工在 1920px / 1024px / 375px 三档视口各主要页面进行审阅。

### AC-11: 免费部署可复现

* **Given**: 按文档步骤在 GitHub 仓库配置好 Supabase/Vercel/Cloudflare 环境变量与 Secrets

* **When**: 提交代码后

* **Then**: Vercel 自动构建并部署成功；通过自定义域名 + Cloudflare CDN 可正常访问；匿名评论可正常写入数据库

* **Verification**: `programmatic`

## Open Questions

* [ ] 剧集数据的版权方与作者信息抓取范围是否需要进一步限定？是否仅抓取公开可访问的元数据？

* [ ] 匿名评分的设备指纹实现方案选型：`fingerprintjs`（免费版） vs 简单浏览器特征哈希？

* [ ] 默认排序/默认榜单维度，是否以「播放量」或「评分」为首要指标？（可在实现阶段定案，暂以播放量为默认）

* [ ] 是否需要深色模式与国际化多语言？（如非必需可延后）

* [ ] 数据可视化是否需要支持「Top N」动态切换数值（如 Top10/Top20/Top50）？

* [ ] Vercel 构建时从 Supabase 拉取数据的凭证（service\_role key）是否走 `SUPABASE_SERVICE_ROLE_KEY` 环境变量？需确认部署安全性。

