@echo off
REM URP 保活 — 配合 Windows 任务计划程序
REM 每 25 分钟由计划任务触发，不弹黑窗

cd /d "C:\Users\Administrator\Desktop\tust-classroom"

REM 用 pythonw.exe 避免弹出控制台窗口
pythonw keepalive.py --once 2>&1
