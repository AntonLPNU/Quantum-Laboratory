@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating an isolated Python environment...
  py -3 -m venv ".venv"
  if errorlevel 1 (
    echo ERROR: Could not create .venv. Install Python 3.10+ and enable the py launcher.
    exit /b 1
  )
)

if not exist ".venv\Scripts\streamlit.exe" (
  echo Installing application dependencies into .venv...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto install_error
  ".venv\Scripts\python.exe" -m pip install -e "."
  if errorlevel 1 goto install_error
)

echo Running regression tests...
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 (
  echo ERROR: One or more tests failed.
  exit /b 1
)
echo All tests passed.
exit /b 0

:install_error
echo ERROR: Dependency installation failed. Check your Python installation and network access.
exit /b 1
