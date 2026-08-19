from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.employee import Base


class Gerencia(Base):
    __tablename__ = 'gerencias'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(150), unique=True, nullable=False, index=True)
    descripcion = Column(String(500), nullable=True)
    estado = Column(String(20), nullable=False, default='Activo', server_default='Activo')
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    departamentos = relationship('Departamento', back_populates='gerencia', cascade='all, delete-orphan')


class Departamento(Base):
    __tablename__ = 'departamentos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(150), unique=True, nullable=False, index=True)
    descripcion = Column(String(500), nullable=True)
    estado = Column(String(20), nullable=False, default='Activo', server_default='Activo')
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    gerencia_id = Column(Integer, ForeignKey('gerencias.id'), nullable=False)
    gerencia = relationship('Gerencia', back_populates='departamentos')
    cargos = relationship('Cargo', back_populates='departamento', cascade='all, delete-orphan')


class Cargo(Base):
    __tablename__ = 'cargos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(150), unique=True, nullable=False, index=True)
    descripcion = Column(String(500), nullable=True)
    estado = Column(String(20), nullable=False, default='Activo', server_default='Activo')
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    departamento_id = Column(Integer, ForeignKey('departamentos.id'), nullable=False)
    departamento = relationship('Departamento', back_populates='cargos')
