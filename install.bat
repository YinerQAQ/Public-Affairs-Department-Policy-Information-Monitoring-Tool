@echo off
chcp 65001 >nul
echo ============================================
echo    政策信息监控工具 - 一键安装
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 创建虚拟环境...
if not exist venv (
    python -m venv venv
    echo     虚拟环境创建完成
) else (
    echo     虚拟环境已存在，跳过
)

echo [2/4] 安装 Python 依赖...
call venv\Scripts\pip.exe install -r requirements.txt -q
echo     依赖安装完成

echo [3/4] 下载浏览器引擎（约150MB，请耐心等待）...
call venv\Scripts\python.exe -m playwright install chromium
echo     浏览器引擎下载完成

echo [4/4] 初始化数据库...
call venv\Scripts\python.exe -c "from database import init_db; init_db(); print('    数据库初始化完成')"

echo.
echo ============================================
echo    安装完成！
echo    运行 start.bat 启动应用
echo    运行 crawl_now.bat 立即爬取并导出
echo ============================================
pause
