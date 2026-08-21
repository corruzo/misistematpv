import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models.employee import Empleado, EstadoEnum
from app.models.organization import Departamento, Cargo, Gerencia
from app.core.config import ALLOWED_IMAGE_EXT, UPLOADS_DIR
from app.services.audit_service import add_audit

MAX_IMAGE_SIZE = 5 * 1024 * 1024
IMAGE_SIGNATURES = {
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.gif': (b'GIF87a', b'GIF89a'),
}


def resolve_employee_org_ids(db: Session, departamento_id: Optional[int] = None, cargo_id: Optional[int] = None,
                            departamento_name: Optional[str] = None, cargo_name: Optional[str] = None,
                            gerencia_id: Optional[int] = None):
    resolved_departamento_id = departamento_id
    resolved_cargo_id = cargo_id

    if resolved_departamento_id is None and departamento_name:
        departamento = db.query(Departamento).filter(Departamento.nombre.like(departamento_name.strip())).first()
        if departamento:
            resolved_departamento_id = departamento.id

    if resolved_cargo_id is None and cargo_name:
        cargo = db.query(Cargo).filter(Cargo.nombre.like(cargo_name.strip())).first()
        if cargo:
            resolved_cargo_id = cargo.id

    if resolved_departamento_id is not None:
        departamento = db.query(Departamento).filter(Departamento.id == resolved_departamento_id).first()
        if departamento is None:
            raise ValueError('El departamento seleccionado no existe.')
        if gerencia_id is not None and departamento.gerencia_id != gerencia_id:
            raise ValueError('El departamento no pertenece a la gerencia seleccionada.')
        if departamento.gerencia and departamento.gerencia.estado == 'Inactivo':
            raise ValueError('No se pueden registrar empleados en una gerencia inhabilitada.')
        if departamento.estado == 'Inactivo':
            raise ValueError('No se pueden registrar empleados en un departamento inhabilitado.')

    if resolved_cargo_id is not None:
        cargo = db.query(Cargo).filter(Cargo.id == resolved_cargo_id).first()
        if cargo is None:
            raise ValueError('El cargo seleccionado no existe.')
        if cargo.departamento_id != resolved_departamento_id:
            raise ValueError('El cargo no pertenece al departamento seleccionado.')

    if resolved_departamento_id is not None and resolved_cargo_id is not None:
        if cargo and cargo.departamento_id != resolved_departamento_id:
            raise ValueError('El cargo no pertenece al departamento seleccionado.')

    return resolved_departamento_id, resolved_cargo_id


def save_image(file: UploadFile) -> Optional[str]:
    if not file or not file.filename:
        return None
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT or (file.content_type or '').lower() not in {'image/png', 'image/jpeg', 'image/gif'}:
        raise ValueError('La foto debe ser una imagen PNG, JPG, JPEG o GIF.')

    contents = file.file.read(MAX_IMAGE_SIZE + 1)
    if len(contents) > MAX_IMAGE_SIZE:
        raise ValueError('La foto no puede superar los 5 MB.')
    if not any(contents.startswith(signature) for signature in IMAGE_SIGNATURES[suffix]):
        raise ValueError('El contenido de la foto no coincide con su formato declarado.')

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / unique_name
    dest.write_bytes(contents)
    return f"uploads/{unique_name}"


def create_employee(db: Session, data, foto: Optional[UploadFile] = None, usuario_id: int | None = None) -> Empleado:
    cedula = str(data.cedula or '').strip()
    nombre_apellido = str(data.nombre_apellido or '').strip()
    if not cedula or not nombre_apellido:
        raise ValueError('La cédula y el nombre del empleado son obligatorios.')

    departamento_id, cargo_id = resolve_employee_org_ids(
        db,
        departamento_id=getattr(data, 'departamento_id', None),
        cargo_id=getattr(data, 'cargo_id', None),
        departamento_name=getattr(data, 'departamento', None),
        cargo_name=getattr(data, 'cargo', None),
        gerencia_id=getattr(data, 'gerencia_id', None),
    )
    foto_url = save_image(foto) if foto else None
    emp = Empleado(
        cedula=cedula,
        codigo_tarjeta=(str(data.codigo_tarjeta).strip() or None) if data.codigo_tarjeta else None,
        nombre_apellido=nombre_apellido,
        fecha_nacimiento=getattr(data, 'fecha_nacimiento', None),
        departamento_id=departamento_id,
        cargo_id=cargo_id,
        estado=data.estado,
        tipo_nomina=(str(data.tipo_nomina).strip() or None) if data.tipo_nomina else None,
        foto_url=foto_url,
    )
    db.add(emp)
    db.flush()
    add_audit(db, usuario_id, 'alta', 'empleados', emp.id, despues={
        'cedula': emp.cedula, 'nombre_apellido': emp.nombre_apellido,
        'departamento_id': emp.departamento_id, 'cargo_id': emp.cargo_id, 'estado': emp.estado,
    })
    db.commit()
    db.refresh(emp)
    return emp


def update_employee(db: Session, emp: Empleado, updates, foto: Optional[UploadFile] = None, eliminar_foto: bool = False, usuario_id: int | None = None) -> Empleado:
    antes = {
        'nombre_apellido': emp.nombre_apellido, 'departamento_id': emp.departamento_id,
        'cargo_id': emp.cargo_id, 'estado': emp.estado, 'tipo_nomina': emp.tipo_nomina,
        'foto_url': emp.foto_url,
    }
    if foto and foto.filename:
        foto_url = save_image(foto)
        old_photo = STATIC_DIR / emp.foto_url if emp.foto_url else None
        emp.foto_url = foto_url
        if old_photo and old_photo.is_file() and UPLOADS_DIR in old_photo.parents:
            old_photo.unlink()
    elif eliminar_foto and emp.foto_url:
        old_photo = STATIC_DIR / emp.foto_url
        if old_photo.is_file() and UPLOADS_DIR in old_photo.parents:
            old_photo.unlink()
        emp.foto_url = None

    payload = updates.dict(exclude_unset=True)
    departamento_id = payload.get('departamento_id')
    cargo_id = payload.get('cargo_id')
    if departamento_id is None and payload.get('departamento'):
        departamento = db.query(Departamento).filter(Departamento.nombre.like(str(payload['departamento']).strip())).first()
        departamento_id = departamento.id if departamento else None
    if cargo_id is None and payload.get('cargo'):
        cargo = db.query(Cargo).filter(Cargo.nombre.like(str(payload['cargo']).strip())).first()
        cargo_id = cargo.id if cargo else None

    if departamento_id is not None or cargo_id is not None:
        departamento_id, cargo_id = resolve_employee_org_ids(
            db,
            departamento_id=departamento_id,
            cargo_id=cargo_id,
            departamento_name=payload.get('departamento'),
            cargo_name=payload.get('cargo'),
            gerencia_id=payload.get('gerencia_id'),
        )
        emp.departamento_id = departamento_id
        emp.cargo_id = cargo_id

    for field, value in payload.items():
        if field in {'departamento', 'cargo', 'gerencia', 'gerencia_id'}:
            continue
        if value is not None or field == 'codigo_tarjeta':
            normalized_value = value.strip() if isinstance(value, str) else value
            if field == 'nombre_apellido' and not normalized_value:
                raise ValueError('El nombre del empleado no puede estar vacío.')
            setattr(emp, field, normalized_value)
    db.add(emp)
    add_audit(db, usuario_id, 'actualizacion', 'empleados', emp.id, antes, {
        'nombre_apellido': emp.nombre_apellido, 'departamento_id': emp.departamento_id,
        'cargo_id': emp.cargo_id, 'estado': emp.estado, 'tipo_nomina': emp.tipo_nomina,
        'foto_url': emp.foto_url,
    })
    db.commit()
    db.refresh(emp)
    return emp


def get_employee_by_id(db: Session, emp_id: int) -> Optional[Empleado]:
    return db.query(Empleado).options(
        joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia),
        joinedload(Empleado.cargo_rel)
    ).filter(Empleado.id == emp_id).first()


def build_employee_query(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, tipo_nomina: Optional[str] = None):
    query = db.query(Empleado).options(
        joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia),
        joinedload(Empleado.cargo_rel)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Empleado.nombre_apellido.like(like)) | (Empleado.cedula.like(like))
        )
    if estado:
        query = query.filter(Empleado.estado == estado)
    if gerencia:
        query = query.join(Empleado.departamento_rel).join(Departamento.gerencia).filter(Gerencia.nombre.like(f"%{gerencia}%"))
    if departamento:
        query = query.join(Empleado.departamento_rel).filter(Departamento.nombre.like(f"%{departamento}%"))
    if tipo_nomina:
        query = query.filter(Empleado.tipo_nomina == tipo_nomina)
    return query


def search_employees(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, tipo_nomina: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Empleado]:
    query = build_employee_query(db, q, estado, gerencia, departamento, tipo_nomina)
    return query.order_by(Empleado.fecha_creacion.desc()).offset(offset).limit(limit).all()


def count_employees(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, tipo_nomina: Optional[str] = None) -> int:
    return build_employee_query(db, q, estado, gerencia, departamento, tipo_nomina).count()


def soft_delete_employee(db: Session, emp: Empleado, usuario_id: int | None = None) -> Empleado:
    antes = {'estado': emp.estado}
    emp.estado = EstadoEnum.Retirado
    db.add(emp)
    add_audit(db, usuario_id, 'baja', 'empleados', emp.id, antes, {'estado': emp.estado})
    db.commit()
    db.refresh(emp)
    return emp


def get_employee_metrics(db: Session):
    status_rows = db.query(Empleado.estado, func.count(Empleado.id)).group_by(Empleado.estado).all()
    estado_counts = {state.value if isinstance(state, EstadoEnum) else state: count for state, count in status_rows}
    estado_counts = {state: estado_counts.get(state, 0) for state in ('Activo', 'Vacaciones', 'Retirado', 'Suspendido')}
    total = sum(estado_counts.values())

    activos = estado_counts['Activo']
    inactivos = sum(value for key, value in estado_counts.items() if key != 'Activo')
    today = datetime.utcnow()

    latest_employee = db.query(Empleado).order_by(Empleado.fecha_creacion.desc()).first()
    latest_employee_label = latest_employee.fecha_creacion.strftime('%d/%m/%Y') if latest_employee and latest_employee.fecha_creacion else 'Sin registros'
    latest_activity = {
        'nombre': latest_employee.nombre_apellido,
        'fecha': latest_employee_label,
    } if latest_employee else None

    departamento_counts = db.query(Departamento.estado, func.count(Departamento.id)).group_by(Departamento.estado).all()
    departamento_counts = {state: count for state, count in departamento_counts}
    total_departamentos = sum(departamento_counts.values())
    departamentos_activas = departamento_counts.get('Activo', 0)
    departamentos_inactivas = total_departamentos - departamentos_activas

    gerencia_counts = db.query(Gerencia.estado, func.count(Gerencia.id)).group_by(Gerencia.estado).all()
    gerencia_counts = {state: count for state, count in gerencia_counts}
    total_gerencias = sum(gerencia_counts.values())
    gerencias_activas = gerencia_counts.get('Activo', 0)
    gerencias_inactivas = total_gerencias - gerencias_activas

    cargo_counts = db.query(Cargo.estado, func.count(Cargo.id)).group_by(Cargo.estado).all()
    cargo_counts = {state: count for state, count in cargo_counts}
    total_cargos = sum(cargo_counts.values())
    cargos_activas = cargo_counts.get('Activo', 0)
    cargos_inactivas = total_cargos - cargos_activas

    unique_departments = db.query(Empleado.departamento_id).filter(Empleado.departamento_id.isnot(None)).distinct().count()
    top_departamentos = db.query(
        Departamento.nombre,
        func.count(Empleado.id).label('total_empleados')
    ).outerjoin(Empleado, Empleado.departamento_id == Departamento.id).group_by(Departamento.id, Departamento.nombre).order_by(func.count(Empleado.id).desc(), Departamento.nombre.asc()).limit(3).all()

    payroll_breakdown = db.query(
        Empleado.tipo_nomina,
        func.count(Empleado.id).label('total')
    ).filter(Empleado.tipo_nomina.isnot(None)).group_by(Empleado.tipo_nomina).order_by(func.count(Empleado.id).desc()).all()

    return {
        'total': total,
        'active': activos,
        'inactive': inactivos,
        'by_estado': estado_counts,
        'depts': unique_departments,
        'gerencias': total_gerencias,
        'cargos': total_cargos,
        'gerencias_activas': gerencias_activas,
        'gerencias_inactivas': gerencias_inactivas,
        'departamentos_activas': departamentos_activas,
        'departamentos_inactivas': departamentos_inactivas,
        'cargos_activas': cargos_activas,
        'cargos_inactivas': cargos_inactivas,
        'latest_employee': latest_employee_label,
        'latest_activity': latest_activity,
        'top_departamentos': [
            {'nombre': nombre, 'total': total_empleados}
            for nombre, total_empleados in top_departamentos
        ],
        'payroll_breakdown': [
            {'nombre': nombre, 'total': total}
            for nombre, total in payroll_breakdown
        ],
        'active_ratio': round((activos / total * 100), 1) if total else 0,
    }
