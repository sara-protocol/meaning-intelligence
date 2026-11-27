# Cloudflare Pages 部署参考

更新日期：2026-11-27

## 环境事实

- Pages 项目名：`msi`。
- 生产分支：`main`。
- 生产地址：`https://msi-axm.pages.dev`。
- 历史自定义别名：`goii.ccwu.cc`，仍为旧版媒体中心，不再作为正式入口。
- GitHub Pages 项目主页：`https://msi.gojj.ccwu.cc/`，与 Cloudflare Pages 不是同一部署系统。
- Cloudflare Pages 单文件上限：25 MiB。

账户 ID 从 `CLOUDFLARE_ACCOUNT_ID` 或 wrangler 登录状态获取，不写入 Skill、文档、提交或输出。

## 本机网络与工具

- Windows Python requests 访问 Cloudflare API 与 `*.pages.dev` 通常比 curl/Schannel 稳定。
- npm 官方源不可达时，使用 `https://registry.npmmirror.com`。
- wrangler 可通过现有 npm 缓存运行：`npx --no-install wrangler --version`。
- 不要因 curl 握手失败误判站点故障。

## 认证

可用 wrangler 已有 OAuth 登录，也可设置环境变量：

```bash
export CLOUDFLARE_API_TOKEN=<Pages:Edit token>
export CLOUDFLARE_ACCOUNT_ID=<account_id>
```

自定义 token 需要 `Account → Cloudflare Pages → Edit`。权限不足的典型错误是 `upload-token` Authentication error 10000；此时项目列表可能仍可读，具有迷惑性。token 一旦进入对话、日志或命令行历史，应立即提醒用户轮换。

## 部署目录

本地 `意义智能有声读物_发布包` 包含 1080p 母版、原始中文音频和 555 MiB 级完整交付包，不能直接部署。先执行：

```bash
python scripts/build_downloads.py
python scripts/verify_package.py
python scripts/build_deploy_zip.py
```

默认生成：

- `deliverables/meaning-intelligence-deploy-staging/`：实际部署目录。
- `deliverables/意义智能_部署包.zip`：根目录含 `index.html` 的归档。
- `deliverables/deployment-report.json`：部署成员、排除项、替换媒体、字节数和 SHA-256。

部署集排除完整交付 ZIP、超大母版、1080p guide 副本、缓存、Office 锁文件和 Baidu 同步临时文件；HTML 与下载 manifest 改用 `audio-web.mp3` 和两个 `*-web.mp4`。构建器逐文件执行 25 MiB 检查。

## wrangler 部署

在技能目录或工作区执行：

```bash
wrangler pages deploy "deliverables/meaning-intelligence-deploy-staging" --project-name=msi --branch=main --commit-dirty=true
```

Windows Git Bash 中若 `wrangler` 不在 PATH，可使用：

```bash
npx --no-install wrangler pages deploy "deliverables/meaning-intelligence-deploy-staging" --project-name=msi --branch=main --commit-dirty=true
```

成功标志是上传文件数与 Deployment URL。断点续传重试时，未变文件显示 already uploaded。网络闪断导致静默 exit 1 时可原样重试；不要通过跳过验证或强制覆盖来掩盖失败。

仪表盘拖 ZIP/文件夹曾出现部署成功但资产不完整，不作为推荐路径。

## 部署后机器验收

```bash
python scripts/verify_site.py --deep --mcp-rate-limit --strict https://<deployment-url>
python scripts/verify_site.py https://<preview>.pages.dev
node scripts/browser_verify.mjs --online https://msi-axm.pages.dev deliverables/online-browser-check.json
```

`verify_site.py` 从 staging manifest 读取预期资源，检查：

- `/`、`/listen.html`、`/downloads.html`、`/mcp.html`、`/project-guide/index.html`。
- 全部 manifest 资源的状态、Content-Type、字节数；可选全量 SHA-256。
- 中英音频、发布视频、二维码、字幕 JSON、SRT/VTT、EPUB、白皮书、PPT、源码 ZIP 和文档。
- Range 请求、首页与下载页关键内容、重复 ID、CORS、未授权拒绝。
- 存在 `MI_MCP_PUBLIC_TOKEN` 时，验证认证 initialize、tools/resources 与只读分析；token 不写入日志。
- `--strict` 要求 deep、生产 token 和限流探测同时启用；缺少任一条件即失败，非严格无 token 模式只报告静态检查通过。

`browser_verify.mjs` 使用真实 Chrome/Edge 检查中英切换、音频源、移动端布局、下载链接、项目说明书和运行时异常。脚本不读取或保存浏览器中的 token。

## 自定义域名

`goii.ccwu.cc` 对无浏览器特征的脚本请求可能返回 403 人机验证；这不是资源不存在的充分证据，但该域名仍为旧版，不作为最终交付入口。Cloudflare 资源验收使用 `https://msi-axm.pages.dev`，GitHub Pages 正式入口使用 `https://msi.gojj.ccwu.cc/` 并以真实浏览器验收。未获得明确授权时，不修改共享域名或安全配置。

## Web MCP 安全边界

- 端点：`POST /api/mcp`，协议 `2025-03-26`。
- 公共绑定必须设置至少 32 字符的 `MI_MCP_PUBLIC_TOKEN`；只存在部署环境密钥中。
- 可选 `MI_MCP_ALLOWED_ORIGINS` 使用逗号分隔的精确 Origin 白名单。
- 仅暴露白名单资源、资源读取和只读分析/复核工具；不提供任意 URL、文件、命令或凭据访问。
- 请求体上限 32 KiB；默认每个来源 IP 每分钟 60 次。
- 没有可用 token 时，只能报告未授权边界已验，不能报告认证只读调用已通过。

## 二维码

正式链接为 `https://msi.gojj.ccwu.cc`，出现在讲课版 PPT、MSI 讲解版 PPT 和发布中心；`https://goii.ccwu.cc` 仅为历史旧版。更换链接时重新生成 `assets/qr_site.png` 与 PPT 用二维码，重截相关页面，只重组装两份 PPTX 并沿用已切分音频，然后重建完整包、部署集并执行全部验收。现有入口为工作区 `rebuild_pptx_qr.py`。
