"""用 GitHub REST API 推送（git push 走不通时的方案）

背景（2026-10-19 实测）：
- 本机 DNS 解析不了 github.com / raw.githubusercontent.com → git push 必然失败
- 但 api.github.com 稳定返回 200 → REST 通道可用
- 所以：逐个文件 fetch SHA → PUT contents，绕过 git 协议

用法：
    set GH_TOKEN=ghp_xxxx
    python push_via_api.py            # 只推本次改动的文件
    python push_via_api.py --all      # 推全部跟踪文件（慎用，请求数多）

安全铁律：
- token 只从环境变量读，绝不写进任何文件、绝不进 git
- 本脚本不打印 token
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "huanweide/tust-classroom"
BRANCH = "main"
API = "https://api.github.com"

# 只推这些文件（本次改动的白名单，避免一把梭全推）
FILES = [
    "static/index.html",
    "static/data/index.json",
    "static/data/search.json",
    "export_static.py",
    "normalize.py",
    "building_policy.py",
    "test_normalize.py",
    "test_e2e_browse.mjs",
    "verify_all.py",
    "shot_browse.mjs",
    "push.bat",
    ".gitignore",
    "README.md",
    "docs/sponsor-setup.md",
]


def api(method, path, body=None, token=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[错误] 未找到 GH_TOKEN / GITHUB_TOKEN 环境变量")
        print("用法：set GH_TOKEN=ghp_xxxx && python push_via_api.py")
        return 1

    files = FILES
    if "--all" in sys.argv:
        out = git("ls-files")
        files = [f for f in out.split("\n") if f]

    ok = fail = skip = 0
    for f in files:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f)
        if not os.path.exists(path):
            print(f"  [跳过] {f} 本地不存在")
            skip += 1
            continue
        with open(path, "rb") as fh:
            content = base64.b64encode(fh.read()).decode()

        # 取远端 SHA（存在才能 update，不存在则 create）
        st, cur = api("GET", f"/repos/{REPO}/contents/{f}?ref={BRANCH}",
                      token=token)
        sha = cur.get("sha") if st == 200 else None

        st, resp = api("PUT", f"/repos/{REPO}/contents/{f}", {
            "message": f"chore: sync {f}",
            "content": content,
            "branch": BRANCH,
            **({"sha": sha} if sha else {}),
        }, token=token)

        if st in (200, 201):
            print(f"  [OK] {f} ({'update' if sha else 'create'})")
            ok += 1
        else:
            msg = resp.get("message", str(resp))[:120]
            print(f"  [FAIL] {f} → {st} {msg}")
            fail += 1

    print(f"\n完成：{ok} 成功 / {fail} 失败 / {skip} 跳过")
    print("GitHub Pages 约 1-2 分钟生效："
          "https://huanweide.github.io/tust-classroom/")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
