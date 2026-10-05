# 接入新学校指南（30 分钟）

> 面向：想让自己学校也能用上本框架的开发者。
> 不需要懂爬虫，只要会用浏览器 F12 看Network 面板。

## 0. 先弄清楚一件事：你要填的是哪四个空

本框架把「爬空闲教室」这件事拆成了**永远不变的部分**和**每校不同的部分**：

| 类型 | 内容 | 谁负责 |
|------|------|--------|
| 不变 | 翻日期、翻楼、翻节次、去重入库、导出 JSON、前端页面 | 框架 |
| 每校不同 | 教务系统网址、有几个校区、有几栋楼、怎么切楼、怎么查空教室、一天几节课 | **你（适配器）** |

所以你只要回答四个问题，写四个方法：

1. `list_campuses` — 你们学校有几个校区？
2. `list_buildings` — 某个校区有几栋楼？
3. `select_building` — 怎么把查询上下文切到某栋楼？
4. `list_free_rooms` — 第 N 节课、第 M 天，哪些教室是空的？

外加一张「学校画像」（网址 + 节次时间表）。

## 1. 生成骨架（1 分钟）

```bash
python -m campusfree new-school nku --name "南开大学"
```

会生成 `adapters/nku.py`，里面全是需要你改的 TODO。

## 2. 抓包：把教务系统的请求抄下来（10 分钟）

这一步是全部工作的核心，做法固定：

1. 用浏览器登录你们学校教务系统，进入「空闲教室查询」页面；
2. 按 F12 打开开发者工具，切到 **Network（网络）** 面板，勾上 **Preserve log**；
3. 在页面上手动操作一遍：选校区 → 选教学楼 → 选节次 → 查询；
4. 面板里会多出几个请求，逐个点开看：
   - **Request URL**：请求地址（相对路径那一段）
   - **Request Method**：一般是 POST
   - **Form Data / Payload**：传了什么参数
   - **Response**：返回了什么 JSON（重点看字段名的层级）
5. 把这四个信息分别填进四个方法里。

::: tip 怎么判断哪个请求是哪个
一般会出现四种请求：校区列表、教学楼列表、切换/设置上下文、查询空闲教室。
看返回的 JSON 里有没有「校区名」「楼名」「教室名」就能认出来。
:::

## 3. 填表（10 分钟）

打开生成的 `adapters/nku.py`：

### 3.1 学校画像

```python
BASE_URL = "https://jw.nankai.edu.cn"   # TODO 1：教务系统根地址

PERIODS = periods_from_list([           # TODO 2：节次时间表
    (1, "08:00-08:45"), (2, "08:55-09:40"),
])

SchoolProfile(
    entry_path="/xxx/freeClassroom/index",   # TODO 3：空闲教室页路径
    default_campus="八里台校区",              # TODO 4：前端默认选中的校区
    ...
)
```

节次时间表**必须**和你们学校教务系统里的一致，否则查出来的「第 3 节」对不上真实时间。

### 3.2 四个方法

把抓包得到的 URL、参数、返回字段名替换掉模板里的示例值。以「查空闲教室」为例：

```python
def list_free_rooms(self, page, period, day_offset):
    result = page.evaluate(
        """async (args) => {
            const resp = await fetch('这里换成你抓到的URL' + args.period, {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: '这里换成你抓到的参数'
            });
            return await resp.json();
        }""",
        {"period": period, "dayoffset": day_offset},
    )
    if not isinstance(result, dict) or "error" in result:
        return []
    # 下面这三个字段名换成你们学校返回的
    rooms = []
    for b in result.get("你抓到的楼数组字段", []) or []:
        bname = b.get("你抓到的楼名字段", "")
        for r in b.get("你抓到的教室数组字段", []) or []:
            name = self.normalize_room_name(r.get("你抓到的教室名字段", ""))
            if name:
                rooms.append(Room(building_name=bname, classroom_name=name))
    return rooms
```

**要点**：把「教务系统的黑话」翻译成框架认识的 `Room(building_name=..., classroom_name=...)`。
翻译完，框架就能帮你存、帮你导出、帮你生成前端。

## 4. 自检（1 分钟）

```bash
python -m campusfree check --school nku
```

这个命令会检查：四个方法在不在、网址格式对不对、节次表有没有漏填时间、
默认校区写没写错。有问题会一条条告诉你改哪里。

## 5. 开爬（5 分钟）

```bash
# 1) 启动浏览器（会打开一个专用窗口），在里面登录一次教务系统
python -m campusfree run --school nku --range 0-6

# 2) 导出静态站
python -m campusfree export --school nku
```

第一次会提示未登录 —— 在自动打开的浏览器窗口里登录一次即可，
登录态保存在该学校专属的 profile 目录里，以后长期复用。

> **为什么不用账号密码自动登录？**
> 教务系统登录通常有验证码、CAS 跳转、设备绑定，脚本模拟登录既脆弱又让你把密码交给代码。
> 复用已登录的浏览器窗口，全程不碰密码、不存 Cookie 文件，反而更安全。

## 6. 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `check` 报「找不到学校适配器」 | 文件没放进 `adapters/`，或没写 `ADAPTER =` | 确认 `adapters/xxx.py` 末尾有 `ADAPTER = XxxAdapter` |
| 一直提示未登录 | 浏览器窗口里没登录成功 | 在该窗口手动打开教务系统登录一次 |
| 爬到 0 条 | 返回字段名猜错了 | 打印 `result` 看看真实结构；或核对节次范围 |
| 只爬到一个校区 | 校区接口返回空 | 实现 `fallback_campuses` 手写校区编码兜底 |
| 数据日期对不上 | 节次表或 `dayplus` 参数语义不同 | 抓包确认偏移量参数含义 |

## 7. 提交你的适配器（欢迎 PR）

1. `adapters/<学校拼音缩写>.py`
2. README 的「已支持学校」表格加一行
3. 附一张查询成功的截图

学校名字段请写中文全称，`school_id` 用小写英文短名。
