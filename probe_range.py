"""快速探测教务系统可查询的 dayplus 上限（有课的最大时间）

复用已登录 Edge 的会话，对若干 dayplus 采样，统计该日空闲教室数，
判断「有数据的最远一天」，从而确定学期边界。
"""
import sys
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

import config
from edge_cdp import CDP_ENDPOINT, ensure_edge_debug
from crawler_playwright import TUSTCrawlerPW

PROBES = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]


def main():
    print("[probe] 确保 Edge 调试实例...", flush=True)
    if not ensure_edge_debug():
        print("[probe] Edge 启动失败", flush=True)
        sys.exit(1)

    c = TUSTCrawlerPW()
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_ENDPOINT)
        ctx = b.contexts[0] if b.contexts else b.new_context()
        page = ctx.new_page()
        print("[probe] 访问空闲教室页...", flush=True)
        page.goto(
            f"{config.BASE_URL}/student/teachingResources/freeClassroom/index",
            timeout=15000,
        )
        page.wait_for_timeout(2000)
        if "authserver" in page.url or "login" in page.url.lower():
            print("[probe] 未登录! Edge Profile 无 URP 登录态，无法在沙箱爬取", flush=True)
            b.close()
            sys.exit(2)
        print("[probe] 登录态 OK", flush=True)

        campuses = c._get_campuses(page)
        if not campuses:
            campuses = c._discover_campuses(page)
        print(f"[probe] 校区: {campuses}", flush=True)
        cc, cn = campuses[0]
        buildings = c._get_buildings(page, cc)
        print(f"[probe] {cn} 教学楼数: {len(buildings)}", flush=True)

        sample = buildings[:8]  # 取前 8 栋楼估算
        print(f"[probe] 采样 {len(sample)} 栋楼 × 13 节次", flush=True)

        for dp in PROBES:
            total = 0
            for bd in sample:
                c._set_building(page, f"{cc}_{bd[0]}", cn)
                for period in range(1, 14):
                    rooms = c._fetch_period(page, period, bd[1], dp)
                    total += len(rooms)
            d = (datetime.now() + timedelta(days=dp)).strftime("%Y-%m-%d")
            print(f"[probe] dayplus={dp:3d} {d} rooms={total}", flush=True)
            time.sleep(0.2)

        b.close()
    print("[probe] 完成", flush=True)


if __name__ == "__main__":
    main()
