@echo off
setlocal
cd /d "%~dp0"

echo Dang khoi dong cac dich vu...
docker compose up -d --no-build --remove-orphans
if errorlevel 1 (
  echo Chua co image hoac image bi thieu. Dang build lan dau...
  docker compose up --build -d --wait --wait-timeout 180
)
if errorlevel 1 (
  echo Khoi dong that bai. Xem loi bang: docker compose ps
  exit /b 1
)

echo.
echo Dang cho giao dien san sang...
set READY=
for /L %%i in (1,1,30) do (
  curl.exe -fsS http://localhost:8000/docs >nul 2>&1 && set READY=1 && goto READY
  timeout /t 1 /nobreak >nul
)
:READY
echo Ung dung: http://localhost:8000
echo RabbitMQ: http://localhost:15672
start "" http://localhost:8000
