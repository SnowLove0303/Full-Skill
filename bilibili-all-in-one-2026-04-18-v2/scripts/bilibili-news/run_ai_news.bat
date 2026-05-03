@echo off
REM Bilibili AI早报生成器
REM 用法: run_ai_news.bat <UP_UID> <UP_NAME> [视频URL]

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PYTHON_SCRIPT=%SCRIPT_DIR%bilibili_news\__init__.py"

if "%1"=="" (
    echo 用法: run_ai_news.bat ^<UP_UID^> ^<UP_NAME^> [视频URL]
    echo 示例: run_ai_news.bat 285286947 橘郡Juya
    exit /b 1
)

set "UP_UID=%1"
set "UP_NAME=%2"
set "VIDEO_URL=%3"

if "%VIDEO_URL%"=="" (
    python "%PYTHON_SCRIPT%" "%UP_UID%" "%UP_NAME%"
) else (
    python "%PYTHON_SCRIPT%" "%UP_UID%" "%UP_NAME%" "%VIDEO_URL%"
)

endlocal
