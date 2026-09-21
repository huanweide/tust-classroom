<!-- badges -->
[![License](https://img.shields.io/github/license/huanweide/tust-classroom)](LICENSE)
[![Pages](https://img.shields.io/badge/在线访问-GitHub%20Pages-blue?logo=github)](https://huanweide.github.io/tust-classroom/)
[![CI](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml)
[![Public](https://img.shields.io/badge/仓库-公开-brightgreen)](https://github.com/huanweide/tust-classroom)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
<!-- /badges -->

# TUST 空闲教室查询系统

> 天津科技大学（TUST）教务系统空闲教室采集与查询工具 —— 复用本地浏览器登录态，自动爬取泰达 + 河西双校区教室，本地存储、静态发布，**手机浏览器随开随查**：[https://huanweide.github.io/tust-classroom/](https://huanweide.github.io/tust-classroom/)

公开仓库，欢迎 Star 反馈。

## 在线访问（手机可用）

**📱 直接打开：[https://huanweide.github.io/tust-classroom/](https://huanweide.github.io/tust-classroom/)**

部署在 GitHub Pages，零后端、纯静态、PWA 可装到桌面/主屏如原生 App。手机浏览器访问即可用，不需要 VPN / 校园网。

## 隐私说明（必读）

本项目**不收集、不存储、不传输任何账号密码**，请放心在本地使用：

- 教务系统账号（学号）与密码**仅通过环境变量读取**，代码中无任何硬编码凭证（`config.py` 中的 `TUST_SID` / `TUST_PWD`）。
- 爬虫通过 **Chrome DevTools Protocol（CDP）复用本机已登录的 Edge 浏览器会话**抓取数据，不会要求你输入或保存密码文件。
- 所有教室数据仅写入**本地 SQLite 数据库**（`data/classrooms.db`），对外发布的静态文件不含任何账号信息。
- 如需对外署，请自行通过 GitHub Pages、内网或隧道发布，**切勿把含有会话信息的本地文件提交到仓库**。

### 凭据安全（重要）

- **禁止提交任何凭据文件。** 本仓库已通过 `.gitignore` 忽略 `data/cookies.txt`。若历史上曾在本地生成过该文件，请立即从工作树删除（`data/cookies.txt`），切勿提交或推送到远端。
- `data/cookies.txt` 等文件中如含有 URP CAS 会话令牌（如 `CASTGC` 的 TGT、`JSESSIONID` 等），属于**明文凭据**，一旦泄露等同于账号失窃。
- **登录态丢失请重新登录**，或在浏览器中重新扫码/访问教务系统获取新的 Cookie，**不要从旧文件复制遗留令牌**。
- **强烈建议轮换 URP 账号密码**：如果曾经把含会话令牌的文件提交或外泄，请尽快修改教务系统登录密码，使旧会话令牌失效。修改密码后旧 Cookie 会自动失效，需重新登录获取新会话。
- 任何通过 CDP 复用登录态的脚本都不会把密码落盘；如确需在本地保存账号密码，请仅通过环境变量 `TUST_SID` / `TUST_PWD` 提供，且这些变量不得写入任何会被纳入版本控制的文件。

## 功能特性

| 能力 | 说明 |
|------|------|
| 多模式查询 | 按节次查空闲 / 时间范围内连续空闲 / 查指定教室的全天空闲节次 |
| 双校区覆盖 | 泰达校区 + 河西校区，自动发现并采集各校区教学楼；**前端默认展示泰达校区** |
| 智能搜索 | 教室名模糊匹配，支持 `9-3` 这类「楼号-房号」简写拆解（`9-3` → 9-楼 3阶梯）、`3阶梯` 模糊匹配；教室当天全满时显示"今天无空闲时段"而非找不到 |
| 日期导航 | 支持按天偏移与日期区间批量爬取（例：未来 7 天 / 整学期） |
| 13 节次时间表 | 内置完整节次与对应时间，前端直接展示空闲时间段 |
| 本地 API | 提供 Flask 接口，便于二次开发与调试 |
| 静态发布 | 一键导出为静态 JSON，GitHub Actions 自动部署 Pages，零后端秒开 |
| 自动刷新 | Windows 任务计划程序每小时抓一次+开机补跑，无需登录（`install_scheduler.bat` 一键安装） |
| 会话保活 | 定时 ping 教务系统，避免 URP 会话空闲超时 |
| 微信小程序 | 附 `wechat-mini/` 小程序版，移动端即用 |

## 质量保障

本项目前端已通过 **Playwright 真实浏览器端到端自动化测试**，覆盖全部交互：默认校区泰达、三种查询模式（按节次 / 时间范围 / 查教室时段）、校区与教学楼切换、日期前后导航、教室名简写解析（`9-3` → `9-`楼 `3阶梯(d)`、`3阶梯` 模糊匹配）、搜索自动补全等，**11/11 全部通过**。普通用户打开链接即用，无需安装；开发者可运行仓库内 `e2e_test.cjs`（`puppeteer-core` + 本地 `static/` 服务）复现。

## 快速开始

环境要求：

- Windows + 已安装的 **Microsoft Edge**（含已登录的教务系统 Session）
- Python 3.x 与依赖：`pip install -r requirements.txt`
- 已安装 Playwright 浏览器内核：`playwright install chromium`

以调试模式启动 Edge（复用登录态）：

```bat
:: 以远程调试端口启动 Edge（使用你自己的用户 Profile）
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%LOCALAPPDATA%\Microsoft\Edge\User Data"
```

可选：配置环境变量（仅在爬虫需要账号信息时使用，一般复用 Session 即可）：

```bash
set TUST_SID=你的学号
set TUST_PWD=你的密码
```

启动本地查询 API（默认 `http://127.0.0.1:5000`）：

```bash
python app.py
```

打开 `static/index.html` 或访问本地 API 即可查询。

## 数据采集与发布

```bash
# 1) 爬取未来 7 天数据（需 Edge 调试端口已就绪）
python crawler_playwright.py --range 0-6

# 2) 爬取单天（明天）
python crawler_playwright.py --dayoffset 1

# 3) 导出静态 JSON 到 static/data/
python export_static.py

# 4) 推送静态站点（README 示例，实际按你的 Pages 配置执行）
git subtree push --prefix=static origin gh-pages
```

也可直接使用 `auto_update.bat` 一键完成「爬取 → 导出 → 提交推送 → 清理过期数据」（Pages 部署由 GitHub Actions 自动接管）。

## 一键自动化部署（推荐）

如果你想「**电脑开着就自动跑，无需登录系统**」，双击 `install_scheduler.bat`（右键管理员身份运行）。它会：

- 注册 Windows 任务计划程序，每 **60 分钟**自动运行一次 `auto_update.bat`
- 开机时自动补跑一次
- 不弹黑窗 / 不阻塞 / 不抢桌面
- 任何时段想停止：双击 `uninstall_scheduler.bat`

完整数据流：

```
[任务计划 60min 触发]
     ↓
[本机 Edge + Playwright CDP 复用登录态]
     ↓
[crawler_playwright.py 抓取泰达+河西双校区未来 7 天]
     ↓
[SQLite 写入 data/classrooms.db]
     ↓
[export_static.py 压缩导出 static/data/*.json]
     ↓
[git commit + push main 分支]
     ↓
[GitHub Actions 自动同步 static/ → GitHub Pages]
     ↓
[📱 手机浏览器立即可见]
```

URP 会话保活（配合 Windows 任务计划每 25 分钟触发）：

```bash
python keepalive.py --once
```

> **内网穿透（cloudflared）**：`cloudflared.exe` 属体积较大的二进制依赖，**不入库**（已被 `.gitignore` 忽略，不会提交或推送）。如需对外临时暴露本机服务，请从 [Cloudflare 官方下载页](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 获取对应平台的 `cloudflared`，本地运行 `cloudflared tunnel --url http://127.0.0.1:5000` 即可，**切勿把该 exe 提交到仓库**。

## 配置说明

主要配置位于 `config.py`：

| 配置项 | 含义 | 默认值 |
|--------|------|--------|
| `BASE_URL` | 教务系统地址 | `http://jwxtxs.tust.edu.cn:46110` |
| `TUST_SID` / `TUST_PWD` | 账号 / 密码（环境变量） | 空（走 CDP 复用） |
| `CAMPUS_CODE` / `CAMPUS_NAME` | 默认校区（`None`=自动发现双校区，前端默认泰达） | `None` / `None` |
| `PERIODS` | 13 个节次及对应时间 | 见 `config.py` |
| `DB_PATH` | 本地 SQLite 路径 | `data/classrooms.db` |
| `DEBUG_PORT` | Edge CDP 调试端口 | `9222` |

## 工作原理

```
┌────────────┐   CDP 复用    ┌──────────────┐   爬取     ┌────────────────┐
│ 本机 Edge  │ ───────────▶ │ crawler_     │ ────────▶ │ 教务系统 URP   │
│ (已登录)   │  登录态       │ playwright   │  空闲教室   │ 空闲教室接口    │
└────────────┘              └──────────────┘            └────────────────┘
                                    │ 写入
                                    ▼
                            ┌──────────────┐  导出   ┌────────────────┐
                            │ SQLite 数据库 │ ──────▶ │ static/data/*. │
                            │ classrooms.db │        │ json (静态)    │
                            └──────────────┘        └────────────────┘
                                                          │ 发布
                                                          ▼
                                                  GitHub Pages / PWA
                                                  （零后端、可离线）
```

- **采集**：`crawler_playwright.py` 通过 CDP 连接本机 Edge，复用已登录 Session，按校区 → 教学楼 → 节次抓取空闲教室，写入 SQLite。
- **发布**：`export_static.py` 把数据库导出为按日期分片的压缩 JSON 与搜索索引，配合 `static/` 下的 PWA 前端（`index.html` / `manifest.json` / `sw.js`）静态托管。
- **保活**：`keepalive.py` 定期通过 CDP 发轻量请求，重置 URP 会话空闲倒计时。

## 目录结构

```
tust-classroom/
├── crawler_playwright.py   # CDP 爬虫（核心,复用 Edge 登录态,自动发现双校区）
├── export_static.py        # SQLite → 静态 JSON 导出
├── keepalive.py            # URP 会话保活（每 25 分钟重置空闲倒计时）
├── app.py                  # Flask 本地查询 API（127.0.0.1:5000）
├── config.py               # 配置文件（含环境变量读取、双校区配置）
├── auto_update.bat         # 一键更新脚本(爬取→导出→提交→清理)
├── install_scheduler.bat   # 一键注册 Windows 任务计划程序(每小时自动跑)
├── uninstall_scheduler.bat # 一键卸载任务计划
├── keepalive_task.bat      # 保活任务(由 schtasks 触发)
├── .github/workflows/
│   ├── ci.yml              # 语法/lint 检查
│   └── pages-deploy.yml    # main 分支 push 自动部署 Pages
├── static/                 # PWA 前端与静态数据
│   ├── index.html          # 前端页面
│   ├── manifest.json       # PWA 清单
│   ├── sw.js               # Service Worker（离线可用）
│   └── data/               # 导出的静态 JSON（自动生成）
├── wechat-mini/            # 微信小程序版
└── data/                   # 本地数据库与日志（*.db 已被 .gitignore 忽略）
```

## 免责声明

本项目为非官方查询工具，数据来源于天津科技大学 URP 教务系统。课程安排可能随时调整，请以教务处最新通知为准。请勿用于任何违规用途。

## 许可证

[MIT](LICENSE)

---

## 关于作者

| # | 项目 | 内容 |
|---|------|------|
| 1 | **作者** | **ReTri · 樊斯瑞** — [@huanweide](https://github.com/huanweide) |
| 2 | **开源** | [huanweide/tust-classroom](https://github.com/huanweide/tust-classroom) · MIT License · 欢迎 Star / Fork |
| 3 | **数据** | 来自天津科技大学 URP 教务系统，本工具**非官方**；课程与教室安排可能临时调整，请以教务处通知为准 |

## 数据新鲜度说明

页面顶部会显示数据覆盖范围与状态条：

- **绿色** — 数据已覆盖今天，可正常查询
- **黄色** — 数据未覆盖今天（尚未开始或已超出覆盖终点），结果仅供参考

> **字段语义提醒**：`index.json` 里的 `updated` 是**数据覆盖的最后一天**（例如 `2027-01-20`），
> **不是抓取时间**。抓取时间由 `generated_at` 单独记录。前端同时读取两者：
> `updated` 判「今天有没有数据」，`generated_at` 判「数据多久没更新」。

## 项目形态说明

本项目主推形态是**已上线的 PWA 网页版**（GitHub Pages 托管，手机浏览器打开即用，可添加到主屏）。

仓库内的 `wechat-mini/` 为微信小程序的探索版本，当前**不具备上架条件**，原因是：

1. 小程序 `wx.request` 只能请求 HTTPS + ICP 备案 + 后台白名单域名，而 `*.github.io` 无法备案；
2. 教务查询类功能在微信服务类目中缺少可申请条目，个人主体无法覆盖；
3. 名称涉及学校名称、数据来源未获授权。

如需小程序形态，可行路径是改用**微信云开发**承载数据层（免域名白名单），并在小程序后台单独解决类目与名称问题。

---

## CI 门禁用法

开箱即可接入 CI：在流水线中运行本工具，它会输出健康分与严重度；若存在不达标项会以非 0 退出码结束，从而拦下问题提交（具体参数见上方「快速开始」）。

## 赞助支持

如果这个项目帮到了你，欢迎 [点 Star](https://github.com/huanweide/tust-classroom) 支持；也可微信扫码自愿赞助（收款码见 `sponsor/wechat-qr.png`，作者本人带 Tri 水印的码，纯静态图片、不含任何密钥）。

## 许可证

详见 [LICENSE](LICENSE)。
