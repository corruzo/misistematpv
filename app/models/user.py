from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func
from app.models.base import Base


class Usuario(Base):
    __tablename__ = 'usuarios'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    password_hash = Column(String(500), nullable=False)
    rol = Column(String(30), nullable=False, default='Administrador', server_default='Administrador')
    activo = Column(Integer, nullable=False, default=1, server_default='1')
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ultimo_acceso = Column(DateTime(timezone=True), nullable=True)
