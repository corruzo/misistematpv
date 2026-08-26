import unittest
from unittest.mock import MagicMock

from app.models.user import Usuario
from app.services import notification_service


class NotificationServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.users = [
            Usuario(id=1, rol='RRHH', activo=1),
            Usuario(id=2, rol='Desarrollador', activo=1),
            Usuario(id=3, rol='Inspector', activo=1),
        ]
        self.db.query.return_value.filter.return_value.all.return_value = self.users

    def test_access_denied_is_sent_to_all_operational_roles(self):
        notification_service.publish_access_denied(self.db, 'Ana', 'Suspendido')

        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual({item.usuario_id for item in added}, {1, 2, 3})
        self.assertTrue(all(item.prioridad == notification_service.PRIORITY_CRITICAL for item in added))

    def test_exception_mark_excludes_developer(self):
        self.db.query.return_value.filter.return_value.all.return_value = self.users[:1] + self.users[2:]

        notification_service.publish_exception_mark(self.db, 'Ana', 7)

        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual({item.usuario_id for item in added}, {1, 3})
        self.assertTrue(all(item.tipo == 'pase_temporal' for item in added))

    def test_technical_event_is_sent_only_to_developer(self):
        self.db.query.return_value.filter.return_value.all.return_value = [self.users[1]]

        notification_service.publish_technical(self.db, 'Falla', 'Revisar logs')

        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].usuario_id, 2)
        self.assertEqual(added[0].prioridad, notification_service.PRIORITY_CRITICAL)


if __name__ == '__main__':
    unittest.main()