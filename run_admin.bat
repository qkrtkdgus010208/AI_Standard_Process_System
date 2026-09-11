@echo off
rem ==============================================================================
rem AI Standard Process System - Central Admin PC Windows Script
rem ==============================================================================
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ==============================================================================
echo  AI Standard Process System - Central Admin PC [Windows]
echo ==============================================================================
echo.

rem [1] Python 실행기 탐색
set "PYTHON_CMD="

py -3.12 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=py -3.12" & goto :PYTHON_FOUND

py -3.11 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=py -3.11" & goto :PYTHON_FOUND

py -3.10 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=py -3.10" & goto :PYTHON_FOUND

python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=python" & goto :PYTHON_FOUND

py -3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=py -3" & goto :PYTHON_FOUND

:PYTHON_NOT_FOUND
echo [오류] Python을 찾을 수 없습니다!
echo 1. Python 3.10 이상을 설치해 주세요.
echo 2. 설치 시 Add python.exe to PATH 옵션을 반드시 체크해야 합니다.
echo 3. 다운로드: https://www.python.org/downloads/
echo.
goto :EXIT_SCRIPT

:PYTHON_FOUND
echo [정보] Python 실행기 확인됨: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

rem [2] Linux 등 타 OS에서 생성된 .venv 정리
if not exist ".venv" goto :CHECK_VENV
if exist ".venv\Scripts\python.exe" goto :CHECK_VENV
echo [안내] Linux 등 다른 OS에서 생성된 .venv 폴더가 감지되어 새로 초기화합니다...
rmdir /s /q ".venv" >nul 2>&1

:CHECK_VENV
if exist ".venv\Scripts\python.exe" goto :VENV_READY

echo [진행] Windows 가상환경 .venv 를 생성합니다...
%PYTHON_CMD% -m venv --prompt venv .venv
if not exist ".venv\Scripts\python.exe" goto :VENV_FAIL

echo [진행] 가상환경에 필수 패키지를 설치합니다 - 최초 1회, 수 분 소요될 수 있습니다...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% EQU 0 goto :INSTALL_OK

echo.
echo [경고] requirements.txt 패키지 설치 중 오류가 발생했습니다.
echo        관리자 필수 패키지 PyQt5 를 단독 설치 시도합니다...
".venv\Scripts\python.exe" -m pip install PyQt5
if %ERRORLEVEL% NEQ 0 goto :PYQT_FAIL

:INSTALL_OK
echo installed > ".venv\.installed"
echo [성공] 패키지 설치가 완료되었습니다.
echo.
goto :VENV_READY

:VENV_FAIL
echo [오류] 가상환경 생성에 실패했습니다.
goto :EXIT_SCRIPT

:PYQT_FAIL
echo.
echo [치명적 오류] PyQt5 설치에 실패했습니다.
echo 원인: 사용 중인 Python 버전과 PyQt5 바이너리 간 호환성 문제일 수 있습니다.
echo 해결: Python 3.11 또는 3.12 를 설치하신 후 다시 실행해 주세요.
goto :EXIT_SCRIPT

:VENV_READY
echo [정보] Windows 가상환경 .venv 준비 완료.
echo.

rem [3] 가상환경 활성화
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

rem [4] 관리자 프로그램 실행
echo ==============================================================================
echo  관리자 프로그램을 시작합니다... [종료하려면 프로그램 창을 닫아주세요]
echo ==============================================================================
echo.

python project_admin\main.py %*
set "APP_EXIT_CODE=%ERRORLEVEL%"

echo.
if %APP_EXIT_CODE% EQU 0 goto :RUN_OK
echo [경고] 프로그램이 비정상 종료되었습니다. 종료 코드: %APP_EXIT_CODE%
goto :EXIT_SCRIPT

:RUN_OK
echo [완료] 프로그램이 정상적으로 종료되었습니다.

:EXIT_SCRIPT
echo.
echo 아무 키나 누르면 창이 닫힙니다...
pause >nul
exit /b %APP_EXIT_CODE%
