"""本地 TCP 转发 —— 让 git/ssh 绕过 DNS 直连 GitHub IP

用法：
    python dns_bypass_proxy.py            # 前台运行，转发 8891→140.82.113.4:443
    python dns_bypass_proxy.py --bg       # 后台运行
    python dns_bypass_proxy.py --stop     # 停止

原理：
    本机 DNS 解析不了 github.com（教育网 DNS 超时），但 GitHub 的 IP 段直连正常。
    起一个本地 TCP 转发，git 配 http.proxy 指向它，TLS SNI 由 git 自己带，
    服务器端按 SNI 正确响应 —— 等价于直连，只是省掉 DNS 这一步。

配好后：
    git -c http.proxy=http://127.0.0.1:8891 -c https.proxy=http://127.0.0.1:8891 push origin main
"""
import argparse
import os
import socket
import subprocess
import sys
import threading

# GitHub 主要 IP（2026-10-19 实测全部 200）
GITHUB_IPS = ["140.82.113.4", "140.82.112.4", "140.82.112.3",
              "20.205.243.166", "20.27.177.113"]
LISTEN_PORT = 8891
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dns_bypass.pid")


def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try: src.close()
        except OSError: pass
        try: dst.close()
        except OSError: pass


def handle(client, upstream_ip):
    """处理一个客户端连接。

    关键：curl 的 `-x` / git 的 http.proxy 会先发 HTTP CONNECT 隧道请求，
    必须先回 `200 Connection Established` 再开始裸 TCP 管道，
    否则客户端一直等响应直到超时（表现为 HTTP 000）。
    """
    try:
        # 读第一个请求，判断是否 CONNECT
        client.settimeout(15)
        first = b""
        while b"\r\n\r\n" not in first:
            chunk = client.recv(4096)
            if not chunk:
                client.close()
                return
            first += chunk
            if len(first) > 16384:
                break
        client.settimeout(None)

        head = first.split(b"\r\n", 1)[0].decode("latin-1", "ignore")
        if head.upper().startswith("CONNECT"):
            # CONNECT host:port HTTP/1.1 → 回确认，然后透传
            upstream = socket.create_connection((upstream_ip, 443), timeout=20)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            # 去掉已读的 CONNECT 头，剩余字节（通常没有）透传
            rest = first.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in first else b""
            if rest:
                upstream.sendall(rest)
        else:
            # 非 CONNECT（极少见，如 git 的 http.proxy 直连）→ 直接透传首个请求
            upstream = socket.create_connection((upstream_ip, 80), timeout=20)
            upstream.sendall(first)
    except OSError:
        try: client.close()
        except OSError: pass
        return

    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()


def pick_ip():
    """挑一个当前能连通的 GitHub IP。"""
    for ip in GITHUB_IPS:
        try:
            s = socket.create_connection((ip, 443), timeout=6)
            s.close()
            return ip
        except OSError:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", action="store_true", help="后台运行")
    ap.add_argument("--stop", action="store_true", help="停止")
    ap.add_argument("--port", type=int, default=LISTEN_PORT)
    args = ap.parse_args()

    if args.stop:
        if os.path.exists(PID_FILE):
            pid = open(PID_FILE).read().strip()
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
            os.remove(PID_FILE)
            print(f"已停止转发（PID {pid}）")
        else:
            print("没有在运行的转发进程")
        return 0

    ip = pick_ip()
    if not ip:
        print("[错误] 所有 GitHub IP 均不可达")
        return 1
    print(f"选用 GitHub IP：{ip}")

    if args.bg:
        # 用 subprocess 起 detached 子进程（Windows 无 fork）
        cmd = [sys.executable, os.path.abspath(__file__), "--port", str(args.port)]
        p = subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS
                             | 0x00000008,  # CREATE_NEW_PROCESS_GROUP
                             close_fds=True,
                             stdout=open(os.path.join(os.path.dirname(PID_FILE),
                                                       ".dns_bypass.log"), "w"),
                             stderr=subprocess.STDOUT)
        open(PID_FILE, "w").write(str(p.pid))
        print(f"转发已在后台运行：127.0.0.1:{args.port} → {ip}:443（PID {p.pid}）")
        print(f"\n推送命令：")
        print(f"  git -c http.proxy=http://127.0.0.1:{args.port} "
              f"-c https.proxy=http://127.0.0.1:{args.port} push origin main")
        return 0

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(128)
    open(PID_FILE, "w").write(str(os.getpid()))
    print(f"转发中：127.0.0.1:{args.port} → {ip}:443（Ctrl+C 停止）")
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