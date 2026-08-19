from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AttendanceOrigin(str, Enum):
    PUERTO_COM = 'PUERTO_COM'
    MANUAL_ADMIN = 'MANUAL_ADMIN'
    SIMULADOR_DEV = 'SIMULADOR_DEV'


class AttendanceType(str, Enum):
    ENTRADA = 'ENTRADA'
    SALIDA = 'SALIDA'


class AttendanceScanRequest(BaseModel):
    codigo_tarjeta: str = Field(..., min_length=1, max_length=100)


class AttendanceManualRequest(BaseModel):
    empleado_id: int = Field(..., gt=0)


class AttendanceRecordOut(BaseModel):
    id: int
    empleado_id: int
    empleado_nombre: str
    codigo_tarjeta: str
    tipo: AttendanceType
    fecha_hora: datetime
    origen: AttendanceOrigin
    cedula: str
    departamento: str | None = None
    gerencia: str | None = None
    cargo: str | None = None
    foto_url: str | None = None


class AttendanceHistoryPage(BaseModel):
    items: list[AttendanceRecordOut]
    total: int
    page: int
    page_size: int


class AttendanceSummary(BaseModel):
    presentes: int
    entradas_hoy: int
    salidas_hoy: int
    marcajes_hoy: int
    presentes_por_area: list[dict]