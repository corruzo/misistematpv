from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class GerenciaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)


class GerenciaOut(GerenciaCreate):
    id: int
    fecha_creacion: Optional[datetime] = None


class DepartamentoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)
    gerencia_id: int


class DepartamentoOut(DepartamentoCreate):
    id: int
    fecha_creacion: Optional[datetime] = None


class CargoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)
    departamento_id: int


class CargoOut(CargoCreate):
    id: int
    fecha_creacion: Optional[datetime] = None


class OrganizationTreeItem(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    estado: str = 'Activo'
    fecha_creacion: Optional[datetime] = None
    departamentos: Optional[List['OrganizationTreeItem']] = None
    cargos: Optional[List['OrganizationTreeItem']] = None


class OrganizationStatusUpdate(BaseModel):
    estado: str = Field(..., min_length=2, max_length=20)


class OrganizationUpdate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    descripcion: Optional[str] = None
    estado: str = Field(default='Activo', min_length=2, max_length=20)


class OrganizationDeleteResult(BaseModel):
    action: str
    detail: str
