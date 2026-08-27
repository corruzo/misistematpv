from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus, urlparse
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pyodbc

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / '.env'

load_dotenv(dotenv_path=ENV_PATH)

APP_ENV = os.getenv('APP_ENV', 'development').lower()
APP_TIMEZONE = os.getenv('APP_TIMEZONE', 'America/Caracas')
try:
    LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
except ZoneInfoNotFoundError:
    if APP_TIMEZONE == 'America/Caracas':
        LOCAL_TIMEZONE = timezone(timedelta(hours=-4), 'America/Caracas')
    else:
        raise RuntimeError(f'Zona horaria inválida o tzdata ausente en APP_TIMEZONE: {APP_TIMEZONE}')
COOKIE_SECURE = APP_ENV == 'production' or os.getenv('COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')
TRUST_SERVER_CERTIFICATE = os.getenv('TRUST_SERVER_CERTIFICATE', 'false' if APP_ENV == 'production' else 'true').lower() in ('1', 'true', 'yes')
CSRF_ALLOWED_ORIGINS = tuple(
    origin.strip().rstrip('/')
    for origin in os.getenv('CSRF_ALLOWED_ORIGINS', '' if APP_ENV == 'production' else 'http://127.0.0.1:8000,http://localhost:8000').split(',')
    if origin.strip()
)
CSRF_ALLOW_SAME_HOST = APP_ENV != 'production'

def is_allowed_csrf_origin(origin: str, request_host: str) -> bool:
    if origin.rstrip('/') in CSRF_ALLOWED_ORIGINS:
        return True
    if not CSRF_ALLOW_SAME_HOST:
        return False
    parsed_origin = urlparse(origin)
    return parsed_origin.scheme in {'http', 'https'} and parsed_origin.netloc == request_host

# Database settings (SQL Server). "auto" supports the default instance and
# the conventional SQL Server Express named instance on the local machine.
DB_DRIVER = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
DB_SERVER = os.getenv('DB_SERVER', 'auto').strip()
DB_NAME = os.getenv('DB_NAME', 'misistema_db')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_TRUSTED = os.getenv('DB_TRUSTED', 'false').lower() in ('1', 'true', 'yes')

TEMPORARY_DATA_RETENTION_DAYS = int(os.getenv('TEMPORARY_DATA_RETENTION_DAYS', '30'))


def _connection_string(server: str, database: str = 'master') -> str:
    credentials = (
        f'Trusted_Connection=yes;'
        if DB_TRUSTED or not DB_USER
        else f'UID={DB_USER};PWD={DB_PASSWORD};'
    )
    return (
        f'DRIVER={{{DB_DRIVER}}};SERVER={server};DATABASE={database};'
        f'{credentials}TrustServerCertificate={"yes" if TRUST_SERVER_CERTIFICATE else "no"}'
    )


def _resolve_db_server() -> str:
    configured_server = DB_SERVER.replace('/', '\\') if DB_SERVER.lower().startswith('localhost/') else DB_SERVER
    if configured_server.lower() != 'auto':
        return configured_server

    candidates = [candidate.strip() for candidate in os.getenv(
        'DB_SERVER_CANDIDATES', 'localhost,localhost\\SQLEXPRESS'
    ).split(',') if candidate.strip()]
    failures = []
    for candidate in candidates:
        try:
            connection = pyodbc.connect(_connection_string(candidate), timeout=2)
            connection.close()
            return candidate
        except pyodbc.Error as exc:
            failures.append(f'{candidate}: {exc.args[0] if exc.args else exc}')
    details = '; '.join(failures)
    raise RuntimeError(
        'No se encontró una instancia local de SQL Server. Se probaron '
        f'{", ".join(candidates)}. Verifica que SQL Server esté iniciado, '
        f'o configura DB_SERVER con el servidor exacto. Detalle: {details}'
    )


DB_SERVER = _resolve_db_server()

# Serial reader settings. Empty port keeps the hardware listener disabled.
SERIAL_PORT = os.getenv('SERIAL_PORT', '').strip()
SERIAL_BAUDRATE = int(os.getenv('SERIAL_BAUDRATE', '9600'))
SERIAL_BYTESIZE = int(os.getenv('SERIAL_BYTESIZE', '8'))
SERIAL_PARITY = os.getenv('SERIAL_PARITY', 'N').strip().upper()
SERIAL_STOPBITS = float(os.getenv('SERIAL_STOPBITS', '1'))
SERIAL_TIMEOUT = float(os.getenv('SERIAL_TIMEOUT', '1'))
SERIAL_ENCODING = os.getenv('SERIAL_ENCODING', 'ascii').strip() or 'ascii'
RFID_OFFLINE_QUEUE_PATH = Path(os.getenv('RFID_OFFLINE_QUEUE_PATH', str(BASE_DIR / 'backups' / 'rfid_offline_queue.sqlite3'))).resolve()
RFID_OFFLINE_QUEUE_LIMIT = int(os.getenv('RFID_OFFLINE_QUEUE_LIMIT', '1000'))
PROLONGED_STAY_HOURS = float(os.getenv('PROLONGED_STAY_HOURS', '12'))

# Query safety defaults. Keep list endpoints bounded even when clients omit parameters.
ATTENDANCE_HISTORY_DEFAULT_DAYS = int(os.getenv('ATTENDANCE_HISTORY_DEFAULT_DAYS', '15'))
DEFAULT_PAGE_SIZE = int(os.getenv('DEFAULT_PAGE_SIZE', '25'))
MAX_PAGE_SIZE = int(os.getenv('MAX_PAGE_SIZE', '100'))
MAX_OFFSET = int(os.getenv('MAX_OFFSET', '1000000'))
MAX_ORGANIZATION_CHILDREN = int(os.getenv('MAX_ORGANIZATION_CHILDREN', '1000'))
PRESENT_EMPLOYEES_LIMIT = int(os.getenv('PRESENT_EMPLOYEES_LIMIT', '500'))

# Server-side SQL Server backups. The SQL Server service account needs write access.
BACKUP_DIR = Path(os.getenv('BACKUP_DIR', str(BASE_DIR / 'backups'))).resolve()
BACKUP_SLOT_COUNT = int(os.getenv('BACKUP_SLOT_COUNT', '3'))
BACKUP_INTERVAL_SECONDS = int(os.getenv('BACKUP_INTERVAL_SECONDS', str(24 * 60 * 60)))

# Build SQLAlchemy URL. Prefer Trusted Connection if configured.
odbc_str = _connection_string(DB_SERVER, DB_NAME)

DATABASE_URL = "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc_str)

# App settings
STATIC_DIR = BASE_DIR / 'static'
UPLOADS_DIR = STATIC_DIR / 'uploads'
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif'}

