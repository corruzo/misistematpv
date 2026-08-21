import unittest

from sqlalchemy import event

from app.database.session import SessionLocal, engine
from app.services.attendance_service import attendance_summary
from app.services.employee_service import get_employee_metrics


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


if __name__ == '__main__':
    unittest.main()