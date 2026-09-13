@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════
REM TUST 空闲教室 — 一键自动更新
REM 爬取 → 导出 → 推送 → GitHub Pages 自动刷新
REM
REM 用法:
REM   双击 auto_update.bat 立刻执行一次
REM   或通过 install_scheduler.bat 注册到 Windows 任务计划程序
REM   (每小时自动跑,无需登录电脑)
REM
REM 路径自动定位本脚本所在目录,不再硬编码桌面,可在任意位置运行。
REM ═══════════════════════════════════════════
cd /d "%~dp0"

set LOGFILE=data\auto_update.log
echo [%date% %time%] ========== 开始自动更新 ========== >> %LOGFILE%

REM ── Step 1: 爬取未来7天数据 ──
echo [%date% %time%] Step 1/4: 爬取数据...
echo [%date% %time%] Step 1/4: 爬取数据... >> %LOGFILE%
python crawler_playwright.py --range 0-6 >> %LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] 爬取失败! exit=%ERRORLEVEL% >> %LOGFILE%
    echo 爬取失败,查看 %LOGFILE%
    exit /b 1
)

REM ── Step 2: 导出静态 JSON ──
echo [%date% %time%] Step 2/4: 导出JSON...
echo [%date% %time%] Step 2/4: 导出JSON... >> %LOGFILE%
python export_static.py >> %LOGFILE% 2>&1

REM ── Step 3: Git 提交并推送 ──
echo [%date% %time%] Step 3/4: 推送GitHub...
echo [%date% %time%] Step 3/4: 推送GitHub... >> %LOGFILE%
for /f "tokens=1 delims= " %%d in ("%date%") do set TODAY=%%d
git add static/ data/index.json config.py crawler_playwright.py export_static.py
git commit -m "auto: data update %TODAY%" >> %LOGFILE% 2>&1
git push origin main >> %LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] push main 失败! exit=%ERRORLEVEL% >> %LOGFILE%
    echo push main 失败,查看 %LOGFILE%
    exit /b 1
)
git subtree push --prefix=static origin gh-pages >> %LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] push gh-pages 失败! exit=%ERRORLEVEL% >> %LOGFILE%
    echo push gh-pages 失败,查看 %LOGFILE%
    exit /b 1
)

REM ── Step 4: 清理过期数据(保留最近30天)──
echo [%date% %time%] Step 4/4: 清理旧数据...
echo [%date% %time%] Step 4/4: 清理旧数据... >> %LOGFILE%
python -c "import sqlite3,config;from datetime import datetime,timedelta;cut=(datetime.now()-timedelta(days=30)).strftime('%%Y-%%m-%%d');conn=sqlite3.connect(config.DB_PATH);conn.execute('DELETE FROM free_rooms WHERE date < ?',(cut,));conn.commit();print(f'已删除 {cut} 之前的数据');conn.close()" >> %LOGFILE% 2>&1

echo [%date% %time%] ========== 更新完成 ========== >> %LOGFILE%
echo 更新完成!GitHub Pages 将在 1-2 分钟内生效
echo 查看日志: %LOGFILE%
