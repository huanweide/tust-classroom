<!-- badges -->
[![License](https://img.shields.io/github/license/huanweide/tust-classroom)](LICENSE)
[![CI](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml)
[![Private](https://img.shields.io/badge/仓库-私有-purple)](https://github.com/huanweide/tust-classroom)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
<!-- /badges -->

# TUST 空闲教室查询系统

> 天津科技大学（TUST）教务系统空闲教室采集与查询工具 —— 复用本地浏览器登录态，自动爬取、本地存储、静态发布，随时查哪间教室有空。

私有仓库，仅作者维护。本文档侧重功能概览与本地运行说明，不对外提供账号相关支持。

## 隐私说明（必读）

本项目**不收集、不存储、不传输任何账号密码**，请放心在本地使用：

- 教务系统账号（学号）与密码**仅通过环境变量读取**，代码中无任何硬编码凭证（`config.py` 中的 `TUST_SID` / `TUST_PWD`）。
- 爬虫通过 **Chrome DevTools Protocol（CDP）复用本机已登录的 Edge 浏览器会话**抓取数据，不会要求你输入或保存密码文件。
- 所有教室数据仅写入**本地 SQLite 数据库**（`data/classrooms.db`），对外发布的静态文件不含任何账号信息。
- 如需对外署，请自行通过 GitHub Pages、内网或隧道发布，**切勿把含有会话信息的本地文件提交到仓库**。

## 功能特性

| 能力 | 说明 |
|------|------|
| 多模式查询 | 按节次查空闲 / 时间范围内连续空闲 / 查指定教室的全天空闲节次 |
| 双校区覆盖 | 泰达校区 + 河西校区，自动发现并采集各校区教学楼 |
| 智能搜索 | 教室名模糊匹配，支持 `9-12` 这类「楼号-房号」拆解匹配与相似项推荐 |
| 日期导航 | 支持按天偏移与日期区间批量爬取（例：未来 7 天 / 整学期） |
| 13 节次时间表 | 内置完整节次与对应时间，前端直接展示空闲时间段 |
| 本地 API | 提供 Flask 接口，便于二次开发与调试 |
| 静态发布 | 一键导出为静态 JSON，配合 GitHub Pages / PWA 部署，零后端秒开 |
| 会话保活 | 定时 ping 教务系统，避免 URP 会话空闲超时 |
| 微信小程序 | 附 `wechat-mini/` 小程序版，移动端即用 |

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

也可直接使用 `auto_update.bat` 一键完成「爬取 → 导出 → 提交推送 → 发布 → 清理过期数据」。

URP 会话保活（配合 Windows 任务计划每 25 分钟触发）：

```bash
python keepalive.py --once
```

## 配置说明

主要配置位于 `config.py`：

| 配置项 | 含义 | 默认值 |
|--------|------|--------|
| `BASE_URL` | 教务系统地址 | `http://jwxtxs.tust.edu.cn:46110` |
| `TUST_SID` / `TUST_PWD` | 账号 / 密码（环境变量） | 空（走 CDP 复用） |
| `CAMPUS_CODE` / `CAMPUS_NAME` | 默认校区代码与名称 | `02` / `泰达` |
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
├── crawler_playwright.py   # CDP 爬虫（核心，复用 Edge 登录态）
├── export_static.py        # SQLite → 静态 JSON 导出
├── keepalive.py            # URP 会话保活
├── app.py                  # Flask 本地查询 API
├── config.py               # 配置文件（含环境变量读取）
├── auto_update.bat         # 一键更新与发布脚本
├── cloudflared.exe         # 隧道工具（本地署可选）
├── static/                 # PWA 前端与静态数据
│   ├── index.html          # 前端页面
│   ├── manifest.json       # PWA 清单
│   ├── sw.js               # Service Worker（离线可用）
│   └── data/               # 导出的静态 JSON
├── wechat-mini/            # 微信小程序版
└── data/                   # 本地数据库与日志（*.db 已被 .gitignore 忽略）
```

## 免责声明

本项目为非官方查询工具，数据来源于天津科技大学 URP 教务系统。课程安排可能随时调整，请以教务处最新通知为准。请勿用于任何违规用途。

## 许可证

[MIT](LICENSE)
