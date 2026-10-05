@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════
REM TUST 空闲教室 — 安装 Windows 任务计划程序
REM
REM 效果:把 auto_update.bat 注册成一个后台任务,
REM      每 60 分钟(或开机)自动跑一次,持续推送最新数据到 GitHub Pages。
REM      无需登录 Windows,服务静默运行,不弹黑窗。
REM
REM 用法:管理员身份双击运行一次即可。
REM 卸载:双击 uninstall_scheduler.bat
REM ═══════════════════════════════════════════

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 请右键「以管理员身份运行」此脚本
    pause
    exit /b 1
)

cd /d "%~dp0"
set SCRIPT=%~dp0auto_update.bat
set TASKNAME=TUST_Classroom_AutoUpdate

REM ── 检查是否已存在同名任务 ──
schtasks /Query /TN "%TASKNAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [提示] 任务 %TASKNAME% 已存在,先删除再重建...
    schtasks /Delete /TN "%TASKNAME%" /F >nul 2>&1
)

REM ── 创建任务,每 60 分钟触发一次,开机时也触发,系统空闲时尽快补跑 ──
echo [安装] 创建任务 %TASKNAME% ...
schtasks /Create /TN "%TASKNAME%" /TR "\"%~dp0auto_update.bat\"" /SC MINUTE /MO 60 /F >nul
if %ERRORLEVEL% NEQ 0 (
    echo [错误] schtasks 创建失败,exit=%ERRORLEVEL%
    pause
    exit /b 1
)

REM ── 加上「开机时立即补跑一次」触发器 ──
schtasks /Create /TN "%TASKNAME%_Boot" /TR "\"%~dp0auto_update.bat\"" /SC ONSTART /F >nul
if %ERRORLEVEL% NEQ 0 (
    echo [警告] ONSTART 触发器注册失败,主任务已生效,不影响核心功能
)

REM ── 注册 URP 会话保活任务(每25分钟,防 CAS 空闲超时导致爬虫失败) ──
REM 关键修复: 旧版 install_scheduler.bat 漏注册保活任务,导致 URP 会话空闲超时后
REM 自动更新每小时都 sys.exit(1) 失败。此处一并注册,确保会话常驻。
set KEEPALIVE_TASK=TUST_Classroom_KeepAlive
schtasks /Query /TN "%KEEPALIVE_TASK%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [提示] 保活任务 %KEEPALIVE_TASK% 已存在,先删除再重建...
    schtasks /Delete /TN "%KEEPALIVE_TASK%" /F >nul 2>&1
)
schtasks /Create /TN "%KEEPALIVE_TASK%" /TR "\"%~dp0keepalive_task.bat\"" /SC MINUTE /MO 25 /F >nul
if %ERRORLEVEL% NEQ 0 (
    echo [警告] 保活任务注册失败,URP 会话可能超时,建议手动注册 keepalive_task.bat
) else (
    echo [OK] 保活任务已注册: 每 25 分钟 ping 一次 URP
)

echo.
echo ═══════════════════════════════════════════
echo ✅ 安装完成!
echo    任务名:    %TASKNAME%
echo    触发频率:  每 60 分钟跑一次 + 开机补跑
echo    静默运行:  是(不弹黑窗)
echo    查看任务:  Win+R → taskschd.msc → 找 TUST_*
echo ═══════════════════════════════════════════
echo.
echo [下一步] 立刻触发一次(可选):
echo   schtasks /Run /TN "%TASKNAME%"
echo.
echo [卸载]
echo   双击 uninstall_scheduler.bat
echo ═══════════════════════════════════════════
pause
