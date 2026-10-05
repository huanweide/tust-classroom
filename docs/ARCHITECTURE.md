# 架构说明

## 一句话

把「只有登录校园网才能看到的空闲教室数据」搬到手机上随开随查的静态站。

## 数据流

```
┌──────────────┐   CDP 复用   ┌───────────────┐   请求   ┌──────────────┐
│ 本机浏览器    │ ──────────▶ │ campusfree    │ ───────▶ │ 教务系统      │
│ (已登录一次)  │   登录态     │ runner 调度层 │  空闲教室  │ (各校不同)    │
└──────────────┘              └───────┬───────┘          └──────────────┘
                                      │ 问路
                              ┌───────▼───────┐
                              │ SchoolAdapter │  ← 每校一个，只写 4 个方法
                              │ (学校适配器)   │
                              └───────┬───────┘
                                      │ 标准化 Room
                              ┌───────▼───────┐
                              │ RoomStore     │  SQLite 去重入库
                              └───────┬───────┘
                                      │
                              ┌───────▼───────┐
                              │ StaticExporter│  导出压缩 JSON
                              └───────┬───────┘
                                      │
                              ┌───────▼───────┐
                              │ static/ 前端   │  PWA，可离线、可装桌面
                              └───────┬───────┘
                                      │
                                 GitHub Pages
```

## 分层与职责

| 层 | 文件 | 职责 | 换学校要改吗 |
|----|------|------|------------|
| 模型 | `campusfree/model.py` | Campus / Building / Room / Period / SchoolProfile | 否 |
| 协议 | `campusfree/adapter.py` | SchoolAdapter 抽象基类 + 契约校验 | 否 |
| 浏览器 | `campusfree/cdp.py` | 探测/拉起/连接 CDP，复用登录态 | 否（路径由适配器给） |
| 调度 | `campusfree/runner.py` | 日期 × 校区 × 楼 × 节次的循环；断点续传；失败隔离 | 否 |
| 存储 | `campusfree/store.py` | SQLite 建表/写入/清理/查询 | 否 |
| 导出 | `campusfree/exporter.py` | SQLite → 静态 JSON | 否（排序由 profile 给） |
| 脚手架 | `campusfree/scaffold.py` | 生成新学校适配器骨架 | 否 |
| 注册 | `campusfree/registry.py` | 自动发现 `adapters/` 下所有适配器 | 否 |
| CLI | `campusfree/cli.py` | schools / check / run / export / new-school | 否 |
| **适配器** | `adapters/*.py` | **各校专属的 4 个方法 + 学校画像** | **是，这是唯一要写的** |

## 关键设计决策（以及为什么）

### 1. 复用浏览器登录态，而不是模拟登录

教务系统登录通常有验证码、CAS 跳转、设备绑定。脚本模拟登录：
- 脆弱（改版就废）
- 要用户把账号密码交给代码（安全风险）

改用 CDP 连到用户已登录的浏览器窗口，借它的会话发请求：
**全程不碰密码、不落盘 Cookie 文件**。

### 2. 每校一个适配器，而不是写一堆 if-else

全国高校教务系统千差万别。如果在主流程里写 `if school == "tust": ... elif ...`，
加一所学就要改主流程，很快就没人敢动。
改成「适配器 + 自动发现注册表」后，加学校 = 加一个文件，**框架一行不动**。

### 3. 静态站，而不是后端服务

教室数据一天变一次，不需要实时接口。
导出成静态 JSON 丢到 GitHub Pages：
- 零服务器成本
- 手机浏览器随开随查，不用校园网/VPN
- Service Worker 缓存后离线可用

### 4. 每天的数据按日期分文件

整学期 130 天全塞一个 JSON 会有几 MB，手机打开慢。
按 `YYYY-MM-DD.json` 分片，前端只取当天那个文件，首屏几十 KB。

### 5. 表结构刻意不改

`free_rooms` 表的列名、唯一约束从 v1 保持到现在，
老用户升级后本地 `data/classrooms.db` 直接可用，不用重新爬一遍。

## 测试策略

| 层 | 怎么测 | 文件 |
|----|--------|------|
| 模型/契约 | 纯 Python 断言 | `tests/test_model.py`、`test_adapter_contract.py` |
| 存储 | 临时 SQLite | `tests/test_store.py` |
| 导出 | 临时目录断言产物 | `tests/test_exporter.py` |
| 调度 | **假页面对象**（不需要真浏览器） | `tests/test_runner.py` |
| 适配器 | 假页面返回 URP 风格 JSON | `tests/test_tust_adapter.py` |
| API | Flask test_client | `tests/test_app.py` |
| 前端 | 真实浏览器点击（可选，需本机 Chrome） | `e2e_test.cjs` |

关键是 `conftest.py` 里的 `FakeUrpPage`：
它只实现 `.url` 和 `.evaluate()`，按请求关键字返回预设数据。
这样整条流水线都能在 CI 里跑，不需要浏览器、不需要校园网、不需要登录态。
