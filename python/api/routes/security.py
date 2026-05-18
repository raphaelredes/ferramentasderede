from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
import os
import time
import threading
from src.config.settings import SALT_FILE
from src.security.vault import SecureVault

router = APIRouter(tags=["security"])
vault = SecureVault()

# In-process unlock throttle. The backend binds to 127.0.0.1, so the realistic
# attacker is a malicious local process brute-forcing the PBKDF2 master key.
# PBKDF2 with 600k iterations already costs ~250ms per try; this caps things
# further to 5 failures / 60s before forcing a cooldown.
#
# Concurrency model: a single in-flight gate guards the "check + reserve a
# slot" sequence so N concurrent unlock attempts can't all pass the gate at
# `4 failures recorded` and then each add a 5th — the previous design had
# exactly that TOCTOU. The full PBKDF2 derivation still runs OUTSIDE the
# lock; the lock only sequences the bookkeeping.
_UNLOCK_FAILURES: list = []
_UNLOCK_INFLIGHT: int = 0
_UNLOCK_LOCK = threading.Lock()
_UNLOCK_MAX_FAILS = 5
_UNLOCK_WINDOW_S = 60.0
_UNLOCK_COOLDOWN_S = 30.0


def _reserve_unlock_slot():
    """Atomically check the throttle and reserve an in-flight slot.

    Counts recorded failures + currently-running unlock attempts together so
    the cap of 5 can't be exceeded by stacking concurrent requests on top of
    4 already-failed ones."""
    global _UNLOCK_INFLIGHT
    with _UNLOCK_LOCK:
        now = time.time()
        recent = [t for t in _UNLOCK_FAILURES if now - t < _UNLOCK_WINDOW_S]
        _UNLOCK_FAILURES.clear()
        _UNLOCK_FAILURES.extend(recent)
        total = len(recent) + _UNLOCK_INFLIGHT
        if total >= _UNLOCK_MAX_FAILS:
            wait = _UNLOCK_COOLDOWN_S - (now - recent[-1]) if recent else _UNLOCK_COOLDOWN_S
            if wait > 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"Muitas tentativas de desbloqueio. Aguarde {int(wait) + 1}s.",
                )
        _UNLOCK_INFLIGHT += 1


def _release_unlock_slot(success: bool):
    global _UNLOCK_INFLIGHT
    with _UNLOCK_LOCK:
        _UNLOCK_INFLIGHT = max(0, _UNLOCK_INFLIGHT - 1)
        if success:
            _UNLOCK_FAILURES.clear()
        else:
            _UNLOCK_FAILURES.append(time.time())


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
    _reserve_unlock_slot()
    try:
        success = vault.unlock(req.password, req.hint)
    finally:
        _release_unlock_slot(False)  # Default: treat as failure; success path overrides below.
    if not success:
        raise HTTPException(status_code=401, detail="Senha incorreta ou falha ao desbloquear.")
    # On real success, undo the failure record the finally block just added.
    with _UNLOCK_LOCK:
        _UNLOCK_FAILURES.clear()
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
