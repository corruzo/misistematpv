import logging
import threading

import serial
from serial import PARITY_EVEN, PARITY_MARK, PARITY_NONE, PARITY_ODD, PARITY_SPACE
from serial import SEVENBITS, EIGHTBITS, STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO

from app.core.config import (
    SERIAL_BAUDRATE,
    SERIAL_BYTESIZE,
    SERIAL_ENCODING,
    SERIAL_PARITY,
    SERIAL_PORT,
    SERIAL_STOPBITS,
    SERIAL_TIMEOUT,
)
from app.database.session import SessionLocal
from app.schemas.attendance import AttendanceOrigin
from app.services.attendance_service import AttendanceError, register_scan

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

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)
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

    @staticmethod
    def _register(card_code):
        db = SessionLocal()
        try:
            register_scan(db, card_code, AttendanceOrigin.PUERTO_COM)
            logger.info('Marcaje serial registrado para tarjeta %s.', card_code)
        except AttendanceError as exc:
            logger.warning('Lectura serial rechazada para tarjeta %s: %s', card_code, exc)
        except Exception:
            db.rollback()
            logger.exception('Error procesando lectura serial.')
        finally:
            db.close()


def get_reader_status() -> dict:
    return dict(_reader_status)
