@echo off
chcp 65001 >nul
echo ============================================
echo    部署到 Windows 服务器
echo ============================================
echo.

REM 先执行安装
call install.bat

echo.
echo [部署] 创建开机自启任务...

REM 使用 Windows 任务计划程序实现开机自启
schtasks /create /tn "PolicyMonitor" /tr "\"%CD%\venv\Scripts\pythonw.exe\" \"%CD%\app.py\"" /sc onstart /ru SYSTEM /f
if errorlevel 1 (
    echo [提示] 任务计划创建失败，尝试使用当前用户...
    schtasks /create /tn "PolicyMonitor" /tr "\"%CD%\venv\Scripts\pythonw.exe\" \"%CD%\app.py\"" /sc onlogon /f
)

echo.
echo [部署] 立即启动服务...
start "" /B venv\Scripts\pythonw.exe app.py

echo.
echo ============================================
echo    服务器部署完成！
echo.
echo    访问地址: http://本机IP:5000
echo    开机自动启动: 已配置
echo    停止服务: 运行 stop.bat
echo    查看任务: schtasks /query /tn "PolicyMonitor"
echo    删除自启: schtasks /delete /tn "PolicyMonitor" /f
echo ============================================
pause
