<p align="center">
  <img src="assets/banner.svg" alt="CampusFreeRoom">
</p>

<!-- badges -->
[![License](https://img.shields.io/github/license/huanweide/tust-classroom)](LICENSE)
[![CI](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/单元测试-102%20passed-brightgreen)](#-质量保障)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![零后端](https://img.shields.io/badge/部署-纯静态%20Pages-blue?logo=github)](https://huanweide.github.io/tust-classroom/)
[![在线访问](https://img.shields.io/badge/手机直接打开-某高校-success)](https://huanweide.github.io/tust-classroom/)
<!-- /badges -->

# 🏫 CampusFreeRoom · 高校空闲教室查询接入框架

> **教务系统里明明有「哪些教室现在是空的」，但它被困在需要登录、只在校园网里、手机上看不了的网页深处** —— 本框架把这份数据搬出来，变成手机浏览器随开随查、可离线、零后端的静态站。
>
> A framework that turns "which classrooms are free right now" out of login-walled campus portals into an offline, zero-backend static PWA.
>
> **自动流**：复用已登录浏览器 → 按 校区 → 教学楼 → 节次 翻数据 → SQLite 去重入库 → 按天分片导出 JSON → 发布到 Pages
> `采集 → 去重 → 导出 → 发布`

**已上线示例（某高校双校区）**：<https://huanweide.github.io/tust-classroom/>

[30 秒看懂](#-30-秒看懂) · [解决什么](#-这个项目解决什么) · [特性](#-特性--features) · [快速开始](#-快速开始--quick-start) · [命令行](#-命令行速查) · [架构](#-架构--architecture) · [接入你的学校](#-接入你自己的学校) · [路线图](#-路线图--roadmap) · [质量保障](#-质量保障) · [贡献](#-贡献) · [License](#-license)

---

## 🏫 30 秒看懂

**现状（全国大多数学校的同学）**：

```
$ 我（想找间空教室自习）
  → 走到教学楼，一间间趴门缝看                  # 跑断腿，还看不全
  → 或者回宿舍开电脑，登录教务系统               # 要校园网 / VPN
  → 点「教学资源 → 空闲教室」，选校区、选楼、选节次  # 4~5 次点击才出结果
  → 想在教学楼现场用手机查？                     # 页面没做移动端，基本没法看
```

**用本框架导出的站**：

```
$ 手机浏览器打开 huanweide.github.io/tust-classroom/
  → 选校区：校区 A / 校区 B
  → 选节次：第 1-13 节
  → 立刻看到哪些教室空着，可「添加到主屏」当 App
  → 不需要校园网、不需要 VPN、不需要登录，断网也能看（Service Worker 缓存）
```

一句话差别：**它不是「某校的空教室查询页面」，而是一条能把任意学校的教务数据变成离线站的流水线** —— 换一所学校的成本是**加一个适配器文件（约 150 行）**。

---

## 🏫 这个项目解决什么

| 角色 | 痛点 | 本项目怎么做 |
|------|------|------------|
| 大学生 | 想找间空教室自习，只能跑到教学楼一间间看，或者登录教务系统在电脑前点半天 | 手机打开网页，选节次 → 立刻看到哪些教室空着 |
| 学生开发者 | 全国每个学校都有人写了「本校空教室查询」，但全是**一次性脚本**，换个学校就得从头造轮子 | 提供通用流水线，**接一所新学校 = 写一个适配器（4 个方法，约 30 分钟）** |

### 和同类项目有什么不同

搜索 GitHub 上的「空闲教室查询」，结果几乎全是**单校单实现**：

| | 单校脚本（绝大多数同类） | 本框架 |
|---|---|---|
| 服务范围 | 1 所学校 | 任意学校（加个文件即可） |
| 换学校成本 | 从零重写 | 写一个适配器（约 150 行） |
| 数据 pipeline | 各写各的，质量参差 | 统一的爬 → 存 → 导出 → 发布 |
| 前端 | 多半没有，或很简陋 | 现成 PWA：可安装、可离线、手机优化 |
| 测试 | 基本没有 | 102 项单元测试 + 真实浏览器端到端 |
| 契约校验 | 无 | `check` 命令提前查出适配器写漏了啥 |

第一所支持的学校是**某高校**，双校区、13 节次、已上线运行。

---

## 🏫 特性 / Features

- **🔌 适配器协议 (Adapter Contract)** —— 一所学校 = 一个适配器，只需实现 `profile` + 4 个方法（`list_campuses` / `list_buildings` / `select_building` / `list_free_rooms`）；翻日期、翻楼、翻节次、去重入库、导出静态站全部由框架接管。`campusfree/adapter.py`
- **🔑 登录态复用层 (CDP Reuse)** —— 通过 Chrome DevTools Protocol 连到你**已经登录好**的浏览器窗口，**全程不碰密码、不保存 Cookie 文件**；教务系统有验证码、CAS 跳转、设备绑定也不怕。`campusfree/cdp.py`
- **🛡️ 导出安全闸门 (Export Gate)** —— 本地数据天数少于线上时 `export` 会被拦下，防止「爬挂了却把线上 130 天数据覆盖成 3 天」；这是最危险的静默数据丢失。`campusfree/exporter.py`
- **🧪 契约体检 (Contract Check)** —— `check` 命令**不连网、不开浏览器**，纯静态检查适配器写没写合格，把「爬了半天才发现漏实现」提前到 3 秒。`campusfree/adapter.py` · `validate_adapter()`
- **📦 按天分片导出 (Daily Sharding)** —— 一天一个 JSON 文件，前端只取当天，首屏几十 KB，而不是一个几 MB 的全量文件。`campusfree/exporter.py`
- **🔁 断点续传调度 (Resumable Runner)** —— 爬取调度带断点续传与失败隔离，某天爬挂了不影响其他天。`campusfree/runner.py`
- **🧭 脚手架生成器 (Scaffold)** —— `new-school` 一键生成带 TODO 的适配器骨架，照着填即可。`campusfree/scaffold.py`
- **🔒 只读体检模式 (Read-Only Dry Run)** —— `refresh_crawl.py --dry-run` 用 `mode=ro` 打开数据库，**物理上写不进去**，可以先体检再决定要不要动数据。`refresh_crawl.py`

---

## 🏫 快速开始 / Quick Start

### 路线 A：我只是想查空教室（该校同学）

直接用这个网址，不用装任何东西：

**📱 <https://huanweide.github.io/tust-classroom/>**

- 手机浏览器打开即用，可「添加到主屏」当 App
- 不需要校园网、不需要 VPN、不需要登录
- 数据每小时自动更新

### 路线 B：我想让我自己的学校也能用（开发者）

> 说明：下列命令中的 `your-school` 为**示例适配器 ID**，请以 `python -m campusfree schools` 实际输出的 ID 为准（文档已脱敏，不绑定具体学校）。

```bash
# 1. 装依赖
pip install -r requirements-dev.txt
playwright install chromium

# 2. 看看现在支持哪些学校
python -m campusfree schools

# 3. 体检某个适配器（不连网，纯静态检查）
python -m campusfree check --school your-school

# 4. 生成你自己学校的适配器骨架
python -m campusfree new-school your-school --name "你的学校"
#    → 生成 adapters/nku.py，照着里面的 TODO 填

# 5. 填完后自检
python -m campusfree check --school nku

# 6. 开爬（会自动拉起浏览器，在里面登录一次教务系统）
python -m campusfree run --school nku --range 0-6

# 7. 导出静态站
python -m campusfree export --school nku
```

完整图文教程：**[docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md)**

**`schools` 示例输出（已脱敏）**：

```
$ python -m campusfree schools
已注册 1 所学校：

ID          学校                  节次    默认校区      教务系统
------------------------------------------------------------------------------------------
your-school        某高校              13    校区 A        http://jwxt.example.edu.cn:46110
```

**`check` 示例输出（已脱敏）**：

```
$ python -m campusfree check --school your-school
体检对象：某高校
  教务系统：http://jwxt.example.edu.cn:46110/student/teachingResources/freeClassroom/index
  节次数量：13
  默认校区：校区 A
  浏览器  ：Microsoft Edge | exe=...\msedge.exe | profile=...\tust-classroom\edge-cdp-profile | port=9222

[合格] 适配器契约检查全部通过，可以开爬。
```

---

## 🏫 命令行速查

| 命令 | 作用 | 需要浏览器吗 |
|------|------|------------|
| `python -m campusfree schools` | 列出所有已注册的学校 | 否 |
| `python -m campusfree check --school your-school` | 体检适配器是否写合格 | 否 |
| `python -m campusfree run --school your-school --range 0-6` | 爬取未来 7 天 | 是 |
| `python -m campusfree run --school your-school --auto` | 自动探测学期边界，一路爬到放假 | 是 |
| `python -m campusfree export --school your-school` | 导出静态 JSON | 否 |
| `python -m campusfree new-school <id>` | 生成新学校适配器骨架 | 否 |

单个学校爬一天：`run --school your-school --dayoffset 1`（1 = 明天）

### 固定刷新爬取（覆盖旧数据）

`INSERT OR IGNORE` 有个隐患：命中 UNIQUE 约束就跳过，**重复爬同一天不会更新数据**，教务改过课表你也看不出来。用 `refresh_crawl.py` 做定期刷新，它先 DELETE 再重插：

```bash
python refresh_crawl.py --dry-run    # 只读体检：不写库、不请求教务系统
python refresh_crawl.py              # 刷新今天起 7 天，覆盖旧值
python refresh_crawl.py --repast 7   # 顺带重爬过去 7 天（修正历史数据）
```

三条保护：① `--dry-run` 用 `mode=ro` 打开数据库，物理上写不进去 ② 默认不清理历史数据（`--prune-days N` 才清理）——线上 130 天是资产 ③ 爬完自校验，某天行数低于阈值立即报警。登录态失效时教务接口会返回空列表，**爬虫不报错但 DB 被清空却插不进新值**，这是最危险的静默数据丢失。

### 只重建元数据（本地数据不全时）

本地 DB 天数少于线上时，`export` 会被安全闸门拦下（这是对的）。但改了归一化逻辑时，只想更新 `index.json` 的 `buildingMeta` 和 `search.json` 的归一化字段，不想动 130 个每日文件：

```bash
python meta_only.py --dry-run   # 预览
python meta_only.py             # 写盘（每日 JSON 一概不碰）
```

---

## 🏫 架构 / Architecture

默认引擎是**「适配器只回答 5 个问题，框架负责剩下全部」的分层流水线**，不是一把梭的爬虫脚本：适配器不许引入 playwright，框架把已登录的页面对象（duck typing，只要有 `.evaluate` / `.url` / `.goto`）传进去，因此适配器可以脱离浏览器做单元测试。

### 核心概念

| 概念 | 含义 |
|------|------|
| 适配器 (adapter) | 一所学校的实现，回答「网址 / 校区 / 楼 / 怎么选楼 / 哪些教室空」5 个问题 |
| 登录态复用 (CDP reuse) | 连到本机已登录的浏览器窗口，不碰密码、不落 Cookie 文件 |
| 契约校验 (contract check) | 不开浏览器的静态体检，提前发现适配器漏实现 |
| 按天分片 (daily shard) | 一天一个 JSON，前端只取当天，首屏几十 KB |
| 导出闸门 (export gate) | 本地数据天数不足时拒绝导出，防止覆盖线上资产 |
| 只读模式 (`mode=ro`) | 以只读方式打开数据库，物理上写不进去 |

### 数据流水线

```
┌──────────────┐   CDP 复用   ┌───────────────┐   请求   ┌──────────────┐
│ 本机浏览器    │ ──────────▶ │ campusfree    │ ───────▶ │ 教务系统      │
│ (已登录一次)  │   登录态     │ 调度层 runner │  空闲教室  │ (各校不同)    │
└──────────────┘              └───────┬───────┘          └──────────────┘
                                      │ 问路
                              ┌───────▼───────┐
                              │ SchoolAdapter │ ← 每校一个，只写 4 个方法
                              └───────┬───────┘
                                      ↓ 标准化
┌──────────────┐   导出    ┌───────────────┐   存储   ┌──────────────┐
│ GitHub Pages │ ◀──────── │ static/data/  │ ◀─────── │ SQLite 去重  │
│ PWA 可离线    │  静态 JSON │ *.json 按天分片│          └──────────────┘
└──────────────┘           └───────────────┘
```

- **采集**：连到你已经登录好的浏览器窗口，按 校区 → 教学楼 → 节次 翻数据，写进 SQLite（自动去重）
- **导出**：压缩成按日期分片的 JSON（一天一个文件，前端只取当天，首屏几十 KB）
- **发布**：丢到 GitHub Pages，零后端、秒开、Service Worker 缓存后可离线

> 详细分层与每个设计决策的理由见 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

### 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 数据模型 | `campusfree/model.py` | `Campus` / `Building` / `Room` / `Period` / `SchoolProfile` |
| 适配器协议 | `campusfree/adapter.py` | `SchoolAdapter` 抽象基类 + `validate_adapter()` 契约校验 |
| 登录态复用 | `campusfree/cdp.py` | 复用本机浏览器会话，`BrowserSpec` 管 exe/profile/port |
| 爬取调度 | `campusfree/runner.py` | 断点续传、失败隔离 |
| 存储 | `campusfree/store.py` | SQLite 去重入库 |
| 导出 | `campusfree/exporter.py` | → 静态 JSON，含导出安全闸门 |
| 脚手架 | `campusfree/scaffold.py` | 新学校骨架生成器 |
| 注册表 | `campusfree/registry.py` | 适配器自动发现 |
| 命令行 | `campusfree/cli.py` | `schools` / `check` / `run` / `export` / `new-school` |

### 为什么不用账号密码登录

教务系统登录通常有验证码、CAS 跳转、设备绑定，脚本模拟登录既脆弱，又要你把密码写进配置里。本框架改为**复用你已经登录好的浏览器窗口**（Chrome DevTools Protocol），全程**不碰密码、不保存 Cookie 文件**。

---

## 🏫 已支持学校

| ID | 学校 | 校区 | 节次 | 状态 |
|----|------|------|------|------|
| `your-school` | 某高校 | 校区 A + 校区 B | 13 | ✅ 官方适配器，已上线 [在线查询](https://huanweide.github.io/tust-classroom/) |

**你的学校不在这？** 看下面，约 30 分钟，欢迎提 PR。

---

## 🏫 接入你自己的学校

一所学校 = 一个适配器，4 个方法：

```python
from campusfree.adapter import SchoolAdapter
from campusfree.model import Building, Campus, Room, SchoolProfile

class YourSchoolAdapter(SchoolAdapter):
    @property
    def profile(self) -> SchoolProfile:
        return SchoolProfile(school_id="nku", school_name="你的学校",
                             base_url="https://jwxt.example.edu.cn", period_count=13)

    def list_campuses(self, page):        return [Campus(name="校区 A")]
    def list_buildings(self, page, campus): return [Building(name="主楼")]
    def select_building(self, page, campus, building) -> bool: ...
    def list_free_rooms(self, page, period, day_offset): return [Room(...)]
```

> 铁律：适配器里**不许引入 playwright**。框架会把已登录的页面对象传进来，你只管在页面里发请求、解析结果 —— 这样适配器才能脱离浏览器做单元测试。

生成器可以帮你起手：`python -m campusfree new-school your-school --name "你的学校"`

---

## 🏫 路线图 / Roadmap

- [x] 通用框架抽出（`campusfree/` 9 模块）
- [x] 首个官方适配器：某高校（双校区 / 13 节次 / 已上线）
- [x] 102 项单元测试（原项目为零测试）
- [x] CI：Python 3.11 + 3.12 矩阵，ruff + pytest + CLI 冒烟 + 前端资源校验
- [x] 导出安全闸门 + 只读体检模式
- [ ] 招 3 个校外适配器 PR（当前仅 `your-school` 一所）
- [ ] 前端支持多学校切换
- [ ] `static/` 模板化，新学校导出即得自己的页面
- [ ] 数据新鲜度告警（`generated_at` 过期自动开 Issue）

---

## 🏫 质量保障

| 类型 | 数量 | 怎么跑 |
|------|------|--------|
| 单元测试 | 102 项全绿 | `pytest` |
| 静态检查 | ruff 全绿 | `ruff check .` |
| 语法编译 | 全绿 | `python -m compileall -q .` |
| 适配器契约 | 每条命令可自检 | `python -m campusfree check --school your-school` |
| 前端端到端 | 11 项真实浏览器点击 | `npm install && npm run e2e` |
| **归一化回归** | 35 项 | `python test_normalize.py` |
| **爬取运维** | 10 项 | `python test_refresh_crawl.py` |
| **选教室 E2E** | 65 项真浏览器 | `node test_e2e_browse.mjs` |
| **整体全链路** | 47 项 | `python verify_all.py` |

`verify_all.py` 一条命令跑完九层校验：数据层回归 → 导出契约 → 每日数据一致性 → 前后端字段对齐 → 真浏览器 E2E → 导出安全闸门 → 爬取运维 → 凭据扫描。**铁律：任何一项 FAIL 都不算交付完成。**

**CI 跑的是前四类**（Python 3.11 / 3.12 双版本矩阵 + 前端资源校验）；后四类依赖本机数据库或真实浏览器，仅本地执行。

测试用一个「假教务页面」对象（`tests/conftest.py`）驱动整条流水线，所以**不需要浏览器、不需要校园网、不需要登录态**，CI 里就能全跑。

```
102 passed in 7.29s
```

---

## 🏫 数据与隐私

- **不收集、不存储、不传输任何账号密码**。代码里没有任何硬编码凭证。
- 只通过 CDP 复用你本机浏览器的会话；**不保存 Cookie 文件**。
- 数据只写进本地 SQLite（`data/classrooms.db`，已被 `.gitignore` 忽略），对外发布的静态文件不含任何账号信息。
- 若你的学校适配器需要账号信息，请只走环境变量，**绝不写进仓库**。

### 凭据安全

- 禁止提交任何凭据文件。`.gitignore` 已忽略 `.env`、`data/cookies.txt`、`*.key` 等。
- 每一次提交前都应扫描待提交内容中是否含密钥特征串（密钥前缀、私钥头、会话 Cookie）。
- 万一外泄：立即修改教务系统密码，旧会话令牌会随之失效。

---

## 🏫 老用户升级说明

从 v1 升级，**你本机的定时任务不用改**：

```bash
python crawler_playwright.py --range 0-6   # 照常可用
python export_static.py                    # 照常可用
python keepalive.py --once                 # 照常可用
```

数据库表结构未变，本地 `data/classrooms.db` 直接复用，不用重新爬。完整变更见 [CHANGELOG.md](CHANGELOG.md)。

---

## 🏫 目录结构

```
.
├── campusfree/            # 通用框架（换学校不用改）
│   ├── model.py           #   Campus/Building/Room/Period/SchoolProfile
│   ├── adapter.py         #   SchoolAdapter 协议 + 契约校验
│   ├── cdp.py             #   复用浏览器登录态
│   ├── runner.py          #   爬取调度（断点续传、失败隔离）
│   ├── store.py           #   SQLite 存储
│   ├── exporter.py        #   → 静态 JSON
│   ├── scaffold.py        #   新学校骨架生成器
│   ├── registry.py        #   适配器自动发现
│   └── cli.py             #   命令行
├── adapters/              # 各校适配器（新增学校只动这里）
│   └── tust.py            #   某高校
├── tests/                 # 102 项单元测试
├── docs/
│   ├── ADAPTER_GUIDE.md   #   30 分钟接入指南
│   └── ARCHITECTURE.md    #   架构说明
├── static/                # PWA 前端 + 导出的静态数据
├── crawler_playwright.py  # 兼容入口（老用法不变）
├── export_static.py       # 兼容入口
└── app.py                 # 本地查询 API（127.0.0.1:5000）
```

---

## 🏫 贡献

最欢迎的贡献：**给你自己的学校写一个适配器**。

1. `python -m campusfree new-school <学校缩写>`
2. 照着 [docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md) 填 4 个方法
3. `python -m campusfree check --school <缩写>` 自检
4. 在 README 的「已支持学校」表格加一行，提 PR

---

## 🏫 免责声明

非官方工具，数据来源于各校教务系统。课程安排可能临时调整，请以教务处通知为准。请勿用于任何违规用途。

## 🧰 同一作者的其他工具

> 作者在做一系列开源效率工具，欢迎顺手点 Star 支持：

- 📚 长篇创作 — AI 小说工坊，本地规则引擎零依赖：[点此访问](https://github.com/huanweide/novel-smith)
- 🎓 网课助手 — 智慧树自动播放/续播/AI 答题：[点此访问](https://github.com/huanweide/zhihuishu-helper)
- 🎬 字幕/视频 — B站字幕一键提取（零 Key 取官方字幕）：[点此访问](https://github.com/huanweide/bili-subtitle-universal)
- 📺 实时字幕 — 直播/会议实时字幕：[点此访问](https://github.com/huanweide/live-subtitle)
- ✂️ 视频摘要 — 长视频一键总结：[点此访问](https://github.com/huanweide/video-brief)
- 🖥️ 总览 — 作者全部开源项目集散：[点此访问](https://github.com/huanweide/family-showcase)
- 🩺 代码健康 — 零依赖多轴静态体检：[点此访问](https://github.com/huanweide/doctors)

## 🏫 License

[MIT](LICENSE) · 作者 [ReTri · huanweide](https://github.com/huanweide)

---

## ⭐ Star

如果你也受够了「跑到教学楼一间间看」或者「想要本校版却得从零造轮子」，点个 Star 让更多学校的人看到这个框架 —— 最欢迎的贡献就是**给你自己的学校写个适配器**。

[![Star](https://img.shields.io/github/stars/huanweide/tust-classroom?style=social)](https://github.com/huanweide/tust-classroom)

← [更多开源工具 · huanweide](https://github.com/huanweide)
