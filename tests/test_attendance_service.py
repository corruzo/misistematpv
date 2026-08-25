from datetime import datetime, timedelta, timezone
import unittest

from app.core.enums import EstadoEmpleado
from app.models.attendance import AttendanceRecord
from app.models.employee import Empleado
from app.schemas.attendance import AttendanceOrigin, AttendanceType
from app.schemas.attendance import AttendanceManualBatchRequest
from app.services.attendance_service import DEBOUNCE_SECONDS, AttendanceError, register_manual, register_scan


class QueryDouble:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *conditions):
        self.conditions = conditions
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        if self.model is Empleado:
            employee = self.db.employees[0]
            values = [getattr(getattr(condition, 'right', None), 'value', None) for condition in self.conditions]
            if employee.codigo_tarjeta in values or employee.id in values:
                return employee
            return None
        return max(self.db.records, key=lambda record: record.fecha_hora, default=None)


class DatabaseDouble:
    def __init__(self, employee):
        self.employees = [employee]
        self.employee_by_id = employee
        self.records = []
        self.audit_records = []
        self.next_id = 1

    def query(self, model):
        return QueryDouble(self, model)

    def add(self, value):
        if isinstance(value, AttendanceRecord):
            self.records.append(value)
        else:
            self.audit_records.append(value)

    def flush(self):
        for record in self.records:
            if record.id is None:
                record.id = self.next_id
                self.next_id += 1

    def commit(self):
        pass

    def refresh(self, _value):
        pass


class AttendanceServiceTest(unittest.TestCase):
    def make_employee(self, estado=EstadoEmpleado.Activo):
        return Empleado(
            id=1,
            cedula='100',
            codigo_tarjeta='RFID-1',
            nombre_apellido='Ana Pérez',
            estado=estado,
            departamento_id=1,
            cargo_id=1,
        )

    def test_manual_mark_alternates_entry_and_exit(self):
        db = DatabaseDouble(self.make_employee())
        first = register_manual(db, 1)
        db.records[0].fecha_hora = datetime.now(timezone.utc) - timedelta(minutes=2)
        second = register_manual(db, 1)

        self.assertEqual(first.tipo, AttendanceType.ENTRADA)
        self.assertEqual(second.tipo, AttendanceType.SALIDA)
        self.assertEqual(len(db.audit_records), 2)

    def test_debounce_rejects_duplicate_mark(self):
        self.assertEqual(DEBOUNCE_SECONDS, 15)
        db = DatabaseDouble(self.make_employee())
        register_manual(db, 1)

        with self.assertRaisesRegex(AttendanceError, 'Lectura duplicada'):
            register_manual(db, 1)

    def test_manual_accepts_past_time(self):
        db = DatabaseDouble(self.make_employee())
        marked_at = datetime.now(timezone.utc) - timedelta(hours=2)

        result = register_manual(db, 1, marked_at=marked_at)

        self.assertEqual(result.tipo, AttendanceType.ENTRADA)
        self.assertEqual(db.records[0].fecha_hora, marked_at)

    def test_manual_can_override_suggested_type(self):
        db = DatabaseDouble(self.make_employee())

        result = register_manual(db, 1, attendance_type=AttendanceType.SALIDA)

        self.assertEqual(result.tipo, AttendanceType.SALIDA)
        self.assertEqual(db.records[0].tipo, AttendanceType.SALIDA.value)

    def test_manual_rejects_future_time(self):
        db = DatabaseDouble(self.make_employee())
        marked_at = datetime.now(timezone.utc) + timedelta(minutes=1)

        with self.assertRaisesRegex(AttendanceError, 'no puede ser futura'):
            register_manual(db, 1, marked_at=marked_at)

    def test_manual_batch_rejects_duplicate_employee(self):
        with self.assertRaises(ValueError):
            AttendanceManualBatchRequest(marcajes=[{'empleado_id': 1}, {'empleado_id': 1}])

    def test_inactive_employee_and_unknown_card_are_rejected(self):
        inactive_db = DatabaseDouble(self.make_employee(EstadoEmpleado.Retirado))
        with self.assertRaisesRegex(AttendanceError, 'no está activo'):
            register_manual(inactive_db, 1)

        unknown_db = DatabaseDouble(self.make_employee())
        unknown_db.employees[0].codigo_tarjeta = 'OTHER'
        with self.assertRaisesRegex(AttendanceError, 'Tarjeta no asociada'):
            register_scan(unknown_db, 'RFID-1', AttendanceOrigin.PUERTO_COM)


if __name__ == '__main__':
    unittest.main()
