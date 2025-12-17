# Sistema de Testes de Integridade

Este diretório contém testes de integração para proteger funcionalidades críticas da aplicação contra quebras acidentais durante o desenvolvimento.

## 📋 Visão Geral

Os testes de integridade garantem que funcionalidades essenciais continuem funcionando corretamente mesmo após modificações no código. Eles atuam como uma "trava" de segurança, prevenindo que novas alterações quebrem recursos que já estavam funcionando.

## 🎯 Por Que Este Sistema Existe

Este sistema foi criado após problemas recorrentes onde funcionalidades críticas paravam de funcionar após modificações no código. Os testes garantem que:

1. **Funcionalidades críticas permaneçam funcionais** mesmo após refatorações
2. **Problemas sejam detectados imediatamente** antes de fazer commits
3. **A qualidade do código seja mantida** ao longo do desenvolvimento
4. **Regressões sejam evitadas** ao fazer novas alterações

## 📁 Estrutura

```
tests/
├── README.md                           # Este arquivo
├── integration/                        # Testes de integração
│   ├── test_system_info_disks.py      # Testes para informações de disco
│   └── [outros testes futuros]
└── [outros tipos de testes]
```

## 🚀 Como Usar

### Validação Antes de Commits (RECOMENDADO)

Execute o script de validação antes de fazer qualquer commit:

```bash
python validate_critical_features.py
```

Este script:
- ✅ Executa todos os testes críticos
- ✅ Mostra um resumo claro dos resultados
- ✅ Indica se é seguro fazer commit
- ✅ Fornece orientações caso algum teste falhe

**IMPORTANTE:** Só faça commit se todos os testes passarem!

### Executar Testes Individuais

Para executar um teste específico:

```bash
# Teste de informações de disco
python tests/integration/test_system_info_disks.py
```

### Executar Todos os Testes de Integração

```bash
# No Windows
for %f in (tests\integration\test_*.py) do python "%f"

# No Linux/Mac
for f in tests/integration/test_*.py; do python "$f"; done
```

## 📝 Testes Disponíveis

### 1. Teste de Informações de Disco (`test_system_info_disks.py`)

**Protege:** Funcionalidade de exibição de discos no painel de informações do sistema

**Testa:**
- ✅ Script PowerShell não usa `JavaScriptSerializer` (causa referência circular)
- ✅ Script PowerShell usa `ConvertTo-Json` para serialização
- ✅ Estrutura de dados dos discos está correta
- ✅ Campo `Disks` está presente em `processed_data`
- ✅ Não existem callbacks duplicados (causa condição de corrida)
- ✅ Métodos críticos existem (`get_disks_info`, `_display_disk_info`)

**Quando executar:**
- Antes de modificar `src/system/core/remote_commands.py`
- Antes de modificar `src/ui/components/system_info_panel.py`
- Antes de modificar `src/ui/components/tool_controllers/sysinfo_controller.py`
- Antes de fazer qualquer commit

**Arquivos protegidos:**
- `src/system/core/remote_commands.py` (linhas 1072-1084)
- `src/ui/components/system_info_panel.py` (linhas 54-114, 141-177)
- `src/ui/components/tool_controllers/sysinfo_controller.py`

## 🔧 Adicionando Novos Testes

Quando você criar uma nova funcionalidade crítica ou corrigir um bug importante, crie um teste de integração:

1. **Crie um novo arquivo de teste:**
   ```bash
   tests/integration/test_sua_funcionalidade.py
   ```

2. **Use a estrutura padrão:**
   ```python
   """
   Teste de Integração: Sua Funcionalidade

   CRÍTICO: Este teste DEVE passar sempre.
   """
   import unittest
   import sys
   import os
   from unittest.mock import Mock, patch

   # Configurar encoding para Windows
   if sys.platform == 'win32':
       import io
       sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
       sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

   class TestSuaFuncionalidade(unittest.TestCase):
       def test_algo_importante(self):
           """Descrição do teste"""
           # Seu código de teste aqui
           pass

   if __name__ == '__main__':
       # Código para executar o teste
       pass
   ```

3. **Adicione o teste ao script de validação:**

   Edite `validate_critical_features.py` e adicione seu teste à lista `critical_tests`:
   ```python
   critical_tests = [
       {
           "path": tests_dir / "test_system_info_disks.py",
           "description": "Teste de Integração - Informações de Disco"
       },
       {
           "path": tests_dir / "test_sua_funcionalidade.py",
           "description": "Teste de Integração - Sua Funcionalidade"
       },
   ]
   ```

## 🛡️ Boas Práticas

### ✅ FAÇA:
- Execute o script de validação antes de cada commit
- Crie testes para funcionalidades críticas
- Corrija testes que falharem antes de fazer commit
- Mantenha os testes atualizados com as mudanças no código
- Documente o que cada teste protege

### ❌ NÃO FAÇA:
- Fazer commit com testes falhando
- Remover testes sem entender o impacto
- Ignorar falhas nos testes
- Modificar testes só para "fazê-los passar" sem corrigir o problema real

## 🐛 Troubleshooting

### Teste falha com erro de encoding

**Problema:** `UnicodeEncodeError: 'charmap' codec can't encode character`

**Solução:** O código já inclui configuração de encoding UTF-8 para Windows. Se o erro persistir, verifique se você tem estas linhas no início do teste:

```python
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

### Teste falha ao importar módulos

**Problema:** `ModuleNotFoundError: No module named 'src'`

**Solução:** Verifique se você tem esta linha no seu teste:

```python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
```

### Teste falha ao mockar Tkinter

**Problema:** `AttributeError: 'SystemInfoPanel' object has no attribute 'tk'`

**Solução:** Para testes de UI, use mocks adequados ou teste apenas a lógica sem criar widgets reais. Veja `test_system_info_disks.py` como exemplo.

## 📞 Suporte

Se você encontrar problemas com os testes:

1. Leia as mensagens de erro cuidadosamente
2. Verifique o troubleshooting acima
3. Execute o teste específico que está falhando para mais detalhes
4. Revise as mudanças que você fez no código

## 🔄 Histórico de Mudanças

- **2025-11-06:** Sistema de testes criado para proteger funcionalidade de discos
  - Teste de integração para informações de disco
  - Script de validação pré-commit
  - Documentação completa

## 📚 Recursos Adicionais

- [Python unittest](https://docs.python.org/3/library/unittest.html)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)

---

**Lembre-se:** Os testes existem para proteger você e seu código. Use-os!
