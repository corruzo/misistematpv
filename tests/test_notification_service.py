import unittest

from app.models.employee import Empleado
from app.models.user import Usuario
from app.services import notification_service


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *criteria):
        rows = list(self.rows)
        for criterion in criteria:
            left = getattr(criterion, 'left', None)
            right = getattr(criterion, 'right', None)
            key = getattr(left, 'key', None) or getattr(left, 'name', None)
            if key == 'rol':
                rows = [row for row in rows if row.rol in right]
            elif key == 'activo':
                rows = [row for row in rows if row.activo == right]
        return FakeQuery(rows)

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def count(self):
        return len(self.rows)


class FakeDB:
    def __init__(self, users):
        self.users = list(users)

    def query(self, model):
        return FakeQuery(self.users if model is Usuario else [])

    def add(self, item):
        self.last_added = item

    def flush(self):
        return None

    def commit(self):
        return None


class NotificationServiceTest(unittest.TestCase):
    def setUp(self):
        self.users = [
            Usuario(id=1, nombre='Ana RRHH', rol='RRHH', activo=1),
            Usuario(id=2, nombre='Diego Desarrollo', rol='Desarrollador', activo=1),
            Usuario(id=3, nombre='Inés Inspección', rol='Inspector', activo=1),
        ]
        self.db = FakeDB(self.users)

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

    def test_employee_lifecycle_notifications_go_to_hr_and_developer_only(self):
        self.db.query.return_value.filter.return_value.first.return_value = self.users[0]

        employee = Empleado(nombre_apellido='Empleado Nuevo', cedula='100')
        notification_service.publish_employee_registered(self.db, employee, 1)

        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual({item.usuario_id for item in added}, {1, 2})
        self.assertTrue(all(item.tipo == 'empleado_registrado' for item in added))
        self.assertNotIn(3, {item.usuario_id for item in added})
        self.assertIn('Empleado Nuevo', added[0].mensaje)
        self.assertIn('Ana RRHH', added[0].mensaje)

    def test_organization_and_user_events_stay_out_of_inspector(self):
        self.db.query.return_value.filter.return_value.first.return_value = self.users[0]

        notification_service.publish_organization_changed(self.db, 'Se actualizó la estructura', 1)
        notification_service.publish_user_changed(self.db, 'usuario.test', 'creó la cuenta', 1)

        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual({item.usuario_id for item in added}, {1, 2})
        self.assertNotIn(3, {item.usuario_id for item in added})

    def test_attendance_correction_notification_reaches_operations_and_hr_but_not_hidden_from_inspector(self):
        self.db.query.return_value.filter.return_value.first.return_value = self.users[1]

        notification_service.publish_attendance_corrected(self.db, 'Ana', 'ENTRADA', 'SALIDA', 'Error de digitación', 2)

        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual({item.usuario_id for item in added}, {1, 2, 3})
        self.assertIn('Diego Desarrollo', added[0].mensaje)
        self.assertIn('Ana', added[0].mensaje)
        self.assertIn('Error de digitación', added[0].mensaje)


if __name__ == '__main__':
    unittest.main()