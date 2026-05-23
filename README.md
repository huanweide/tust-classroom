# 🏫 TUST 空闲教室

> 天津科技大学空闲教室实时查询系统 · 泰达 & 河西双校区

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-在线访问-0891B2?style=flat&logo=github)](https://huanweide.github.io/tust-classroom/)
[![PWA Ready](https://img.shields.io/badge/PWA-可安装-22C55E?style=flat&logo=pwa)](https://huanweide.github.io/tust-classroom/)
[![Data Updated](https://img.shields.io/badge/数据-2026.07.01-64748B?style=flat)](https://huanweide.github.io/tust-classroom/)

**🔗 在线地址：[huanweide.github.io/tust-classroom](https://huanweide.github.io/tust-classroom/)**

## ✨ 功能

- 🔍 **三种查询模式**：按节次查空闲 / 时间范围查连续空闲 / 查某教室空闲时段
- 🏫 **双校区覆盖**：泰达校区 + 河西校区，59 栋教学楼
- 📅 **日期导航**：左右翻日，40 天学期数据覆盖（2026.05.23 ~ 2026.07.01）
- 🔎 **智能搜索**：模糊匹配教室名，输错自动推荐相似教室
- 📱 **PWA 支持**：可添加到手机桌面，离线可用
- ⚡ **纯静态**：无需后端，GitHub Pages 直接托管，秒开

## 📖 使用方式

### 网页版

打开 [huanweide.github.io/tust-classroom](https://huanweide.github.io/tust-classroom/)

1. 选择校区（泰达 / 河西）
2. 选择日期（默认今天，可左右翻日）
3. 选择查询模式，填入条件，点查询

### 添加到手机桌面（推荐）

- **iOS Safari**：底部「分享」→「添加到主屏幕」
- **Android Chrome**：菜单「添加到主屏幕」
- 添加后体验接近原生 App

### 微信内使用

将链接加入微信「收藏」，或公众号菜单跳转。

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 数据采集 | Playwright + CDP 复用 Edge 登录态 |
| 数据处理 | Python 爬虫 → SQLite → 静态 JSON |
| 前端 | 纯 HTML/CSS/JS（PWA，零框架） |
| 托管 | GitHub Pages（免费） |
| 保活 | Windows 任务计划 + CDP 会话保活 |

## 📂 项目结构

```
├── crawler_playwright.py   # CDP 爬虫（核心）
├── export_static.py        # SQLite → JSON 导出
├── keepalive.py            # URP 会话保活
├── app.py                  # Flask API（本地开发用）
├── config.py               # 配置文件
├── static/
│   ├── index.html          # PWA 前端（线上版本）
│   ├── manifest.json       # PWA 清单
│   ├── sw.js               # Service Worker
│   └── data/               # 静态 JSON 数据（40天）
└── schedule_crawl.bat      # 定时爬取脚本
```

## 🔄 数据更新

```bash
# 爬取未来 7 天
python crawler_playwright.py --range 0-6

# 爬取指定范围
python crawler_playwright.py --range 0-39

# 导出静态 JSON
python export_static.py

# 推送到 GitHub Pages
git subtree push --prefix=static origin gh-pages
```

建议配合 Windows 任务计划每周日自动运行。

## ⚠️ 免责声明

本项目为非官方查询工具，数据来源于天津科技大学 URP 教务系统。课程安排可能随时调整，请以教务处最新通知为准。

## 📄 License

MIT
