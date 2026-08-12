"""URP 会话保活 — 定期 ping 教务系统防止 Session 空闲超时

原理：URP 服务端 Session 有"空闲超时"机制（比如 30 分钟无请求就销毁）。
本脚本每 25 分钟通过 Edge CDP 发一次 API 请求，模拟活人在浏览，
把超时倒计时不断重置。

用法：
  python keepalive.py          # 前台运行
  python keepalive.py --once   # 只 ping 一次（配合任务计划程序用）
"""
import argparse
import os
import signal
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

# 优雅退出标志：收到 SIGINT/SIGTERM 后置位，run_loop 在下个检查点退出
_stop = False


def _request_stop(signum, frame):
    global _stop
    _stop = True
    log(f"收到信号 {signum}，请求停止保活循环...")


signal.signal(signal.SIGINT, _request_stop)
signal.signal(signal.SIGTERM, _request_stop)

EDGE_USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DEBUG_PORT = 9222
CDP_ENDPOINT = f"http://localhost:{DEBUG_PORT}"
URP_BASE = "http://jwxtxs.tust.edu.cn:46110"
PING_INTERVAL = 25 * 60  # 25 分钟
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "keepalive.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def cdp_available():
    """检查 Edge 调试端口是否可用（不重启 Edge）"""
    import urllib.request
    try:
        urllib.request.urlopen(f"{CDP_ENDPOINT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def ping_urp():
    """连接 Edge，ping URP API 保持会话活跃"""
    if not cdp_available():
        log("Edge 调试端口未开启，跳过保活")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
            contexts = browser.contexts
            if not contexts:
                log("无浏览器上下文，跳过")
                browser.close()
                return False

            context = contexts[0]
            page = context.new_page()

            # 用轻量 API 请求替代加载完整页面，更省资源
            result = page.evaluate("""
                async () => {
                    try {
                        const resp = await fetch(
                            '/student/teachingResources/freeClassroom/queryCodeTeaBuildingList',
                            {
                                method: 'POST',
                                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                body: 'xqh=02'
                            }
                        );
                        return {ok: resp.ok, status: resp.status};
                    } catch (e) {
                        return {ok: false, error: e.message};
                    }
                }
            """)

            page.close()
            browser.close()

            if result.get("ok"):
                log("保活 ping 成功")
                return True
            elif result.get("status") == 302:
                # 302 重定向 → 被 CAS 拦截 → Session 已过期
                log("Session 已过期（302 → CAS），需要重新登录")
                return False
            else:
                log(f"保活 ping 异常响应: {result}")
                return False

    except Exception as e:
        log(f"保活异常: {e}")
        return False


def run_loop():
    """前台循环模式"""
    log("URP 保活启动")
    log(f"间隔: {PING_INTERVAL // 60} 分钟")
    log(f"Edge 调试端口: {CDP_ENDPOINT}")

    success = 0
    fail = 0

    while not _stop:
        try:
            if ping_urp():
                success += 1
            else:
                fail += 1
            log(f"累计 成功={success} 失败={fail}")
        except Exception as e:
            log(f"未预期错误: {e}")
            fail += 1

        if _stop:
            break

        # 分段 sleep，保证及时响应停止信号（而非一次性睡满 25 分钟）
        for _ in range(PING_INTERVAL // 5):
            if _stop:
                break
            time.sleep(5)

    log("URP 保活循环已优雅停止")


def run_once():
    """单次模式（配合 Windows 任务计划程序）"""
    ping_urp()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="URP 会话保活")
    parser.add_argument("--once", action="store_true", help="只 ping 一次后退出")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        run_loop()
