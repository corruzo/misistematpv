import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app' / 'templates' / 'users.html'


class UsersPageTemplateTest(unittest.TestCase):
    def test_user_form_exposes_active_and_suspended_states(self):
        html = TEMPLATE.read_text(encoding='utf-8')

        self.assertIn('id="userStatus"', html)
        self.assertIn('<option value="true">Activo</option>', html)
        self.assertIn('<option value="false">Suspendido</option>', html)
        self.assertIn("statusInput.value = user.activo ? 'true' : 'false';", html)
        self.assertIn("payload.activo = statusInput.value === 'true';", html)


if __name__ == '__main__':
    unittest.main()