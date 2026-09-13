@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════════════
REM TUST 空闲教室 — 一键全流程更新(固定封装)
REM
REM 双击运行即可,全流程自动:
REM   1. 拉起专用 Edge(与日常 Edge 互不干扰)
REM   2. 已登录 → 直接开爬;未登录 → 弹出登录页等你登录
REM   3. 自动爬取泰达+河西双校区全学期 40 天数据
REM   4. 导出静态 JSON → 推送 GitHub → Pages 自动刷新
REM
REM 前提:aTrust 已连接(能访问教务系统)
REM 登录态保存在专用 Profile,只需登录一次,之后双击即全自动
REM ═══════════════════════════════════════════════════
cd /d "%~dp0"

echo [1/4] 检查 Python 环境...
py -3.14 -c "import playwright,flask" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [错误] py -3.14 缺少 playwright/flask,先运行:
    echo        py -3.14 -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [2/4] 启动全自动流程(等待登录/爬取/导出/推送)...
py -3.14 wait_and_crawl.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [失败] 查看上方日志或 data\auto_update.log
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════
echo ✅ 全流程完成!
echo    📱 手机访问: https://huanweide.github.io/tust-classroom/
echo ═══════════════════════════════════════════════════
pause
