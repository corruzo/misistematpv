import base64
import hashlib
import secrets
import unittest

from app.core.auth import (
    PERMISSION_MANAGE_ATTENDANCE,
    PERMISSION_MANAGE_EMPLOYEES,
    PERMISSION_MANAGE_ORGANIZATION,
    PERMISSION_MANAGE_SYSTEM,
    PERMISSION_MANAGE_USERS,
    PERMISSION_READ_ATTENDANCE,
    PERMISSION_READ_MASTER_DATA,
    ROLE_DEVELOPER,
    ROLE_HR,
    ROLE_INSPECTOR,
    ROLE_PERMISSIONS,
    has_permission,
    require_developer,
    require_roles,
)
from app.core.rate_limit import is_rate_limited
from app.core.security import hash_password, password_needs_rehash, verify_password
from app.controllers.employee_controller import router
from run import configured_worker_count, validate_serial_worker_count
from app.services.backup_service import backup_path


class SecurityContractTest(unittest.TestCase):
    def test_backup_download_accepts_only_configured_slots(self):
        self.assertEqual(backup_path('backup_1.bak').name, 'backup_1.bak')
        with self.assertRaises(ValueError):
            backup_path('../.env')
        with self.assertRaises(ValueError):
            backup_path('database.bak')

    def test_serial_reader_rejects_multiple_workers(self):
        with self.assertRaisesRegex(RuntimeError, 'un solo worker'):
            validate_serial_worker_count(2, 'COM3')

    def test_serial_reader_allows_single_worker_or_no_port(self):
        validate_serial_worker_count(1, 'COM3')
        validate_serial_worker_count(4, '')

    def test_worker_count_reads_uvicorn_argument_or_environment(self):
        self.assertEqual(configured_worker_count(['uvicorn', 'run:app', '--workers', '3'], {}), 3)
        self.assertEqual(configured_worker_count(['uvicorn', 'run:app', '--workers=4'], {}), 4)
        self.assertEqual(configured_worker_count(['uvicorn', 'run:app'], {'WEB_CONCURRENCY': '2'}), 2)

    def test_password_hashes_verify_and_old_cost_is_rehashed(self):
        password = 'UnaClaveSegura123'
        encoded = hash_password(password)

        self.assertTrue(verify_password(password, encoded))
        self.assertFalse(password_needs_rehash(encoded))

        salt = secrets.token_bytes(16)
        old_key = hashlib.scrypt(
            password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=128 * 1024 * 1024
        )
        encode = lambda value: base64.urlsafe_b64encode(value).decode('ascii')
        old_encoded = f'scrypt$16384$8$1${encode(salt)}${encode(old_key)}'
        self.assertTrue(verify_password(password, old_encoded))
        self.assertTrue(password_needs_rehash(old_encoded))

    def test_role_dependencies_accept_only_declared_roles(self):
        developer = type('User', (), {'rol': ROLE_DEVELOPER})()
        hr = type('User', (), {'rol': ROLE_HR})()
        inspector = type('User', (), {'rol': ROLE_INSPECTOR})()

        self.assertIs(require_roles(ROLE_DEVELOPER, ROLE_HR)(developer), developer)
        self.assertIs(require_roles(ROLE_DEVELOPER, ROLE_HR)(hr), hr)
        with self.assertRaises(Exception):
            require_roles(ROLE_DEVELOPER, ROLE_HR)(inspector)

    def test_role_permission_matrix_is_explicit(self):
        developer = type('User', (), {'rol': ROLE_DEVELOPER})()
        hr = type('User', (), {'rol': ROLE_HR})()
        inspector = type('User', (), {'rol': ROLE_INSPECTOR})()

        self.assertTrue(has_permission(developer, PERMISSION_MANAGE_SYSTEM))
        self.assertTrue(has_permission(developer, PERMISSION_MANAGE_ORGANIZATION))
        self.assertTrue(has_permission(hr, PERMISSION_MANAGE_EMPLOYEES))
        self.assertTrue(has_permission(hr, PERMISSION_MANAGE_ATTENDANCE))
        self.assertFalse(has_permission(hr, PERMISSION_MANAGE_USERS))
        self.assertTrue(has_permission(inspector, PERMISSION_READ_MASTER_DATA))
        self.assertTrue(has_permission(inspector, PERMISSION_READ_ATTENDANCE))
        self.assertFalse(has_permission(inspector, PERMISSION_MANAGE_EMPLOYEES))
        self.assertFalse(has_permission(inspector, PERMISSION_MANAGE_ATTENDANCE))
        self.assertEqual(set(ROLE_PERMISSIONS), {ROLE_DEVELOPER, ROLE_HR, ROLE_INSPECTOR})

    def test_developer_role_can_access_system_tools(self):
        developer = type('User', (), {'rol': ROLE_DEVELOPER})()
        inspector = type('User', (), {'rol': ROLE_INSPECTOR})()

        self.assertIs(require_developer(developer), developer)
        with self.assertRaises(Exception):
            require_developer(inspector)

    def test_rate_limit_is_scoped_by_username(self):
        self.assertFalse(is_rate_limited('/login-test', '127.0.0.1', 'ana'))
        self.assertFalse(is_rate_limited('/login-test', '127.0.0.1', 'bruno'))

    def test_employee_api_routes_declare_authentication_dependencies(self):
        api_routes = [route for route in router.routes if route.path.startswith('/api/')]
        self.assertGreater(len(api_routes), 0)
        for route in api_routes:
            dependency_names = {dependency.call.__name__ for dependency in route.dependant.dependencies}
            self.assertTrue(
                {'require_read_access', 'require_employee_manager', 'require_developer'} & dependency_names,
                route.path,
            )


if __name__ == '__main__':
    unittest.main()