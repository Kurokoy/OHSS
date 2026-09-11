@echo off
chcp 65001 >nul
title OHSS 高蛋白饮食智能计算器

echo ============================================
echo   OHSS 高蛋白饮食智能计算器
echo   生殖医学中心 · 护理宣教工具
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] 检查依赖...
pip install -r requirements.txt -q

echo [2/2] 启动服务...
echo.
echo 请在浏览器中打开：http://localhost:5000
echo 按 Ctrl+C 停止服务
echo.

python app.py
pause