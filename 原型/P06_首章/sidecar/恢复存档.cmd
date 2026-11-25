@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHON=%~dp0sidecar\runtime\python.exe"
if not exist "%PYTHON%" (
    echo 找不到随包 Python，请完整解压 Windows 发布包。
    pause
    exit /b 2
)
"%PYTHON%" -X utf8 -B -I "%~dp0sidecar\recover_save.py" %*
exit /b %ERRORLEVEL%
