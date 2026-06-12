@echo off
chcp 65001 >nul
echo ============================================
echo    立即爬取并导出
echo ============================================
echo.

REM 切换到项目根目录（tools/ 的上一级）
cd /d "%~dp0.."

REM 让 Playwright 使用项目内置的浏览器
set PLAYWRIGHT_BROWSERS_PATH=0

python\python.exe crawl_export.py
echo.
echo 导出完成！文件在 output 目录下
pause
