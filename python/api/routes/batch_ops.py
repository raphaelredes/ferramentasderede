# python/api/routes/batch_ops.py
"""Endpoints da API para Execução em Lote (Batch Runner) e Repositório de Snippets."""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import src.system.core.batch_runner as batch_runner
import src.system.core.snippets_manager as snippets_manager
from src.core.database import db
from api.routes.security import vault

router = APIRouter(prefix="/batch", tags=["Execução em Lote & Snippets"])


class BatchTarget(BaseModel):
    id: Optional[int] = None
    ip: str
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = 5985
    use_ssl: Optional[bool] = False
    auth: Optional[str] = "ntlm"


class BatchExecuteRequest(BaseModel):
    command: str = Field(..., description="Comando PowerShell ou CMD a ser executado")
    targets: List[BatchTarget] = Field(..., description="Lista de hosts de destino")
    max_workers: Optional[int] = Field(10, description="Número máximo de threads simultâneas")
    timeout: Optional[int] = Field(30, description="Timeout por host em segundos")


class SnippetCreateRequest(BaseModel):
    title: str = Field(..., description="Título do snippet")
    command: str = Field(..., description="Comando PowerShell/CMD")
    description: Optional[str] = Field("", description="Descrição do que o comando faz")
    category: Optional[str] = Field("Geral", description="Categoria do script")
    type: Optional[str] = Field("powershell", description="powershell ou cmd")


@router.post("/execute")
async def execute_batch(req: BatchExecuteRequest) -> Dict[str, Any]:
    """Executa um comando remotamente em múltiplos alvos em paralelo."""
    try:
        # Preencher credenciais do cofre caso o target não traga credenciais explícitas
        target_dicts = []
        for t in req.targets:
            t_dict = t.model_dump()
            if not t_dict.get("username") or not t_dict.get("password"):
                # Tentar buscar credencial do host no host_manager ou vault
                creds = vault.get_credentials()
                if creds:
                    # Usar primeira credencial padrão do cofre se disponível
                    first_cred = list(creds.values())[0]
                    t_dict["username"] = t_dict.get("username") or first_cred.get("username")
                    t_dict["password"] = t_dict.get("password") or first_cred.get("password")
            target_dicts.append(t_dict)

        results = batch_runner.execute_batch_command(
            targets=target_dicts,
            command=req.command,
            max_workers=req.max_workers or 10,
            timeout=req.timeout or 30
        )
        
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "total": len(results),
            "success_count": success_count,
            "failed_count": len(results) - success_count,
            "results": results
        }
    except Exception as exc:
        logging.error(f"Erro na execução em lote: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/snippets")
async def get_snippets(category: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Lista todos os snippets salvos no repositório."""
    try:
        return snippets_manager.list_snippets(category=category)
    except Exception as exc:
        logging.error(f"Erro ao listar snippets: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/snippets")
async def create_snippet(req: SnippetCreateRequest) -> Dict[str, Any]:
    """Cria um novo snippet no repositório."""
    try:
        snippet_id = snippets_manager.save_snippet(
            title=req.title,
            command=req.command,
            description=req.description or "",
            category=req.category or "Geral",
            snippet_type=req.type or "powershell"
        )
        return {"id": snippet_id, "status": "created"}
    except Exception as exc:
        logging.error(f"Erro ao criar snippet: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/snippets/{snippet_id}")
async def remove_snippet(snippet_id: int) -> Dict[str, Any]:
    """Exclui um snippet pelo ID."""
    try:
        success = snippets_manager.delete_snippet(snippet_id)
        if not success:
            raise HTTPException(status_code=404, detail="Snippet não encontrado.")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Erro ao excluir snippet {snippet_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
