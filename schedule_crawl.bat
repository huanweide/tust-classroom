@echo off
REM TUST 空闲教室 — 爬取脚本
REM 复用 Edge 登录态 → 自动爬取双校区 7 天数据

cd /d "C:\Users\Administrator\Desktop\tust-classroom"

echo [%date% %time%] 开始爬取（近7天）...

python crawler_playwright.py --range 0-6

echo [%date% %time%] 完成, exit=%ERRORLEVEL%
