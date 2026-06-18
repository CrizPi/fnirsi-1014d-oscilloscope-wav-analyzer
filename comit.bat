@echo off
set /p mensaje=Ingrese el mensaje del commit: 

git add .
git commit -m "%mensaje%"
if errorlevel 1 (
    pause
    exit /b
)

git push
if errorlevel 1 (
    pause
    exit /b
)