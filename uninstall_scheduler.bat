@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════
REM TUST 空闲教室 — 卸载 Windows 任务计划程序
REM ═══════════════════════════════════════════

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 请右键「以管理员身份运行」此脚本
    pause
    exit /b 1
)

echo [卸载] 删除 TUST_Classroom_AutoUpdate ...
schtasks /Delete /TN "TUST_Classroom_AutoUpdate" /F >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✓ 已删除 TUST_Classroom_AutoUpdate
) else (
    echo   - 主任务不存在,跳过
)

schtasks /Delete /TN "TUST_Classroom_AutoUpdate_Boot" /F >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✓ 已删除 TUST_Classroom_AutoUpdate_Boot
) else (
    echo   - 开机触发器不存在,跳过
)

echo.
echo ✅ 卸载完成
pause
