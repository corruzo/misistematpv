from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.models.base import Base


class GateAgent(Base):
    __tablename__ = 'agentes_garita'

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(100), nullable=False, unique=True, index=True)
    nombre = Column(String(150), nullable=False)
    api_key_hash = Column(String(64), nullable=False, unique=True)
    activo = Column(Boolean, nullable=False, default=True, server_default='1')
    ultima_conexion = Column(DateTime(timezone=True), nullable=True)
    ultimo_heartbeat = Column(DateTime(timezone=True), nullable=True)
    version_agente = Column(String(40), nullable=True)
    cola_reportada = Column(Integer, nullable=False, default=0, server_default='0')
    lector_conectado = Column(Boolean, nullable=False, default=False, server_default='0')
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default='SYSUTCDATETIME()')
    revocado_en = Column(DateTime(timezone=True), nullable=True)