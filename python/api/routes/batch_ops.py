# python/api/routes/batch_ops.py
"""Endpoints da API para Execução em Lote (Batch Runner) e Repositório de Snippets."""

import logging
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
import src.system.core.batch_runner as batch_runner
import src.system.core.snippets_manager as snippets_manager
from src.core.database import db
from api.routes.security import vault

router = APIRouter(prefix="/batch", tags=["Execução em Lote & Snippets"])

_SAFE_TARGET_RE = re.compile(
    r"^(?:(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9][A-Za-z0-9._\-]{0,252})$"
)


def _validate_target_ip(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Alvo inválido.")
    cleaned = value.strip()
    if not cleaned or not _SAFE_TARGET_RE.match(cleaned):
        raise ValueError(f"Host ou IP inválido: {value!r}")
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", cleaned):
        if not all(0 <= int(o) <= 255 for o in cleaned.split(".")):
            raise ValueError(f"IPv4 inválido: {value!r}")
    return cleaned


class BatchTarget(BaseModel):
    id: Optional[int] = None
    ip: str
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = 5985
    use_ssl: Optional[bool] = False
    auth: Optional[str] = "ntlm"

    @field_validator("ip")
    @classmethod
    def _ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


class BatchExecuteRequest(BaseModel):
    command: str = Field(..., description="Comando PowerShell ou CMD a ser executado")
    targets: List[BatchTarget] = Field(..., description="Lista de hosts de destino")
    credential_id: Optional[str] = Field(None, description="ID opcional de credencial no Cofre")
    max_workers: Optional[int] = Field(10, ge=1, le=32, description="Número máximo de threads simultâneas")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Timeout por host em segundos")


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
        vault_cred = None
        needs_vault = any((not t.username or not t.password) for t in req.targets)
        if needs_vault:
            if req.credential_id:
                if not vault.is_unlocked:
                    raise HTTPException(
                        status_code=401,
                        detail="Cofre bloqueado. Desbloqueie o Cofre na aba Segurança para usar credenciais salvas.",
                    )
                vault_cred = vault.get_credential(req.credential_id)
                if not vault_cred:
                    raise HTTPException(status_code=404, detail="Credencial selecionada não encontrada no Cofre.")
            elif vault.is_unlocked:
                all_creds = vault.get_all_credentials(include_passwords=True)
                if all_creds:
                    vault_cred = all_creds[0]

        target_dicts = []
        missing_creds_all = True
        for t in req.targets:
            t_dict = t.model_dump()
            if (not t_dict.get("username") or not t_dict.get("password")) and vault_cred:
                t_dict["username"] = t_dict.get("username") or vault_cred.get("username")
                t_dict["password"] = t_dict.get("password") or vault_cred.get("password")
            if t_dict.get("username") and t_dict.get("password"):
                missing_creds_all = False
            target_dicts.append(t_dict)

        if target_dicts and missing_creds_all:
            raise HTTPException(
                status_code=401,
                detail="Nenhuma credencial disponível. Desbloqueie o Cofre na aba Segurança ou informe credenciais.",
            )

        results = batch_runner.execute_batch_command(
            targets=target_dicts,
            command=req.command,
            max_workers=min(max(req.max_workers or 10, 1), 32),
            timeout=min(max(req.timeout or 30, 1), 300),
        )

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "total": len(results),
            "success_count": success_count,
            "failed_count": len(results) - success_count,
            "results": results,
        }
    except HTTPException:
        raise
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
