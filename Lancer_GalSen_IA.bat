@echo off
setlocal

:: ============================================
::   LANCEUR GALSEN IA - Claude Code
:: ============================================

:: Aller dans le dossier où se trouve ce fichier .bat
cd /d "%~dp0"

echo.
echo ============================================
echo   GalSen IA - Lancement de Claude Code
echo   Dossier : %cd%
echo ============================================
echo.

:: Lancer le serveur proxy
echo [1/2] Demarrage du serveur proxy (fcc-server)...
start "GalSen IA - Server" powershell -NoExit -Command "fcc-server"

:: Attendre que le serveur demarre
timeout /t 6 /nobreak >nul

:: Lancer Claude Code
echo [2/2] Lancement de Claude Code...
start "GalSen IA - Claude Code" powershell -NoExit -Command "fcc-claude"

echo.
echo ============================================
echo   Claude Code est lance pour GalSen IA
echo   Garde la fenetre "Server" ouverte
echo ============================================
echo.
pause