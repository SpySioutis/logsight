@echo off
REM LogSight startup script (Windows). Double-click or run: start.bat
setlocal

REM Resolve the project root regardless of the caller's working directory.
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker is not installed or not on PATH. See MANUAL.md ^(Prerequisites^).
  exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker Compose v2 is not available. See MANUAL.md ^(Prerequisites^).
  exit /b 1
)

echo Starting LogSight (this may take a few minutes on first run)...
echo App: http://localhost:8080   API: http://localhost:8000/api/docs
docker compose up --build
set STATUS=%ERRORLEVEL%
if not %STATUS%==0 (
  echo ERROR: LogSight failed to start ^(exit %STATUS%^). See MANUAL.md ^(Troubleshooting^).
)
exit /b %STATUS%
