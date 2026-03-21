@echo off
title VoiceTyper
cd /d "%~dp0"

:: Activer l'environnement virtuel
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [ERREUR] L'environnement virtuel n'existe pas.
    echo Lance d'abord setup.bat pour installer.
    pause
    exit /b 1
)

:: Lancer VoiceTyper
python voice_typer.py

:: Si le script crash, garder la fenetre ouverte
if errorlevel 1 (
    echo.
    echo [ERREUR] VoiceTyper s'est arrete avec une erreur.
    pause
)
