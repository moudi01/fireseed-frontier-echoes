@echo off
setlocal
set "P06_RELEASE=windows-20261124-235726-e44ab7"
if exist "%~dp0build\%P06_RELEASE%\P06.exe" goto launch
for /f "delims=" %%B in ('dir /b /ad /o-n "%~dp0build\windows-*" 2^>nul') do (
    if exist "%~dp0build\%%B\P06.exe" if exist "%~dp0build\%%B\sidecar\runtime\python.exe" (
        set "P06_RELEASE=%%B"
        goto launch
    )
)
echo Run build_windows.ps1 to build P06 first. 1>&2
exit /b 1
:launch
"%~dp0build\%P06_RELEASE%\sidecar\runtime\python.exe" -B -I "%~dp0playtest.py" "%P06_RELEASE%" %*
exit /b %errorlevel%
