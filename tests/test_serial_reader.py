import unittest
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


if __name__ == '__main__':
    unittest.main()
