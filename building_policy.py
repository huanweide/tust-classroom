"""低效楼栋策略 —— 实测结论与落地规则

【实测结论（130 天全量数据，勿推翻）】
1. 零空闲教室：0 间。数据质量很好，不存在「一直查不到」的教室。
2. 458/470 间教室 130 天从不缺失，只有 12 间缺 1~3 天（阶梯教室被排满时教务系统不返回）。
3. 空 periods 记录：0 条。导出层不会写入空数组。
4. 真正的问题在**楼栋颗粒度**：50 栋楼里 35 栋房间数 ≤5，中位数只有 2 间。
   · 20 栋只有 1 间房（点进去毫无意义）
   · 15 栋有 2~5 间
   · 13 栋 ≥10 间（这才是主力）

【为什么不能真删】
那20 栋 1 间房楼不是脏数据，是教务系统真实存在的教学场所：
  仪器分析实验室/无机化学实验室/物理一实验室… 各只有「实验室1」
  田径场/体育馆/大活/表演厅 —— 是场地，不是教室
  网络（在线）/学院教室（虚拟）—— 是线上资源与虚拟教室
删掉它们 = 对需要查这些场地的人造成功能缺失，而且违反「数据来自教务系统原样呈现」。

【所以采用：降级 + 折叠，而非删除】
- 前端楼栋列表：默认只铺「有教学价值的楼」（≥6 间房，共 15 栋），
  低效楼折叠进「其他场所」分组，可展开。
- 阶梯教室所在楼（泰达 9- / 河西 阶梯）无论房间数一律置顶。
- 1 间房的楼点进去直接跳到教室详情，不显示中间列表（省一次无用点击）。
- 搜索框永不做过滤 —— 用户搜「田径场」必须能搜到。

本模块只提供判定，数据由 export_static 写进 index.json。
"""

# 单间房阈值：≤ 此值的楼折叠进「其他场所」
SINGLE_ROOM_THRESHOLD = 1
# 低效阈值：≤ 此值的楼不算「主力教学楼」
LOW_ROOM_THRESHOLD = 5
# 有教学价值的门槛：≥ 此值才默认铺开
MAIN_ROOM_THRESHOLD = 6

# 场地类：本质不是教室，但教务系统里有，保留展示
VENUE_HINT = ("田径场", "运动场", "体育馆", "大活", "表演厅", "网络", "在线")

# 虚拟类：教务系统的虚拟教室，占用逻辑与实体教室不同
VIRTUAL_HINT = ("虚拟",)


def classify_building(nb, room_count):
    """给单个楼栋定展示策略。

    nb: normalize_building() 的输出
    room_count: 该楼真实房间数

    返回 dict:
      tier      step 阶梯楼 / main 教学楼 / low 小型场所 / venue 场地 / virtual 虚拟
      display   显示名
      sort      列表内排序权重（越小越靠前）
      skip_list 单间房楼：点进去直接看教室，不需要中间列表

    排序规则（2026-10-19 用户明确要求，勿改）：
      1. 阶梯教室楼永远最前（泰达 9- / 河西 阶梯）
      2. 其余按「房间数降序」—— 信息多的楼排上面
      3. 房间数相同按显示名
    折叠规则：一律不折叠。「什么楼都可选再跳转」是硬要求，
    折叠会让部分楼无法一键直达。
    """
    name = nb["key"]
    is_venue = nb["kind"] == "venue" or any(h in name for h in VENUE_HINT)
    is_virtual = nb["kind"] == "virtual" or any(h in name for h in VIRTUAL_HINT)

    if nb["is_step_bld"]:
        tier, sort = "step", 0
    elif is_virtual:
        tier, sort = "virtual", 200000 - min(room_count, 1000)
    elif is_venue:
        tier, sort = "venue", 100000 - min(room_count, 1000)
    else:
        tier = "main"
        # 房间数越多 sort 越小 → 排越前（信息多的放上面）
        sort = 1000 - min(room_count, 999)

    return {
        "tier": tier,
        "display": nb["display"],
        # 单间房楼：点进去直接看教室，不需要中间列表
        "skip_list": room_count <= SINGLE_ROOM_THRESHOLD,
        "room_count": room_count,
        "sort": sort,
    }


TIER_LABEL = {
    "step": "阶梯教室楼",
    "main": "教学楼",
    "low": "小型场所",
    "venue": "场地",
    "virtual": "虚拟教室",
}
