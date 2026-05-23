"""TUST 教务系统爬虫 — CAS 登录 → 查空闲教室 → 存 SQLite"""
import json
import os
import pickle
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from http.cookiejar import LWPCookieJar
from urllib.parse import urljoin

import requests

import config

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "session.json")
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cookies.txt")


def encrypt_cas_password(password, salt):
    """调用 Node.js 执行 CAS 的 encryptPassword"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "encrypt_password.js")
    result = subprocess.run(
        ["node", script, password, salt],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"密码加密失败: {result.stderr}")
    return result.stdout.strip()


class TUSTCrawler:
    """天津科技大学教务系统爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self._ensure_db()
        self._load_session()

    # ── 数据库 ──

    def _ensure_db(self):
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS free_rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campus_name TEXT NOT NULL,
                    building_name TEXT NOT NULL,
                    classroom_name TEXT NOT NULL,
                    period INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    UNIQUE(campus_name, building_name, classroom_name, period, date)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_free_rooms_query
                ON free_rooms(campus_name, building_name, period, date)
            """)

    def clear_today_cache(self, date_str):
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute("DELETE FROM free_rooms WHERE date = ?", (date_str,))

    # ── Session 持久化 ──

    def _load_session(self):
        """从保存的浏览器状态恢复 cookies"""
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                for cookie in state.get('cookies', []):
                    self.session.cookies.set(
                        cookie['name'], cookie['value'],
                        domain=cookie.get('domain', ''),
                        path=cookie.get('path', '/'),
                    )
                print("[Session] 已从 Playwright 状态恢复 Cookies")
            except Exception as e:
                print(f"[Session] 恢复失败: {e}")

    def _save_session(self):
        """保存当前 cookies 供后续复用"""
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        try:
            # 同时保存为 LWPCookieJar 格式（requests 原生支持）
            jar = LWPCookieJar(COOKIE_FILE)
            for cookie in self.session.cookies:
                jar.set_cookie(cookie)
            jar.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
            print(f"[Session] Cookies 已保存到 {COOKIE_FILE}")
        except Exception as e:
            print(f"[Session] 保存失败: {e}")

    # ── 登录 (Apereo CAS) ──

    def login(self, student_id=None, password=None, max_retries=2):
        """通过 CAS 统一认证登录教务系统。
        优先用已保存的浏览器 Cookies（绕过 MFA），过期则提示手动登录。
        """
        sid = student_id or config.STUDENT_ID
        pwd = password or config.PASSWORD
        if not sid or not pwd:
            raise RuntimeError(
                "学号/密码未设置。请设环境变量: "
                "export TUST_SID=你的学号 && export TUST_PWD=你的密码"
            )

        # Path A: 检查已保存的 cookie
        print("[登录] 检查已保存的 Cookies...")
        if self.check_logged_in():
            print("[登录] Cookie 仍有效，无需重新登录 [OK]")
            self._save_session()
            return True

        # Path B: 尝试自动化 CAS 登录（可能触发 MFA）
        print("[登录] Cookie 已过期，尝试自动登录...")
        if self._cas_login(sid, pwd, max_retries):
            self._save_session()
            return True

        # Path C: 自动登录失败（MFA 拦截），提示手动登录
        print("[登录] 自动登录被 MFA 拦截")
        print("[登录] 请运行: python save_session.py 完成手动登录")
        print("[登录] 完成后按 Enter 继续...")
        input()
        self._load_session()
        if self.check_logged_in():
            print("[登录] Session 恢复成功 [OK]")
            return True
        raise RuntimeError("手动登录后仍无法访问教务系统，请重试 save_session.py")

    def _cas_login(self, sid, pwd, max_retries):
        """自动化 CAS 登录（无 MFA 时有效）"""

        # 1. 访问 URP → 被重定向到 CAS 登录页
        print("[CAS] 访问教务系统首页...")
        resp = self.session.get(config.LOGIN_PAGE, timeout=15, allow_redirects=True)
        html = resp.text

        # 检查是否被重定向到 MFA
        if "isMultifactor" in resp.url or "reAuthCheck" in resp.url:
            print("[CAS] 被重定向到 MFA 页面，自动登录不可用")
            return False

        cas_base = "http://id.tust.edu.cn"
        print(f"[CAS] 重定向到 CAS: {resp.url}")

        # 2. 解析 CAS 表单
        salt = self._extract(html, r'id="pwdEncryptSalt"[^>]*value="([^"]*)"')
        execution = self._extract(html, r'name="execution"[^>]*value="([^"]*)"')
        print(f"[登录] pwdEncryptSalt={salt}")
        print(f"[登录] execution={execution[:60]}...")

        if not salt or not execution:
            raise RuntimeError("无法解析 CAS 登录表单，页面结构可能已变更")

        for attempt in range(1, max_retries + 1):
            print(f"[登录] 第 {attempt}/{max_retries} 次尝试...")

            # 3. 重新获取 CAS 页面（保证 execution token 新鲜）
            if attempt > 1:
                resp = self.session.get(config.LOGIN_PAGE, timeout=15, allow_redirects=True)
                html = resp.text
                salt = self._extract(html, r'id="pwdEncryptSalt"[^>]*value="([^"]*)"')
                execution = self._extract(html, r'name="execution"[^>]*value="([^"]*)"')
                if not salt or not execution:
                    raise RuntimeError("无法解析 CAS 登录表单")

            # 4. 立即加密密码（不调用 checkNeedCaptcha，首次登录不需要）
            encrypted = encrypt_cas_password(pwd, salt)
            print(f"[登录] 加密完成: {encrypted[:40]}...")

            # 5. 构建登录表单并立即提交
            login_url = f"{cas_base}/authserver/login"
            if "service=" in resp.url:
                login_url += "?" + resp.url.split("?", 1)[1]

            form_data = {
                "username": sid,
                "password": encrypted,
                "execution": execution,
                "_eventId": "submit",
                "cllt": "userNameLogin",
                "dllt": "generalLogin",
                "lt": "",
            }

            resp = self.session.post(
                login_url,
                data=form_data,
                allow_redirects=True,
                timeout=15,
            )

            # 7. 验证结果
            if self.check_logged_in():
                print("[登录] 登录成功 [OK]")
                return True

            # 分析失败原因
            print(f"[CAS] 登录后 URL: {resp.url}")

            # MFA 拦截 → 返回 False，调用方走手动登录流程
            if "isMultifactor" in resp.url or "reAuthCheck" in resp.url:
                print("[CAS] MFA 拦截，自动登录不可用")
                return False

            # 保存响应以便调试
            debug_path = os.path.join(os.path.dirname(__file__), "data", "cas_response.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(resp.text)

            # 检查 CAS 错误消息
            error_msg = self._extract(resp.text, r'id="showErrorTip"[^>]*>([^<]+)<')
            if error_msg:
                print(f"[CAS] CAS 错误提示: {error_msg}")
                if "密码" in error_msg:
                    raise RuntimeError(f"密码错误: {error_msg}")
                if "用户" in error_msg:
                    raise RuntimeError(f"用户问题: {error_msg}")

            if "密码" in resp.text and "错误" in resp.text:
                raise RuntimeError("密码错误，请检查环境变量 TUST_PWD")
            if "用户" in resp.text and ("不存在" in resp.text or "禁用" in resp.text):
                raise RuntimeError(f"用户 {sid} 不存在或被禁用")

            print(f"[CAS] 登录失败，URL 最终停留在: {resp.url}")
            if attempt < max_retries:
                time.sleep(0.5)

        return False

    def _extract(self, text, pattern):
        m = re.search(pattern, text)
        return m.group(1) if m else ""

    def _check_need_captcha(self, cas_base, username):
        """检查 CAS 是否要求验证码（首登通常不需要）"""
        try:
            resp = self.session.post(
                f"{cas_base}/authserver/checkNeedCaptcha.htl",
                data={"username": username},
                timeout=5,
            )
            data = resp.json()
            return data.get("isNeed", False)
        except Exception:
            return False

    def check_logged_in(self):
        """检查当前会话是否已登录"""
        try:
            resp = self.session.get(
                f"{config.BASE_URL}/student/teachingResources/freeClassroomQuery/tomrrowDate",
                timeout=10,
            )
            return "spareroomObjList" in resp.text or "freeClassroom" in resp.text
        except Exception:
            return False

    # ── 数据获取 ──

    def get_campuses(self):
        resp = self.session.post(config.CAMPUS_LIST_API, timeout=10)
        data = resp.json()
        campuses = []
        for item in data if isinstance(data, list) else [data]:
            code = item.get("xqh") or item.get("code") or item.get("id")
            name = item.get("xqmc") or item.get("name") or item.get("text")
            if code and name:
                campuses.append((str(code), str(name)))
        print(f"[校区] {campuses}")
        return campuses

    def get_buildings(self, campus_code):
        resp = self.session.post(
            config.BUILDING_LIST_API,
            data={"xqh": campus_code},
            timeout=10,
        )
        data = resp.json()
        buildings = []
        for item in data if isinstance(data, list) else [data]:
            code = item.get("jxlh") or item.get("code") or item.get("id")
            name = item.get("jxlmc") or item.get("name") or item.get("text")
            if code and name:
                buildings.append((str(code), str(name)))
        print(f"[教学楼] campus={campus_code} → {buildings}")
        return buildings

    def get_free_rooms_for_period(self, period, dayplus=1):
        resp = self.session.post(
            f"{config.FREE_ROOM_API}/{period}",
            data={"dayplus": dayplus},
            timeout=10,
        )
        data = resp.json()
        rooms = data.get("spareroomObjList", [])
        results = []
        for building in rooms:
            bname = building.get("acmcBuildingName") or building.get("jxlmc") or ""
            for room in building.get("claroom", []):
                rname = room.get("classroom") or room.get("name") or ""
                if rname:
                    results.append({
                        "building_name": bname,
                        "classroom_name": rname,
                    })
        return results

    # ── 完整爬取 ──

    def crawl_all(self, date_str=None, dayoffset=1):
        if date_str is None:
            date_str = (datetime.now() + timedelta(days=dayoffset)).strftime("%Y-%m-%d")

        print(f"[爬取] 开始, 目标日期={date_str}")
        self.clear_today_cache(date_str)

        campuses = self.get_campuses()
        total = 0

        for campus_code, campus_name in campuses:
            self.get_buildings(campus_code)

            for period in range(1, 14):
                try:
                    rooms = self.get_free_rooms_for_period(period, dayplus=dayoffset)
                    count = self._save_rooms(campus_name, rooms, period, date_str)
                    total += count
                    if count > 0:
                        print(f"  [{campus_name}] 第{period}节 → {count}间空闲")
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  [WARN] 第{period}节查询失败: {e}")
                    time.sleep(1)

        print(f"[爬取] 完成, 共写入 {total} 条记录")
        return total

    def _save_rooms(self, campus_name, rooms, period, date_str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(config.DB_PATH) as conn:
            count = 0
            for room in rooms:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO free_rooms
                        (campus_name, building_name, classroom_name, period, date, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        campus_name,
                        room["building_name"],
                        room["classroom_name"],
                        period,
                        date_str,
                        now,
                    ))
                    count += 1
                except Exception as e:
                    print(f"  [DB ERR] {room}: {e}")
            return count


if __name__ == "__main__":
    crawler = TUSTCrawler()
    crawler.login()
    total = crawler.crawl_all()
    print(f"\n完成! 共 {total} 条空闲教室记录")
