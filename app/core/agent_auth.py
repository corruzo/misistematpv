from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.agent_service import authenticate_agent


def require_agent(api_key: Annotated[str | None, Header(alias='Authorization')] = None, db: Session = Depends(get_db)):
    if not api_key or not api_key.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Se requiere autenticación Bearer.')
    token = api_key[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail='La API key es inválida.')
    return token


def require_agent_token(token: str = Depends(require_agent)) -> str:
    return token


def require_garita_agent(garita_id: str, token: str = Depends(require_agent), db: Session = Depends(get_db)):
    agent = authenticate_agent(db, token, garita_id)
    if not agent:
        raise HTTPException(status_code=403, detail='Agente de garita no autorizado.')
    return agent