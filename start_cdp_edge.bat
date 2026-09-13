@echo off
REM 启动专用 CDP Edge 实例(供 schtasks 调用)
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\tust-classroom\edge-cdp-profile" --no-first-run --no-default-browser-check "http://jwxtxs.tust.edu.cn:46110/"
