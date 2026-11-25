@echo off
rem MinesteinKraft launcher (Windows).
rem First run: creates .venv and installs the dependencies; later runs reinstall
rem them only when requirements.txt changes. Arguments are passed to the game,
rem e.g.  run.bat --world-dir D:\my-worlds     (--setup-only: prepare, don't start)
setlocal
cd /d "%~dp0"
set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "MARKER=%VENV%\.requirements.sha256"

if exist "%PY%" goto have_venv
set "PYTHON="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON (
    echo MinesteinKraft needs Python 3.10 or newer. Install it from https://www.python.org/downloads/
    echo ^(tick "Add python.exe to PATH"^), then run this script again.
    pause
    exit /b 1
)
echo Creating the Python environment in %VENV%...
%PYTHON% -m venv "%VENV%" || goto failed

:have_venv
for /f "usebackq delims=" %%h in (`%PY% -c "import hashlib; print(hashlib.sha256(open('requirements.txt', 'rb').read()).hexdigest())"`) do set "WANTED=%%h"
set "CURRENT="
if exist "%MARKER%" set /p CURRENT=<"%MARKER%"
if "%CURRENT%"=="%WANTED%" goto run
echo Installing dependencies...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade pip || goto failed
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt || goto failed
>"%MARKER%" echo %WANTED%

:run
rem --setup-only: prepare the environment and stop (used by the VS Code debug configuration)
if "%~1"=="--setup-only" (
    echo Environment ready: %PY%
    exit /b 0
)
"%PY%" main.py %*
exit /b %ERRORLEVEL%

:failed
echo Setup failed, see the messages above.
pause
exit /b 1
