@echo off
echo ===========================================
echo  Ferramentas de Rede - Build Completo
echo ===========================================
echo.

echo [1/3] Construindo Backend Python...
cd python
call build_exe.bat
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao construir backend Python!
    exit /b %ERRORLEVEL%
)
cd ..
echo.

echo [2/3] Instalando dependencias do Frontend...
cd electron
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao instalar dependencias!
    exit /b %ERRORLEVEL%
)
echo.

echo [3/3] Construindo Aplicacao Electron...
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao construir aplicacao Electron!
    exit /b %ERRORLEVEL%
)
cd ..
echo.

echo ===========================================
echo  Build Completo com Sucesso!
echo  Instalador em: electron\release
echo ===========================================
