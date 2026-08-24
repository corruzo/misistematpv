from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.datetime_utils import utc_now
from app.models.base import Base


class AttendanceRecord(Base):
    __tablename__ = 'marcajes_asistencia'

    id = Column(Integer, primary_key=True, autoincrement=True)
    empleado_id = Column(Integer, ForeignKey('empleados.id'), nullable=False, index=True)
    tipo = Column(String(10), nullable=False)
    fecha_hora = Column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    origen = Column(String(20), nullable=False)
    empleado = relationship('Empleado')