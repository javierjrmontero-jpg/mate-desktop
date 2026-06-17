@echo off
:: MATE — Launcher
:: Doble clic para iniciar. No requiere abrir terminal.

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set VOICE_DIR=%SCRIPT_DIR%voice
set VENV_PYTHON=%VOICE_DIR%\mate-wakeword-env\Scripts\pythonw.exe
set ENV_FILE=%VOICE_DIR%\.env

:: Verificar que el venv existe
if not exist "%VENV_PYTHON%" (
    echo [MATE] Venv no encontrado. Corri primero setup_mate.ps1
    pause
    exit /b 1
)

:: Cargar variables del .env como variables de entorno del proceso
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" (
            if not "%%B"=="" set "%%A=%%B"
        )
    )
)

:: Iniciar el orbe (pythonw = sin ventana de consola)
start "" "%VENV_PYTHON%" "%VOICE_DIR%\mate_orb.py"

endlocal
