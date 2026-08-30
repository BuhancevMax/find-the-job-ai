@echo off
chcp 65001 > nul
title Find the Job AI — Launcher
color 0A

echo =======================================================
echo        🚀 Find the Job AI — Launcher
echo =======================================================
echo.

:: 1. Setup & Start Python Backend
cd /d "%~dp0PythonScripts"

if not exist ".venv" (
    echo [1/3] Создание виртуального окружения Python...
    python -m venv .venv
    echo [1/3] Установка зависимостей Python...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo [2/3] Запуск Python AI Backend (порт 8000)...
start /b python -m uvicorn main:app --port 8000 > nul 2>&1

:: Wait 2 seconds for backend to initialize
timeout /t 2 /nobreak > nul

:: 2. Start Blazor Frontend
cd /d "%~dp0"
echo [3/3] Запуск веб-интерфейса .NET Blazor...
echo.
echo =======================================================
echo   Приложение готово к работе!
echo   Открытие в браузере: http://localhost:5104
echo   Для завершения работы закройте это окно консоли.
echo =======================================================
echo.

:: Open default browser
start http://localhost:5104

:: Run Blazor Server
dotnet run
