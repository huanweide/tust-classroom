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
  echo [失败] 推送未成功。常见原因：
  echo   - 凭据弹窗被关掉或输错
  echo   - PAT 没有 repo 权限
  echo   - 网络/DNS 不通（可试 ghssh 远端：git remote add ghssh git@github.com:huanweide/tust-classroom.git）
  pause
  exit /b 1
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