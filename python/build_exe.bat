@echo off
echo ===================================
echo  Ferramentas de Rede - Build Script
echo ===================================
echo.

echo [1/3] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo      OK!
echo.

echo [2/3] Construindo executavel...
pyinstaller build_config.spec --clean --noconfirm
echo      OK!
echo.

echo [3/3] Verificando resultado...
if not exist "dist\server\server.exe" (
    echo [ERRO] O executavel do servidor nao foi encontrado em dist\server\server.exe
    exit /b 1
)
echo      SUCESSO! Executavel criado em: dist\server\server.exe
for %%A in (dist\server\server.exe) do echo      Tamanho: %%~zA bytes
echo.

echo ===================================
echo  Build concluido!
echo ===================================

