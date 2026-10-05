"""浏览器 CDP 复用层 —— 通用版

核心思路（为什么不用账号密码）：
    教务系统登录一般有验证码、CAS 跳转、设备绑定，脚本模拟登录既脆弱又
    要碰用户密码。我们改成「复用你已经登录好的那个浏览器窗口」——
    通过 Chrome DevTools Protocol 连进去，借它的会话去发请求。
    全程不碰密码、不存 Cookie 文件，比存账号安全得多。

本模块只做三件事：探测端口有没有活着、拉起带调试端口的浏览器、连上去。
具体浏览器路径和 profile 目录由适配器的 BrowserSpec 决定（各校可不同）。
"""
from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request

from .adapter import BrowserSpec

# 进程内单实例保护：避免同一进程里并发重复拉起浏览器
_launching = False


def _port_probe(url: str, timeout: float = 1.5) -> bool:
    """探测 CDP 端口是否活着（/json/version 能返回即为就绪）"""
    try:
        with urllib.request.urlopen(f"{url}/json/version", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def cdp_available(spec: BrowserSpec) -> bool:
    """调试端口是否已经在跑"""
    return _port_probe(spec.cdp_endpoint)


def launch_browser(spec: BrowserSpec, wait_seconds: int = 25) -> bool:
    """以调试端口启动浏览器（用专属 profile，不碰用户日常目录）

    返回是否成功在 wait_seconds 内等到端口就绪。
    """
    global _launching
    if _launching:
        return cdp_available(spec)

    if not spec.exe_path or not os.path.exists(spec.exe_path):
        return False

    os.makedirs(spec.profile_dir, exist_ok=True)
    _launching = True
    try:
        subprocess.Popen(
            [
                spec.exe_path,
                f"--remote-debugging-port={spec.debug_port}",
                f"--user-data-dir={spec.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=Translate,OptimizationHints",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _port_probe(spec.cdp_endpoint, timeout=1.0):
                return True
            time.sleep(1)
        return False
    finally:
        _launching = False


def ensure_browser(spec: BrowserSpec, wait_seconds: int = 25) -> bool:
    """确保浏览器调试模式可用：活着就直接用，没活就拉起来"""
    if cdp_available(spec):
        return True
    return launch_browser(spec, wait_seconds=wait_seconds)


def connect_cdp(spec: BrowserSpec):
    """连到 CDP，返回一个已连接的浏览器对象（需要 playwright）

    这个函数单独隔离，是为了让整个框架在没有装 playwright 的机器上
    也能 import、也能跑单元测试（只有真开爬时才会调到这里）。
    """
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 - 延迟导入

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(spec.cdp_endpoint)
    # 把 playwright 上下文挂到 browser 上，方便调用方统一 stop()
    browser._campusfree_pw = pw  # type: ignore[attr-defined]
    return browser


def pick_context(browser):
    """从已连接的浏览器里挑一个可用上下文（优先复用已登录的那个）"""
    contexts = browser.contexts
    if contexts:
        return contexts[0]
    return browser.new_context()


def open_entry_page(browser, spec: BrowserSpec, entry_url: str, timeout_ms: int = 15000):
    """打开空闲教室首页并等待片刻，返回 page 对象"""
    ctx = pick_context(browser)
    page = ctx.new_page()
    page.goto(entry_url, timeout=timeout_ms)
    page.wait_for_timeout(2000)
    return page


def login_hint_text(spec: BrowserSpec) -> str:
    """登录态失效时的提示文本"""
    target = spec.login_url or "教务系统"
    return f"浏览器未登录，请在该窗口里登录一次：{target}"
