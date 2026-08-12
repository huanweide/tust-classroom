"""TUST 空闲教室查询 API — Flask 后端"""
import sqlite3

from flask import Flask, jsonify, request, send_from_directory

import config

app = Flask(__name__, static_folder="static", static_url_path="")


def query_db(sql, params=()):
    """执行查询并返回 dict 列表"""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ── API ──

@app.route("/api/campuses")
def api_campuses():
    """获取所有有数据的校区"""
    rows = query_db("SELECT DISTINCT campus_name FROM free_rooms ORDER BY campus_name")
    return jsonify([r["campus_name"] for r in rows])


@app.route("/api/buildings")
def api_buildings():
    """获取某校区所有教学楼 ?campus=泰达"""
    campus = request.args.get("campus", config.CAMPUS_NAME)
    rows = query_db(
        "SELECT DISTINCT building_name FROM free_rooms "
        "WHERE campus_name = ? ORDER BY building_name",
        (campus,),
    )
    return jsonify([r["building_name"] for r in rows])


@app.route("/api/periods")
def api_periods():
    """获取所有节次及其时间"""
    return jsonify([
        {"period": k, "time": v} for k, v in sorted(config.PERIODS.items())
    ])


@app.route("/api/dates")
def api_dates():
    """获取数据库中有数据的日期"""
    rows = query_db("SELECT DISTINCT date FROM free_rooms ORDER BY date DESC LIMIT 7")
    return jsonify([r["date"] for r in rows])


@app.route("/api/free-rooms")
def api_free_rooms():
    """查询空闲教室
    ?date=2026-05-23&period=3&campus=泰达&building=9号楼
    """
    date = request.args.get("date", "")
    period = request.args.get("period", "")
    campus = request.args.get("campus", config.CAMPUS_NAME)
    building = request.args.get("building", "")

    sql = """
        SELECT campus_name, building_name, classroom_name, period, date
        FROM free_rooms WHERE 1=1
    """
    params = []

    if date:
        sql += " AND date = ?"
        params.append(date)
    if period:
        try:
            params.append(int(period))
        except (ValueError, TypeError):
            return jsonify({"error": "period 必须是整数"}), 400
        sql += " AND period = ?"
    if campus:
        sql += " AND campus_name = ?"
        params.append(campus)
    if building:
        sql += " AND building_name = ?"
        params.append(building)

    sql += " ORDER BY building_name, classroom_name"

    rows = query_db(sql, params)
    for r in rows:
        r["time_range"] = config.PERIODS.get(r["period"], "")

    return jsonify(rows)


@app.route("/api/classrooms/search")
def api_classrooms_search():
    """模糊搜索教室名
    ?q=9-12&campus=泰达&limit=10
    支持：精确匹配 > 教室名包含 > 教学楼+教室号组合匹配
    """
    q = request.args.get("q", "").strip()
    campus = request.args.get("campus", "")
    try:
        limit = int(request.args.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10

    if not q:
        return jsonify([])

    results = []
    sql_params = []

    # 1. 教室名精确匹配
    exact = query_db(
        "SELECT DISTINCT campus_name, building_name, classroom_name "
        "FROM free_rooms WHERE classroom_name = ?"
        + (" AND campus_name = ?" if campus else ""),
        (q,) + ((campus,) if campus else ()),
    )
    results = [(r["campus_name"], r["building_name"], r["classroom_name"], 0) for r in exact]

    # 2. 教室名包含查询词
    like_q = f"%{q}%"
    like_rows = query_db(
        "SELECT DISTINCT campus_name, building_name, classroom_name "
        "FROM free_rooms WHERE classroom_name LIKE ?"
        + (" AND campus_name = ?" if campus else "")
        + " LIMIT ?",
        (like_q,) + ((campus,) if campus else ()) + (limit,),
    )
    for r in like_rows:
        key = (r["campus_name"], r["building_name"], r["classroom_name"])
        if key not in {(x[0], x[1], x[2]) for x in results}:
            results.append((r["campus_name"], r["building_name"], r["classroom_name"], 1))

    # 3. 智能解析查询词：如 "9-12" → 教学楼 "9-" 中房间号含 "12"
    import re
    m = re.match(r'^(\d+)[-—](\d+.*)$', q)
    if m:
        bld_prefix = m.group(1)
        room_part = m.group(2)
        # 直接一条 SQL：教学楼匹配 + 教室名匹配
        smart_rows = query_db(
            "SELECT DISTINCT campus_name, building_name, classroom_name "
            "FROM free_rooms "
            "WHERE (building_name LIKE ? OR building_name = ? OR building_name LIKE ?)"
            + (" AND campus_name = ?" if campus else ""),
            (f"%{bld_prefix}%", f"{bld_prefix}-", f"{bld_prefix}号楼%",
             *((campus,) if campus else ())),
        )
        for r in smart_rows:
            key = (r["campus_name"], r["building_name"], r["classroom_name"])
            if key not in {(x[0], x[1], x[2]) for x in results}:
                cname = r["classroom_name"].lower()
                if room_part.lower() in cname or cname.startswith(room_part.lower()):
                    results.append((r["campus_name"], r["building_name"], r["classroom_name"], 2))
        # 第二优先级：教室名 LIKE 包含完整查询词的房间
        more_rows = query_db(
            "SELECT DISTINCT campus_name, building_name, classroom_name "
            "FROM free_rooms "
            "WHERE classroom_name LIKE ?"
            + (" AND campus_name = ?" if campus else ""),
            (f"%{q}%", *((campus,) if campus else ())),
        )
        for r in more_rows:
            key = (r["campus_name"], r["building_name"], r["classroom_name"])
            if key not in {(x[0], x[1], x[2]) for x in results}:
                results.append((r["campus_name"], r["building_name"], r["classroom_name"], 3))

    # 4. 回退：教学楼名包含查询词
    if len(results) < 3 and campus:
        bld_rows = query_db(
            "SELECT DISTINCT campus_name, building_name, classroom_name "
            "FROM free_rooms "
            "WHERE building_name LIKE ? AND campus_name = ?",
            (like_q, campus),
        )
        for r in bld_rows:
            key = (r["campus_name"], r["building_name"], r["classroom_name"])
            if key not in {(x[0], x[1], x[2]) for x in results}:
                results.append((r["campus_name"], r["building_name"], r["classroom_name"], 4))

    # 5. 回退：教室名以查询词开头
    if len(results) < 3 and campus:
        start_rows = query_db(
            "SELECT DISTINCT campus_name, building_name, classroom_name "
            "FROM free_rooms "
            "WHERE classroom_name LIKE ? AND campus_name = ?",
            (f"{q}%", campus),
        )
        for r in start_rows:
            key = (r["campus_name"], r["building_name"], r["classroom_name"])
            if key not in {(x[0], x[1], x[2]) for x in results}:
                results.append((r["campus_name"], r["building_name"], r["classroom_name"], 5))

    # 格式化输出
    output = []
    for campus_name, building_name, classroom_name, match_type in results[:limit]:
        output.append({
            "campus_name": campus_name,
            "building_name": building_name,
            "classroom_name": classroom_name,
            "full_name": f"{building_name}{classroom_name}",
            "match_type": match_type,  # 0=exact, 1=like, 2=smart-decompose, 3=full-like, 4=bld-like, 5=prefix
        })

    return jsonify(output)


@app.route("/api/classroom/<name>/slots")
def api_classroom_slots(name):
    """查询某教室在某日全部空闲节次
    ?date=2026-05-23&campus=泰达
    """
    date = request.args.get("date", "")
    campus = request.args.get("campus", config.CAMPUS_NAME)

    if not date:
        return jsonify({"error": "需要 date 参数"}), 400

    # 先检查教室是否存在于数据库（任一日期）
    exists = query_db(
        "SELECT 1 FROM free_rooms "
        "WHERE classroom_name = ? AND campus_name = ? LIMIT 1",
        (name, campus),
    )
    if not exists:
        # 返回相似教室建议
        like_q = f"%{name}%"
        suggestions = query_db(
            "SELECT DISTINCT building_name, classroom_name FROM free_rooms "
            "WHERE classroom_name LIKE ? AND campus_name = ? "
            "ORDER BY classroom_name LIMIT 6",
            (like_q, campus),
        )
        # 也尝试教学楼前缀匹配
        import re as _re
        m = _re.match(r'^(\d+)[-—](\d+.*)$', name)
        if m and len(suggestions) < 5:
            bld_prefix = m.group(1)
            room_part = m.group(2)
            more = query_db(
                "SELECT DISTINCT building_name, classroom_name FROM free_rooms "
                "WHERE (building_name LIKE ? OR building_name = ?)"
                " AND classroom_name LIKE ? AND campus_name = ? "
                "ORDER BY classroom_name LIMIT ?",
                (f"%{bld_prefix}%", f"{bld_prefix}-", f"%{room_part}%", campus, 10 - len(suggestions)),
            )
            suggestions.extend(more)

        sug_list = [
            {"building_name": r["building_name"], "classroom_name": r["classroom_name"],
             "full_name": f"{r['building_name']}{r['classroom_name']}"}
            for r in suggestions[:8]
        ]
        return jsonify({
            "error": f"找不到 '{name}'",
            "detail": "名称不完全匹配，以下是相似结果",
            "suggestions": sug_list,
        }), 404

    free_rows = query_db(
        "SELECT period FROM free_rooms "
        "WHERE classroom_name = ? AND date = ? AND campus_name = ? "
        "ORDER BY period",
        (name, date, campus),
    )

    # 如果该日期没有任何空闲记录，检查日期本身是否有数据
    if not free_rows:
        date_has_data = query_db(
            "SELECT 1 FROM free_rooms WHERE date = ? AND campus_name = ? LIMIT 1",
            (date, campus),
        )
        if not date_has_data:
            return jsonify({"error": f"{date} 暂无爬取数据，请先运行爬虫"}), 404

    free_set = {r["period"] for r in free_rows}
    free_periods = [
        {"period": p, "time_range": config.PERIODS[p]}
        for p in sorted(free_set)
    ]
    busy_periods = [
        {"period": p, "time_range": t}
        for p, t in config.PERIODS.items()
        if p not in free_set
    ]

    return jsonify({
        "classroom": name,
        "date": date,
        "campus": campus,
        "free_periods": free_periods,
        "busy_periods": busy_periods,
        "free_count": len(free_periods),
        "total_periods": len(config.PERIODS),
    })


@app.route("/api/free-classrooms-in-range")
def api_free_classrooms_in_range():
    """查询某时间范围内始终空闲的教室
    ?date=2026-05-23&start_period=3&end_period=5&campus=泰达
    """
    date = request.args.get("date", "")
    try:
        start = int(request.args.get("start_period", 1))
        end = int(request.args.get("end_period", 13))
    except (ValueError, TypeError):
        return jsonify({"error": "start_period 和 end_period 必须是整数"}), 400
    campus = request.args.get("campus", config.CAMPUS_NAME)
    building = request.args.get("building", "")

    if not date:
        return jsonify({"error": "需要 date 参数"}), 400

    # 起始节次大于结束节次时，交换以避免 period_count 为负、
    # SQL 的 BETWEEN 区间反转导致静默返回空结果
    if start > end:
        start, end = end, start

    period_count = end - start + 1
    sql = """
        SELECT building_name, classroom_name,
               GROUP_CONCAT(period, ',') as periods
        FROM free_rooms
        WHERE date = ? AND campus_name = ? AND period BETWEEN ? AND ?
    """
    params = [date, campus, start, end]

    if building:
        sql += " AND building_name = ?"
        params.append(building)

    sql += """
        GROUP BY building_name, classroom_name
        HAVING COUNT(DISTINCT period) = ?
        ORDER BY building_name, classroom_name
    """
    params.append(period_count)

    rows = query_db(sql, params)
    for r in rows:
        r["period_list"] = [int(p) for p in r["periods"].split(",")]

    return jsonify(rows)


# ── 前端入口 ──

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── 启动 ──

if __name__ == "__main__":
    print("TUST 空闲教室 API 启动 → http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
