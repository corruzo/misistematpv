from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator

Role = Literal['RRHH', 'Desarrollador', 'Inspector']


class UsuarioCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9._-]+$')
    nombre: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=10, max_length=128)
    rol: Role = 'Inspector'

    @field_validator('username', 'nombre', 'password', mode='before')
    @classmethod
    def strip_values(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip()


class UsuarioUpdate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9._-]+$')
    nombre: str = Field(..., min_length=2, max_length=150)
    password: str | None = Field(None, min_length=10, max_length=128)
    rol: Role = 'Inspector'
    activo: bool | None = None

    @field_validator('username', 'nombre', 'password', mode='before')
    @classmethod
    def strip_values(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class UsuarioOut(BaseModel):
    id: int
    username: str
    nombre: str
    rol: str
    activo: bool
    fecha_creacion: datetime
    ultimo_acceso: datetime | None = None

    @classmethod
    def from_model(cls, usuario):
        return cls(
            id=usuario.id,
            username=usuario.username,
            nombre=usuario.nombre,
            rol=usuario.rol,
            activo=bool(usuario.activo),
            fecha_creacion=usuario.fecha_creacion,
            ultimo_acceso=usuario.ultimo_acceso,
        )


class UsuarioPage(BaseModel):
    items: list[UsuarioOut]
    total: int
    page: int
    page_size: int


class UsuarioStatusUpdate(BaseModel):
    activo: bool
