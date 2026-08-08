@echo off
echo ============================================
echo   Lancement de Free Claude Code
echo ============================================
echo.

echo [1/2] Demarrage du serveur proxy (fcc-server)...
start "Free Claude Server" powershell -NoExit -Command "fcc-server"

echo.
echo Attente de 6 secondes...
timeout /t 6 /nobreak >nul

echo.
echo [2/2] Lancement de Claude Code...
start "Claude Code" powershell -NoExit -Command "fcc-claude"

echo.
echo ============================================
echo   Tout est lance !
echo   - Garde la fenetre "Free Claude Server" ouverte
echo   - Tu peux utiliser la fenetre "Claude Code"
echo ============================================
pause