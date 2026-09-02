import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.controllers import system_controller
from app.schemas.attendance import AttendanceSummary
from app.services import backup_service
from app.services.attendance_service import build_daily_report_payload


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

    def test_backup_loop_runs_immediately_and_then_daily(self):
        async def run_check():
            async def fake_sleep(delay):
                raise asyncio.CancelledError

            async def fake_to_thread(func, *args, **kwargs):
                return func(*args, **kwargs)

            with patch.object(system_controller.asyncio, 'to_thread', new=fake_to_thread), patch.object(system_controller.asyncio, 'sleep', side_effect=fake_sleep), patch.object(system_controller, 'run_scheduled_backup') as run_backup:
                task = asyncio.create_task(system_controller.backup_loop())
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertGreaterEqual(run_backup.call_count, 1)

        asyncio.run(run_check())

    def test_build_daily_report_payload_includes_summary_and_recent_audit(self):
        payload = build_daily_report_payload(
            AttendanceSummary(
                presentes=2,
                entradas_hoy=3,
                salidas_hoy=2,
                marcajes_hoy=5,
                presentes_por_area=[{'gerencia': 'Gerencia A', 'departamento': 'Depto 1', 'total': 2}],
            ),
            [{'id': 1, 'tipo': 'ENTRADA', 'fecha_hora': '2026-09-01T08:00:00+00:00'}],
            [{'id': 10, 'accion': 'actualizacion', 'entidad': 'empleados', 'fecha': '2026-09-01T09:00:00+00:00'}],
            report_date='2026-09-01',
        )

        self.assertEqual(payload['date'], '2026-09-01')
        self.assertEqual(payload['summary']['presentes'], 2)
        self.assertEqual(payload['recent_records'][0]['id'], 1)
        self.assertEqual(payload['recent_audit'][0]['accion'], 'actualizacion')


if __name__ == '__main__':
    unittest.main()