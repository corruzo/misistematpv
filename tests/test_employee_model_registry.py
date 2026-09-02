from app.database.session import SessionLocal
from app.models.employee import Empleado


def test_employee_mapper_can_query_database():
    db = SessionLocal()
    try:
        rows = db.query(Empleado).limit(1).all()
        assert isinstance(rows, list)
    finally:
        db.close()
