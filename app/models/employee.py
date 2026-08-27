from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.enums import EstadoEmpleado
from app.models.base import Base

EstadoEnum = EstadoEmpleado

class Empleado(Base):
    __tablename__ = 'empleados'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cedula = Column(String(50), unique=True, nullable=False, index=True)
    codigo_tarjeta = Column(String(100), unique=True, nullable=True, index=True)
    nombre_apellido = Column(String(200), nullable=False)
    fecha_nacimiento = Column(Date, nullable=True)
    telefono = Column(String(30), nullable=True)
    email = Column(String(254), nullable=True)
    contacto_emergencia_parentesco = Column(String(100), nullable=True)
    contacto_emergencia_telefono = Column(String(30), nullable=True)
    departamento_id = Column(Integer, ForeignKey('departamentos.id'), nullable=False)
    cargo_id = Column(Integer, ForeignKey('cargos.id'), nullable=False)
    estado = Column(Enum(EstadoEnum), nullable=False, default=EstadoEnum.Activo)
    tipo_nomina = Column(String(50), nullable=True)
    foto_url = Column(String(300), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    departamento_rel = relationship('Departamento', foreign_keys=[departamento_id])
    cargo_rel = relationship('Cargo', foreign_keys=[cargo_id])

    @property
    def departamento(self):
        return self.departamento_rel.nombre if self.departamento_rel else None

    @property
    def cargo(self):
        return self.cargo_rel.nombre if self.cargo_rel else None

    @property
    def gerencia(self):
        if self.departamento_rel and self.departamento_rel.gerencia:
            return self.departamento_rel.gerencia.nombre
        return None

    @property
    def gerencia_id(self):
        if self.departamento_rel and self.departamento_rel.gerencia:
            return self.departamento_rel.gerencia.id
        return None
