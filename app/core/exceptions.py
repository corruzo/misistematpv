"""Excepciones de dominio personalizadas y utilidades de manejo de errores."""

class AppException(Exception):
    """Excepción base de la aplicación."""
    def __init__(self, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class DatabaseConnectionError(AppException):
    """Lanzada cuando hay fallos de conectividad con SQL Server."""
    def __init__(self, message: str = "Error de conexión con la base de datos SQL Server."):
        super().__init__(message, status_code=503)


class EntityNotFoundError(AppException):
    """Lanzada cuando un recurso no se encuentra en el sistema."""
    def __init__(self, message: str = "El recurso solicitado no fue encontrado."):
        super().__init__(message, status_code=404)


class BusinessValidationError(AppException):
    """Lanzada cuando una regla de negocio es violada."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=422, details=details)


class OrganizationInUseError(BusinessValidationError):
    """Lanzada al intentar eliminar elementos de la estructura organizacional en uso."""
    def __init__(self, item_name: str, count: int, item_type: str = "empleados"):
        message = f"No se puede eliminar '{item_name}' porque tiene {count} {item_type} asociado(s)."
        super().__init__(message, details={"item_name": item_name, "count": count, "item_type": item_type})


class SessionExpiredError(AppException):
    """Lanzada cuando una sesión de usuario expira o queda desactivada."""
    def __init__(self, message: str = "Tu sesión ha expirado o tu usuario fue desactivado. Por favor, inicia sesión nuevamente."):
        super().__init__(message, status_code=401)
