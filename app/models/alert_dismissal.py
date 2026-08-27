from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.models.base import Base


class AlertDismissal(Base):
    __tablename__ = 'alertas_descartadas'
    __table_args__ = (
        UniqueConstraint('usuario_id', 'alerta_id', name='UX_alertas_descartadas_usuario_alerta'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    alerta_id = Column(String(64), nullable=False)
    descartada_en = Column(DateTime(timezone=True), nullable=False, server_default=func.sysutcdatetime())