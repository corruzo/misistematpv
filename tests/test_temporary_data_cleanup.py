import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from app.services.notification_service import cleanup_temporary_data


class TemporaryDataCleanupTest(unittest.TestCase):
    def test_cleanup_uses_retention_cutoff_and_only_commits_temporary_rows(self):
        db = MagicMock()
        notifications = MagicMock()
        notifications.delete.return_value = 3
        dismissals = MagicMock()
        dismissals.delete.return_value = 2
        db.query.side_effect = [MagicMock(filter=MagicMock(return_value=notifications)), MagicMock(filter=MagicMock(return_value=dismissals))]

        with patch('app.services.notification_service.utc_now') as utc_now:
            utc_now.return_value = __import__('datetime').datetime(2026, 8, 27)
            result = cleanup_temporary_data(db, 30)

        self.assertEqual(result, {'notifications': 3, 'alert_dismissals': 2})
        self.assertEqual(db.commit.call_count, 1)
        self.assertEqual(db.query.call_count, 2)
        self.assertEqual((utc_now.return_value - timedelta(days=30)).day, 28)


if __name__ == '__main__':
    unittest.main()
