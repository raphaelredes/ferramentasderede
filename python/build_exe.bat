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
if exist dist\FerramentasDeRede_v1.1.exe (
    echo      SUCESSO! Executavel criado em: dist\FerramentasDeRede_v1.1.exe
    for %%A in (dist\FerramentasDeRede_v1.1.exe) do echo      Tamanho: %%~zA bytes
) else (
    echo      ERRO! Executavel nao foi criado.
)
echo.

echo ===================================
echo  Build concluido!
echo ===================================
pause
