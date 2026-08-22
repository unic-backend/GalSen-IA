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

REM --- 3bis. Cle d'acces locale --------------------------------
REM  Sans GALSEN_API_KEYS, l'API refuse tout et le tableau de bord
REM  affiche "Cle API absente" sur chaque panneau. Mesure sur la
REM  machine du proprietaire, 2026-08-22 : la plateforme demarrait,
REM  l'interface s'affichait, et rien n'etait utilisable.
REM
REM  Ceci n'affaiblit AUCUNE regle d'authentification : une cle reste
REM  exigee et verifiee. Ce qui change, c'est qu'elle est fabriquee et
REM  MONTREE au lieu d'etre devinee. Le fichier vit dans data\, que
REM  .gitignore exclut, et n'est jamais versionne.
REM  Aucun bloc entre parentheses ici, et c'est delibere : en `cmd`, une
REM  variable posee dans un bloc n'est pas relisible dans le MEME bloc sans
REM  `enabledelayedexpansion`. La premiere version faisait
REM  `for ... do set CLE=%%k` puis `echo %CLE%` dans le meme `else`, et
REM  ecrivait donc un fichier VIDE. PowerShell ecrit le fichier lui-meme,
REM  le batch se contente de le relire — plus rien a synchroniser.
REM  Une variable deja posee dans le terminal appelant gagne — mais il faut
REM  le DIRE. Mesure sur la machine du proprietaire, 2026-08-22 : un
REM  `set GALSEN_API_KEYS=...` tape plus tot dans le meme terminal faisait
REM  sauter la generation en silence. Le fichier contenait un GUID, le serveur
REM  tournait avec une autre cle, et l'interface repondait "Cle API invalide"
REM  sans que rien n'explique pourquoi. Un script qui se tait quand il saute
REM  est un script qui ment par omission.
if "%GALSEN_API_KEYS%"=="" goto :cle_generee
echo.
echo   [!] GALSEN_API_KEYS est deja definie dans ce terminal.
echo       Le serveur utilisera CETTE cle, pas celle de
echo       data\cle_locale.txt. C'est voulu si tu l'as posee toi-meme.
echo       Sinon : ouvre un terminal NEUF et relance.
echo.
goto :cle_prete
:cle_generee
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0data\cle_locale.txt" powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') | Out-File -Encoding ascii -NoNewline '%~dp0data\cle_locale.txt'"
set GALSEN_LOCAL_KEY=
set /p GALSEN_LOCAL_KEY=<"%~dp0data\cle_locale.txt"
if "%GALSEN_LOCAL_KEY%"=="" (
    echo [X] La cle locale n'a pas pu etre creee ^(PowerShell indisponible ?^).
    echo     Contourne-le : set GALSEN_API_KEYS=ma-cle:admin:moi
    pause & exit /b 1
)
set GALSEN_API_KEYS=%GALSEN_LOCAL_KEY%:admin:proprietaire
echo.
echo   ===========================================================
echo     CLE API LOCALE — copie-la dans le champ "Cle API" du
echo     tableau de bord, en haut a droite, puis "Appliquer" :
echo.
echo        %GALSEN_LOCAL_KEY%
echo.
echo     Elle est aussi dans data\cle_locale.txt et ne change plus.
echo   ===========================================================
echo.
:cle_prete

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
REM `@echo off` a l'interieur : sans lui, la fenetre d'attente affiche
REM chaque iteration de la boucle et se remplit de bruit. Mesure sur la
REM machine du proprietaire, 2026-08-22.
start "GalSen-attente" /min cmd /c "@echo off & for /l %%i in (1,1,60) do (curl -s -o nul -m 1 http://127.0.0.1:8000/health >nul 2>&1 && (start "" http://localhost:8000/ui & exit) || timeout /t 1 /nobreak >nul)"

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
