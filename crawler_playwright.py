"""TUST 空闲教室爬虫 — CDP 复用登录态版

通过 Chrome DevTools Protocol 连到用户正在运行的 Edge，
复用 Edge 已有的 URP 登录 Cookies，不再需要每次手动登录。

用法：
  1. 先确保 Edge 以调试模式启动（运行 launch_edge_debug.bat）
  2. python crawler_playwright.py
"""
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

import config
from edge_cdp import CDP_ENDPOINT, ensure_edge_debug  # IMP-056：统一 CDP 常量与启动逻辑


class TUSTCrawlerPW:
    def __init__(self):
        self._ensure_db()

    def _ensure_db(self):
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS free_rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campus_name TEXT NOT NULL,
                    building_name TEXT NOT NULL,
                    classroom_name TEXT NOT NULL,
                    period INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    UNIQUE(campus_name, building_name, classroom_name, period, date)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_free_rooms_query
                ON free_rooms(campus_name, building_name, period, date)
            """)

    def clear_today_cache(self, date_str):
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute("DELETE FROM free_rooms WHERE date = ?", (date_str,))

    def _ensure_edge_debug(self):
        """确保 Edge 以调试模式运行，复用用户 Profile（委托 edge_cdp.ensure_edge_debug）"""
        return ensure_edge_debug()

    def run(self, date_str=None, dayoffset=1, day_range=None, auto=False):
        """爬取空闲教室

        dayoffset: 单天模式，相对今天的天数偏移（默认 1=明天）
        day_range: 范围模式，(start, end)，如 (0, 6) = 今天~6天后
                   指定后覆盖 dayoffset
        auto:      自动边界探测模式，从今天(dayplus=0)往后爬，
                   连续 STOP_THRESHOLD 天无数据即判定学期边界并停止。
                   同时自动清除「今天之前」的旧学期数据，只保留本次爬取。
        """
        MAX_DAYS = 140          # 自动模式天数上限：覆盖当前秋季学期(9月~次年1月底)
        STOP_THRESHOLD = 14     # 连续无数据天数阈值（容忍国庆等长假期）

        if auto:
            # 清掉今天之前的旧学期数据，只保留「本次爬取」（删旧留新）
            today = datetime.now().strftime("%Y-%m-%d")
            with sqlite3.connect(config.DB_PATH) as conn:
                conn.execute("DELETE FROM free_rooms WHERE date < ?", (today,))
            print(f"[清旧] 已删除 {today} 之前的旧学期数据")

        if day_range is not None:
            offsets = list(range(day_range[0], day_range[1] + 1))
        elif auto:
            offsets = list(range(0, MAX_DAYS))
        else:
            offsets = [dayoffset]

        total = 0

        if not self._ensure_edge_debug():
            print("[错误] 无法启动 Edge 调试模式")
            sys.exit(1)

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
            contexts = browser.contexts
            if not contexts:
                context = browser.new_context()
            else:
                context = contexts[0]

            page = context.new_page()

            print("[爬取] 加载空闲教室页面...")
            page.goto(
                f"{config.BASE_URL}/student/teachingResources/freeClassroom/index",
                timeout=15000,
            )
            page.wait_for_timeout(2000)

            if "authserver" in page.url or "login" in page.url.lower():
                print("[错误] Edge 未登录 URP，请先在 Edge 中访问并登录教务系统")
                print("       http://jwxtxs.tust.edu.cn:46110")
                browser.close()
                sys.exit(1)

            print("[登录] 已通过 Edge Profile 复用登录态 [OK]")

            campuses = self._get_campuses(page)
            if not campuses:
                print("[警告] 未获取到校区列表，用试探法发现校区")
                campuses = self._discover_campuses(page)

            print(f"[爬取] {len(campuses)} 个校区: {[(c[0], c[1]) for c in campuses]}")

            for day_idx, dayoff in enumerate(offsets):
                if date_str and day_idx == 0:
                    d = date_str
                else:
                    d = (datetime.now() + timedelta(days=dayoff)).strftime("%Y-%m-%d")
                day_begin = total

                print(f"\n{'#'*50}")
                print(f"# 日期 [{day_idx+1}/{len(offsets)}] {d} (dayoffset={dayoff})")
                print(f"{'#'*50}")

                # 续传（范围模式）：当日已有数据则整日跳过——不 clear_today_cache、不重爬，
                # 避免无谓的 DELETE 与重复爬取（IMP-053）。
                if len(offsets) > 1:
                    with sqlite3.connect(config.DB_PATH) as conn:
                        cnt = conn.execute(
                            "SELECT COUNT(*) FROM free_rooms WHERE date = ?", (d,)
                        ).fetchone()[0]
                    if cnt > 0:
                        print(f"[SKIP] {d} 已有 {cnt} 条记录，整日跳过（不删不重爬）")
                        total += cnt
                        continue

                # 仅当确实需要（重新）爬取当天时才清空缓存
                self.clear_today_cache(d)

                for campus_code, campus_name in campuses:
                    print(f"\n{'='*40}")
                    print(f"[校区] {campus_name} (code={campus_code})")

                    buildings = self._get_buildings(page, campus_code)
                    if not buildings:
                        print(f"  [SKIP] 无教学楼")
                        continue

                    print(f"[教学楼] {len(buildings)} 栋")

                    for idx, (bld_code, bld_name) in enumerate(buildings, 1):
                        position = f"{campus_code}_{bld_code}"
                        print(f"  [{idx}/{len(buildings)}] {bld_name}")

                        ok = self._set_building(page, position, campus_name)
                        if not ok:
                            print(f"    [SKIP] 设置教学楼失败")
                            continue

                        time.sleep(0.3)

                        for period in range(1, 14):
                            try:
                                rooms = self._fetch_period(page, period, bld_name, dayoff)
                                if rooms:
                                    count = self._save_rooms(campus_name, rooms, period, d)
                                    total += count
                            except Exception as e:
                                print(f"    第{period}节 ERR: {e}")

            browser.close()

        print(f"\n[爬取] 完成, 共写入 {total} 条记录")
        return total

    def _discover_campuses(self, page):
        """试探不同 campus code 来发现校区"""
        campuses = []
        for code in ["02", "01"]:
            buildings = self._get_buildings(page, code)
            if buildings:
                name = "泰达" if code == "02" else "河西"
                campuses.append((code, name))
                print(f"  [发现] code={code} → {len(buildings)} 栋楼 → {name}")
        return campuses

    def _get_campuses(self, page):
        """获取校区列表（如果 API 可用）"""
        result = page.evaluate("""
            async () => {
                const resp = await fetch('/student/teachingResources/freeClassroom/queryCodeCampusList', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                });
                if (!resp.ok) return [];
                return await resp.json();
            }
        """)
        campuses = []
        for item in result:
            code = item.get("id") or item.get("code") or item.get("xqh", "")
            name = item.get("text") or item.get("name") or item.get("xqmc", "")
            if code and name:
                name = re.sub(r'[\s\r\n]+', '', name)
                if name:
                    campuses.append((str(code), str(name)))
        return campuses

    def _get_buildings(self, page, campus_code):
        """获取某校区所有教学楼"""
        result = page.evaluate(
            """async (campus_code) => {
                const formData = new URLSearchParams();
                formData.append('xqh', campus_code);
                const resp = await fetch('/student/teachingResources/freeClassroom/queryCodeTeaBuildingList', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: formData.toString()
                });
                if (!resp.ok) return [];
                return await resp.json();
            }""",
            campus_code,
        )
        buildings = []
        for item in result:
            inner = item.get("id", item)
            code = inner.get("teachingBuildingNumber", "")
            name = item.get("teachingBuildingName", "")
            if code and name:
                name = re.sub(r'[\s\r\n]+', '', name)
                if name:
                    buildings.append((code, name))
        return buildings

    def _set_building(self, page, position, campus_name):
        """设置当前查询的教学楼上下文"""
        try:
            result = page.evaluate(
                """async (args) => {
                    const formData = new URLSearchParams();
                    formData.append('position', args.position);
                    formData.append('xqm', args.xqm);
                    const resp = await fetch('/student/teachingResources/freeClassroom/today', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: formData.toString()
                    });
                    return resp.ok;
                }""",
                {"position": position, "xqm": campus_name},
            )
            return result
        except Exception:
            return False

    def _fetch_period(self, page, period, building_name, dayoffset):
        """查询某个节次的空闲教室"""
        result = page.evaluate(
            """async (args) => {
                try {
                    const resp = await fetch(
                        '/student/teachingResources/freeClassroom/today/' + args.period,
                        {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: 'dayplus=' + args.dayoffset
                        }
                    );
                    if (!resp.ok) return {error: 'HTTP ' + resp.status};
                    return await resp.json();
                } catch (e) {
                    return {error: e.message};
                }
            }""",
            {"period": period, "dayoffset": dayoffset},
        )

        if "error" in result:
            return []

        rooms = result.get("spareroomObjList", [])
        output = []
        for building in rooms:
            bname = building.get("acmcBuildingName", building_name)
            for room in building.get("claroom", []):
                rname = room.get("classroom", "")
                if rname:
                    output.append({
                        "building_name": bname,
                        "classroom_name": rname,
                    })
        return output

    def _save_rooms(self, campus_name, rooms, period, date_str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            (campus_name, r["building_name"], r["classroom_name"], period, date_str, now)
            for r in rooms
        ]
        if not rows:
            return 0
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.executemany("""
                INSERT OR IGNORE INTO free_rooms
                (campus_name, building_name, classroom_name, period, date, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rows)
            return len(rows)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TUST 空闲教室爬虫 (CDP)")
    parser.add_argument("--range", type=str, default=None,
                        help="日期范围，如 '0-6' 表示今天到6天后（共7天）")
    parser.add_argument("--dayoffset", type=int, default=1,
                        help="单天偏移，默认1=明天")
    args = parser.parse_args()

    crawler = TUSTCrawlerPW()
    if args.range:
        parts = args.range.split("-")
        if len(parts) != 2:
            print(f"[错误] --range 格式应为 '起-止'（如 '0-6'），收到: {args.range!r}",
                  file=sys.stderr)
            sys.exit(2)
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            print(f"[错误] --range 的起止都必须是整数，收到: {args.range!r}",
                  file=sys.stderr)
            sys.exit(2)
        if start > end:
            print(f"[错误] --range 的起止无效，起始({start}) 必须不大于 结束({end})",
                  file=sys.stderr)
            sys.exit(2)
        total = crawler.run(day_range=(start, end))
    else:
        total = crawler.run(dayoffset=args.dayoffset)
    print(f"\n完成! 共 {total} 条空闲教室记录")
