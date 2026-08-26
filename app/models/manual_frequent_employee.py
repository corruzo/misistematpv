from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class ManualFrequentEmployee(Base):
    __tablename__ = 'empleados_frecuentes_manual'
    __table_args__ = (UniqueConstraint('usuario_id', 'empleado_id', name='UQ_empleados_frecuentes_manual_usuario_empleado'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    empleado_id = Column(Integer, ForeignKey('empleados.id'), nullable=False, index=True)
    posicion = Column(Integer, nullable=False, default=0)

    empleado = relationship('Empleado')