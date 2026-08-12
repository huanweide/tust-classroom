"""Edge CDP 公共模块（IMP-056）

统一常量定义、调试端口探测与启动逻辑，供 crawler_playwright.py 与
keepalive.py 复用，避免两文件各写一份常量与探测代码。
"""
import os
import subprocess
import time
import urllib.request

EDGE_USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DEBUG_PORT = 9222
CDP_ENDPOINT = f"http://localhost:{DEBUG_PORT}"

# 进程内单实例保护：避免同一进程内并发重复拉起调试实例
_launching = False


def cdp_available():
    """探测 Edge 调试端口是否可用（不重启 Edge）"""
    try:
        urllib.request.urlopen(f"{CDP_ENDPOINT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def _wait_ready(timeout=15):
    """轮询等待 CDP 端口就绪"""
    for _ in range(timeout):
        time.sleep(1)
        if cdp_available():
            return True
    return False


def ensure_edge_debug():
    """确保 Edge 以调试模式运行（单实例保护），复用用户 Profile。

    - 端口已就绪：直接返回 True（不重复拉起）。
    - 端口不可用：先给出保存提醒，再拉起一个带调试端口的 Edge 实例并等待就绪。
    - 单实例保护：端口不可用时才启动；进程内用 _launching 锁避免并发重复启动。
    """
    global _launching
    if cdp_available():
        return True

    if _launching:
        # 已有其它调用在启动中，等待其就绪即可
        return _wait_ready()

    _launching = True
    try:
        print("[CDP] Edge 未以调试模式运行，正在启动...")
        print("      ⚠ 请保存 Edge 中未完成的表单/文档，5 秒后自动重启")
        time.sleep(5)

        subprocess.Popen(
            [
                EDGE_EXE,
                f"--remote-debugging-port={DEBUG_PORT}",
                f"--user-data-dir={EDGE_USER_DATA}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return _wait_ready()
    finally:
        _launching = False
