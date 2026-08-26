from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.core.datetime_utils import utc_now
from app.models.base import Base


class AccessDeniedEvent(Base):
    __tablename__ = 'eventos_acceso_denegado'

    id = Column(Integer, primary_key=True, autoincrement=True)
    empleado_id = Column(Integer, ForeignKey('empleados.id'), nullable=True, index=True)
    empleado_nombre = Column(String(200), nullable=False)
    estado = Column(String(20), nullable=False)
    fecha_hora = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
