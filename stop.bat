@echo off
chcp 65001 >nul
echo 正在停止政策信息监控工具...
taskkill /F /FI "WINDOWTITLE eq 政策*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo 已停止
timeout /t 2
