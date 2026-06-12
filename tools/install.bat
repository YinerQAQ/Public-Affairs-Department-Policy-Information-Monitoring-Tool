@echo off
chcp 65001 >nul
echo ============================================
echo    政策信息监控工具 - 首次初始化
echo ============================================
echo.

REM 切换到项目根目录（tools/ 的上一级）
cd /d "%~dp0.."

echo [1/2] 检查内置 Python 环境...
if not exist "python\python.exe" (
    echo [错误] 未找到内置 Python 环境
    echo        请确保 python 文件夹完整未被删除
    pause
    exit /b 1
)
echo     内置 Python 环境正常

echo [2/2] 初始化数据库...
python\python.exe -c "import sys; sys.path.insert(0, '.'); from database import init_db; init_db(); print('    数据库初始化完成')"
if errorlevel 1 (
    echo [错误] 数据库初始化失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo    初始化完成！
echo.
echo    [数据库] 默认使用 SQLite（无需配置）
echo    如需使用 MySQL，请修改 config.py 中的 MYSQL_CONFIG
echo    参考：tools\MySQL安装指南.txt
echo.
echo    运行 tools\start.bat 启动应用
echo    运行 tools\crawl_now.bat 立即爬取并导出
echo ============================================
pause
