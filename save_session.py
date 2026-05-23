"""打开独立 Edge 窗口 → 手动登录 → Cookies 持久化到浏览器 Profile

用 launch_persistent_context 保持浏览器 Profile 目录，
登录后的 Cookies/Session 自动持久化，爬虫复用同一目录。
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "browser_profile")
URP_URL = "http://jwxtxs.tust.edu.cn:46110"


def main():
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    print("=" * 55)
    print("|  即将打开 Edge 浏览器窗口                          |")
    print("|  1. 输入学号 + 密码                                |")
    print("|  2. 填写短信验证码                                 |")
    print("|  3. 等页面跳到教务系统首页                          |")
    print("|  脚本自动检测登录成功，关闭浏览器                    |")
    print("=" * 55)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel="msedge",
            headless=False,
        )
        page = context.new_page()
        page.goto(URP_URL)
        print(f"\n当前页面: {page.url[:80]}...")

        # 轮询检测登录成功（5分钟超时）
        for sec in range(300):
            time.sleep(1)
            url = page.url

            logged_in = (
                "jwxtxs" in url
                and "authserver" not in url
                and "login" not in url.lower()
            )
            if logged_in:
                print(f"\n检测到已登录! ({sec}秒)")
                break

            if sec == 15:
                print(f"等待中... 当前: {url[:80]}")
            if sec == 60:
                print(f"已等 1 分钟，请确认浏览器中是否已完成登录")
        else:
            print(f"超时 (3分钟)。当前页面: {url}")
            print("仍保留浏览器 Profile（可能未登录）")

        print(f"\n浏览器 Profile 已保存: {USER_DATA_DIR}")
        context.close()


if __name__ == "__main__":
    main()
