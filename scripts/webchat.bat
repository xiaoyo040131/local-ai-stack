@echo off
chcp 65001 >nul
title local-ai-stack : Terminal chat (web search)

REM ============================================================
REM   local-ai-stack - terminal chat with web search
REM
REM   BEFORE USE: edit the PYTHON path below to match your machine.
REM   Change the model via OLLAMA_MODEL below.
REM ============================================================

set "PYTHON=C:\YOUR_PATHS\Python\python.exe"
set "OLLAMA_MODEL=gpt-oss:20b"

set "SCRIPT=%~dp0webchat.py"

echo Starting terminal chat (model: %OLLAMA_MODEL%)
"%PYTHON%" "%SCRIPT%"
