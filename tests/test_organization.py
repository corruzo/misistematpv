import unittest
import uuid

from app.models.employee import Empleado
from app.models.organization import Gerencia, Departamento, Cargo
from app.services.organization_service import (
    create_gerencia,
    create_departamento,
    create_cargo,
    set_organization_state,
    get_organization_tree,
)
from app.schemas.organization import GerenciaCreate, DepartamentoCreate, CargoCreate
from app.database.session import SessionLocal


class OrganizationModelTest(unittest.TestCase):
    def test_hierarchy_creation(self):
        gerencia = Gerencia(nombre='Gerencia de Recursos Humanos', descripcion='Apoya personal', estado='Activo')
        departamento = Departamento(nombre='Departamento de Recursos Humanos', gerencia=gerencia, descripcion='RRHH', estado='Activo')
        cargo = Cargo(nombre='Analista de RR. HH.', departamento=departamento, descripcion='Analiza procesos', estado='Activo')

        self.assertEqual(gerencia.nombre, 'Gerencia de Recursos Humanos')
        self.assertEqual(gerencia.descripcion, 'Apoya personal')
        self.assertEqual(gerencia.estado, 'Activo')
        self.assertEqual(departamento.nombre, 'Departamento de Recursos Humanos')
        self.assertEqual(departamento.descripcion, 'RRHH')
        self.assertEqual(cargo.nombre, 'Analista de RR. HH.')
        self.assertEqual(cargo.descripcion, 'Analiza procesos')
        self.assertEqual(gerencia.departamentos[0].nombre, 'Departamento de Recursos Humanos')
        self.assertEqual(departamento.cargos[0].nombre, 'Analista de RR. HH.')

    def test_employee_uses_normalized_relationship_keys(self):
        column_names = Empleado.__table__.columns.keys()

        self.assertIn('departamento_id', column_names)
        self.assertIn('cargo_id', column_names)
        self.assertNotIn('gerencia_id', column_names)
        self.assertNotIn('gerencia', column_names)
        self.assertNotIn('departamento', column_names)
        self.assertNotIn('cargo', column_names)

    def test_employee_gerencia_is_derived_from_department(self):
        gerencia = Gerencia(nombre='Gerencia Comercial', descripcion='Ventas', estado='Activo')
        departamento = Departamento(nombre='Departamento de Ventas', gerencia=gerencia, descripcion='Operaciones', estado='Activo')
        cargo = Cargo(nombre='Analista Comercial', departamento=departamento, descripcion='Soporte', estado='Activo')
        empleado = Empleado(nombre_apellido='Ana Gómez', cedula='54321', departamento_id=1, cargo_id=1)
        empleado.departamento_rel = departamento
        empleado.cargo_rel = cargo

        self.assertEqual(empleado.gerencia, 'Gerencia Comercial')
        self.assertEqual(empleado.departamento, 'Departamento de Ventas')
        self.assertEqual(empleado.cargo, 'Analista Comercial')

    def test_create_department_fails_when_gerencia_is_inactive(self):
        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre=f'Gerencia Operaciones {suffix}', descripcion='Operaciones', estado='Inactivo'))
            with self.assertRaises(ValueError):
                create_departamento(db, DepartamentoCreate(nombre=f'Departamento de Operaciones {suffix}', descripcion='Ops', estado='Activo', gerencia_id=gerencia['id']))
        finally:
            db.close()

    def test_create_cargo_fails_when_department_is_inactive(self):
        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre=f'Gerencia Producción {suffix}', descripcion='Producción', estado='Activo'))
            departamento = create_departamento(db, DepartamentoCreate(nombre=f'Departamento de Producción {suffix}', descripcion='Producción', estado='Inactivo', gerencia_id=gerencia['id']))
            with self.assertRaises(ValueError):
                create_cargo(db, CargoCreate(nombre=f'Supervisor de Producción {suffix}', descripcion='Supervisor', estado='Activo', departamento_id=departamento['id']))
        finally:
            db.close()

    def test_set_organization_state_rejects_child_updates_for_inactive_parent(self):
        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre=f'Gerencia QA {suffix}', descripcion='QA', estado='Activo'))
            departamento = create_departamento(db, DepartamentoCreate(nombre=f'Departamento de QA {suffix}', descripcion='QA', estado='Activo', gerencia_id=gerencia['id']))
            create_cargo(db, CargoCreate(nombre=f'Analista QA {suffix}', descripcion='QA', estado='Activo', departamento_id=departamento['id']))

            set_organization_state(db, Gerencia, gerencia['id'], 'Inactivo')

            with self.assertRaises(ValueError):
                set_organization_state(db, Departamento, departamento['id'], 'Inactivo')
        finally:
            db.close()

    def test_session_factory_creates_distinct_sessions_per_call(self):
        first = SessionLocal()
        second = SessionLocal()

        self.assertIsNot(first, second)

        first.close()
        second.close()

    def test_organization_tree_orders_active_first(self):
        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        try:
            active_gerencia = create_gerencia(db, GerenciaCreate(nombre=f'Gerencia Activa {suffix}', descripcion='Activa', estado='Activo'))
            inactive_gerencia = create_gerencia(db, GerenciaCreate(nombre=f'Gerencia Inactiva {suffix}', descripcion='Inactiva', estado='Inactivo'))

            tree = get_organization_tree(db)
            names = [item['nombre'] for item in tree]

            self.assertLess(names.index(f'Gerencia Activa {suffix}'), names.index(f'Gerencia Inactiva {suffix}'))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
