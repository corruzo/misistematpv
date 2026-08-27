from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.agent_auth import require_agent_token, require_garita_agent
from app.database.session import get_db
from app.models.gate_agent import GateAgent
from app.schemas.attendance import AttendanceOrigin
from app.schemas.gate_agent import AgentHeartbeatRequest, AgentScanRequest
from app.services.access_event_service import record_denied_event
from app.services.agent_service import authenticate_agent, clock_skew_warning, update_agent_heartbeat
from app.services.attendance_service import AttendanceError, EmployeeAccessDeniedError, register_scan

router = APIRouter()


@router.post('/api/v1/asistencia/lectura', status_code=201)
def receive_agent_scan(
    payload: AgentScanRequest,
    db: Session = Depends(get_db),
    token: str = Depends(require_agent_token),
):
    agent = authenticate_agent(db, token, payload.garita_id)
    if not agent:
        raise HTTPException(status_code=403, detail='Agente de garita no autorizado.')
    if payload.timestamp_envio is not None:
        clock_skew_warning(payload.timestamp_envio)
    try:
        result = register_scan(
            db,
            payload.codigo_tarjeta,
            AttendanceOrigin.PUERTO_COM,
            marked_at=payload.timestamp_lectura,
            operation_id=payload.operation_id,
        )
        return result
    except EmployeeAccessDeniedError as exc:
        if not record_denied_event(db, exc):
            raise HTTPException(status_code=503, detail='No se pudo registrar la alerta de acceso.')
        return JSONResponse(status_code=403, content={
            'code': 'employee_access_denied',
            'detail': str(exc),
            'empleado_nombre': exc.employee_name,
            'estado': exc.employee_status,
            'fecha_hora': exc.marked_at.isoformat() if exc.marked_at else None,
        })
    except AttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail='No se pudo persistir la lectura.') from exc


@router.post('/api/v1/garitas/{garita_id}/heartbeat')
def receive_agent_heartbeat(
    garita_id: str,
    payload: AgentHeartbeatRequest,
    agent: GateAgent = Depends(require_garita_agent),
    db: Session = Depends(get_db),
):
    if payload.garita_id != garita_id:
        raise HTTPException(status_code=422, detail='La garita del payload no coincide con la ruta.')
    update_agent_heartbeat(db, agent, payload)
    return {'ok': True}