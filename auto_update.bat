@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════
REM TUST 空闲教室 — 一键自动更新
REM 爬取 → 导出 → 推送 → GitHub Pages 自动刷新
REM ═══════════════════════════════════════════
cd /d "C:\Users\Administrator\Desktop\tust-classroom"

set LOGFILE=data\auto_update.log
echo [%date% %time%] ========== 开始自动更新 ========== >> %LOGFILE%

REM ── Step 1: 爬取未来7天数据 ──
echo [%date% %time%] Step 1/4: 爬取数据...
echo [%date% %time%] Step 1/4: 爬取数据... >> %LOGFILE%
python crawler_playwright.py --range 0-6 >> %LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] 爬取失败! exit=%ERRORLEVEL% >> %LOGFILE%
    echo 爬取失败，查看 %LOGFILE%
    pause
    exit /b 1
)

REM ── Step 2: 导出静态 JSON ──
echo [%date% %time%] Step 2/4: 导出JSON...
echo [%date% %time%] Step 2/4: 导出JSON... >> %LOGFILE%
python export_static.py >> %LOGFILE% 2>&1

REM ── Step 3: Git 提交并推送 ──
echo [%date% %time%] Step 3/4: 推送GitHub...
echo [%date% %time%] Step 3/4: 推送GitHub... >> %LOGFILE%
git add static/data/ static/index.html config.py crawler_playwright.py export_static.py
git commit -m "auto: 数据更新 %date%" >> %LOGFILE% 2>&1
git push origin main >> %LOGFILE% 2>&1
git subtree push --prefix=static origin gh-pages >> %LOGFILE% 2>&1

REM ── Step 4: 清理过期数据（保留最近30天）──
echo [%date% %time%] Step 4/4: 清理旧数据...
echo [%date% %time%] Step 4/4: 清理旧数据... >> %LOGFILE%
python -c "import sqlite3,config;from datetime import datetime,timedelta;cut=(datetime.now()-timedelta(days=30)).strftime('%%Y-%%m-%%d');conn=sqlite3.connect(config.DB_PATH);conn.execute('DELETE FROM free_rooms WHERE date < ?',(cut,));conn.commit();print(f'已删除 {cut} 之前的数据');conn.close()" >> %LOGFILE% 2>&1

echo [%date% %time%] ========== 更新完成 ========== >> %LOGFILE%
echo.
echo 更新完成！GitHub Pages 将在1-2分钟内生效
echo 查看日志: %LOGFILE%
