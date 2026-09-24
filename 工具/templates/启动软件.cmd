@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "BOOT_PY="
set "BOOT_ARGS="
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
if not errorlevel 1 (
  set "BOOT_PY=py"
  set "BOOT_ARGS=-3"
)
if not defined BOOT_PY (
  python -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
  if not errorlevel 1 set "BOOT_PY=python"
)
if not defined BOOT_PY (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    set "BOOT_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  )
)
if not defined BOOT_PY (
  echo 未找到 Python 3.11 以上版本。请安装 Python 后重试。
  goto failed
)
set "LOCAL_DEPS=%~dp0..\..\..\..\工具\.packages"
if exist "%LOCAL_DEPS%\PyQt6" (
  set "PYTHONPATH=%LOCAL_DEPS%;%PYTHONPATH%"
  "%BOOT_PY%" %BOOT_ARGS% -c "@DEPENDENCY_CHECK@" >nul 2>nul
  if not errorlevel 1 (
    "%BOOT_PY%" %BOOT_ARGS% main.py
    if errorlevel 1 goto failed
    exit /b 0
  )
)
if not exist ".venv\Scripts\python.exe" (
  "%BOOT_PY%" %BOOT_ARGS% -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "@DEPENDENCY_CHECK@" >nul 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo 启动失败。请查看上方的具体错误信息。
pause
exit /b 1
