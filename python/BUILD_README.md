# Build Instructions - Ferramentas de Rede v1.1

## Como criar o executável

### Método 1: Script Automático (Recomendado)
Execute o arquivo `build_exe.bat` que irá:
1. Limpar builds anteriores
2. Criar o executável
3. Verificar o resultado

### Método 2: Manual
```bash
# Limpar builds anteriores
rmdir /s /q build
rmdir /s /q dist

# Criar executável
pyinstaller build_config.spec --clean --noconfirm
```

## Localização do Executável
Após o build, o executável estará em:
```
dist/FerramentasDeRede_v1.1.exe
```

## Requisitos
- Python 3.8 ou superior
- PyInstaller instalado: `pip install pyinstaller`
- Todas as dependências do projeto instaladas

## Ícone
O executável usa o ícone PNG de alta qualidade localizado em:
```
assets/icon.png
```
**Nota**: O ícone é carregado em resolução 256x256 usando o algoritmo LANCZOS para máxima qualidade na barra de tarefas.

## Tamanho Esperado
O executável único tem aproximadamente **27 MB**.

## Arquivos Importantes
- `build_config.spec` - Configuração do PyInstaller
- `assets/icon.ico` - Ícone da aplicação
- `languages/*.json` - Arquivos de tradução (incluídos no executável)

## Solução de Problemas

### Erro de permissão durante o build
- Feche qualquer instância do executável que esteja rodando
- Desabilite temporariamente o antivírus
- Execute o build novamente

### Executável não inicia
- Verifique se todas as dependências estão instaladas
- Tente executar em modo de console alterando `console=False` para `console=True` no spec file

### Ícone aparece embaçado ou em baixa qualidade
- O sistema agora usa `assets/icon.png` diretamente em resolução 256x256
- Certifique-se de que o arquivo PNG existe e tem boa qualidade
- O ícone é redimensionado usando interpolação LANCZOS para melhor qualidade
