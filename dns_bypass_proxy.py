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
        try:
            src.close()
        except OSError:
            pass
        try:
            dst.close()
        except OSError:
            pass


def handle(client, upstream_ips):
    """处理一个客户端连接。

    关键点：
    1. curl/git 的 http.proxy 会先发 HTTP CONNECT，必须先回
       `200 Connection Established` 再开始裸 TCP 管道，
       否则客户端一直等响应直到超时（表现为 HTTP 000）。
    2. 上游 IP 会自动故障转移：GitHub 的 IP 会漂移，
       某个 IP 超时后换下一个，避免整条链路时通时断。
    """
    try:
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
        is_connect = head.upper().startswith("CONNECT")
        port = 443 if is_connect else 80

        upstream = None
        for ip in upstream_ips:
            try:
                upstream = socket.create_connection((ip, port), timeout=10)
                break
            except OSError:
                continue
        if upstream is None:
            client.close()
            return

        if is_connect:
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            rest = first.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in first else b""
            if rest:
                upstream.sendall(rest)
        else:
            upstream.sendall(first)
    except OSError:
        try:
            client.close()
        except OSError:
            pass
        return

    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()


def pick_ip():
    """并行探测全部 IP，按「先连通的排前面」返回有序列表。

    返回 list（可能为空）。这样 handle() 里直接按顺序取第一个，
    不用在建连接时等超时 —— 实测踩坑：把探测放进 handle()
    会让 CONNECT 握手等 10-30 秒，客户端（curl/git）早就超时了（HTTP 000）。
    """
    import concurrent.futures
    import queue

    ok_ips, q = [], queue.Queue()

    def probe(ip):
        try:
            s = socket.create_connection((ip, 443), timeout=6)
            s.close()
            q.put(ip)
        except OSError:
            pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        for ip in GITHUB_IPS:
            ex.submit(probe, ip)
        # 最多等 12 秒，先到先得
        deadline_rounds = 0
        while deadline_rounds < 12:
            try:
                ok_ips.append(q.get(timeout=1))
            except queue.Empty:
                deadline_rounds += 1
    # 探测通的排前面，没探测到的垫后（万一网络恢复还能用）
    return ok_ips + [ip for ip in GITHUB_IPS if ip not in ok_ips]


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

    ips = pick_ip()
    if not ips:
        print("[错误] 所有 GitHub IP 均不可达")
        return 1
    print(f"可用 GitHub IP（按可达性排序）：{ips}")

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
        print(f"转发已在后台运行：127.0.0.1:{args.port} → GitHub IP 池（PID {p.pid}）")
        print("\n推送命令：")
        print(f"  git -c http.proxy=http://127.0.0.1:{args.port} "
              f"-c https.proxy=http://127.0.0.1:{args.port} push origin main")
        return 0

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(128)
    open(PID_FILE, "w").write(str(os.getpid()))
    print(f"转发中：127.0.0.1:{args.port} → GitHub IP 池 {GITHUB_IPS}（Ctrl+C 停止）")
    try:
        while True:
            c, _ = srv.accept()
            # 传整个 IP 池，按连接故障转移
            threading.Thread(target=handle, args=(c, GITHUB_IPS),
                             daemon=True).start()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.close()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
