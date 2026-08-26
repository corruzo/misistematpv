import logging
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone

import serial
from serial import PARITY_EVEN, PARITY_MARK, PARITY_NONE, PARITY_ODD, PARITY_SPACE
from serial import SEVENBITS, EIGHTBITS, STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO

from app.core.config import (
    SERIAL_BAUDRATE,
    SERIAL_BYTESIZE,
    SERIAL_ENCODING,
    RFID_OFFLINE_QUEUE_LIMIT,
    RFID_OFFLINE_QUEUE_PATH,
    SERIAL_PARITY,
    SERIAL_PORT,
    SERIAL_STOPBITS,
    SERIAL_TIMEOUT,
)
from app.database.session import SessionLocal
from app.schemas.attendance import AttendanceOrigin
from app.services.access_event_service import record_denied_event
from app.services.attendance_service import AttendanceError, EmployeeAccessDeniedError, register_scan
from app.services.notification_service import publish_technical
from app.services.live_bus import notify_live_change

logger = logging.getLogger(__name__)
_reader_status = {'configured': bool(SERIAL_PORT), 'connected': False, 'message': 'Lector no configurado' if not SERIAL_PORT else 'Lector desconectado'}

_BYTESIZES = {7: SEVENBITS, 8: EIGHTBITS}
_PARITIES = {
    'N': PARITY_NONE,
    'E': PARITY_EVEN,
    'O': PARITY_ODD,
    'M': PARITY_MARK,
    'S': PARITY_SPACE,
}
_STOPBITS = {
    1.0: STOPBITS_ONE,
    1.5: STOPBITS_ONE_POINT_FIVE,
    2.0: STOPBITS_TWO,
}


class SerialAttendanceReader:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._sync_thread = None
        self._queue_lock = threading.Lock()
        self._initialize_queue()

    def _initialize_queue(self):
        RFID_OFFLINE_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(RFID_OFFLINE_QUEUE_PATH)) as connection:
            with connection:
                connection.execute(
                    'CREATE TABLE IF NOT EXISTS pending_scans ('
                    'id INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'operation_id TEXT NOT NULL UNIQUE, card_code TEXT NOT NULL, '
                    'marked_at TEXT NOT NULL, created_at TEXT NOT NULL)'
                )

    def _queue_scan(self, card_code, operation_id, marked_at):
        now = datetime.now(timezone.utc).isoformat()
        with self._queue_lock, closing(sqlite3.connect(RFID_OFFLINE_QUEUE_PATH)) as connection:
            with connection:
                connection.execute(
                    'INSERT INTO pending_scans (operation_id, card_code, marked_at, created_at) VALUES (?, ?, ?, ?)',
                    (operation_id, card_code, marked_at, now),
                )
                connection.execute(
                    'DELETE FROM pending_scans WHERE id NOT IN '
                    '(SELECT id FROM pending_scans ORDER BY id DESC LIMIT ?)',
                    (RFID_OFFLINE_QUEUE_LIMIT,),
                )
        _reader_status['message'] = 'Lecturas RFID pendientes de sincronizar'

    def _pending_scans(self):
        with self._queue_lock, closing(sqlite3.connect(RFID_OFFLINE_QUEUE_PATH)) as connection:
            return connection.execute(
                'SELECT id, operation_id, card_code, marked_at FROM pending_scans ORDER BY id'
            ).fetchall()

    def _remove_scan(self, queue_id):
        with self._queue_lock, closing(sqlite3.connect(RFID_OFFLINE_QUEUE_PATH)) as connection:
            with connection:
                connection.execute('DELETE FROM pending_scans WHERE id = ?', (queue_id,))

    def _sync_pending(self):
        for queue_id, operation_id, card_code, marked_at in self._pending_scans():
            db = SessionLocal()
            try:
                register_scan(
                    db,
                    card_code,
                    AttendanceOrigin.PUERTO_COM,
                    marked_at=datetime.fromisoformat(marked_at),
                    operation_id=operation_id,
                )
                self._remove_scan(queue_id)
                logger.info('Marcaje RFID pendiente sincronizado para tarjeta %s.', card_code)
            except EmployeeAccessDeniedError as exc:
                self._remove_scan(queue_id)
                if not record_denied_event(db, exc):
                    logger.error('La alerta de acceso denegado no quedó registrada para %s.', exc.employee_name)
                logger.warning('Lectura RFID pendiente rechazada para tarjeta %s: %s', card_code, exc)
            except AttendanceError as exc:
                self._remove_scan(queue_id)
                logger.warning('Lectura RFID pendiente rechazada para tarjeta %s: %s', card_code, exc)
            except Exception:
                db.rollback()
                try:
                    publish_technical(db, 'Falla de sincronización RFID', 'No se pudo sincronizar una lectura RFID pendiente; el sistema reintentará automáticamente.')
                    db.commit()
                    notify_live_change()
                except Exception:
                    db.rollback()
                logger.exception('No se pudo sincronizar una lectura RFID pendiente; se reintentará.')
                break
            finally:
                db.close()

    def _sync_loop(self):
        while not self._stop_event.is_set():
            try:
                self._sync_pending()
            except Exception:
                logger.exception('Error consultando la cola offline RFID.')
            self._stop_event.wait(5)

    @property
    def enabled(self):
        return bool(SERIAL_PORT)

    def start(self):
        if not self.enabled:
            _reader_status.update(connected=False, message='Lector no configurado')
            logger.info('Lector serial desactivado: SERIAL_PORT no está configurado.')
            return
        _reader_status.update(configured=True, message='Lector conectando...')
        self._thread = threading.Thread(target=self._run, name='serial-attendance-reader', daemon=True)
        self._thread.start()
        self._sync_thread = threading.Thread(target=self._sync_loop, name='serial-attendance-sync', daemon=True)
        self._sync_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)
        if self._sync_thread and self._sync_thread is not threading.current_thread():
            self._sync_thread.join(timeout=3)
        if self.enabled:
            _reader_status.update(connected=False, message='Lector detenido')

    def _run(self):
        try:
            bytesize = _BYTESIZES[SERIAL_BYTESIZE]
            parity = _PARITIES[SERIAL_PARITY]
            stopbits = _STOPBITS[SERIAL_STOPBITS]
        except KeyError:
            _reader_status.update(connected=False, message='Configuración serial inválida')
            logger.error('Configuración serial inválida. Use bytes 7/8, paridad N/E/O/M/S y stop bits 1/1.5/2.')
            return

        while not self._stop_event.is_set():
            try:
                with serial.Serial(
                    port=SERIAL_PORT,
                    baudrate=SERIAL_BAUDRATE,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                    timeout=SERIAL_TIMEOUT,
                ) as connection:
                    logger.info('Lector serial conectado en %s.', SERIAL_PORT)
                    _reader_status.update(connected=True, message=f'Lector conectado en {SERIAL_PORT}')
                    self._read_connection(connection)
            except serial.SerialException as exc:
                _reader_status.update(connected=False, message='Lector desconectado')
                logger.error('No se pudo abrir el lector serial %s: %s', SERIAL_PORT, exc)
                self._stop_event.wait(5)

    def _read_connection(self, connection):
        while not self._stop_event.is_set():
            raw_value = connection.readline()
            if not raw_value:
                continue
            try:
                card_code = raw_value.decode(SERIAL_ENCODING).strip()
            except UnicodeDecodeError:
                logger.warning('Se recibió una lectura serial con codificación inválida.')
                continue
            if card_code:
                self._register(card_code)

    def _register(self, card_code):
        operation_id = str(uuid.uuid4())
        marked_at = datetime.now(timezone.utc).isoformat()
        db = None
        try:
            db = SessionLocal()
            register_scan(
                db,
                card_code,
                AttendanceOrigin.PUERTO_COM,
                marked_at=datetime.fromisoformat(marked_at),
                operation_id=operation_id,
            )
            logger.info('Marcaje serial registrado para tarjeta %s.', card_code)
        except EmployeeAccessDeniedError as exc:
            if not record_denied_event(db, exc):
                logger.error('La alerta de acceso denegado no quedó registrada para %s.', exc.employee_name)
            logger.warning('Lectura serial rechazada para tarjeta %s: %s', card_code, exc)
        except AttendanceError as exc:
            logger.warning('Lectura serial rechazada para tarjeta %s: %s', card_code, exc)
        except Exception:
            if db:
                db.rollback()
            try:
                self._queue_scan(card_code, operation_id, marked_at)
            except Exception:
                logger.exception('Error guardando lectura serial en la cola offline.')
            logger.exception('Error procesando lectura serial; lectura guardada para reintento.')
        finally:
            if db:
                db.close()


def get_reader_status() -> dict:
    return dict(_reader_status)
