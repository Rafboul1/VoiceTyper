@echo off
cd /d "%~dp0"

:: Lance VoiceTyper sans fenêtre visible (mode silencieux)
:: Les logs sont écrits dans voice_typer.log

if exist venv\Scripts\pythonw.exe (
    start "" venv\Scripts\pythonw.exe voice_typer.py
) else (
    echo [ERREUR] Le venv n'existe pas. Lance d'abord setup.bat
    pause
)
