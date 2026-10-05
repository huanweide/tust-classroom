# 更新日志

本项目采用 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式。

## [2.0.0] - 2026-10-05

### 定位变更（Breaking）

项目从「天津科技大学空闲教室查询器」升级为
**CampusFreeRoom —— 任意高校空闲教室查询接入框架**。
天津科技大学降级为「第一个官方适配器」。

原因：单校工具的天花板太低（同类项目全国遍地，全是单校单实现的一次性脚本）；
而「接入框架」是空白赛道 —— 让任何学校都能 30 分钟接进来，
同时本校用户的使用体验完全不变。

### 新增

- `campusfree/` 框架包：模型、适配器协议、CDP 复用、爬取调度、存储、静态导出、脚手架、注册表、CLI
- `adapters/` 适配器包：`adapters/tust.py` 为首个官方适配器，新增学校只需加一个文件
- CLI：`python -m campusfree schools|check|run|export|new-school`
- 契约校验 `validate_adapter()`：适配器漏写方法/网址格式错/节次没填时间，运行时前就能查出来
- 脚手架 `new-school`：一条命令生成可通过校验的适配器骨架
- 测试套件 102 项：模型、契约、存储、导出、调度、适配器、Flask API、脚手架、CLI
- `pyproject.toml`（ruff 规则收敛到「能抓真 bug」）、`pytest.ini`、`requirements-dev.txt`
- `docs/ADAPTER_GUIDE.md`（30 分钟接入指南）、`docs/ARCHITECTURE.md`
- 导出产物新增 `school`、`default_campus`、`source` 字段

### 修复

- **requirements.txt 漏写 playwright**：按 README 装完依赖后一运行就 ImportError（P0）
- **e2e_test.cjs 写死作者本机路径**：Chrome 路径和截图目录硬编码，别人 clone 下来完全跑不了；
  改为自动探测 + 环境变量覆盖，并内置静态服务，跑完自动关闭
- **`/api/periods` 字段名不一致**：该接口返回 `time`，而 `/api/free-rooms` 返回 `time_range`；统一为 `time_range`
- **`export_static.py` 硬编码「泰达优先」排序**：改为读取适配器的 `campus_order`
- **前端硬编码默认校区「泰达」**：改为读 `index.json` 的 `default_campus`（换学校不用改前端）

### 变更

- CI 从「只做语法检查 + 不失败的 lint」升级为：Python 3.11/3.12 矩阵 + ruff + pytest + CLI 冒烟 + 前端资源校验
- `config.py` 降级为兼容视图：值全部从 `adapters/tust.py` 派生，不再单独维护
- `crawler_playwright.py` / `export_static.py` 保留为兼容入口，内部改为调用框架，参数语义不变
- `app.py` 支持 `CAMPUSFREE_SCHOOL` 环境变量切换学校
- 历史开发文档 `IMPLEMENTATION_PLAN.md`、`REVIEW.md` 移入 `docs/`
- 移除对 `requests` / `ddddocr` 的默认依赖（CDP 方案用不到，ddddocr 体积大）

### 兼容性

老用法全部保留，作者本机的 Windows 任务计划与 `auto_update.bat` 无需改动：

```bash
python crawler_playwright.py --range 0-6   # 照常可用
python export_static.py                    # 照常可用
python keepalive.py --once                 # 照常可用
```

数据库表结构未变，本地 `data/classrooms.db` 可直接复用。

## [1.x] - 2026-09

- TUST 双校区（泰达 + 河西）空闲教室采集
- CDP 复用 Edge 登录态
- 静态 JSON 导出 + GitHub Pages PWA 前端
- Windows 任务计划每小时自动更新
- URP 会话保活
- 微信小程序探索版
