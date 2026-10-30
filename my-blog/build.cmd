@echo off
rem Local build/preview wrapper. Usage:
rem   build.cmd                 build into public\
rem   build.cmd --serve         build + preview at http://127.0.0.1:8000
rem   build.cmd --clean         clean public\ then build
rem   build.cmd --new "title"   create a new draft
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PYEXE="
call :trypy "%PYTHON%"
call :trypy python
call :trypy python3
call :trypy py
call :trypy "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if not defined PYEXE (
  echo [ERROR] No usable Python 3 found. Install Python 3.11+ ^(python.org^) or set the PYTHON env var.
  exit /b 1
)

if "%~1"=="" (set "ARGS=--clean") else (set "ARGS=%*")
set PYTHONIOENCODING=utf-8
echo [build] interpreter: %PYEXE%
"%PYEXE%" build.py !ARGS!
exit /b %ERRORLEVEL%

:trypy
if defined PYEXE exit /b 0
if "%~1"=="" exit /b 0
"%~1" -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYEXE=%~1"
exit /b 0