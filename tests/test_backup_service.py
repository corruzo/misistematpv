import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services import backup_service


class BackupServiceTest(unittest.TestCase):
    def test_list_backups_returns_only_existing_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory)
            (backup_dir / 'backup_1.bak').write_bytes(b'backup')
            (backup_dir / 'backup_4.bak').write_bytes(b'ignored')
            with patch.object(backup_service, 'BACKUP_DIR', backup_dir), patch.object(backup_service, 'BACKUP_SLOT_COUNT', 3):
                backups = backup_service.list_backups()

        self.assertEqual([item['filename'] for item in backups], ['backup_1.bak'])
        self.assertEqual(backups[0]['size_bytes'], 6)

    def test_create_backup_uses_server_side_sql_and_selected_slot(self):
        db = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory)
            with patch.object(backup_service, 'engine') as engine, patch.object(backup_service, 'BACKUP_DIR', backup_dir), patch.object(backup_service, 'BACKUP_SLOT_COUNT', 3), patch.object(
                backup_service,
                'list_backups',
                side_effect=[[{'filename': 'backup_1.bak', 'slot': 1}], [{'filename': 'backup_2.bak', 'slot': 2}]],
            ):
                connection = engine.raw_connection.return_value
                cursor = connection.cursor.return_value
                cursor.description = [('lock_result',)]
                cursor.fetchone.return_value = (0,)
                backup = backup_service.create_backup(db)

            self.assertIn('BACKUP DATABASE', cursor.execute.call_args_list[-1].args[0])
            connection.close.assert_called_once()
        self.assertEqual(backup['filename'], 'backup_2.bak')


if __name__ == '__main__':
    unittest.main()