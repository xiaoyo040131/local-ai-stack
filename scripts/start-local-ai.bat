@echo off
chcp 65001 >nul
title local-ai-stack : Backend (Ollama + proxy)

REM ============================================================
REM   local-ai-stack - start the backend services only
REM   (Ollama + the Anthropic/OpenAI proxy on port 11435)
REM
REM   BEFORE USE: edit the two PATHS below to match your machine.
REM     - OLLAMA : full path to ollama.exe
REM     - PYTHON : full path to python.exe
REM   You can change the model via OLLAMA_MODEL below.
REM ============================================================

set "OLLAMA=C:\YOUR_PATHS\Ollama\ollama.exe"
set "PYTHON=C:\YOUR_PATHS\Python\python.exe"
set "OLLAMA_MODEL=gpt-oss:20b"

REM scripts live next to this .bat (%~dp0)
set "PROXY=%~dp0gptoss_proxy.py"

echo ==========================================================
echo   local-ai-stack Backend  (Ollama + proxy)
echo ==========================================================

REM ---- 1. Start Ollama if not running ----
tasklist /fi "imagename eq ollama.exe" 2>nul | findstr /i "ollama.exe" >nul
if errorlevel 1 (
    echo [1/2] Starting Ollama...
    start "" "%OLLAMA%" serve
    timeout /t 6 /nobreak >nul
) else (
    echo [1/2] Ollama already running.
)

REM ---- 2. Start proxy on port 11435 if not running ----
netstat -ano | findstr ":11435.*LISTENING" >nul
if errorlevel 1 (
    echo [2/2] Starting proxy on 11435...
    start "proxy" /min "%PYTHON%" "%PROXY%"
    timeout /t 3 /nobreak >nul
) else (
    echo [2/2] Proxy already running.
)

echo.
echo ==========================================================
echo   Backend ready. Now open a new terminal and run:
echo       claude          (Claude Code + your local model)
echo       python webchat.py   (terminal chat with web search)
echo ==========================================================
echo.
pause
