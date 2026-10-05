# 优化工作日志（GH-Optimizer）

> 本文件由自动化优化代理维护。每次优化追加一条，记录「为什么改」和「改了什么」，
> 下次运行时先读这里，延续上次方向，避免反复推翻重来。

---

## Round 1 — 2026-10-05 · 仓库 `tust-classroom`

### 一、存活评估（规范一）：保留

按项目宣称用途（高校空闲教室查询）在 GitHub 检索同类：

- 中文侧：`w1ndys/QFNUFreeClassroomsFinder`（曲阜师大）、`Guscccc/HustFreeRoomQuery`（华科）、
  `Bistutu/BistuEmpty`（北京信息科大）、`Nemoyuzx/where_to_study`（北邮）、
  `xmy3/jxnu-classroom`（江西师大）等
- 英文侧：`aayzhao/ClassroomAvailabilityApp`（UNC）、`fairlycodeparents/AlmaSpot`（博洛尼亚）等

**结论：不存在碾压级替代。** 全部同类都是「单校单实现」的小项目，stars 普遍个位数到几十，
彼此不通用。本校数据（天科大泰达+河西）本身就是天然壁垒，外部通用工具覆盖不到。
→ 判定保留，进入方向选择。

### 二、方向选定（规范二）：整体转向新方向

**从「TUST 单校查询器」→「CampusFreeRoom：任意高校空闲教室查询接入框架」。**

三种视角交叉验证：

1. **第一性原理**：这个项目真正的资产不是「天科大的数据」，而是
   「把教务系统空教室数据变成离线可查 PWA」的那条流水线。
   这条流水线对全国 3000 所高校都成立，现在却只为 1 所学校服务。
2. **马斯克式颠覆质疑**：如果只是服务一所学校，star 天花板 = 天科大在校生里
   知道 GitHub 的那部分人（乐观估计 < 100）。为什么不做成别人也能用的？
   市场上「单校脚本」遍地，但「接入框架」是空白 —— 这就是机会。
3. **费曼式简化**：一个学校 = 一个适配器，只需回答 4 个问题
   （几个校区 / 几栋楼 / 怎么切楼 / 怎么查空教室）+ 一张节次表。
   这个接缝是真实存在的，不是为抽象而抽象。

**为什么不选「单点深度特化」**：本项目的 PWA 前端、数据覆盖、自动化已经相当完善
（130 天数据、每小时自动更新），单点继续深挖边际收益低；而赛道天花板才是真瓶颈。

### 三、具体改动

#### 1. 架构：抽出通用框架（最大改动）

新增 `campusfree/` 包，把原来和 TUST 死死绑在一起的流水线拆成两层：

| 新文件 | 职责 |
|--------|------|
| `model.py` | Campus / Building / Room / Period / SchoolProfile |
| `adapter.py` | `SchoolAdapter` 抽象基类 + `validate_adapter()` 契约校验 |
| `cdp.py` | 浏览器登录态复用（探测/拉起/连接 CDP） |
| `runner.py` | 日期 × 校区 × 楼 × 节次 调度；断点续传；失败隔离 |
| `store.py` | SQLite 存储（表结构与 v1 完全一致） |
| `exporter.py` | SQLite → 静态 JSON |
| `scaffold.py` | 新学校适配器骨架生成器 |
| `registry.py` | 自动发现 `adapters/` 下所有适配器 |
| `cli.py` / `__main__.py` | `schools` / `check` / `run` / `export` / `new-school` |

新增 `adapters/tust.py`：TUST 降级为第一个官方适配器（4 个方法 + 学校画像）。

**换学校 = 加一个文件，框架一行不用改。**

#### 2. 修复的真实缺陷

| # | 问题 | 为什么严重 | 修法 |
|---|------|-----------|------|
| 1 | `requirements.txt` **漏写 playwright** | P0：按 README 装完依赖，一运行就 ImportError，新用户直接流失 | 补上 `playwright>=1.44.0`；把用不上的 `requests`/`ddddocr` 改为可选 |
| 2 | `e2e_test.cjs` 写死作者本机路径 | 别人 clone 下来完全跑不了，README 却宣称「11/11 通过」，等于无法验证 | 浏览器自动探测 + 环境变量覆盖 + 内置静态服务，`npm run e2e` 一条命令 |
| 3 | 项目**零测试** | 手写 SQL 拼装、搜索 UNION 分支、区间翻转等全是隐藏雷 | 新增 102 项单元测试 |
| 4 | CI 形同虚设 | 只做 compileall + `continue-on-error` 的 lint，永远绿 | 改为 3.11/3.12 矩阵 + ruff 强制 + pytest + CLI 冒烟 + 前端资源校验 |
| 5 | `/api/periods` 返回 `time`，`/api/free-rooms` 返回 `time_range` | 两个接口字段不一致，前端/二次开发必踩 | 统一为 `time_range` |
| 6 | `export_static.py` 硬编码 `campus_name='泰达'` 排序 | 换个学校导出顺序就错 | 改为读 `profile.campus_order` |
| 7 | 前端硬编码默认校区「泰达」 | 换学校要改前端 | 改为读 `index.json` 的 `default_campus`（带老数据兼容） |
| 8 | README 有从别的项目模板复制来的「CI 门禁用法」段落 | 讲的是「健康分与严重度」，与本项目毫无关系，显得不专业 | 删除，重写 README |

#### 3. 文档与工程化

- README 完全重写：新定位、对比表、两条快速开始路线、命令表、架构图
- 新增 `docs/ADAPTER_GUIDE.md`（30 分钟接入教程，含抓包步骤与常见问题表）
- 新增 `docs/ARCHITECTURE.md`（分层职责表 + 5 个关键设计决策及理由）
- 新增 `CHANGELOG.md`（含 Breaking Changes 与兼容性说明）
- 历史开发文档 `IMPLEMENTATION_PLAN.md` / `REVIEW.md` 移入 `docs/`，根目录不再堆噪音
- 新增 `pyproject.toml`：ruff 规则收敛到「能抓真 bug」（E4/E7/E9/F/W/I），
  不强制风格 —— 否则 172 条告警全是噪音，反而没人看
- 新增 `pytest.ini`、`requirements-dev.txt`、`package.json`
- `.gitignore` 按凭据安全铁律补全（密钥/证书/`.npmrc`/会话 cookie 等）
- `static/data/index.json` 补 `school` / `default_campus` / `source` 字段，
  让**线上站点立刻**受益于前端动态化（无需等下次爬取）

#### 4. 向后兼容（作者本机的每日自动任务不能断）

- `config.py` 降级为「只读视图」，值全部从 `adapters/tust.py` 派生，不重复定义
- `crawler_playwright.py` / `export_static.py` 保留为兼容入口，
  **参数语义完全不变**，`auto_update.bat` 与 Windows 任务计划照常工作
- 数据库表结构一字未改，本地 `data/classrooms.db` 直接复用
- TUST 适配器刻意沿用老的浏览器 profile 目录，老用户升级后不用重新登录

### 四、自检结果

```
ruff check .        → All checks passed!
pytest              → 102 passed in 8.52s
python -m compileall -q .  → OK
python -m campusfree schools  → 已注册 1 所学校（tust）
python -m campusfree check --school tust → [合格] 契约检查全部通过
```

### 五、自身错误与倾向（反省）

| 错误 / 倾向 | 具体表现 | 下次怎么避免 |
|------------|---------|------------|
| **脚本判断失误** | 第一版选池脚本用 `gh api ... -q .name` 判空，404 时误判成「已优化」，37 个仓库全报 HAS，差点误导选池 | 判存在性要用 HTTP 状态码或输出内容，不要靠 `-q` 的空/非空 |
| **低估网络环境** | SSH clone 卡死 4 分钟、git fetch 卡死 6 分钟，浪费了约 10 分钟 | 先用 `gh api .../tarball` 拿源码 + 本地 `git init` 重建仓库；push 走 https+代理更快 |
| **同文件并行编辑** | 对 `static/index.html` 同时发两个 Edit，第二个报 EBUSY 失败 | 同一文件一次只发一个 Edit（这条已在用户记忆里，本次仍犯） |
| **ruff 默认规则过严** | 不加配置直接跑出 172 条，绝大多数是风格噪音（UP006 占 63 条） | 新项目第一步就写 `pyproject.toml` 收敛规则集 |
| **模板与 JS 花括号冲突** | 脚手架模板用 `str.format()`，而模板里全是 JS 的 `{}`，直接 ValueError | 模板渲染改用 `__占位符__ + replace` |
| **倾向：过度抽象风险** | 差点把「换学校」抽象成一堆配置类。克制点：只抽象真实存在的接缝（4 个方法），其余保持直白 | 每加一层抽象先问：换学校时这层真的会变吗？ |
| **倾向：重功能轻验证** | 一开始想直接重写 README 交差 | 把测试补上才是真护城河 —— 补测试过程中真的挖出了接口字段不一致的 bug |

### 六、下一步候选

1. 招适配器：在学校论坛/QQ 群发「30 分钟接入你自己的学校」，目标 3 个校外 PR
2. 前端支持多学校切换（一个站点汇聚多校适配器产出的数据）
3. `static/` 通用化为模板，让新学校导出后直接得到自己的页面
4. 数据新鲜度告警：连续 N 天 `generated_at` 未更新时发 Issue

---
