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
import subprocess
import sys
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

import config

EDGE_USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DEBUG_PORT = 9222
CDP_ENDPOINT = f"http://localhost:{DEBUG_PORT}"


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
        """确保 Edge 以调试模式运行，复用用户 Profile"""
        try:
            import urllib.request
            urllib.request.urlopen(f"{CDP_ENDPOINT}/json/version", timeout=2)
            print("[CDP] Edge 调试端口已就绪")
            return True
        except Exception:
            pass

        print("[CDP] Edge 未以调试模式运行，正在启动...")
        print("      ⚠ 请保存 Edge 中未完成的表单/文档，5 秒后自动重启")
        time.sleep(5)

        # 关闭现有 Edge（仅调试端口进程，避免误杀）

        # 用用户真实 Profile 启动 Edge + 调试端口
        subprocess.Popen([
            EDGE_EXE,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={EDGE_USER_DATA}",
            "--no-first-run",
            "--no-default-browser-check",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 等待 CDP 就绪
        for _ in range(15):
            time.sleep(1)
            try:
                import urllib.request
                urllib.request.urlopen(f"{CDP_ENDPOINT}/json/version", timeout=2)
                print("[CDP] Edge 调试端口就绪")
                return True
            except Exception:
                pass

        print("[CDP] Edge 启动超时")
        return False

    def run(self, date_str=None, dayoffset=1, day_range=None):
        """爬取空闲教室

        dayoffset: 单天模式，相对今天的天数偏移（默认 1=明天）
        day_range: 范围模式，(start, end)，如 (0, 6) = 今天~6天后
                   指定后覆盖 dayoffset
        """
        if day_range is not None:
            offsets = list(range(day_range[0], day_range[1] + 1))
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

                print(f"\n{'#'*50}")
                print(f"# 日期 [{day_idx+1}/{len(offsets)}] {d} (dayoffset={dayoff})")
                print(f"{'#'*50}")

                # 续传：如果该日已有数据且非单天模式，跳过
                if len(offsets) > 1:
                    with sqlite3.connect(config.DB_PATH) as conn:
                        cnt = conn.execute(
                            "SELECT COUNT(*) FROM free_rooms WHERE date = ?", (d,)
                        ).fetchone()[0]
                    if cnt > 0:
                        print(f"[SKIP] {d} 已有 {cnt} 条记录，跳过")
                        total += cnt
                        continue

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
            """(campus_code) => {
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
                """(args) => {
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
            """(args) => {
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
