@echo off
python -m pip install --upgrade pip
python -m pip install pyinstaller
rmdir /s /q build
rmdir /s /q dist
python -m PyInstaller app.spec
xcopy /e /y dist\FNIRSI1014DAnalyzer\* dist\ 2>nul
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
rmdir /s /q build
