"""GitHub Pages 专用转发 —— 让浏览器访问 huanweide.github.io

本机 DNS 解析不了 *.github.io，但 185.199.108-111.153 直连正常。
浏览器配 --proxy-server=http://127.0.0.1:8895 即可访问线上站点。

用法：
    python pages_proxy.py           # 前台，8895 → 185.199.108.153:443
    python pages_proxy.py --bg      # 后台
"""
import argparse
import os
import socket
import subprocess
import sys
import threading

PAGES_IPS = ["185.199.108.153", "185.199.109.153",
             "185.199.110.153", "185.199.111.153"]
PORT = 8895
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pages_proxy.pid")


def pipe(src, dst):
    try:
        while True:
            d = src.recv(65536)
            if not d:
                break
            dst.sendall(d)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except OSError:
                pass


def handle(client, ip):
    """必须回 CONNECT 确认再透传，否则客户端等到超时（HTTP 000）。"""
    try:
        client.settimeout(15)
        first = b""
        while b"\r\n\r\n" not in first:
            c = client.recv(4096)
            if not c:
                client.close()
                return
            first += c
            if len(first) > 16384:
                break
        client.settimeout(None)
        head = first.split(b"\r\n", 1)[0].decode("latin-1", "ignore")
        if head.upper().startswith("CONNECT"):
            up = socket.create_connection((ip, 443), timeout=20)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            rest = first.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in first else b""
            if rest:
                up.sendall(rest)
        else:
            up = socket.create_connection((ip, 80), timeout=20)
            up.sendall(first)
    except OSError:
        try:
            client.close()
        except OSError:
            pass
        return
    threading.Thread(target=pipe, args=(client, up), daemon=True).start()
    threading.Thread(target=pipe, args=(up, client), daemon=True).start()


def pick():
    """并行探测（串行最坏 4×6=24 秒，脚本像卡死）。"""
    import concurrent.futures

    def probe(ip):
        try:
            s = socket.create_connection((ip, 443), timeout=6)
            s.close()
            return True
        except OSError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(probe, ip): ip for ip in PAGES_IPS}
        for fut in concurrent.futures.as_completed(futs, timeout=15):
            if fut.result():
                return futs[fut]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args()

    if a.stop:
        if os.path.exists(PID_FILE):
            pid = open(PID_FILE).read().strip()
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
            os.remove(PID_FILE)
            print(f"已停止（PID {pid}）")
        else:
            print("没有运行中的进程")
        return 0

    ip = pick()
    if not ip:
        print("[错误] 所有 Pages IP 不可达")
        return 1

    if a.bg:
        p = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--port", str(a.port)],
            creationflags=subprocess.DETACHED_PROCESS | 0x00000008,
            close_fds=True,
            stdout=open(os.path.join(os.path.dirname(PID_FILE), ".pages_proxy.log"), "w"),
            stderr=subprocess.STDOUT)
        open(PID_FILE, "w").write(str(p.pid))
        print(f"后台运行：127.0.0.1:{a.port} → {ip}:443（PID {p.pid}）")
        return 0

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", a.port))
    srv.listen(128)
    open(PID_FILE, "w").write(str(os.getpid()))
    print(f"Pages 转发中：127.0.0.1:{a.port} → {ip}:443（Ctrl+C 停）")
    try:
        while True:
            c, _ = srv.accept()
            threading.Thread(target=handle, args=(c, ip), daemon=True).start()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.close()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
