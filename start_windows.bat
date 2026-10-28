@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating an isolated Python environment...
  py -3 -m venv ".venv"
  if errorlevel 1 goto python_error
)

if not exist ".venv\Scripts\pip.exe" goto python_error
if not exist ".venv\Scripts\streamlit.exe" (
  echo Installing Python scientific dependencies...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto install_error
  ".venv\Scripts\python.exe" -m pip install -e "."
  if errorlevel 1 goto install_error
)

where node >nul 2>nul
if errorlevel 1 goto node_error
where npm >nul 2>nul
if errorlevel 1 goto node_error

if not exist "frontend\node_modules\vite\bin\vite.js" (
  echo Installing the locked React and Three.js dependencies...
  pushd frontend
  call npm ci
  if errorlevel 1 (popd & goto npm_error)
  popd
)

echo Building the Orbital Lab interface...
pushd frontend
call npm run build
if errorlevel 1 (popd & goto build_error)
popd

echo Starting the local API on an available loopback port and checking readiness...
start "Quantum Laboratory local API" /min "%CD%\.venv\Scripts\python.exe" "%CD%\scripts\launch_local.py"
if errorlevel 1 goto launch_error
echo The launcher will open the verified URL. Startup diagnostics are saved under %%LOCALAPPDATA%%\QuantumLaboratory\startup.log.
exit /b 0

:python_error
echo ERROR: Python 3.10+ and the Windows py launcher are required.
pause
exit /b 1

:install_error
echo ERROR: Python dependency installation failed.
pause
exit /b 1

:node_error
echo ERROR: Node.js and npm are required to build the Orbital Lab interface.
pause
exit /b 1

:npm_error
echo ERROR: Frontend dependency installation failed.
pause
exit /b 1

:build_error
echo ERROR: Orbital Lab frontend build failed.
pause
exit /b 1

:launch_error
echo ERROR: The local API launcher could not start.
pause
exit /b 1
