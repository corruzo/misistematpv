from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / '.env'

load_dotenv(dotenv_path=ENV_PATH)

APP_ENV = os.getenv('APP_ENV', 'development').lower()
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'true' if APP_ENV == 'production' else 'false').lower() in ('1', 'true', 'yes')
TRUST_SERVER_CERTIFICATE = os.getenv('TRUST_SERVER_CERTIFICATE', 'false' if APP_ENV == 'production' else 'true').lower() in ('1', 'true', 'yes')
CSRF_ALLOWED_ORIGINS = tuple(
    origin.strip().rstrip('/')
    for origin in os.getenv('CSRF_ALLOWED_ORIGINS', 'http://127.0.0.1:8000,http://localhost:8000').split(',')
    if origin.strip()
)

# Database settings (SQL Server)
DB_DRIVER = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
DB_SERVER = os.getenv('DB_SERVER', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'misistema_db')
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_TRUSTED = os.getenv('DB_TRUSTED', 'false').lower() in ('1', 'true', 'yes')

# Build SQLAlchemy URL. Prefer Trusted Connection if configured.
if DB_TRUSTED or not DB_USER:
    # Use Windows Authentication / Trusted Connection
    odbc_str = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes;TrustServerCertificate={'yes' if TRUST_SERVER_CERTIFICATE else 'no'}"
    )
else:
    odbc_str = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD};TrustServerCertificate={'yes' if TRUST_SERVER_CERTIFICATE else 'no'}"
    )

DATABASE_URL = "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc_str)

# App settings
STATIC_DIR = BASE_DIR / 'static'
UPLOADS_DIR = STATIC_DIR / 'uploads'
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif'}

