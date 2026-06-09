@echo off
chcp 65001 >nul
echo 正在启动政策信息监控工具...
echo 启动后请打开浏览器访问: http://127.0.0.1:5000
echo 按 Ctrl+C 停止
echo.

cd /d "%~dp0"

REM 让 Playwright 使用项目内置的浏览器
set PLAYWRIGHT_BROWSERS_PATH=0

python\python.exe app.py
pause
