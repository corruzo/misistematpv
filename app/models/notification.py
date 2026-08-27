from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text

from app.core.datetime_utils import utc_now
from app.models.base import Base


class Notification(Base):
    __tablename__ = 'notificaciones'
    __table_args__ = (
        CheckConstraint("prioridad IN ('critica', 'advertencia', 'informativa')", name='CK_notificaciones_prioridad'),
        CheckConstraint("tipo IN ('acceso_no_autorizado', 'pase_temporal', 'incidencia_tecnica', 'empleado_registrado', 'empleado_estado_cambiado', 'marcaje_corregido', 'lector_estado_cambiado')", name='CK_notificaciones_tipo'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    tipo = Column(String(40), nullable=False, index=True)
    prioridad = Column(String(15), nullable=False, index=True)
    titulo = Column(String(150), nullable=False)
    mensaje = Column(Text, nullable=False)
    creada_en = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    leida_en = Column(DateTime(timezone=True), nullable=True)
    descartada_en = Column(DateTime(timezone=True), nullable=True)