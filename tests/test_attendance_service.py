import json
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from app.core.enums import EstadoEmpleado
from app.models.attendance import AttendanceRecord
from app.models.employee import Empleado
from app.schemas.attendance import AttendanceOrigin, AttendanceType
from app.schemas.attendance import AttendanceManualBatchRequest
from app.services.attendance_service import DEBOUNCE_SECONDS, AttendanceError, attendance_records_are_too_close, correct_attendance, inspector_dashboard, normalize_inspector_dashboard_payload, register_manual, register_manual_batch, register_scan


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

    def rollback(self):
        self.records.clear()
        self.audit_records.clear()

    def refresh(self, _value):
        pass


class AttendanceServiceTest(unittest.TestCase):
    def test_dashboard_only_flags_attendance_within_debounce_window(self):
        reference = datetime.now(timezone.utc)
        self.assertTrue(attendance_records_are_too_close(reference, reference + timedelta(seconds=10)))
        self.assertFalse(attendance_records_are_too_close(reference, reference + timedelta(seconds=31)))
        self.assertFalse(attendance_records_are_too_close(reference, reference + timedelta(minutes=2)))

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

    def test_inspector_dashboard_handles_incomplete_data_without_crashing(self):
        payload = normalize_inspector_dashboard_payload(
            summary=None,
            present=None,
            recent_records=[type('BadRecord', (), {
                'id': 1,
                'empleado_id': 77,
                'tipo': 'ENTRADA',
                'fecha_hora': datetime.now(timezone.utc),
                'origen': 'PUERTO_COM',
                'empleado': None,
            })()],
            expected_employees=[],
            alerts=[{'id': 'abc123', 'message': 'Prueba'}],
        )

        self.assertEqual(payload['summary']['presentes'], 0)
        self.assertEqual(payload['recent'][0]['empleado_nombre'], 'Empleado no identificado')
        self.assertEqual(payload['alerts'][0]['message'], 'Prueba')

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

    def test_vacation_employee_can_mark(self):
        db = DatabaseDouble(self.make_employee(EstadoEmpleado.Vacaciones))

        result = register_manual(db, 1)

        self.assertEqual(result.tipo, AttendanceType.ENTRADA)
        self.assertEqual(result.estado, EstadoEmpleado.Vacaciones.value)

    def test_manual_can_override_suggested_type(self):
        db = DatabaseDouble(self.make_employee())

        result = register_manual(db, 1, attendance_type=AttendanceType.SALIDA)

        self.assertEqual(result.tipo, AttendanceType.SALIDA)
        self.assertEqual(db.records[0].tipo, AttendanceType.SALIDA.value)

    def test_manual_rejects_same_type_as_previous_record(self):
        db = DatabaseDouble(self.make_employee())
        previous = AttendanceRecord(id=10, empleado_id=1, tipo=AttendanceType.ENTRADA.value, fecha_hora=datetime.now(timezone.utc) - timedelta(hours=1))

        with patch('app.services.attendance_service._attendance_neighbors', return_value=(previous, None)):
            with self.assertRaisesRegex(AttendanceError, 'registro anterior ya es una entrada'):
                register_manual(db, 1, attendance_type=AttendanceType.ENTRADA)

    def test_manual_rejects_same_type_as_next_record_when_backdating(self):
        db = DatabaseDouble(self.make_employee())
        next_record = AttendanceRecord(id=11, empleado_id=1, tipo=AttendanceType.SALIDA.value, fecha_hora=datetime.now(timezone.utc) + timedelta(hours=1))

        with patch('app.services.attendance_service._attendance_neighbors', return_value=(None, next_record)):
            with self.assertRaisesRegex(AttendanceError, 'registro posterior ya es una salida'):
                register_manual(db, 1, marked_at=datetime.now(timezone.utc) - timedelta(minutes=30), attendance_type=AttendanceType.SALIDA)

    @patch('app.services.attendance_service.publish_attendance_corrected')
    def test_correction_updates_values_and_audits_reason(self, publish_notification):
        db = DatabaseDouble(self.make_employee())
        register_manual(db, 1)
        record = db.records[0]
        record.empleado = db.employee_by_id

        corrected = correct_attendance(db, record.id, 7, 'Error de digitación', attendance_type=AttendanceType.SALIDA)

        self.assertEqual(corrected.tipo, AttendanceType.SALIDA)
        self.assertEqual(record.tipo, AttendanceType.SALIDA.value)
        self.assertEqual(db.audit_records[-1].accion, 'correccion_marcaje')
        self.assertEqual(json.loads(db.audit_records[-1].datos_despues)['motivo'], 'Error de digitación')
        publish_notification.assert_called_once_with(db, 'Ana Pérez', 'ENTRADA', 'SALIDA', 'Error de digitación', 7)

    def test_correction_requires_reason_and_a_changed_value(self):
        db = DatabaseDouble(self.make_employee())
        register_manual(db, 1)
        record = db.records[0]
        record.empleado = db.employee_by_id

        with self.assertRaisesRegex(AttendanceError, 'motivo'):
            correct_attendance(db, record.id, 7, 'no', attendance_type=AttendanceType.SALIDA)
        with self.assertRaisesRegex(AttendanceError, 'al menos un valor'):
            correct_attendance(db, record.id, 7, 'Corrección válida')

    def test_manual_rejects_future_time(self):
        db = DatabaseDouble(self.make_employee())
        marked_at = datetime.now(timezone.utc) + timedelta(minutes=1)

        with self.assertRaisesRegex(AttendanceError, 'no puede ser futura'):
            register_manual(db, 1, marked_at=marked_at)

    def test_manual_batch_rejects_duplicate_employee(self):
        with self.assertRaises(ValueError):
            AttendanceManualBatchRequest(marcajes=[{'empleado_id': 1}, {'empleado_id': 1}])

    def test_manual_batch_rolls_back_when_a_mark_fails(self):
        db = DatabaseDouble(self.make_employee())
        marks = AttendanceManualBatchRequest(marcajes=[
            {'empleado_id': 1},
            {'empleado_id': 999},
        ])

        result = register_manual_batch(db, marks.marcajes)

        self.assertEqual(result['items'], [])
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(db.records, [])

    def test_inactive_employee_and_unknown_card_are_rejected(self):
        inactive_db = DatabaseDouble(self.make_employee(EstadoEmpleado.Retirado))
        with self.assertRaisesRegex(AttendanceError, 'no está activo'):
            register_manual(inactive_db, 1)

        unknown_db = DatabaseDouble(self.make_employee())
        unknown_db.employees[0].codigo_tarjeta = 'OTHER'
        with self.assertRaisesRegex(AttendanceError, 'Tarjeta no asociada'):
            register_scan(unknown_db, 'RFID-1', AttendanceOrigin.PUERTO_COM)

    def test_inactive_employee_can_leave_after_open_entry(self):
        db = DatabaseDouble(self.make_employee())
        register_manual(db, 1, marked_at=datetime.now(timezone.utc) - timedelta(minutes=2))
        db.employee_by_id.estado = EstadoEmpleado.Suspendido

        result = register_scan(db, 'RFID-1', AttendanceOrigin.PUERTO_COM)

        self.assertEqual(result.tipo, AttendanceType.SALIDA)

    def test_inactive_employee_cannot_enter_without_open_entry(self):
        db = DatabaseDouble(self.make_employee(EstadoEmpleado.Suspendido))

        with self.assertRaisesRegex(AttendanceError, 'no está activo'):
            register_scan(db, 'RFID-1', AttendanceOrigin.PUERTO_COM)


if __name__ == '__main__':
    unittest.main()
