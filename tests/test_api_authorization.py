import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.controllers.attendance_controller import router as attendance_router
from app.controllers.employee_controller import router as employee_router
from app.controllers.organization_controller import router as organization_router
from app.controllers.notification_controller import router as notification_router
from app.controllers.user_controller import router as user_router
from app.core.auth import current_user_optional
from app.database.session import get_db


class ApiAuthorizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(employee_router)
        app.include_router(organization_router)
        app.include_router(user_router)
        app.include_router(attendance_router)
        app.include_router(notification_router)
        app.dependency_overrides[current_user_optional] = lambda: None
        app.dependency_overrides[get_db] = lambda: None
        cls.client = TestClient(app)

    def test_every_api_endpoint_requires_a_session(self):
        requests = [
            ('GET', '/api/organization', None),
            ('GET', '/api/system/status', None),
            ('GET', '/api/employees/1', None),
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
            ('POST', '/api/attendance/manual-mark', {}),
            ('PATCH', '/api/attendance/1/correct', {}),
            ('GET', '/api/attendance/history', None),
            ('GET', '/api/attendance/export.csv', None),
            ('GET', '/api/attendance/summary', None),
            ('GET', '/api/attendance/present', None),
            ('GET', '/api/attendance/filter-options', None),
            ('GET', '/api/attendance/denied-events', None),
            ('POST', '/api/attendance/alerts/' + ('a' * 64) + '/dismiss', None),
            ('GET', '/api/attendance/manual-employees', None),
            ('POST', '/api/attendance/kiosk-scan', {}),
            ('GET', '/api/notifications', None),
            ('PATCH', '/api/notifications/read', None),
            ('DELETE', '/api/notifications/1', None),
        ]
        for method, path, payload in requests:
            response = self.client.request(method, path, json=payload)
            self.assertEqual(response.status_code, 401, f'{method} {path}: {response.text}')

        with self.assertRaises(Exception):
            with self.client.websocket_connect('/api/ws'):
                pass

    def test_html_pages_redirect_to_login_without_exposing_json(self):
        for path in ('/users', '/employees', '/organization', '/attendance/summary'):
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 307, path)
            self.assertEqual(response.headers['location'], '/login?reason=session_expired')


if __name__ == '__main__':
    unittest.main()
