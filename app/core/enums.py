from enum import Enum


class EstadoEmpleado(str, Enum):
    Activo = 'Activo'
    Vacaciones = 'Vacaciones'
    Retirado = 'Retirado'
    Suspendido = 'Suspendido'
