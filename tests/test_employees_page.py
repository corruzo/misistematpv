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

    def test_employee_page_exposes_requested_kpis_and_scoped_filters(self):
        html = TEMPLATE.read_text(encoding='utf-8')
        javascript = (ROOT / 'app' / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')

        self.assertIn('Total empleados activos', html)
        self.assertIn('Total empleados de vacaciones', html)
        self.assertIn('Total retirados / suspendidos', html)
        self.assertIn("params.set('gerencia_id', gerenciaFilter.value)", javascript)
        self.assertIn("params.set('departamento_id', departamentoFilter.value)", javascript)
        self.assertIn("this.populateFilterSelects();", javascript)

    def test_employee_page_exposes_profile_modal_and_bounded_filters(self):
        html = TEMPLATE.read_text(encoding='utf-8')
        javascript = (ROOT / 'app' / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')

        self.assertIn('id="employeeProfileModal"', html)
        self.assertIn('id="profileDays"', html)
        self.assertIn('id="profilePageSize"', html)
        self.assertIn('/profile?days=${days}&page=${page}&page_size=${pageSize}', javascript)
        self.assertIn('Ver ficha del empleado', javascript)

    def test_navigation_separates_master_data_from_attendance_operations(self):
        base = (ROOT / 'app' / 'templates' / 'base.html').read_text(encoding='utf-8')

        self.assertIn('Administración de datos maestros', base)
        self.assertIn('Operación de asistencia', base)
        self.assertIn('module-system', base)
        self.assertIn('Backups y mantenimiento', base)
        self.assertIn('/attendance/summary', base)
        self.assertIn('/employees', base)
        self.assertIn('/organization', base)
        self.assertIn('/users', base)


if __name__ == '__main__':
    unittest.main()
