@echo off
@rem ==============================================================================
@rem 중앙 관제 프로그램 (Admin Monitoring PC) Windows 원클릭 실행 스크립트
@rem ==============================================================================
@rem [중요] 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System\)에서 실행됩니다.
@rem 가상환경(.venv) 및 의존성 패키지가 없으면 최초 1회 자동 설치 후 즉시 실행합니다.
@rem 윈도우 탐색기에서 더블 클릭하거나 명령 프롬프트(CMD)/PowerShell에서 실행 가능합니다.
@rem ==============================================================================

chcp 65001 >nul
setlocal enabledelayedexpansion

@rem 배치 파일 위치를 기준으로 프로젝트 루트 디렉토리 강제 이동
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo ==============================================================================
echo  AI Standard Process System - Monitoring PC (관리자 프로그램)
echo ==============================================================================

@rem [1단계] Python 설치 확인
set "PYTHON_CMD="
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    py -3 --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo ❌ [오류] Python이 설치되어 있지 않거나 PATH 환경 변수에 등록되어 있지 않습니다.
    echo    Python 3.10 이상을 설치하고, 설치 시 반드시 'Add python.exe to PATH'에 체크해 주세요.
    echo    공식 다운로드: https://www.python.org/downloads/
    echo.
    goto :ERROR_EXIT
)

@rem [2단계] 가상환경(.venv) 및 패키지 설정
@rem 타 OS(Linux 등)에서 생성된 .venv 폴더 감지 시 자동 재구성
if exist ".venv" (
    if not exist ".venv\Scripts\activate.bat" (
        echo ⚠️ Linux 등 다른 OS에서 생성되었거나 손상된 가상환경(.venv)이 감지되었습니다.
        echo    Windows용 가상환경으로 새로 구성합니다...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\.installed" (
    echo.
    echo ⚙️ 필수 환경을 설정합니다 (Windows 가상환경 생성 및 의존성 패키지 설치)...

    if exist ".venv" (
        echo ⚠️ 미완료된 기존 가상환경(.venv)을 정리하고 새로 구성합니다...
        rmdir /s /q ".venv"
    )

    echo 📦 Windows 가상환경(.venv)을 생성합니다...
    %PYTHON_CMD% -m venv --prompt venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ 가상환경 생성에 실패했습니다. Python 버전을 확인해 주세요.
        goto :ERROR_EXIT
    )

    if not exist ".venv\Scripts\activate.bat" (
        echo ❌ 가상환경 활성화 스크립트를 찾을 수 없습니다.
        goto :ERROR_EXIT
    )

    echo ⚡ 가상환경 (venv)을 활성화합니다...
    call ".venv\Scripts\activate.bat"

    echo 📥 활성화된 (venv) 가상환경에 필수 패키지를 설치합니다...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ 의존성 패키지 설치 중 오류가 발생했습니다.
        goto :ERROR_EXIT
    )

    type nul > ".venv\.installed"
    echo ✅ 의존성 설치가 완료되었습니다!
) else (
    if exist ".venv\Scripts\activate.bat" (
        call ".venv\Scripts\activate.bat"
    ) else (
        echo ❌ 가상환경 활성화 스크립트가 없습니다. .venv 폴더를 삭제 후 다시 실행해 주세요.
        goto :ERROR_EXIT
    )
)

@rem [3단계] 초기 데이터베이스 확인 (최초 실행 시 샘플 데이터 자동 생성)
if not exist "project_admin\factory.db" (
    echo.
    echo 🗄️ 초기 데이터베이스가 없어 기본 관리자 계정(admin/admin1234)을 생성합니다...
    python project_admin\sample_data.py
)

@rem [4단계] 관리자 프로그램 실행
echo.
echo 🚀 중앙 관제 프로그램을 실행합니다...
python project_admin\main.py %*
set "APP_EXIT_CODE=%ERRORLEVEL%"

if %APP_EXIT_CODE% NEQ 0 (
    echo.
    echo ❌ 프로그램이 비정상 종료되었습니다. (종료 코드: %APP_EXIT_CODE%)
    goto :ERROR_EXIT
)

echo.
echo ✅ 프로그램이 정상 종료되었습니다.

@rem 탐색기 더블클릭 실행 시 창이 바로 닫히지 않도록 대기
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul
if %ERRORLEVEL% EQU 0 (
    pause
)
exit /b 0

:ERROR_EXIT
echo.
pause
exit /b 1
