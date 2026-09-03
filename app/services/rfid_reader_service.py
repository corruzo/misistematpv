import logging
import threading
import time
from collections.abc import Callable

import serial

from app.core.config import (
    SERIAL_BAUDRATE,
    SERIAL_BYTESIZE,
    SERIAL_ENCODING,
    SERIAL_PARITY,
    SERIAL_PORT,
    SERIAL_STOPBITS,
    SERIAL_TIMEOUT,
)

logger = logging.getLogger(__name__)
reader = None


class RFIDReaderError(RuntimeError):
    pass


class RFIDReader:
    def __init__(self, on_attendance_scan: Callable[[str], None] | None = None):
        self._on_attendance_scan = on_attendance_scan
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._capture_condition = threading.Condition()
        self._capturing = False
        self._captured_code: str | None = None
        self._buffer = bytearray()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, name='rfid-reader', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._capture_condition:
            self._capture_condition.notify_all()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._thread = None

    def read_card(self, timeout: float = 30) -> str:
        self.start()
        deadline = time.monotonic() + timeout
        with self._capture_condition:
            if self._capturing:
                raise RFIDReaderError('Ya hay otra lectura de tarjeta en curso.')
            self._capturing = True
            self._captured_code = None
            while self._captured_code is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._capturing = False
                    raise RFIDReaderError('No se recibió ninguna tarjeta antes de agotarse el tiempo.')
                self._capture_condition.wait(remaining)
            code = self._captured_code
            self._capturing = False
            self._captured_code = None
            return code

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with serial.Serial(
                    port=SERIAL_PORT,
                    baudrate=SERIAL_BAUDRATE,
                    bytesize=SERIAL_BYTESIZE,
                    parity=SERIAL_PARITY,
                    stopbits=SERIAL_STOPBITS,
                    timeout=SERIAL_TIMEOUT,
                ) as connection:
                    logger.info('Lector HID conectado en %s a %s baudios.', SERIAL_PORT, SERIAL_BAUDRATE)
                    while not self._stop_event.is_set():
                        raw_code = connection.read(64)
                        if raw_code:
                            self._buffer.extend(raw_code)
                            self._handle_buffered_codes()
                        elif self._buffer:
                            self._handle_code(bytes(self._buffer))
                            self._buffer.clear()
            except (serial.SerialException, OSError) as exc:
                logger.warning('Lector HID no disponible en %s: %s', SERIAL_PORT, exc)
                self._stop_event.wait(5)

    def _handle_code(self, raw_code: bytes) -> None:
        try:
            code = raw_code.decode(SERIAL_ENCODING, errors='ignore').strip()
        except LookupError:
            code = raw_code.decode('ascii', errors='ignore').strip()
        if not code:
            return

        with self._capture_condition:
            if self._capturing:
                self._captured_code = code
                self._capture_condition.notify_all()
                logger.info('Lectura HID reservada para registro de tarjeta.')
                return

        if self._on_attendance_scan:
            try:
                self._on_attendance_scan(code)
            except Exception:
                logger.exception('No se pudo procesar el marcaje leído por HID.')

    def _handle_buffered_codes(self) -> None:
        while True:
            separator_positions = [position for position in (self._buffer.find(b'\r'), self._buffer.find(b'\n')) if position >= 0]
            if not separator_positions:
                return
            separator_position = min(separator_positions)
            code = bytes(self._buffer[:separator_position])
            del self._buffer[:separator_position + 1]
            while self._buffer[:1] in (b'\r', b'\n'):
                del self._buffer[:1]
            self._handle_code(code)


def get_reader() -> RFIDReader:
    global reader
    if reader is None:
        reader = RFIDReader()
    return reader
