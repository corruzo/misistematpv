import unittest
from app.core.exceptions import AppException, BusinessValidationError, DatabaseConnectionError, EntityNotFoundError, OrganizationInUseError, SessionExpiredError

class ExceptionsTest(unittest.TestCase):
    def test_app_exception_defaults(self):
        exc = AppException("Error de prueba")
        self.assertEqual(exc.message, "Error de prueba")
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.details, {})

    def test_organization_in_use_error(self):
        exc = OrganizationInUseError("Sistemas", 5, "empleados")
        self.assertEqual(exc.status_code, 422)
        self.assertIn("Sistemas", exc.message)
        self.assertIn("5", exc.message)
        self.assertEqual(exc.details["item_name"], "Sistemas")
        self.assertEqual(exc.details["count"], 5)

    def test_database_connection_error(self):
        exc = DatabaseConnectionError()
        self.assertEqual(exc.status_code, 503)

    def test_session_expired_error(self):
        exc = SessionExpiredError()
        self.assertEqual(exc.status_code, 401)

if __name__ == "__main__":
    unittest.main()
