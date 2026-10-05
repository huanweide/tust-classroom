"""Edge CDP 公共模块（IMP-056）

统一常量定义、调试端口探测与启动逻辑，供 crawler_playwright.py 与
keepalive.py 复用，避免两文件各写一份常量与探测代码。

⚠ 新版 Edge（Chromium 136+）安全限制：
   DevTools 远程调试端口不允许绑定「默认 User Data 目录」，
   报错 "DevTools remote debugging requires a non-default data directory"。
   因此本项目改用专用 Profile 目录 edge-cdp-profile —— 首次使用时在
   该窗口中登录一次 URP，登录态持久化在专用目录里，之后爬虫/保活
   自动复用，不再依赖日常使用的 Edge Profile。
"""
import os
import subprocess
import time
import urllib.request

# 专用 CDP Profile 目录（非默认目录，绕开新版 Edge 调试端口安全限制）
EDGE_USER_DATA = os.path.expandvars(
    r"%LOCALAPPDATA%\tust-classroom\edge-cdp-profile"
)
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
URP_LOGIN_URL = "http://jwxtxs.tust.edu.cn:46110"
DEBUG_PORT = 9222
# 明确用 IPv4 回环地址,避免 Playwright(Node) 把 localhost 解析到 ::1 导致连不上
CDP_ENDPOINT = f"http://127.0.0.1:{DEBUG_PORT}"

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
    """确保 Edge 以调试模式运行（单实例保护），复用专用 Profile。

    - 端口已就绪：直接返回 True（不重复拉起）。
    - 端口不可用：拉起一个带调试端口的专用 Profile Edge 实例并等待就绪。
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
        print("[CDP] Edge 调试实例未运行，正在启动专用 Profile...")
        # 清理残留 Edge 进程：沙箱回收长任务时会遗留 msedge 实例，
        # 累积占用资源会导致新拉起的 Edge 立即崩溃(TargetClosedError)。
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "msedge.exe"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
        except Exception:
            pass
        time.sleep(1)  # 等残留进程退出释放资源
        os.makedirs(EDGE_USER_DATA, exist_ok=True)
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
