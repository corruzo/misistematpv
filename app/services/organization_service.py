from typing import Optional, Type
from sqlalchemy.orm import Session
from app.models.organization import Gerencia, Departamento, Cargo
from app.schemas.organization import GerenciaCreate, DepartamentoCreate, CargoCreate
from app.services.audit_service import add_audit


def normalize_organization_state(value: Optional[str]) -> str:
    if value is None:
        return 'Activo'
    normalized = str(value).strip()
    if not normalized:
        return 'Activo'
    mapping = {'activo': 'Activo', 'inactivo': 'Inactivo'}
    lowered = normalized.lower()
    if lowered in mapping:
        return mapping[lowered]
    raise ValueError('El estado debe ser Activo o Inactivo.')


def get_organization_tree(db: Session):
    gerencias = db.query(Gerencia).order_by(Gerencia.nombre.asc()).all()
    result = []
    for gerencia in gerencias:
        departamentos = []
        for departamento in sorted(gerencia.departamentos, key=lambda item: (0 if (item.estado or 'Activo') == 'Activo' else 1, item.nombre.lower())):
            cargos = [
                {
                    'id': cargo.id,
                    'nombre': cargo.nombre,
                    'descripcion': cargo.descripcion,
                    'estado': cargo.estado,
                    'fecha_creacion': cargo.fecha_creacion,
                }
                for cargo in sorted(departamento.cargos, key=lambda item: (0 if (item.estado or 'Activo') == 'Activo' else 1, item.nombre.lower()))
            ]
            departamentos.append({
                'id': departamento.id,
                'nombre': departamento.nombre,
                'descripcion': departamento.descripcion,
                'estado': departamento.estado,
                'fecha_creacion': departamento.fecha_creacion,
                'cargos': cargos,
            })
        result.append({
            'id': gerencia.id,
            'nombre': gerencia.nombre,
            'descripcion': gerencia.descripcion,
            'estado': gerencia.estado,
            'fecha_creacion': gerencia.fecha_creacion,
            'departamentos': sorted(departamentos, key=lambda item: (0 if (item['estado'] or 'Activo') == 'Activo' else 1, item['nombre'].lower())),
        })
    return sorted(result, key=lambda item: (0 if (item['estado'] or 'Activo') == 'Activo' else 1, item['nombre'].lower()))


def set_organization_state(db: Session, model_cls: Type, item_id: int, estado: Optional[str], usuario_id: int | None = None):
    item = db.query(model_cls).filter(model_cls.id == item_id).first()
    if not item:
        raise ValueError('El registro no existe.')

    normalized_state = normalize_organization_state(estado)
    if model_cls is Departamento:
        gerencia = db.query(Gerencia).filter(Gerencia.id == item.gerencia_id).first()
        if gerencia and gerencia.estado == 'Inactivo':
            raise ValueError('No se puede modificar un departamento dentro de una gerencia inhabilitada.')
    elif model_cls is Cargo:
        departamento = db.query(Departamento).filter(Departamento.id == item.departamento_id).first()
        if departamento and departamento.estado == 'Inactivo':
            raise ValueError('No se puede modificar un cargo dentro de un departamento inhabilitado.')
        if departamento and departamento.gerencia and departamento.gerencia.estado == 'Inactivo':
            raise ValueError('No se puede modificar un cargo dentro de una gerencia inhabilitada.')

    antes = {'estado': item.estado}
    item.estado = normalized_state
    add_audit(db, usuario_id, 'cambio_estado', model_cls.__tablename__, item.id, antes, {'estado': item.estado})
    db.commit()
    db.refresh(item)
    return item


def create_gerencia(db: Session, payload: GerenciaCreate, usuario_id: int | None = None):
    nombre = payload.nombre.strip()
    if not nombre:
        raise ValueError('El nombre de la gerencia es obligatorio.')
    if db.query(Gerencia).filter(Gerencia.nombre.like(nombre)).first():
        raise ValueError('Ya existe una gerencia con ese nombre.')
    item = Gerencia(
        nombre=nombre,
        descripcion=(payload.descripcion or '').strip() or None,
        estado=normalize_organization_state(payload.estado),
    )
    db.add(item)
    db.flush()
    add_audit(db, usuario_id, 'alta', 'gerencias', item.id, despues={'nombre': item.nombre, 'estado': item.estado})
    db.commit()
    db.refresh(item)
    return {'id': item.id, 'nombre': item.nombre, 'descripcion': item.descripcion, 'estado': item.estado, 'fecha_creacion': item.fecha_creacion}


def create_departamento(db: Session, payload: DepartamentoCreate, usuario_id: int | None = None):
    nombre = payload.nombre.strip()
    gerencia = db.query(Gerencia).filter(Gerencia.id == payload.gerencia_id).first()
    if not gerencia:
        raise ValueError('La gerencia seleccionada no existe.')
    if gerencia.estado == 'Inactivo':
        raise ValueError('No se puede crear un departamento dentro de una gerencia inhabilitada.')
    if not nombre:
        raise ValueError('El nombre del departamento es obligatorio.')
    if db.query(Departamento).filter(Departamento.gerencia_id == gerencia.id, Departamento.nombre.like(nombre)).first():
        raise ValueError('Ya existe un departamento con ese nombre.')
    item = Departamento(
        nombre=nombre,
        descripcion=(payload.descripcion or '').strip() or None,
        estado=normalize_organization_state(payload.estado),
        gerencia_id=gerencia.id,
    )
    db.add(item)
    db.flush()
    add_audit(db, usuario_id, 'alta', 'departamentos', item.id, despues={'nombre': item.nombre, 'gerencia_id': item.gerencia_id, 'estado': item.estado})
    db.commit()
    db.refresh(item)
    return {'id': item.id, 'nombre': item.nombre, 'descripcion': item.descripcion, 'estado': item.estado, 'fecha_creacion': item.fecha_creacion, 'gerencia_id': gerencia.id}


def create_cargo(db: Session, payload: CargoCreate, usuario_id: int | None = None):
    nombre = payload.nombre.strip()
    departamento = db.query(Departamento).filter(Departamento.id == payload.departamento_id).first()
    if not departamento:
        raise ValueError('El departamento seleccionado no existe.')
    if departamento.estado == 'Inactivo':
        raise ValueError('No se puede crear un cargo dentro de un departamento inhabilitado.')
    if departamento.gerencia and departamento.gerencia.estado == 'Inactivo':
        raise ValueError('No se puede crear un cargo dentro de una gerencia inhabilitada.')
    if not nombre:
        raise ValueError('El nombre del cargo es obligatorio.')
    if db.query(Cargo).filter(Cargo.departamento_id == departamento.id, Cargo.nombre.like(nombre)).first():
        raise ValueError('Ya existe un cargo con ese nombre.')
    item = Cargo(
        nombre=nombre,
        descripcion=(payload.descripcion or '').strip() or None,
        estado=normalize_organization_state(payload.estado),
        departamento_id=departamento.id,
    )
    db.add(item)
    db.flush()
    add_audit(db, usuario_id, 'alta', 'cargos', item.id, despues={'nombre': item.nombre, 'departamento_id': item.departamento_id, 'estado': item.estado})
    db.commit()
    db.refresh(item)
    return {'id': item.id, 'nombre': item.nombre, 'descripcion': item.descripcion, 'estado': item.estado, 'fecha_creacion': item.fecha_creacion, 'departamento_id': departamento.id}
