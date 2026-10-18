@echo off
cd /d "%~dp0"

set CORVUS=
for %%f in (corvus*.exe) do (
  echo %%f | findstr /i "corvus_gui" >nul || set CORVUS=%%f
)
if "%CORVUS%"=="" (
  echo corvus.exe was not found in this folder. Put it next to build.bat and try again.
  pause
  exit /b 1
)
echo Bundling %CORVUS%

python -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo Could not install PyInstaller.
  pause
  exit /b 1
)

python -m PyInstaller --onefile --windowed --name corvus_gui --add-binary "%CORVUS%;." corvus_gui.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Done. Your program is: dist\corvus_gui.exe
pause
