import uuid
from pathlib import Path
from typing import List, Optional
from datetime import timedelta
from sqlalchemy.orm import Session
from fastapi import UploadFile
from enum import Enum
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models.employee import Empleado, EstadoEnum
from app.models.organization import Departamento, Cargo, Gerencia
from app.core.config import ALLOWED_IMAGE_EXT, UPLOADS_DIR
from app.services.audit_service import add_audit
from app.services.notification_service import publish_employee_registered, publish_employee_status_changed
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditRecord
from app.schemas.employee import EmpleadoOut
from app.core.datetime_utils import utc_now

MAX_IMAGE_SIZE = 5 * 1024 * 1024
IMAGE_SIGNATURES = {
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.gif': (b'GIF87a', b'GIF89a'),
}


def _audit_contact(value: str | None) -> str | None:
    if not value:
        return None
    return f'***{value[-4:]}' if len(value) > 4 else '***'


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
        telefono=(str(data.telefono).strip() or None) if data.telefono else None,
        email=(str(data.email).strip().lower() or None) if data.email else None,
        contacto_emergencia_parentesco=(str(data.contacto_emergencia_parentesco).strip() or None) if data.contacto_emergencia_parentesco else None,
        contacto_emergencia_telefono=(str(data.contacto_emergencia_telefono).strip() or None) if data.contacto_emergencia_telefono else None,
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
        'telefono': _audit_contact(emp.telefono), 'email': _audit_contact(emp.email),
    })
    publish_employee_registered(db, emp, usuario_id)
    db.commit()
    db.refresh(emp)
    return emp


def update_employee(db: Session, emp: Empleado, updates, foto: Optional[UploadFile] = None, eliminar_foto: bool = False, usuario_id: int | None = None) -> Empleado:
    antes = {
        'nombre_apellido': emp.nombre_apellido, 'departamento_id': emp.departamento_id,
        'cargo_id': emp.cargo_id, 'estado': emp.estado, 'tipo_nomina': emp.tipo_nomina,
        'foto_url': bool(emp.foto_url), 'telefono': _audit_contact(emp.telefono), 'email': _audit_contact(emp.email),
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

    previous_status = emp.estado.value if isinstance(emp.estado, EstadoEnum) else str(emp.estado)
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
            normalized_value = value.strip().lower() if field == 'email' and isinstance(value, str) else (value.strip() if isinstance(value, str) else value)
            if field == 'nombre_apellido' and not normalized_value:
                raise ValueError('El nombre del empleado no puede estar vacío.')
            setattr(emp, field, normalized_value)
    db.add(emp)
    add_audit(db, usuario_id, 'actualizacion', 'empleados', emp.id, antes, {
        'nombre_apellido': emp.nombre_apellido, 'departamento_id': emp.departamento_id,
        'cargo_id': emp.cargo_id, 'estado': emp.estado, 'tipo_nomina': emp.tipo_nomina,
        'foto_url': bool(emp.foto_url), 'telefono': _audit_contact(emp.telefono), 'email': _audit_contact(emp.email),
    })
    current_status = emp.estado.value if isinstance(emp.estado, EstadoEnum) else str(emp.estado)
    if current_status != previous_status:
        publish_employee_status_changed(db, emp.nombre_apellido, previous_status, current_status, usuario_id)
    else:
        publish_employee_updated(db, emp.nombre_apellido, usuario_id)
    db.commit()
    db.refresh(emp)
    return emp


def get_employee_by_id(db: Session, emp_id: int) -> Optional[Empleado]:
    return db.query(Empleado).options(
        joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia),
        joinedload(Empleado.cargo_rel)
    ).filter(Empleado.id == emp_id).first()


def get_employee_profile(db: Session, emp_id: int, days: int = 30, page: int = 1, page_size: int = 25):
    employee = get_employee_by_id(db, emp_id)
    if not employee:
        return None
    days = max(1, min(days, 365))
    page_size = max(1, min(page_size, 100))
    start = utc_now() - timedelta(days=days)
    attendance_query = db.query(AttendanceRecord).filter(
        AttendanceRecord.empleado_id == emp_id,
        AttendanceRecord.fecha_hora >= start,
    )
    total_attendance = attendance_query.count()
    attendance = attendance_query.order_by(
        AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    audit_query = db.query(AuditRecord).filter(
        AuditRecord.entidad == 'empleados',
        AuditRecord.entidad_id == emp_id,
        AuditRecord.fecha >= start,
    )
    audits = audit_query.order_by(AuditRecord.fecha.desc(), AuditRecord.id.desc()).limit(100).all()
    return {
        'employee': EmpleadoOut.model_validate(employee).model_dump(mode='json'),
        'filters': {'days': days, 'page': page, 'page_size': page_size},
        'attendance': {
            'items': [_attendance_profile_item(record) for record in attendance],
            'total': total_attendance,
        },
        'audit': [_audit_profile_item(record) for record in audits],
    }


def _attendance_profile_item(record: AttendanceRecord) -> dict:
    return {'id': record.id, 'tipo': record.tipo, 'fecha_hora': record.fecha_hora.isoformat(), 'origen': record.origen}


def _audit_profile_item(record: AuditRecord) -> dict:
    return {'id': record.id, 'accion': record.accion, 'fecha': record.fecha.isoformat(), 'datos_antes': record.datos_antes, 'datos_despues': record.datos_despues}


def build_employee_query(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, gerencia_id: Optional[int] = None, departamento_id: Optional[int] = None, tipo_nomina: Optional[str] = None):
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
    if gerencia_id is not None:
        query = query.join(Empleado.departamento_rel).filter(Departamento.gerencia_id == gerencia_id)
    if departamento_id is not None:
        query = query.filter(Empleado.departamento_id == departamento_id)
    if tipo_nomina:
        query = query.filter(Empleado.tipo_nomina == tipo_nomina)
    return query


def search_employees(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, gerencia_id: Optional[int] = None, departamento_id: Optional[int] = None, tipo_nomina: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Empleado]:
    query = build_employee_query(db, q, estado, gerencia, departamento, gerencia_id, departamento_id, tipo_nomina)
    return query.order_by(Empleado.fecha_creacion.desc()).offset(offset).limit(limit).all()


def count_employees(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, gerencia_id: Optional[int] = None, departamento_id: Optional[int] = None, tipo_nomina: Optional[str] = None) -> int:
    return build_employee_query(db, q, estado, gerencia, departamento, gerencia_id, departamento_id, tipo_nomina).count()


def soft_delete_employee(db: Session, emp: Empleado, usuario_id: int | None = None) -> Empleado:
    antes = {'estado': emp.estado}
    previous_status = emp.estado.value if isinstance(emp.estado, EstadoEnum) else str(emp.estado)
    emp.estado = EstadoEnum.Retirado
    db.add(emp)
    add_audit(db, usuario_id, 'baja', 'empleados', emp.id, antes, {'estado': emp.estado})
    if previous_status != EstadoEnum.Retirado.value:
        publish_employee_status_changed(db, emp.nombre_apellido, previous_status, EstadoEnum.Retirado.value, usuario_id)
    db.commit()
    db.refresh(emp)
    return emp


def normalize_employee_status_counts(rows):
    normalized = {state: 0 for state in ('Activo', 'Vacaciones', 'Retirado', 'Suspendido')}
    for state, count in rows or []:
        if state is None:
            continue
        label = state.value if isinstance(state, EstadoEnum) else str(state).strip()
        if label not in normalized:
            continue
        try:
            normalized[label] = int(count or 0)
        except (TypeError, ValueError):
            normalized[label] = 0
    return normalized


def get_employee_metrics(db: Session):
    status_rows = db.query(Empleado.estado, func.count(Empleado.id)).group_by(Empleado.estado).all()
    estado_counts = normalize_employee_status_counts(status_rows)
    total = sum(estado_counts.values())

    activos = estado_counts['Activo']
    inactivos = sum(value for key, value in estado_counts.items() if key != 'Activo')
    latest_employee = db.query(Empleado).order_by(Empleado.fecha_creacion.desc()).first()
    latest_employee_label = latest_employee.fecha_creacion.strftime('%d/%m/%Y') if latest_employee and latest_employee.fecha_creacion else 'Sin registros'
    latest_activity = {
        'nombre': latest_employee.nombre_apellido,
        'fecha': latest_employee_label,
    } if latest_employee else None

    departamento_counts = db.query(Departamento.estado, func.count(Departamento.id)).group_by(Departamento.estado).all()
    departamento_counts = {
        state.value if isinstance(state, Enum) else str(state or 'Activo'): count
        for state, count in departamento_counts
    }
    total_departamentos = sum(departamento_counts.values())
    departamentos_activas = departamento_counts.get('Activo', 0)
    departamentos_inactivas = total_departamentos - departamentos_activas

    gerencia_counts = db.query(Gerencia.estado, func.count(Gerencia.id)).group_by(Gerencia.estado).all()
    gerencia_counts = {
        state.value if isinstance(state, Enum) else str(state or 'Activo'): count
        for state, count in gerencia_counts
    }
    total_gerencias = sum(gerencia_counts.values())
    gerencias_activas = gerencia_counts.get('Activo', 0)
    gerencias_inactivas = total_gerencias - gerencias_activas

    cargo_counts = db.query(Cargo.estado, func.count(Cargo.id)).group_by(Cargo.estado).all()
    cargo_counts = {
        state.value if isinstance(state, Enum) else str(state or 'Activo'): count
        for state, count in cargo_counts
    }
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

    payroll_breakdown = [
        {'nombre': str(nombre or 'Sin nómina'), 'total': int(total or 0)}
        for nombre, total in payroll_breakdown
    ]

    return {
        'total': int(total or 0),
        'active': int(activos or 0),
        'vacation': int(estado_counts['Vacaciones'] or 0),
        'retired_suspended': int((estado_counts['Retirado'] or 0) + (estado_counts['Suspendido'] or 0)),
        'inactive': int(inactivos or 0),
        'by_estado': estado_counts,
        'depts': int(unique_departments or 0),
        'gerencias': int(total_gerencias or 0),
        'cargos': int(total_cargos or 0),
        'gerencias_activas': int(gerencias_activas or 0),
        'gerencias_inactivas': int(gerencias_inactivas or 0),
        'departamentos_activas': int(departamentos_activas or 0),
        'departamentos_inactivas': int(departamentos_inactivas or 0),
        'cargos_activas': int(cargos_activas or 0),
        'cargos_inactivas': int(cargos_inactivas or 0),
        'latest_employee': latest_employee_label,
        'latest_activity': latest_activity,
        'top_departamentos': [
            {'nombre': str(nombre or 'Sin departamento'), 'total': int(total_empleados or 0)}
            for nombre, total_empleados in top_departamentos
        ],
        'payroll_breakdown': payroll_breakdown,
        'active_ratio': round((activos / total * 100), 1) if total else 0,
    }
