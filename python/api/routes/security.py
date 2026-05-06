from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
import os
from src.config.settings import SALT_FILE
from src.security.vault import SecureVault

router = APIRouter(tags=["security"])
vault = SecureVault()

class UnlockRequest(BaseModel):
    password: str
    hint: Optional[str] = None

class CredentialEntry(BaseModel):
    id: Optional[str] = None
    name: str
    username: str
    password: str
    description: Optional[str] = ""

@router.post("/security/unlock")
def unlock_vault(req: UnlockRequest):
    success = vault.unlock(req.password, req.hint)
    if not success:
        raise HTTPException(status_code=401, detail="Senha incorreta ou falha ao desbloquear.")
    return {"status": "success", "message": "Cofre desbloqueado."}

@router.post("/security/lock")
def lock_vault():
    vault.lock()
    return {"status": "success", "message": "Cofre bloqueado."}

@router.get("/security/status")
def get_vault_status():
    has_salt = os.path.exists(SALT_FILE)
    return {
        "is_unlocked": vault.is_unlocked,
        "has_vault": has_salt or (vault.is_unlocked and vault.master_key is not None)
    }

@router.get("/security/credentials")
def get_credentials():
    if not vault.is_unlocked:
        raise HTTPException(status_code=403, detail="Cofre bloqueado.")
    return vault.get_all_credentials()

@router.post("/security/credentials")
def add_credential(entry: CredentialEntry):
    if not vault.is_unlocked:
        raise HTTPException(status_code=403, detail="Cofre bloqueado.")
    
    saved_entry = vault.add_credential(entry.model_dump())
    return saved_entry

@router.delete("/security/credentials/{entry_id}")
def delete_credential(entry_id: str):
    if not vault.is_unlocked:
        raise HTTPException(status_code=403, detail="Cofre bloqueado.")
    
    vault.delete_credential(entry_id)
    return {"status": "success"}

@router.post("/security/credentials/decrypt")
def decrypt_credential(body: dict = Body(...)):
    if not vault.is_unlocked:
        raise HTTPException(status_code=403, detail="Cofre bloqueado.")
    
    entry_id = body.get("id")
    cred = vault.get_credential(entry_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credencial não encontrada.")
    
    return {"password": cred["password"]}

@router.get("/security/hint")
def get_vault_hint():
    hint = vault.get_hint()
    return {"hint": hint}

@router.post("/security/reset")
def reset_vault():
    success = vault.reset()
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao resetar cofre.")
    return {"status": "success", "message": "Cofre resetado com sucesso."}
