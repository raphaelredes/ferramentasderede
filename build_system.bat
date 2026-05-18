@echo off
REM ==========================================================================
REM  BUILD COMPLETO - Ferramentas de Rede (Portatil ~40 MB)
REM
REM  Pipeline correto:
REM    1. npm install         (deps do frontend)
REM    2. vite build          (gera electron/dist/)
REM    3. pyinstaller build_webview.spec  (empacota electron/dist + backend)
REM
REM  Artefato final: python\dist\Ferramentas.de.Rede.v<versao>.exe (~40 MB)
REM
REM  NUNCA rode "npm run build" inteiro - ele invoca electron-builder, que
REM  produz um portatil de 400 MB com Chromium completo. ISSO NAO E PORTATIL.
REM ==========================================================================
echo ===========================================
echo  Ferramentas de Rede - Build Portatil
echo ===========================================
echo.

echo [1/3] Instalando dependencias do Frontend...
cd electron
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha em npm install.
    exit /b %ERRORLEVEL%
)
echo.

echo [2/3] Construindo bundle do Frontend (vite build)...
call npx vite build
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha no vite build.
    exit /b %ERRORLEVEL%
)
cd ..
echo.

echo [3/3] Construindo executavel portatil (PyInstaller)...
cd python
call build_exe.bat
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] PyInstaller falhou.
    cd ..
    exit /b %ERRORLEVEL%
)
cd ..
echo.

echo ===========================================
echo  Build Completo!
echo  Portatil em: python\dist\Ferramentas.de.Rede.v*.exe
echo ===========================================
