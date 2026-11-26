---
name: meaning-intelligence-publish
description: 《意义智能》双语有声读物、视频、项目说明书与只读 Web MCP 的构建、打包、部署和验收技能。覆盖完整交付包、Cloudflare Pages 25 MiB 资产限制、独立部署集、wrangler 发布、线上资源与哈希验证、真实浏览器验收、二维码及域名排查。当用户要求更新或部署站点、重建下载包、更换二维码、验证线上资源或排查发布故障时使用。
---

# Meaning Intelligence Publish — 发布中心构建与验收

## 概述

发布源目录是 `意义智能有声读物_发布包`，其中包含本地完整交付包与超大的 1080p 母版。Cloudflare Pages 单文件上限为 25 MiB，因此必须先用 `build_deploy_zip.py` 生成独立部署集；不得直接上传完整源目录或完整交付 ZIP。

域名分工：

- `https://msi.gojj.ccwu.cc/`：GitHub Pages 项目主页。
- `https://goii.ccwu.cc/`：双语视听中心与二维码正式入口。
- Pages 默认地址以当次 wrangler 输出为准；当前项目为 `msi-axm.pages.dev`，发布前必须确认未被 Cloudflare Access 拦截。
- Pages 项目名：`msi`；生产分支：`main`。

文件数、字节数和部署结果以当次脚本报告为准，不在 Skill 中硬编码。

## 标准工作流

1. 修改源素材、文稿、文档或生成脚本。
2. 运行 `build_downloads.py`，重建 EPUB、源码 ZIP、下载页、 manifest、完整交付包与当次浏览器证据。
3. 运行 `verify_package.py`，修复全部结构、媒体、哈希、Office、EPUB、ZIP 与 Web MCP 失败项。
4. 运行 `build_deploy_zip.py`，生成不含完整包和超大母版的部署目录、ZIP 与报告。
5. 在部署目录执行 `node scripts/browser_verify.mjs --deployment` 的等价目录参数，或运行 `verify_package.py <部署 ZIP>`，确认部署集通过。
6. 获得明确授权后，从部署目录用 wrangler 发布，确保 Pages Function 被识别。
7. 运行 `verify_site.py --deep` 与 `browser_verify.mjs --online`，验证生产资源、哈希、Range、MCP 和真实浏览器行为。
8. 记录部署 URL、时间、文件数、哈希和未覆盖项；只有实际证据齐全时才报告完成。

## 1. 完整交付包

在技能目录执行：

```bash
python scripts/build_downloads.py
python scripts/verify_package.py
python scripts/verify_package.py --json
```

完整包必须包含双语项目说明书、中英音频、字幕、三版 EPUB、白皮书、Word/PDF 文档、PPT、中英视频与网页版媒体、智能体源码与测试、Web MCP 源码与测试、SDK/MSI/白皮书生成器与仓库工具源码、发布与维护 Skill、生成脚本、验证报告和 SHA-256 清单。完整 ZIP 不包含自身；网站下载页与本地交付包使用可复核的对应哈希。

`verify_package.py` 检查核心文件、JSON、PPTX/DOCX/PDF 结构、EPUB 容器与 spine、SRT/VTT、媒体时长与流、HTML 本地引用、重复 ID、manifest 路径安全/字节数/SHA-256、源码与完整 ZIP 成员、网页媒体报告和 Web MCP JavaScript 语法。旧版仅检查核心包的命令通过不能替代扩展验收。

## 2. 独立部署集

```bash
python scripts/build_deploy_zip.py
# 或指定 ZIP 输出位置
python scripts/build_deploy_zip.py "D:/publish/意义智能视听中心_部署包.zip"
```

默认输出：

- `deliverables/meaning-intelligence-deploy-staging/`：wrangler 实际部署目录。
- `deliverables/意义智能_部署包.zip`：根目录含 `index.html` 的部署 ZIP。
- `deliverables/deployment-report.json`：成员、排除项、替换项、哈希与大小报告。

构建器只读取发布源目录，在部署集中排除完整交付 ZIP、原始超大中文音频、1080p 发布母版、项目说明书中的 1080p 副本、缓存和同步临时文件；网页 HTML 与 manifest 同步改用合规派生媒体。每个部署文件必须小于 25 MiB。ZIP 用于归档或仪表盘排查，推荐部署路径仍是 wrangler 部署 staging 目录。

## 3. Cloudflare Pages 部署

优先使用 wrangler；不要用仪表盘拖 ZIP 或文件夹。历史上仪表盘曾显示 success 但只上传部分资产。

```bash
export CLOUDFLARE_API_TOKEN=<Pages:Edit token>
export CLOUDFLARE_ACCOUNT_ID=<account_id>
cd deliverables/meaning-intelligence-deploy-staging
wrangler pages deploy . --project-name=msi --branch=main --commit-dirty=true
```

- 必须从 staging 目录部署，让 wrangler 发现 `functions/`；只上传静态目录而跳过 Function 不算完成。
- `functions/api/mcp.js` 必须导出 Pages Function `onRequest`，不能只有 Worker 默认导出。
- 部署日志出现 `No routes found ... functions` 时，修复后重新部署并验证 `/api/mcp`。

- token 需要 `Account → Cloudflare Pages → Edit`。
- npm 官方源不可达时可用 `https://registry.npmmirror.com`。
- 本机 curl 的 Schannel 握手可能失败；Cloudflare API 与线上验证优先用 Python requests。
- 未获得用户明确授权时，只构建和验证，不部署，不修改共享域名配置。
- `MI_MCP_PUBLIC_TOKEN` 只从部署环境密钥读取，不写入前端、日志、文档、提交或输出。

## 4. 线上机器验收

```bash
python scripts/verify_site.py --deep https://<deployment-url>
node scripts/browser_verify.mjs --online https://<deployment-url> deliverables/online-browser-check.json
```

`verify_site.py` 以部署 manifest 为资源事实源，检查页面、全部下载资源、Content-Type、字节数、可选全量哈希、Range、关键内容、CORS、未授权拒绝、认证 initialize、tools/resources 和只读分析。在线 token 只从 `MI_MCP_PUBLIC_TOKEN` 环境变量读取且不输出；没有 token 时不得把认证调用写成已通过。

`browser_verify.mjs` 使用本机 Chrome/Edge CDP 检查中英切换、音频源、播放、移动端布局、下载链接、Range、manifest、MCP 空 token 安全、项目说明书和运行时异常。`--deployment <staging>` 使用本地服务器和部署集边界，`--online <url>` 使用同一部署集边界检查远端；两者都要求排除完整交付 ZIP。脚本请求遇到 403 人机验证时，应区分防护拦截与资源错误，不能据此宣称线上通过。

## 5. 二维码与域名维护

正式二维码链接为 `https://goii.ccwu.cc`，用于讲课版 PPT、MSI 讲解版 PPT 和发布中心。更换链接时：重新生成二维码 → 更新发布包 → 重截相关 PPT 页面 → 只重组装 PPTX 并沿用已切分音频 → 重建完整包与部署集 → 部署 → 验证。工作区 `rebuild_pptx_qr.py` 是现有重建入口。

## 快速排障

| 症状 | 根因 | 处置 |
|---|---|---|
| 首页 200 但空白 | ZIP 带外层目录或根目录无 `index.html` | 用本技能脚本重打部署 ZIP |
| 部署 success 但资源 404 | 仪表盘直传截断 | 改用 wrangler，重跑结构及线上验证 |
| `No routes found ... functions` | Function 未导出 `onRequest` 或 wrangler 工作目录错误 | 从 staging 部署；检查 `/api/mcp` 真实响应 |
| 页面 302 到 Cloudflare Access | 账户或项目启用了访问策略 | 由账户管理员明确授权后配置公网发布；不得擅自放宽其他站点权限 |
| 资产超过 25 MiB | 上传了本地母版或完整包 | 使用独立部署集与网页版派生媒体 |
| `upload-token` Authentication error 10000 | token 缺少 Pages:Edit | 重建设置正确权限的 token |
| 自定义域名脚本请求 403 | Cloudflare 人机验证 | 用 pages.dev 验证资源，用浏览器验证域名 |
| wrangler 静默 exit 1 | 网络闪断 | 原样重试，利用已上传文件续传 |
| 章节或字幕错位 | 音频变化但时间轴/字幕未更新 | 重新生成时间轴、字幕与 `listen.html` |

## 安全

API token 一旦进入对话、日志或命令行历史，应提醒用户在 Cloudflare 控制台轮换或删除。不要在 Skill、文档、提交或输出中记录 token、账户邮箱或完整账户标识。Web MCP 只暴露白名单资源与只读工具，不提供任意文件、URL、命令或凭据访问。
