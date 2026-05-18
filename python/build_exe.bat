@echo off
REM ==========================================================================
REM  Build do executavel portatil (Ferramentas de Rede)
REM
REM  IMPORTANTE: este script gera o portatil single-file ~40 MB usando
REM  build_webview.spec (FastAPI + pywebview empacotados num exe so).
REM
REM  NAO USE outro spec. NAO USE electron-builder. Caminhos errados que
REM  geram um portatil quebrado de 400 MB:
REM    - build_config.spec    (gerava server.exe headless para o Electron)
REM    - electron-builder --target portable  (zipa Chromium inteiro)
REM
REM  Pre-requisito: o frontend deve estar buildado em ..\electron\dist\
REM  porque o spec o empacota como pasta gui/. O build_system.bat faz isso
REM  antes de chamar este script.
REM ==========================================================================
echo ===================================
echo  Ferramentas de Rede - Build Script
echo ===================================
echo.

if not exist "..\electron\dist\index.html" (
    echo [ERRO] Frontend nao encontrado em ..\electron\dist\
    echo        Rode "cd ..\electron && npx vite build" antes deste script,
    echo        ou use build_system.bat na raiz que faz tudo na ordem certa.
    exit /b 1
)

echo [1/3] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo      OK!
echo.

echo [2/3] Construindo executavel portatil (build_webview.spec)...
pyinstaller build_webview.spec --clean --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] PyInstaller falhou.
    exit /b %ERRORLEVEL%
)
echo      OK!
echo.

echo [3/3] Verificando resultado...
REM Procura por qualquer .exe gerado em dist (o nome inclui a versao).
set "FOUND="
for %%F in (dist\Ferramentas.de.Rede.v*.exe) do set "FOUND=%%F"
if not defined FOUND (
    echo [ERRO] Nenhum portatil encontrado em dist\Ferramentas.de.Rede.v*.exe
    exit /b 1
)
for %%A in ("%FOUND%") do (
    echo      SUCESSO! Portatil em: %%~fA
    echo      Tamanho: %%~zA bytes
)
echo.

echo ===================================
echo  Build concluido!
echo ===================================
