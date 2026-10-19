@echo off
REM ─────────────────────────────────────────────────────────────
REM  tust-classroom 推送 + GitHub Pages 上线
REM  用法：双击本文件，或在项目目录执行 push.bat
REM  需要：Git for Windows（git 命令可用）
REM  说明：git 凭据首次会弹窗，输入 GitHub 用户名 + PAT
REM        （PAT 需 repo 权限：Settings → Developer settings →
REM         Personal access tokens → Fine-grained → 选 tust-classroom → Contents: Read/Write）
REM ─────────────────────────────────────────────────────────────
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] 检查工作区...
git status --short

echo.
echo [2/4] 本地 vs 远端提交...
git log --oneline origin/main..HEAD

echo.
echo [3/4] 推送到 origin main...
git push origin main
if errorlevel 1 (
  echo.
  echo [提示] 常规推送失败，尝试 REST 兜底（只动 ref 指针）...
  echo        需要先设置 GH_TOKEN 环境变量。
  if "%GH_TOKEN%"=="" (
    echo [需要] 请先执行：set GH_TOKEN=你的PAT
    echo        然后重跑本脚本，或手动执行：
    echo          python update_ref.py --commit
    pause
    exit /b 1
  )
  python update_ref.py --commit
  if errorlevel 1 (
    echo [失败] REST 兜底也未成功。
    pause
    exit /b 1
  )
)

echo.
echo [4/4] 推送成功。
echo GitHub Pages 通常 1-2 分钟后生效：
echo   https://huanweide.github.io/tust-classroom/
echo.
echo 深链示例（装到桌面后点开即达）：
echo   .../index.html?room=9-16
echo   .../index.html?campus=河西&bld=1-&room=101
pause