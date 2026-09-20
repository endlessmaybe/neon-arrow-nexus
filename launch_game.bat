@echo off
setlocal
cd /d "%~dp0"

set "GAME=%~dp0dist\NeonArrowNexus-Python.exe"

if not exist "%GAME%" (
    echo [ERROR] Game executable was not found:
    echo         "%GAME%"
    echo.
    echo If this project was downloaded from GitHub, extract the ZIP completely
    echo before running this launcher. Do not run the BAT inside the ZIP preview.
    echo.
    pause
    exit /b 2
)

"%GAME%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Neon Arrow Nexus exited with code %EXIT_CODE%.
    echo If Windows blocked the downloaded EXE, open its Properties page and
    echo choose Unblock, then run this launcher again.
    echo.
    pause
)

exit /b %EXIT_CODE%
