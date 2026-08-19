from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / '.env'

load_dotenv(dotenv_path=ENV_PATH)

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
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes"
    )
else:
    odbc_str = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD}"
    )

DATABASE_URL = "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc_str)

# App settings
STATIC_DIR = BASE_DIR / 'static'
UPLOADS_DIR = STATIC_DIR / 'uploads'
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif'}

