import unittest
import tempfile
from unittest.mock import patch

from app.services.serial_reader import (
    EIGHTBITS,
    PARITY_NONE,
    STOPBITS_ONE,
    SerialAttendanceReader,
)


class FakeConnection:
    def __init__(self, reader):
        self.reader = reader
        self.reads = 0

    def readline(self):
        self.reads += 1
        if self.reads == 1:
            return b'  CARD-001\r\n'
        self.reader._stop_event.set()
        return b''


class SerialReaderTest(unittest.TestCase):
    def test_default_serial_protocol_is_9600_8n1(self):
        from app.core import config

        self.assertEqual(config.SERIAL_BAUDRATE, 9600)
        self.assertEqual(config.SERIAL_BYTESIZE, 8)
        self.assertEqual(config.SERIAL_PARITY, 'N')
        self.assertEqual(config.SERIAL_STOPBITS, 1.0)
        self.assertEqual(EIGHTBITS, 8)
        self.assertEqual(PARITY_NONE, 'N')
        self.assertEqual(STOPBITS_ONE, 1)

    def test_reader_strips_line_terminator_before_registering(self):
        reader = SerialAttendanceReader()
        connection = FakeConnection(reader)

        with patch('app.services.serial_reader.SerialAttendanceReader._register') as register:
            reader._read_connection(connection)

        register.assert_called_once_with('CARD-001')

    def test_failed_read_is_persisted_with_operation_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch('app.services.serial_reader.RFID_OFFLINE_QUEUE_PATH', __import__('pathlib').Path(temp_dir) / 'queue.sqlite3'):
            reader = SerialAttendanceReader()
            with patch('app.services.serial_reader.SessionLocal', side_effect=RuntimeError('SQL Server fuera de servicio')):
                reader._register('CARD-002')

            pending = reader._pending_scans()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0][2], 'CARD-002')
            self.assertTrue(pending[0][1])

    def test_pending_read_is_removed_after_successful_sync(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch('app.services.serial_reader.RFID_OFFLINE_QUEUE_PATH', __import__('pathlib').Path(temp_dir) / 'queue.sqlite3'):
            reader = SerialAttendanceReader()
            reader._queue_scan('CARD-003', 'operation-003', '2026-08-26T12:00:00+00:00')
            with patch('app.services.serial_reader.register_scan') as register:
                reader._sync_pending()

            self.assertEqual(reader._pending_scans(), [])
            self.assertEqual(register.call_args.kwargs['operation_id'], 'operation-003')


if __name__ == '__main__':
    unittest.main()
