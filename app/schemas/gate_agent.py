from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AgentScanRequest(BaseModel):
    garita_id: str = Field(..., min_length=1, max_length=100)
    operation_id: str = Field(..., min_length=16, max_length=64)
    codigo_tarjeta: str = Field(..., min_length=1, max_length=100)
    timestamp_lectura: datetime
    timestamp_envio: datetime | None = None
    agent_version: str | None = Field(None, max_length=40)

    @field_validator('timestamp_lectura')
    @classmethod
    def require_timestamp_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timestamp_lectura debe incluir un offset UTC.')
        return value

    @field_validator('timestamp_envio')
    @classmethod
    def require_send_timestamp_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('timestamp_envio debe incluir un offset UTC.')
        return value


class AgentHeartbeatRequest(BaseModel):
    garita_id: str = Field(..., min_length=1, max_length=100)
    agent_version: str | None = Field(None, max_length=40)
    reader_connected: bool
    queue_depth: int = Field(0, ge=0)
    last_scan_at: datetime | None = None

    @field_validator('last_scan_at')
    @classmethod
    def require_timestamp_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('last_scan_at debe incluir un offset UTC.')
        return value