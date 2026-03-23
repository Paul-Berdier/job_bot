@echo off
:: =============================================================
::  Job Bot – Script d'installation Windows
:: =============================================================

echo.
echo   ╔══════════════════════════════════════╗
echo   ║     Job Bot - Installation Windows   ║
echo   ╚══════════════════════════════════════╝
echo.

:: Vérification Python
echo [1/5] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python non trouve. Installez Python 3.10+ depuis python.org
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version') do echo Python %%i detecte

:: Environnement virtuel
echo [2/5] Creation environnement virtuel...
if not exist ".venv" (
    python -m venv .venv
    echo Virtualenv cree
) else (
    echo .venv existe deja
)

:: Activer venv
call .venv\Scripts\activate.bat

:: Dépendances
echo [3/5] Installation des dependances...
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo Dependances installees

:: Playwright
echo [4/5] Installation Playwright Chromium...
playwright install chromium
echo Playwright installe

:: Dossiers
echo [5/5] Creation des dossiers...
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo ============================================
echo   Installation terminee !
echo ============================================
echo.
echo Prochaines etapes :
echo   1. Editez config.yaml
echo   2. Placez votre CV dans data\cv.pdf
echo   3. Activez le venv : .venv\Scripts\activate
echo.
echo Commandes :
echo   python main.py config
echo   python main.py run --dry-run
echo   python main.py run
echo   python dashboard.py
echo.
pause
