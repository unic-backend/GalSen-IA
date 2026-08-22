@echo off
REM ============================================================
REM  Demarrer GalSen IA — de zero a une interface qui repond.
REM
REM  Ce fichier ne suppose rien : il verifie chaque prerequis,
REM  dit ce qui manque, et s'arrete plutot que de lancer une
REM  plateforme a moitie prete.
REM
REM  Usage : double-clic, ou "Demarrer_GalSen.bat" dans un terminal.
REM ============================================================
setlocal
cd /d "%~dp0"
title GalSen IA

echo.
echo ===============================================
echo   GalSen IA — demarrage
echo ===============================================
echo.

REM --- 1. Python -----------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python introuvable.
    echo     Installe Python 3.11+ : https://www.python.org/downloads/
    echo     Coche "Add Python to PATH" pendant l'installation.
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER%

REM --- 2. Dependances ------------------------------------------
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [..] Installation des dependances ^(une seule fois, ~2 min^)
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [X] L'installation a echoue. Lis l'erreur ci-dessus.
        pause & exit /b 1
    )
)
echo [OK] Dependances presentes

REM --- 3. Ollama : le moteur qui fait REPONDRE l'IA -------------
REM  Sans lui, la plateforme demarre mais /generate repond 503.
REM  Ce n'est pas une panne : c'est une capacite non activee.
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] Ollama introuvable — l'IA ne pourra pas REPONDRE.
    echo     Tout le reste fonctionnera ^(agents, workflows, interface^).
    echo.
    echo     Pour l'installer : https://ollama.com/download
    echo     Puis relance ce fichier.
    echo.
    set SANS_MODELE=1
) else (
    echo [OK] Ollama installe
    REM Le serveur repond-il deja ?
    curl -s -o nul -m 3 http://127.0.0.1:11434/api/tags
    if errorlevel 1 (
        echo [..] Demarrage du serveur Ollama
        start "Ollama" /min ollama serve
        timeout /t 5 /nobreak >nul
    )
    REM Un modele est-il present ? Contexte minimum 8192, sinon
    REM le selecteur de GalSen IA le refuse et le dit.
    ollama list | findstr /i "qwen2.5-coder" >nul 2>&1
    if errorlevel 1 (
        echo [..] Telechargement du modele ^(~9 Go, une seule fois^)
        echo     Tu peux aller boire un cafe.
        ollama pull qwen2.5-coder:14b
    )
    echo [OK] Modele pret
)

REM --- 4. Persistance ------------------------------------------
REM  Par defaut tout vit en memoire et disparait a l'arret.
REM  Ces deux variables donnent une memoire durable a la plateforme.
if "%GALSEN_STORAGE_BACKEND%"=="" set GALSEN_STORAGE_BACKEND=sqlite
if "%GALSEN_DATA_DIR%"=="" set GALSEN_DATA_DIR=%~dp0data
if not exist "%GALSEN_DATA_DIR%" mkdir "%GALSEN_DATA_DIR%"
echo [OK] Donnees dans %GALSEN_DATA_DIR%

REM --- 5. Verification honnete avant de servir ------------------
echo.
echo [..] Verification de bout en bout
python scripts\demonstration.py
echo.

REM --- 6. L'API ------------------------------------------------
echo ===============================================
echo   Interface  : http://localhost:8000/ui
echo   Les routes : http://localhost:8000/docs
echo   Sante      : http://localhost:8000/health
echo.
echo   Ctrl+C pour arreter.
echo ===============================================
echo.
if defined SANS_MODELE (
    echo [!] Rappel : sans Ollama, /generate repondra 503.
    echo.
)
REM Le navigateur s'ouvre APRES que le serveur reponde, jamais avant.
REM Premiere version : `start` etait sur la ligne d'avant, et Edge affichait
REM ERR_CONNECTION_REFUSED parce qu'uvicorn met quelques secondes a demarrer.
REM Mesure sur la machine du proprietaire, 2026-08-22.
start "GalSen-attente" /min cmd /c "for /l %%i in (1,1,60) do (curl -s -o nul -m 1 http://127.0.0.1:8000/health && (start "" http://localhost:8000/ui & exit) || timeout /t 1 /nobreak >nul)"

python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000

REM Sans cette pause, un crash d'uvicorn ferme la fenetre et emporte le
REM message d'erreur avec elle. Mesure sur la machine du proprietaire,
REM 2026-08-22 : la fenetre avait disparu et il ne restait rien a lire.
echo.
echo ===============================================
echo   Le serveur s'est arrete.
echo   Si une erreur est affichee au-dessus, elle
echo   est la cause. Cette fenetre reste ouverte.
echo ===============================================
pause

endlocal
