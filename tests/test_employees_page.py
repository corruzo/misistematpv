import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app' / 'templates' / 'employees.html'


class EmployeePageTemplateTest(unittest.TestCase):
    def test_employees_template_contains_employee_modal_and_form(self):
        html = TEMPLATE.read_text(encoding='utf-8')

        self.assertIn('id="employeeModal"', html)
        self.assertIn('id="employeeForm"', html)
        self.assertIn('name="cedula"', html)
        self.assertIn('name="nombre_apellido"', html)

    def test_employees_template_has_visible_action_buttons(self):
        html = TEMPLATE.read_text(encoding='utf-8')

        self.assertIn('Ver estructura', html)
        self.assertIn('Nuevo registro', html)

    def test_employees_template_has_search_and_filters(self):
        html = TEMPLATE.read_text(encoding='utf-8')

        self.assertIn('id="searchInput"', html)
        self.assertIn('id="gerenciaFilter"', html)
        self.assertIn('id="departamentoFilter"', html)
        self.assertIn('id="estadoFilter"', html)

    def test_employee_status_options_match_persisted_states(self):
        html = TEMPLATE.read_text(encoding='utf-8')

        for state in ['Activo', 'Vacaciones', 'Retirado', 'Suspendido']:
            self.assertIn(f'value="{state}"', html)


if __name__ == '__main__':
    unittest.main()
