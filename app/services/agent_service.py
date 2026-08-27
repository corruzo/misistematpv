import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import AGENT_CLOCK_SKEW_MINUTES, AGENT_HEARTBEAT_PERSIST_SECONDS
from app.core.datetime_utils import utc_now
from app.models.gate_agent import GateAgent
from app.services.notification_service import publish_reader_status_changed

logger = logging.getLogger(__name__)
HEARTBEAT_PERSIST_INTERVAL = timedelta(seconds=AGENT_HEARTBEAT_PERSIST_SECONDS)


def hash_agent_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()


def authenticate_agent(db: Session, api_key: str, garita_id: str) -> GateAgent | None:
    key_hash = hash_agent_api_key(api_key)
    agent = db.query(GateAgent).filter(GateAgent.codigo == garita_id, GateAgent.activo == True).first()
    if not agent or not hmac.compare_digest(agent.api_key_hash, key_hash):
        return None
    return agent


def clock_skew_warning(timestamp: datetime) -> None:
    now = datetime.now(timezone.utc)
    difference = abs((now - timestamp.astimezone(timezone.utc)).total_seconds())
    if difference > AGENT_CLOCK_SKEW_MINUTES * 60:
        logger.warning(
            'Desincronización de reloj del agente RFID: diferencia_segundos=%s umbral_minutos=%s',
            round(difference), AGENT_CLOCK_SKEW_MINUTES,
        )


def update_agent_heartbeat(db: Session, agent: GateAgent, payload, now: datetime | None = None) -> bool:
    now = now or utc_now()
    previous = agent.ultimo_heartbeat
    previous_connected = agent.lector_conectado
    previous_queue = agent.cola_reportada
    should_persist = (
        previous is None
        or now - previous >= HEARTBEAT_PERSIST_INTERVAL
        or previous_connected != payload.reader_connected
        or previous_queue != payload.queue_depth
    )
    if not should_persist:
        return False
    agent.ultimo_heartbeat = now
    agent.ultima_conexion = now
    agent.version_agente = payload.agent_version
    agent.cola_reportada = payload.queue_depth
    agent.lector_conectado = payload.reader_connected
    if previous_connected != payload.reader_connected:
        publish_reader_status_changed(db, agent.nombre, payload.reader_connected)
    db.commit()
    return True


def get_agent_status(db: Session, garita_id: str | None = None) -> dict:
    query = db.query(GateAgent).filter(GateAgent.activo == True)
    if garita_id:
        query = query.filter(GateAgent.codigo == garita_id)
    agent = query.order_by(GateAgent.ultimo_heartbeat.desc()).first()
    if not agent:
        return {'configured': bool(garita_id), 'connected': False, 'reader_connected': False, 'queue_depth': 0, 'message': 'Agente de garita no configurado'}
    now = utc_now()
    heartbeat = agent.ultimo_heartbeat
    age = (now - heartbeat).total_seconds() if heartbeat else None
    connected = age is not None and age <= max(AGENT_HEARTBEAT_PERSIST_SECONDS * 3, 180)
    if not connected:
        message = 'Agente de garita desconectado'
    elif agent.cola_reportada:
        message = f'Agente en línea; {agent.cola_reportada} lectura(s) en cola'
    elif not agent.lector_conectado:
        message = 'Agente en línea; lector desconectado'
    else:
        message = 'Agente y lector en línea'
    return {
        'configured': True,
        'connected': connected,
        'reader_connected': bool(agent.lector_conectado),
        'queue_depth': agent.cola_reportada,
        'message': message,
        'last_seen': heartbeat,
        'garita_id': agent.codigo,
    }