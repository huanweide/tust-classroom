@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════
REM TUST 空闲教室 — URP 首次登录窗口
REM
REM 新版 Edge 不允许在默认 Profile 上开调试端口,
REM 本项目改用专用 Profile(edge-cdp-profile)。
REM 首次使用请双击本脚本,在弹出的 Edge 窗口里登录一次 URP,
REM 登录态会持久保存,之后爬虫/保活全自动复用,无需再登。
REM ═══════════════════════════════════════════

set PROFILE=%LOCALAPPDATA%\tust-classroom\edge-cdp-profile

if not exist "%PROFILE%" mkdir "%PROFILE%"

echo [启动] 打开专用 Edge 窗口(端口 9222)...
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%PROFILE%" ^
  --no-first-run ^
  --no-default-browser-check ^
  "http://jwxtxs.tust.edu.cn:46110"

echo.
echo ✅ Edge 已打开,请在窗口里登录 URP 教务系统
echo    登录成功后关闭本窗口即可,登录态已保存。
pause
