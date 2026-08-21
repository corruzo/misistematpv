from datetime import datetime, timezone
import unittest

from app.core.datetime_utils import to_local


class DateTimeUtilsTest(unittest.TestCase):
    def test_utc_attendance_is_presented_in_caracas_time(self):
        utc_value = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
        local_value = to_local(utc_value)

        self.assertEqual(local_value.hour, 11)
        self.assertEqual(local_value.utcoffset().total_seconds(), -4 * 60 * 60)


if __name__ == '__main__':
    unittest.main()