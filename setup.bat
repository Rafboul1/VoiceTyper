@echo off
cd /d "%~dp0"
echo ============================================
echo   VoiceTyper - Installation
echo ============================================
echo.

:: Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Telecharge Python 3.10+ sur https://python.org
    echo IMPORTANT : Coche "Add Python to PATH" pendant l'installation !
    pause
    exit /b 1
)

echo [1/3] Creation de l'environnement virtuel...
python -m venv venv
if errorlevel 1 (
    echo [ERREUR] Impossible de creer l'environnement virtuel.
    pause
    exit /b 1
)

echo [2/3] Activation de l'environnement...
call venv\Scripts\activate.bat

echo [3/3] Installation des dependances...
echo      (ca peut prendre quelques minutes)
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ============================================
echo   Installation terminee !
echo.
echo   IMPORTANT - CUDA (GPU) :
echo   Si tu as une carte NVIDIA, installe aussi
echo   CUDA Toolkit 12.x depuis :
echo   https://developer.nvidia.com/cuda-downloads
echo.
echo   Pour lancer VoiceTyper : double-clique sur start.bat
echo ============================================
pause
