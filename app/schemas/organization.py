from typing import Optional
from pydantic import BaseModel, Field


class GerenciaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)


class DepartamentoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)
    gerencia_id: int


class CargoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)
    departamento_id: int


class OrganizationStatusUpdate(BaseModel):
    estado: str = Field(..., min_length=2, max_length=20)


class OrganizationUpdate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)


class OrganizationDeleteResult(BaseModel):
    action: str
    detail: str
