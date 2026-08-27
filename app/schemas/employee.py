from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import date, datetime
from app.core.enums import EstadoEmpleado

EstadoEnum = EstadoEmpleado

class EmpleadoCreate(BaseModel):
    cedula: str = Field(..., min_length=1, max_length=50)
    codigo_tarjeta: Optional[str] = Field(None, min_length=1, max_length=100)
    nombre_apellido: str = Field(..., min_length=2, max_length=200)
    fecha_nacimiento: Optional[date] = None
    telefono: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=254)
    contacto_emergencia_parentesco: Optional[str] = Field(None, max_length=100)
    contacto_emergencia_telefono: Optional[str] = Field(None, max_length=30)
    gerencia: Optional[str] = Field(None, max_length=150)
    departamento: Optional[str] = Field(None, max_length=150)
    cargo: Optional[str] = Field(None, max_length=150)
    gerencia_id: Optional[int] = None
    departamento_id: Optional[int] = None
    cargo_id: Optional[int] = None
    estado: EstadoEnum = EstadoEnum.Activo
    tipo_nomina: Optional[str] = Field(None, max_length=50)

    @field_validator('codigo_tarjeta', mode='before')
    @classmethod
    def normalize_card_code(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

class EmpleadoUpdate(BaseModel):
    codigo_tarjeta: Optional[str] = Field(None, min_length=1, max_length=100)
    nombre_apellido: Optional[str] = Field(None, min_length=2, max_length=200)
    fecha_nacimiento: Optional[date] = None
    telefono: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=254)
    contacto_emergencia_parentesco: Optional[str] = Field(None, max_length=100)
    contacto_emergencia_telefono: Optional[str] = Field(None, max_length=30)
    gerencia: Optional[str] = Field(None, max_length=150)
    departamento: Optional[str] = Field(None, max_length=150)
    cargo: Optional[str] = Field(None, max_length=150)
    gerencia_id: Optional[int] = None
    departamento_id: Optional[int] = None
    cargo_id: Optional[int] = None
    estado: Optional[EstadoEnum] = None
    tipo_nomina: Optional[str] = Field(None, max_length=50)

    @field_validator('codigo_tarjeta', mode='before')
    @classmethod
    def normalize_card_code(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

class EmpleadoOut(BaseModel):
    id: int
    cedula: str
    codigo_tarjeta: Optional[str] = None
    nombre_apellido: str
    fecha_nacimiento: Optional[date] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    contacto_emergencia_parentesco: Optional[str] = None
    contacto_emergencia_telefono: Optional[str] = None
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