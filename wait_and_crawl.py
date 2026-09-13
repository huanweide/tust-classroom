"""一键全自动更新 — 等待 URP 登录后自动爬取全学期

流程:
1. 拉起专用 CDP Edge(若未运行)
2. 打开 URP 登录页,置前
3. 每 5 秒轮询登录状态(最多等 30 分钟)
4. 检测到登录成功 → 调用 crawler 爬全学期 40 天(双校区自动发现)
5. 导出静态 JSON → git commit + push → Pages 自动刷新

用法: py -3.14 wait_and_crawl.py
"""
import subprocess
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

import config
from edge_cdp import CDP_ENDPOINT, URP_LOGIN_URL, ensure_edge_debug

FREE_INDEX = f"{config.BASE_URL}/student/teachingResources/freeClassroom/index"
WAIT_LOGIN_TIMEOUT = 30 * 60  # 最多等 30 分钟
POLL_INTERVAL = 5


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def is_logged_in(page):
    """检查当前会话是否已登录 URP(访问空闲教室页不被重定向到 CAS)"""
    try:
        page.goto(FREE_INDEX, timeout=15000)
        page.wait_for_timeout(1000)
        url = page.url.lower()
        return "authserver" not in url and "login" not in url
    except Exception as e:
        log(f"[探测] 访问异常: {e}")
        return False


def main():
    log("=== 一键全自动更新启动 ===")

    if not ensure_edge_debug():
        log("[错误] 无法启动 Edge 调试实例")
        sys.exit(1)
    log("[CDP] Edge 调试实例就绪")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()

        if is_logged_in(page):
            log("[登录] 检测到已有登录态,跳过等待")
        else:
            log("[登录] 打开登录页,等待用户登录(最多等 30 分钟)...")
            page.goto(URP_LOGIN_URL, timeout=20000)
            try:
                page.bring_to_front()
            except Exception:
                pass

            deadline = time.time() + WAIT_LOGIN_TIMEOUT
            ok = False
            while time.time() < deadline:
                time.sleep(POLL_INTERVAL)
                if is_logged_in(page):
                    ok = True
                    break
            if not ok:
                log("[超时] 30 分钟内未检测到登录,退出")
                sys.exit(1)
            log("[登录] 登录成功!")

        browser.close()

    # ── 爬取全学期 40 天 ──
    log("[爬取] 自动边界探测：从今天爬到连续无数据(学期结束)即停(双校区)...")
    r = subprocess.run(
        [sys.executable, "crawler_playwright.py", "--auto"],
        capture_output=True, text=True,
    )
    tail = (r.stdout or "").strip().splitlines()[-5:]
    for line in tail:
        log(f"  {line}")
    if r.returncode != 0:
        log(f"[错误] 爬取失败 exit={r.returncode}")
        for line in (r.stderr or "").strip().splitlines()[-5:]:
            log(f"  {line}")
        sys.exit(1)

    # ── 导出 ──
    log("[导出] SQLite → 静态 JSON...")
    r = subprocess.run([sys.executable, "export_static.py"], capture_output=True, text=True)
    for line in (r.stdout or "").strip().splitlines()[-8:]:
        log(f"  {line}")

    # ── 提交推送 ──
    log("[推送] git commit + push...")
    subprocess.run(["git", "add", "static/"], capture_output=True)
    c = subprocess.run(
        ["git", "commit", "-m", f"auto: full-semester data update {datetime.now():%Y-%m-%d}"],
        capture_output=True, text=True,
    )
    if "nothing to commit" in (c.stdout + c.stderr):
        log("[推送] 数据无变化,跳过提交")
    else:
        pr = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        if pr.returncode != 0:
            log(f"[错误] push 失败: {(pr.stderr or '')[:200]}")
            sys.exit(1)
        log("[推送] main 已推送,Pages 1-2 分钟内生效")

    log("=== 全部完成! 手机访问: https://huanweide.github.io/tust-classroom/ ===")


if __name__ == "__main__":
    main()
