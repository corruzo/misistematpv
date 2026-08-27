from datetime import datetime
from pathlib import Path
import re
from threading import Lock

from sqlalchemy.orm import Session

from app.core.config import BACKUP_DIR, BACKUP_SLOT_COUNT, DB_NAME
from app.database.session import engine


_backup_lock = Lock()


BACKUP_NAME_PATTERN = re.compile(r'^backup_([1-9][0-9]*)\.bak$')


def _slot_name(slot: int) -> str:
    if slot < 1 or slot > BACKUP_SLOT_COUNT:
        raise ValueError('El slot de backup no es válido.')
    return f'backup_{slot}.bak'


def backup_path(filename: str) -> Path:
    match = BACKUP_NAME_PATTERN.fullmatch(filename)
    if not match or int(match.group(1)) > BACKUP_SLOT_COUNT:
        raise ValueError('El archivo de backup no es válido.')
    path = (BACKUP_DIR / filename).resolve()
    if path.parent != BACKUP_DIR:
        raise ValueError('La ruta de backup no es válida.')
    return path


def list_backups() -> list[dict]:
    backups = []
    for slot in range(1, BACKUP_SLOT_COUNT + 1):
        path = BACKUP_DIR / _slot_name(slot)
        if not path.is_file():
            continue
        stat = path.stat()
        backups.append({
            'filename': path.name,
            'slot': slot,
            'size_bytes': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
        })
    return sorted(backups, key=lambda item: item['modified_at'], reverse=True)


def create_backup(db: Session, slot: int | None = None) -> dict:
    with _backup_lock:
        connection = engine.raw_connection()
        try:
            connection.connection.autocommit = True
            cursor = connection.cursor()
            if slot is None:
                existing = list_backups()
                slot = (existing[0]['slot'] % BACKUP_SLOT_COUNT + 1) if existing else 1
            filename = _slot_name(slot)
            path = backup_path(filename)
            sql_database = DB_NAME.replace(']', ']]')
            sql_path = str(path).replace("'", "''")
            statement = (
                f"BACKUP DATABASE [{sql_database}] TO DISK = N'{sql_path}' "
                "WITH INIT, CHECKSUM"
            )
            cursor.execute(statement)
        finally:
            connection.close()
    return next(item for item in list_backups() if item['filename'] == filename)



