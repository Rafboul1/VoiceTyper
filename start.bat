@echo off
title VoiceTyper
cd /d "%~dp0"

:: Lancer VoiceTyper avec le python du venv directement (chemin relatif apres le cd).
:: On NE passe PAS par "activate + python" : avec plusieurs Python installes sur la
:: machine, le "python" du PATH ne resout pas toujours vers le venv (-> ModuleNotFoundError).
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe voice_typer.py
) else (
    echo [ERREUR] L'environnement virtuel n'existe pas.
    echo Lance d'abord setup.bat pour installer.
    pause
    exit /b 1
)

:: Si le script crash, garder la fenetre ouverte
if errorlevel 1 (
    echo.
    echo [ERREUR] VoiceTyper s'est arrete avec une erreur.
    pause
)
