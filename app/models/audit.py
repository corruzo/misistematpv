from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.organization import Cargo, Departamento, Gerencia
from app.models.user import Usuario


class AuditRecord(Base):
    __tablename__ = 'auditoria'

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True, index=True)
    accion = Column(String(50), nullable=False)
    entidad = Column(String(50), nullable=False)
    entidad_id = Column(Integer, nullable=True)
    datos_antes = Column(Text, nullable=True)
    datos_despues = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), nullable=False, server_default=func.sysutcdatetime(), index=True)