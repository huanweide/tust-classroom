# TUST 空闲教室查询系统 — 完整复盘

> 2026-05-23 · 从零到上线 · 40天数据覆盖 · PWA + 微信小程序双端

---

## 一、最终架构

```
                 ┌──────────────────────────┐
                 │  URP 教务系统              │
                 │  jwxtxs.tust.edu.cn:46110 │
                 └──────────┬───────────────┘
                            │ CDP 复用 Edge 登录态
                            ▼
┌───────────────────────────────────────────────┐
│  crawler_playwright.py                        │
│  playwright.connect_over_cdp("localhost:9222")│
│  --range 0-39  爬取40天 × 2校区 × 13节次      │
│  写入 SQLite (带断点续传)                      │
└───────────┬───────────────────────────────────┘
            │
            ▼
┌───────────────────────┐     ┌──────────────┐
│  export_static.py     │     │  app.py      │
│  SQLite → 静态JSON    │     │  Flask API   │
│  输出到 static/data/  │     │  本地调试用   │
└───────┬───────────────┘     └──────────────┘
        │
        │ git subtree push --prefix=static origin gh-pages
        ▼
┌─────────────────────────────────────────────┐
│  GitHub Pages  (huanweide.github.io)        │
│  ┌─────────────────────────────────────┐    │
│  │  static/index.html  纯前端PWA       │    │
│  │  + data/*.json  (~0.8MB / 40天)     │    │
│  │  + sw.js  + manifest.json           │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
        │                    │
        │ 浏览器访问           │  wx.request()
        ▼                    ▼
    PWA (可安装)        微信小程序 (WXML原生)
```

---

## 二、关键技术决策

### 1. 登录方案：CDP 复用浏览器 Profile（正确方向）

**路线演进**：
```
requests.Session + ddddocr → 验证码死活过不去
Selenium + OCR → 滑块验证码持续拦截  
Playwright CDP 复用 Edge → 一次登录，永久复用 ✓
```

**核心原理**：Edge 已经登录了 URP 教务系统。启动 Edge 时开 debug port，Playwright 通过 CDP 连接进去，直接复用已有的 cookies 和 session。教务系统看到的请求来自"真实的、已经登录过的 Edge 浏览器"。

**代价**：必须保持 Edge 开着 debug port（`--remote-debugging-port=9222`），需要 keepalive 脚本每 25 分钟 ping 一次 URP 防会话过期。

### 2. 数据架构：静态 JSON 替代动态 API

前端从纯静态 JSON 读取数据，所有查询计算在浏览器本地执行。

**选择理由**：
- GitHub Pages 免费托管，零服务器成本
- JSON 体积可控（40天 × 双校区 = 0.8MB）
- 查询速度比走网络 API 快得多
- 微信小程序可以直接 `wx.request` 拉 JSON

**不做**：SQLite 在生产环境用、后端动态查询 —— 因为 GitHub Pages 跑不了 Python。

### 3. 前端架构：单文件 PWA（705 行 HTML）

没有框架、没有构建工具、没有依赖。一个 HTML 文件包含全部 CSS + JS。

**选择理由**：
- 零构建步骤，改完直接 push
- 微信内置浏览器兼容性好
- 加载快（无框架 overhead）
- PWA 可安装到手机桌面

**代价**：代码组织靠注释分隔符（`// ═══`），模块化靠约定。

---

## 三、踩坑记录

| # | 坑 | 原因 | 解决方案 |
|---|----|------|----------|
| 1 | 验证码识别率 0% | URP 的滑块验证码不是 OCR 问题，是人机检测 | 放弃破解，CDP 复用已登录浏览器 |
| 2 | `8-` 教学楼 code 不是 8 | URP 内部教学楼 code ≠ 实际编号，如"8-"实际 code 是 `20234` | 先调校区 API 获取 code 列表，再逐 code 查 |
| 3 | gh-pages 子目录路径全挂 | 项目站点 URL 是 `/tust-classroom/` 而非 `/`，绝对路径 `/manifest.json` 解析到错误域名 | 全部改为相对路径 `./manifest.json`、`start_url: "./"` |
| 4 | `git add -A` 误提交 Edge browser_profile | Edge Profile 目录有几千个缓存文件 | `.gitignore` 加 `data/browser_profile/` |
| 5 | `git subtree push` 只推 `static/` 目录 | 如果直接 push main，gh-pages 拿不到 HTML | 必须 `git subtree push --prefix=static origin gh-pages` |
| 6 | 个人小程序不能用 `<web-view>` | 微信要求：企业主体 + ICP 备案域名，GitHub Pages 无法备案 | 改用原生 WXML 渲染 + `wx.request` 拉 JSON |
| 7 | `%date%` 在中文 Windows 下输出 `2026/05/23 周六` | git commit 消息含空格被截断 | `for /f "tokens=1 delims= "` 只取日期部分 |
| 8 | `config.py` 只配了泰达校区 | 硬编码 `CAMPUS_CODE = "02"` | 爬虫改为动态发现校区，config 保留但仅作默认值 |

---

## 四、自动化运维

### keepalive（保活）
```
Windows 任务计划: TUST_URP_KeepAlive
频率: 每 25 分钟
动作: pythonw keepalive.py --once
目的: 维持 Edge 中 URP 的登录会话不超时
```

### auto_update（数据更新）
```
Windows 任务计划: TUST_AutoUpdate  
频率: 每周日 22:00
动作: C:\...\auto_update.bat
流程:
  1. python crawler_playwright.py --range 0-6  (爬未来7天)
  2. python export_static.py                   (导出JSON)
  3. git add + commit + push origin main       (推送主分支)
  4. git subtree push --prefix=static origin gh-pages (推送Pages)
  5. SQL DELETE WHERE date < 30天前           (清理旧数据)
```

### 前端更新感知
用户打开页面 → JS 从 `index.json` 读 `updated` 字段 → 和 `localStorage` 中上次版本比对 → 不同则亮起"🆕 有新数据！点击刷新"徽章。

---

## 五、代码规模

| 文件 | 行数 | 职责 |
|------|------|------|
| `crawler_playwright.py` | 362 | CDP 爬虫核心 |
| `export_static.py` | 119 | SQLite → JSON 导出 |
| `app.py` | 357 | Flask API（本地调试） |
| `static/index.html` | 705 | PWA 前端（纯静态） |
| `static/sw.js` | 52 | Service Worker 缓存策略 |
| `config.py` | 29 | 配置常量 |
| `keepalive.py` | 142 | URP 会话保活 |
| `auto_update.bat` | 53 | 一键自动更新脚本 |
| `wechat-mini/*` | 900+ | 微信小程序（8文件） |
| **总计** | **~2700** | |

---

## 六、如果重来一次会怎么做

1. **第一天就用 CDP**，不在验证码破解上浪费两天
2. **先确认小程序限制**再决定是否做原生开发 —— 花了几小时才发现个人小程序禁 `<web-view>`
3. **爬虫一开始就支持多天**—— 最初只爬当天，后来改 `--range` 要重构一半代码
4. **search.json 建前缀索引**而非全量数组——现在 475 条还好，上了千就会卡
5. **auto_update.bat 加钉钉/微信通知**——现在失败只能看日志，无人值守时不放心

---

## 七、可复用模式（如果你要做类似项目）

**适用场景**：教务系统/校内平台 → 爬数据 → 静态站 → 人人可访问

**通用公式**：
```
1. CDP 复用浏览器登录态（如果目标系统需要登录）
2. Python 爬虫 + SQLite 本地存储 + 断点续传
3. 导出为静态 JSON（GitHub Pages 能读的大小）
4. 纯前端 PWA（零框架，单文件）
5. Windows 任务计划定时跑（大学生用自己电脑当服务器）
6. 可选：微信小程序原生壳 + wx.request 拉同源数据
```

**关键约束**：
- 数据量要小（<5MB），否则 GitHub Pages 加载太慢
- 目标系统的反爬策略要稳定（CDP 方案对大多数国产教务系统有效）
- 个人小程序只能用原生渲染，不能嵌网页
