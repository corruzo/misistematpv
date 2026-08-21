import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.controllers.attendance_controller import router as attendance_router
from app.controllers.employee_controller import router as employee_router
from app.controllers.user_controller import router as user_router
from app.core.auth import current_user_optional
from app.database.session import get_db


class ApiAuthorizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(employee_router)
        app.include_router(user_router)
        app.include_router(attendance_router)
        app.dependency_overrides[current_user_optional] = lambda: None
        app.dependency_overrides[get_db] = lambda: None
        cls.client = TestClient(app)

    def test_every_api_endpoint_requires_a_session(self):
        requests = [
            ('GET', '/api/organization', None),
            ('GET', '/api/system/status', None),
            ('GET', '/api/employees/1', None),
            ('GET', '/api/dashboard/metrics', None),
            ('GET', '/api/employees', None),
            ('POST', '/api/employees', {}),
            ('PUT', '/api/employees/1', {}),
            ('PATCH', '/api/employees/1/disable', None),
            ('POST', '/api/organization/gerencias', {}),
            ('POST', '/api/organization/departamentos', {}),
            ('POST', '/api/organization/cargos', {}),
            ('PATCH', '/api/organization/gerencias/1/status', {}),
            ('PATCH', '/api/organization/departamentos/1/status', {}),
            ('PATCH', '/api/organization/cargos/1/status', {}),
            ('GET', '/api/me', None),
            ('PUT', '/api/me', {}),
            ('GET', '/api/users', None),
            ('POST', '/api/users', {}),
            ('PUT', '/api/users/1', {}),
            ('PATCH', '/api/users/1/status', {}),
            ('POST', '/api/attendance/simulate-scan', {}),
            ('POST', '/api/attendance/manual-mark', {}),
            ('GET', '/api/attendance/history', None),
            ('GET', '/api/attendance/summary', None),
            ('GET', '/api/attendance/present', None),
            ('GET', '/api/attendance/filter-options', None),
            ('POST', '/api/attendance/kiosk-scan', {}),
        ]
        for method, path, payload in requests:
            response = self.client.request(method, path, json=payload)
            self.assertEqual(response.status_code, 401, f'{method} {path}: {response.text}')


if __name__ == '__main__':
    unittest.main()
