"""用 REST API 更新 ref（git push 被拒时的最终手段）

为什么需要：
    git push 走 github.com 的 smart HTTP，本机 DNS 解析不了该域名，
    虽经本地转发能建立 TCP，但服务端对 push 的 ref 协商返回 non-fast-forward
    （即使实际是快进 —— 转发的 Host/SNI 处理让服务端看到了非预期状态）。
    而 api.github.com 完全可用，故直接用 REST 把 ref 指到目标 commit。

前置：目标 commit 及其所有祖先必须已在远端（即先推过树对象）。
      本脚本只动 ref 指针，不传对象 —— 所以只适用于「本地领先且已 fetch 过」的场景。

安全：
    - 只从环境变量读 token，绝不写文件
    - 默认 dry-run，必须显式 --commit 才动
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "huanweide/tust-classroom"
BRANCH = "main"
API = "https://api.github.com"


def api(method, path, body=None, token=None):
    req = urllib.request.Request(f"{API}{path}",
                                 data=json.dumps(body).encode() if body else None,
                                 method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[错误] 需要 GH_TOKEN 环境变量")
        return 1

    dry = "--commit" not in sys.argv
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    st, cur = api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}", token=token)
    remote = cur.get("object", {}).get("sha", "?")

    print(f"本地 HEAD : {head[:10]}")
    print(f"远端 main : {remote[:10]}")
    if head == remote:
        print("已一致，无需操作。")
        return 0

    # 确认本地 HEAD 的父提交就是远端顶端（纯快进）
    parent = subprocess.run(["git", "rev-parse", "HEAD^"], capture_output=True,
                            text=True).stdout.strip()
    print(f"本地父提交: {parent[:10]}")
    if parent != remote:
        print("[警告] 不是纯快进！本地父提交 != 远端顶端。")
        print("        这种情况不能直接改 ref，会丢远端的提交。")
        print("        请先 git fetch 再处理。")
        return 2

    if dry:
        print("\n[dry-run] 将是纯快进，可安全更新。加 --commit 执行。")
        return 0

    st, resp = api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}",
                   {"sha": head, "force": False}, token=token)
    if st == 200:
        print(f"\n[OK] main 已更新到 {head[:10]}")
        print("GitHub Pages 约 1-2 分钟生效："
              "https://huanweide.github.io/tust-classroom/")
        return 0
    print(f"[FAIL] {st} {resp.get('message', resp)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
