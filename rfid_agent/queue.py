import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import threading


class ScanQueue:
    def __init__(self, path: Path, limit: int = 10000):
        self.path = path
        self.limit = limit
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute('''
                    CREATE TABLE IF NOT EXISTS pending_scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation_id TEXT NOT NULL UNIQUE,
                        card_code TEXT NOT NULL,
                        timestamp_lectura TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT
                    )
                ''')
                connection.execute('''
                    CREATE TABLE IF NOT EXISTS rejected_scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation_id TEXT NOT NULL UNIQUE,
                        card_code TEXT NOT NULL,
                        timestamp_lectura TEXT NOT NULL,
                        status_code INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                ''')

    def enqueue(self, operation_id: str, card_code: str, timestamp: str) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.lock, closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute(
                    'INSERT OR IGNORE INTO pending_scans '
                    '(operation_id, card_code, timestamp_lectura, created_at) VALUES (?, ?, ?, ?)',
                    (operation_id, card_code, timestamp, created_at),
                )
                count = connection.execute('SELECT COUNT(*) FROM pending_scans').fetchone()[0]
                if count > self.limit:
                    raise RuntimeError('La cola RFID alcanzó su límite; no se descartan lecturas.')

    def pending(self):
        with self.lock, closing(sqlite3.connect(self.path)) as connection:
            return connection.execute(
                'SELECT id, operation_id, card_code, timestamp_lectura, attempts FROM pending_scans ORDER BY id'
            ).fetchall()

    def mark_attempt(self, queue_id: int, error: str) -> None:
        with self.lock, closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute(
                    'UPDATE pending_scans SET attempts = attempts + 1, last_error = ? WHERE id = ?',
                    (error[:500], queue_id),
                )

    def acknowledge(self, queue_id: int) -> None:
        with self.lock, closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute('DELETE FROM pending_scans WHERE id = ?', (queue_id,))

    def reject(self, queue_id: int, operation_id: str, card_code: str, timestamp: str, status_code: int, reason: str) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.lock, closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute(
                    'INSERT OR IGNORE INTO rejected_scans '
                    '(operation_id, card_code, timestamp_lectura, status_code, reason, created_at) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (operation_id, card_code, timestamp, status_code, reason[:500], created_at),
                )
                connection.execute('DELETE FROM pending_scans WHERE id = ?', (queue_id,))