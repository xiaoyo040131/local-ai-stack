@echo off
chcp 65001 >nul
title local-ai-stack : Claude Code + local model

REM ============================================================
REM   local-ai-stack - launch Claude Code with your local model
REM   (starts Ollama + proxy, then opens Claude Code)
REM
REM   BEFORE USE: edit the three PATHS below to match your machine.
REM     - OLLAMA : full path to ollama.exe
REM     - PYTHON : full path to python.exe
REM     - CLAUDE : full path to claude.exe
REM   Change the model via OLLAMA_MODEL below.
REM ============================================================

set "OLLAMA=C:\YOUR_PATHS\Ollama\ollama.exe"
set "PYTHON=C:\YOUR_PATHS\Python\python.exe"
set "CLAUDE=C:\YOUR_PATHS\claude.exe"
set "OLLAMA_MODEL=gpt-oss:20b"

set "PROXY=%~dp0gptoss_proxy.py"

echo ==========================================================
echo   Claude Code  +  local model  (local-ai-stack)
echo ==========================================================

REM ---- 1. Start Ollama if not running ----
tasklist /fi "imagename eq ollama.exe" 2>nul | findstr /i "ollama.exe" >nul
if errorlevel 1 (
    echo [1/3] Starting Ollama...
    start "" "%OLLAMA%" serve
    timeout /t 6 /nobreak >nul
) else (
    echo [1/3] Ollama already running.
)

REM ---- 2. Start proxy on port 11435 if not running ----
netstat -ano | findstr ":11435.*LISTENING" >nul
if errorlevel 1 (
    echo [2/3] Starting proxy on 11435...
    start "proxy" /min "%PYTHON%" "%PROXY%"
    timeout /t 3 /nobreak >nul
) else (
    echo [2/3] Proxy already running.
)

REM ---- 3. Launch Claude Code (interactive) ----
echo [3/3] Launching Claude Code with your local model...
echo Type your request in Claude Code. Ctrl+C to exit.
echo.
"%CLAUDE%"
