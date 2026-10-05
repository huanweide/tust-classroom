<!-- badges -->
[![License](https://img.shields.io/github/license/huanweide/tust-classroom)](LICENSE)
[![CI](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/单元测试-102%20passed-brightgreen)](#质量保障)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![零后端](https://img.shields.io/badge/部署-纯静态%20Pages-blue?logo=github)](https://huanweide.github.io/tust-classroom/)
[![在线访问](https://img.shields.io/badge/手机直接打开-天津科技大学%20TUST-success)](https://huanweide.github.io/tust-classroom/)
<!-- /badges -->

# CampusFreeRoom · 高校空闲教室查询接入框架

> **教务系统里明明有「哪些教室现在是空的」，但它被困在需要登录、只在校园网里、手机上看不了的网页深处。**
> 本框架把这份数据搬出来，变成手机浏览器随开随查、可离线、零后端的静态站。
>
> **已上线示例（天津科技大学 泰达 + 河西双校区）：<https://huanweide.github.io/tust-classroom/>**

---

## 这个项目解决什么

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

第一所支持的学校是**天津科技大学（TUST）**，双校区、13 节次、已上线运行。

---

## 已支持学校

| ID | 学校 | 校区 | 节次 | 状态 |
|----|------|------|------|------|
| `tust` | 天津科技大学 | 泰达 + 河西 | 13 | ✅ 官方适配器，已上线 [在线查询](https://huanweide.github.io/tust-classroom/) |

**你的学校不在这？** 看下面「接入你自己的学校」，约 30 分钟，欢迎提 PR。

---

## 快速开始（分两条路）

### 路线 A：我只是想查空教室（TUST 同学）

直接用这个网址，不用装任何东西：

**📱 <https://huanweide.github.io/tust-classroom/>**

- 手机浏览器打开即用，可「添加到主屏」当 App
- 不需要校园网、不需要 VPN、不需要登录
- 数据每小时自动更新

### 路线 B：我想让我自己的学校也能用（开发者）

```bash
# 1. 装依赖
pip install -r requirements-dev.txt
playwright install chromium

# 2. 看看现在支持哪些学校
python -m campusfree schools

# 3. 体检某个适配器（不连网，纯静态检查）
python -m campusfree check --school tust

# 4. 生成你自己学校的适配器骨架
python -m campusfree new-school nku --name "南开大学"
#    → 生成 adapters/nku.py，照着里面的 TODO 填

# 5. 填完后自检
python -m campusfree check --school nku

# 6. 开爬（会自动拉起浏览器，在里面登录一次教务系统）
python -m campusfree run --school nku --range 0-6

# 7. 导出静态站
python -m campusfree export --school nku
```

完整图文教程：**[docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md)**

---

## 命令行

| 命令 | 作用 | 需要浏览器吗 |
|------|------|------------|
| `python -m campusfree schools` | 列出所有已注册的学校 | 否 |
| `python -m campusfree check --school tust` | 体检适配器是否写合格 | 否 |
| `python -m campusfree run --school tust --range 0-6` | 爬取未来 7 天 | 是 |
| `python -m campusfree run --school tust --auto` | 自动探测学期边界，一路爬到放假 | 是 |
| `python -m campusfree export --school tust` | 导出静态 JSON | 否 |
| `python -m campusfree new-school <id>` | 生成新学校适配器骨架 | 否 |

单个学校爬一天：`run --school tust --dayoffset 1`（1 = 明天）

---

## 它是怎么工作的

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

### 为什么不用账号密码登录

教务系统登录通常有验证码、CAS 跳转、设备绑定，脚本模拟登录既脆弱，
又要你把密码写进配置里。本框架改为**复用你已经登录好的浏览器窗口**
（Chrome DevTools Protocol），全程**不碰密码、不保存 Cookie 文件**。

---

## 目录结构

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
│   └── tust.py            #   天津科技大学
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

## 质量保障

| 类型 | 数量 | 怎么跑 |
|------|------|--------|
| 单元测试 | 102 项全绿 | `pytest` |
| 静态检查 | ruff 全绿 | `ruff check .` |
| 适配器契约 | 每条命令可自检 | `python -m campusfree check --school tust` |
| 前端端到端 | 11 项真实浏览器点击 | `npm install && npm run e2e` |

测试用一个「假教务页面」对象（`tests/conftest.py`）驱动整条流水线，
所以**不需要浏览器、不需要校园网、不需要登录态**，CI 里就能全跑。

```
102 passed in 8.52s
```

---

## 数据与隐私

- **不收集、不存储、不传输任何账号密码**。代码里没有任何硬编码凭证。
- 只通过 CDP 复用你本机浏览器的会话；**不保存 Cookie 文件**。
- 数据只写进本地 SQLite（`data/classrooms.db`，已被 `.gitignore` 忽略），
  对外发布的静态文件不含任何账号信息。
- 若你的学校适配器需要账号信息，请只走环境变量，**绝不写进仓库**。

### 凭据安全

- 禁止提交任何凭据文件。`.gitignore` 已忽略 `.env`、`data/cookies.txt`、`*.key` 等。
- 每一次提交前都应扫描待提交内容中是否含密钥特征串（密钥前缀、私钥头、会话 Cookie）。
- 万一外泄：立即修改教务系统密码，旧会话令牌会随之失效。

---

## 老用户升级说明

从 v1 升级，**你本机的定时任务不用改**：

```bash
python crawler_playwright.py --range 0-6   # 照常可用
python export_static.py                    # 照常可用
python keepalive.py --once                 # 照常可用
```

数据库表结构未变，本地 `data/classrooms.db` 直接复用，不用重新爬。
完整变更见 [CHANGELOG.md](CHANGELOG.md)。

---

## 贡献

最欢迎的贡献：**给你自己的学校写一个适配器**。

1. `python -m campusfree new-school <学校缩写>`
2. 照着 [docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md) 填 4 个方法
3. `python -m campusfree check --school <缩写>` 自检
4. 在 README 的「已支持学校」表格加一行，提 PR

---

## 免责声明

非官方工具，数据来源于各校教务系统。课程安排可能临时调整，请以教务处通知为准。请勿用于任何违规用途。

## 许可证

[MIT](LICENSE) · 作者 [ReTri · 樊斯瑞](https://github.com/huanweide)
