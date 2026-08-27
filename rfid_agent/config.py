from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AgentConfig:
    serial_port: str
    baud_rate: int
    bytesize: int
    parity: str
    stopbits: float
    timeout: float
    encoding: str
    server_url: str
    garita_id: str
    api_key: str
    queue_path: Path
    queue_limit: int
    heartbeat_seconds: int


def load_config(path: str | Path = '.env') -> AgentConfig:
    load_dotenv(path, override=False)
    return AgentConfig(
        serial_port=os.getenv('PUERTO_COM', '').strip(),
        baud_rate=int(os.getenv('BAUD_RATE', '9600')),
        bytesize=int(os.getenv('SERIAL_BYTESIZE', '8')),
        parity=os.getenv('SERIAL_PARITY', 'N').strip().upper(),
        stopbits=float(os.getenv('SERIAL_STOPBITS', '1')),
        timeout=float(os.getenv('SERIAL_TIMEOUT', '1')),
        encoding=os.getenv('SERIAL_ENCODING', 'ascii').strip() or 'ascii',
        server_url=os.getenv('URL_SERVIDOR', '').rstrip('/'),
        garita_id=os.getenv('GARITA_ID', '').strip(),
        api_key=os.getenv('API_KEY', '').strip(),
        queue_path=Path(os.getenv('QUEUE_PATH', 'rfid-agent.sqlite3')).expanduser(),
        queue_limit=int(os.getenv('QUEUE_LIMIT', '10000')),
        heartbeat_seconds=int(os.getenv('HEARTBEAT_SECONDS', '15')),
    )