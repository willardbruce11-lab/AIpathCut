@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 优先使用 Anaconda Python
set "ANACONDA_PY=D:\ANACONDA\python.exe"
if exist "%ANACONDA_PY%" (
    set "PYTHON_EXE=%ANACONDA_PY%"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" gui.py
if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查是否已安装所需依赖：
    echo "%PYTHON_EXE%" -m pip install -r requirements.txt
    pause
)
