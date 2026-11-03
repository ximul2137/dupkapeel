@echo off
setlocal
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo BLAD: Docker nie dziala. Uruchom Docker Desktop i sprobuj ponownie.
  pause
  exit /b 1
)

if not exist ".env" (
  python -c "import secrets;open('.env','w').write('ADMIN_KEY='+secrets.token_urlsafe(24)+'\nPORT=7860\n')"
  if errorlevel 1 (
    echo BLAD: nie udalo sie utworzyc .env. Czy Python jest zainstalowany?
    pause
    exit /b 1
  )
  echo Utworzono plik .env z haslem do panelu.
)

docker compose up -d --build
if errorlevel 1 (
  echo BLAD: docker compose nie wystartowal.
  pause
  exit /b 1
)

echo.
echo Proxy dziala:  http://localhost:7860/v1
echo Panel admina:  http://localhost:7860/
for /f "tokens=1,* delims==" %%a in (.env) do if "%%a"=="ADMIN_KEY" echo Haslo panelu:  %%b
echo.
pause
