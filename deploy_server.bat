@echo off
chcp 65001 >nul
echo ============================================
echo    部署到 Windows 服务器
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 检查内置 Python 环境...
if not exist "python\python.exe" (
    echo [错误] 未找到内置 Python 环境，请确保文件夹完整
    pause
    exit /b 1
)
echo     环境正常

REM 让 Playwright 使用项目内置的浏览器
set PLAYWRIGHT_BROWSERS_PATH=0

echo [2/3] 初始化数据库...
python\python.exe -c "import sys; sys.path.insert(0, '.'); from database import init_db; init_db()"
if errorlevel 1 (
    echo [错误] 数据库初始化失败
    pause
    exit /b 1
)
echo     数据库就绪

echo [3/3] 配置开机自启任务...
schtasks /create /tn "PolicyMonitor" /tr "cmd /c \"cd /d %CD% && set PLAYWRIGHT_BROWSERS_PATH=0 && %CD%\python\pythonw.exe %CD%\app.py\"" /sc onstart /ru SYSTEM /f
if errorlevel 1 (
    echo [提示] 系统级任务创建失败，尝试当前用户登录时启动...
    schtasks /create /tn "PolicyMonitor" /tr "cmd /c \"cd /d %CD% && set PLAYWRIGHT_BROWSERS_PATH=0 && %CD%\python\pythonw.exe %CD%\app.py\"" /sc onlogon /f
)

echo.
echo [启动] 后台运行服务...
start "" /B python\pythonw.exe app.py

echo.
echo ============================================
echo    服务器部署完成！
echo.
echo    访问地址: http://本机IP:5000
echo    停止服务: stop.bat
echo    查看任务: schtasks /query /tn "PolicyMonitor"
echo    删除自启: schtasks /delete /tn "PolicyMonitor" /f
echo ============================================
pause
