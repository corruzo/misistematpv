from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.core.enums import EstadoEmpleado

EstadoEnum = EstadoEmpleado

class EmpleadoCreate(BaseModel):
    cedula: str = Field(..., min_length=1, max_length=50)
    nombre_apellido: str = Field(..., min_length=2, max_length=200)
    gerencia: Optional[str] = Field(None, max_length=150)
    departamento: Optional[str] = Field(None, max_length=150)
    cargo: Optional[str] = Field(None, max_length=150)
    gerencia_id: Optional[int] = None
    departamento_id: Optional[int] = None
    cargo_id: Optional[int] = None
    estado: EstadoEnum = EstadoEnum.Activo
    tipo_nomina: Optional[str] = Field(None, max_length=50)

class EmpleadoUpdate(BaseModel):
    nombre_apellido: Optional[str] = Field(None, min_length=2, max_length=200)
    gerencia: Optional[str] = Field(None, max_length=150)
    departamento: Optional[str] = Field(None, max_length=150)
    cargo: Optional[str] = Field(None, max_length=150)
    gerencia_id: Optional[int] = None
    departamento_id: Optional[int] = None
    cargo_id: Optional[int] = None
    estado: Optional[EstadoEnum] = None
    tipo_nomina: Optional[str] = Field(None, max_length=50)

class EmpleadoOut(BaseModel):
    id: int
    cedula: str
    nombre_apellido: str
    gerencia: Optional[str] = None
    departamento: Optional[str] = None
    cargo: Optional[str] = None
    gerencia_id: Optional[int] = None
    departamento_id: Optional[int] = None
    cargo_id: Optional[int] = None
    estado: EstadoEnum
    tipo_nomina: Optional[str] = None
    foto_url: Optional[str] = None
    fecha_creacion: datetime

    # Configuración para compatibilidad con ORM (SQLAlchemy) en Pydantic v2
    model_config = ConfigDict(from_attributes=True)