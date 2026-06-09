@echo off
chcp 65001 >nul
echo ============================================
echo    立即爬取并导出
echo ============================================
echo.
call venv\Scripts\python.exe crawl_export.py
echo.
echo 导出完成！文件在 output 目录下
pause
