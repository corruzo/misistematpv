import unittest

from sqlalchemy import event

from app.database.session import SessionLocal, engine
from app.services.attendance_service import attendance_summary, normalize_attendance_summary_counts
from app.services.employee_service import get_employee_metrics, normalize_employee_status_counts


class DashboardQueryTest(unittest.TestCase):
    def _count_queries(self, callback):
        count = 0

        def before_cursor_execute(*_args):
            nonlocal count
            count += 1

        event.listen(engine, 'before_cursor_execute', before_cursor_execute)
        try:
            callback()
        finally:
            event.remove(engine, 'before_cursor_execute', before_cursor_execute)
        return count

    def test_attendance_summary_does_not_query_per_present_employee(self):
        db = SessionLocal()
        try:
            queries = self._count_queries(lambda: attendance_summary(db))
            self.assertLessEqual(queries, 2)
        finally:
            db.close()

    def test_employee_metrics_use_aggregated_status_queries(self):
        db = SessionLocal()
        try:
            queries = self._count_queries(lambda: get_employee_metrics(db))
            self.assertLessEqual(queries, 8)
        finally:
            db.close()

    def test_employee_status_counts_are_normalized_and_zero_safe(self):
        payload = [('Activo', 3), ('Vacaciones', 2), ('X', 9), (None, 5)]
        normalized = normalize_employee_status_counts(payload)
        self.assertEqual(normalized['Activo'], 3)
        self.assertEqual(normalized['Vacaciones'], 2)
        self.assertEqual(normalized['Retirado'], 0)
        self.assertEqual(normalized['Suspendido'], 0)
        self.assertNotIn(None, normalized)
        self.assertNotIn('X', normalized)

    def test_attendance_summary_counts_are_normalized_for_invalid_data(self):
        payload = {
            'presentes': None,
            'entradas_hoy': '7',
            'salidas_hoy': '2',
            'marcajes_hoy': '9',
            'presentes_por_area': [{'gerencia': None, 'departamento': None, 'total': '5'}],
        }
        normalized = normalize_attendance_summary_counts(payload)
        self.assertEqual(normalized['presentes'], 0)
        self.assertEqual(normalized['entradas_hoy'], 7)
        self.assertEqual(normalized['salidas_hoy'], 2)
        self.assertEqual(normalized['marcajes_hoy'], 9)
        self.assertEqual(normalized['presentes_por_area'][0]['gerencia'], 'Sin gerencia')
        self.assertEqual(normalized['presentes_por_area'][0]['departamento'], 'Sin departamento')
        self.assertEqual(normalized['presentes_por_area'][0]['total'], 5)

if __name__ == '__main__':
    unittest.main()