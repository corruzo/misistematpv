import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.employee import Empleado
from app.models.organization import Gerencia, Departamento, Cargo
from app.services.organization_service import (
    create_gerencia,
    create_departamento,
    create_cargo,
    set_organization_state,
    get_organization_tree,
    update_organization,
    delete_or_disable_organization,
)
from app.schemas.organization import GerenciaCreate, DepartamentoCreate, CargoCreate, OrganizationUpdate
from app.models.base import Base


class OrganizationModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            'sqlite://',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
        )
        event.listen(
            cls.engine,
            'connect',
            lambda connection, _record: connection.create_function(
                'sysutcdatetime', 0, lambda: datetime.now(timezone.utc).isoformat(sep=' ')
            ),
        )
        Base.metadata.create_all(cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine, expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def new_session(self):
        return self.session_factory()

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
        db = self.new_session()
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia Operaciones', descripcion='Operaciones', estado='Inactivo'))
            with self.assertRaises(ValueError):
                create_departamento(db, DepartamentoCreate(nombre='Departamento de Operaciones', descripcion='Ops', estado='Activo', gerencia_id=gerencia['id']))
        finally:
            db.close()

    def test_create_cargo_fails_when_department_is_inactive(self):
        db = self.new_session()
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia Producción', descripcion='Producción', estado='Activo'))
            departamento = create_departamento(db, DepartamentoCreate(nombre='Departamento de Producción', descripcion='Producción', estado='Inactivo', gerencia_id=gerencia['id']))
            with self.assertRaises(ValueError):
                create_cargo(db, CargoCreate(nombre='Supervisor de Producción', descripcion='Supervisor', estado='Activo', departamento_id=departamento['id']))
        finally:
            db.close()

    def test_set_organization_state_rejects_child_updates_for_inactive_parent(self):
        db = self.new_session()
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia QA', descripcion='QA', estado='Activo'))
            departamento = create_departamento(db, DepartamentoCreate(nombre='Departamento de QA', descripcion='QA', estado='Activo', gerencia_id=gerencia['id']))
            create_cargo(db, CargoCreate(nombre='Analista QA', descripcion='QA', estado='Activo', departamento_id=departamento['id']))

            set_organization_state(db, Gerencia, gerencia['id'], 'Inactivo')

            with self.assertRaises(ValueError):
                set_organization_state(db, Departamento, departamento['id'], 'Inactivo')
        finally:
            db.close()

    def test_session_factory_creates_distinct_sessions_per_call(self):
        first = self.new_session()
        second = self.new_session()

        self.assertIsNot(first, second)

        first.close()
        second.close()

    def test_organization_tree_orders_active_first(self):
        db = self.new_session()
        try:
            active_gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia Activa', descripcion='Activa', estado='Activo'))
            inactive_gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia Inactiva', descripcion='Inactiva', estado='Inactivo'))

            tree = get_organization_tree(db)
            names = [item['nombre'] for item in tree]

            self.assertLess(names.index(active_gerencia['nombre']), names.index(inactive_gerencia['nombre']))
        finally:
            db.close()

    def test_unlinked_hierarchy_is_deleted_permanently(self):
        db = self.new_session()
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia Eliminable', descripcion='Temporal'))
            departamento = create_departamento(db, DepartamentoCreate(nombre='Departamento Eliminable', descripcion='Temporal', gerencia_id=gerencia['id']))
            cargo = create_cargo(db, CargoCreate(nombre='Cargo Eliminable', descripcion='Temporal', departamento_id=departamento['id']))

            result = delete_or_disable_organization(db, Gerencia, gerencia['id'])

            self.assertEqual(result['action'], 'deleted')
            self.assertIsNone(db.query(Gerencia).filter_by(id=gerencia['id']).first())
            self.assertIsNone(db.query(Departamento).filter_by(id=departamento['id']).first())
            self.assertIsNone(db.query(Cargo).filter_by(id=cargo['id']).first())
        finally:
            db.close()

    def test_linked_hierarchy_is_disabled_and_can_be_updated(self):
        db = self.new_session()
        try:
            gerencia = create_gerencia(db, GerenciaCreate(nombre='Gerencia Vinculada'))
            departamento = create_departamento(db, DepartamentoCreate(nombre='Departamento Vinculado', gerencia_id=gerencia['id']))
            cargo = create_cargo(db, CargoCreate(nombre='Cargo Vinculado', departamento_id=departamento['id']))
            employee = Empleado(nombre_apellido='Empleado Vinculado', cedula='linked-1', departamento_id=departamento['id'], cargo_id=cargo['id'])
            db.add(employee)
            db.commit()

            result = delete_or_disable_organization(db, Gerencia, gerencia['id'])
            persisted_gerencia = db.query(Gerencia).filter_by(id=gerencia['id']).first()

            self.assertEqual(result['action'], 'disabled')
            self.assertEqual(persisted_gerencia.estado, 'Inactivo')
            updated = update_organization(db, Gerencia, gerencia['id'], OrganizationUpdate(nombre='Gerencia Reactivada', descripcion='Actualizada', estado='Activo'))
            self.assertEqual(updated.nombre, 'Gerencia Reactivada')
            self.assertEqual(updated.estado, 'Activo')
        finally:
            db.close()

    def test_organization_template_has_contextual_branch_actions(self):
        html = (Path(__file__).resolve().parents[1] / 'app' / 'templates' / 'organization.html').read_text(encoding='utf-8')

        self.assertIn('data-create-type="departamento"', html)
        self.assertIn('data-create-type="cargo"', html)
        self.assertIn('function openCreateForm', html)


if __name__ == '__main__':
    unittest.main()
