@echo off
REM FNIRSI 1014D Oscilloscope WAV Analyzer - Inicio automatico
REM Crea el entorno virtual, instala dependencias y ejecuta la aplicacion

setlocal enabledelayedexpansion

title FNIRSI 1014D Analyzer

REM ---------------------------------------------------------------
REM 1. Verificar que Python esta disponible
REM ---------------------------------------------------------------
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] No se encontro Python. Instala Python 3.8+ desde https://python.org
    echo        Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 2. Verificar que requirements.txt existe
REM ---------------------------------------------------------------
if not exist "%~dp0requirements.txt" (
    echo [ERROR] No se encuentra requirements.txt en la carpeta del proyecto.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 3. Crear el entorno virtual si no existe
REM ---------------------------------------------------------------
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [1/4] Creando entorno virtual...
    python -m venv "%~dp0venv"
    if !errorlevel! neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Entorno virtual ya existe.
)

REM ---------------------------------------------------------------
REM 4. Instalar dependencias
REM ---------------------------------------------------------------
echo [2/4] Instalando dependencias...
"%~dp0venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 5. Ejecutar la aplicacion
REM ---------------------------------------------------------------
echo [3/4] Iniciando aplicacion...
echo [4/4] Abriendo ventana principal...
echo.
start "" /B "%~dp0venv\Scripts\python.exe" "%~dp0app.py"

REM Esperar a que el servidor Flask arranque
timeout /t 3 /nobreak >nul

REM ---------------------------------------------------------------
REM 6. Mostrar informacion de la aplicacion
REM ---------------------------------------------------------------
echo La aplicacion se abrira en una ventana nativa.
echo Si no aparece, abre http://127.0.0.1:5000/ en tu navegador.

echo.
echo Listo. Cierra esta ventana para detener la aplicacion.
