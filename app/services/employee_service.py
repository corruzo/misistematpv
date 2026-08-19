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
        departamento = db.query(Departamento).filter(Departamento.nombre.ilike(departamento_name.strip())).first()
        if departamento:
            resolved_departamento_id = departamento.id

    if resolved_cargo_id is None and cargo_name:
        cargo = db.query(Cargo).filter(Cargo.nombre.ilike(cargo_name.strip())).first()
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
    if not file:
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


def create_employee(db: Session, data, foto: Optional[UploadFile] = None) -> Empleado:
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
    db.commit()
    db.refresh(emp)
    return emp


def update_employee(db: Session, emp: Empleado, updates, foto: Optional[UploadFile] = None) -> Empleado:
    if foto:
        foto_url = save_image(foto)
        emp.foto_url = foto_url

    payload = updates.dict(exclude_unset=True)
    departamento_id = payload.get('departamento_id')
    cargo_id = payload.get('cargo_id')
    if departamento_id is None and payload.get('departamento'):
        departamento = db.query(Departamento).filter(Departamento.nombre.ilike(str(payload['departamento']).strip())).first()
        departamento_id = departamento.id if departamento else None
    if cargo_id is None and payload.get('cargo'):
        cargo = db.query(Cargo).filter(Cargo.nombre.ilike(str(payload['cargo']).strip())).first()
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
        if value is not None:
            normalized_value = value.strip() if isinstance(value, str) else value
            if field == 'nombre_apellido' and not normalized_value:
                raise ValueError('El nombre del empleado no puede estar vacío.')
            setattr(emp, field, normalized_value)
    db.add(emp)
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
            (Empleado.nombre_apellido.ilike(like)) | (Empleado.cedula.ilike(like))
        )
    if estado:
        query = query.filter(Empleado.estado == estado)
    if gerencia:
        query = query.join(Empleado.departamento_rel).join(Departamento.gerencia).filter(Gerencia.nombre.ilike(f"%{gerencia}%"))
    if departamento:
        query = query.join(Empleado.departamento_rel).filter(Departamento.nombre.ilike(f"%{departamento}%"))
    if tipo_nomina:
        query = query.filter(Empleado.tipo_nomina == tipo_nomina)
    return query


def search_employees(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, tipo_nomina: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Empleado]:
    query = build_employee_query(db, q, estado, gerencia, departamento, tipo_nomina)
    return query.order_by(Empleado.fecha_creacion.desc()).offset(offset).limit(limit).all()


def count_employees(db: Session, q: Optional[str] = None, estado: Optional[str] = None, gerencia: Optional[str] = None, departamento: Optional[str] = None, tipo_nomina: Optional[str] = None) -> int:
    return build_employee_query(db, q, estado, gerencia, departamento, tipo_nomina).count()


def soft_delete_employee(db: Session, emp: Empleado) -> Empleado:
    emp.estado = EstadoEnum.Retirado
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def get_employee_metrics(db: Session):
    total = db.query(Empleado).count()

    estado_counts = {
        'Activo': db.query(Empleado).filter(Empleado.estado == EstadoEnum.Activo).count(),
        'Vacaciones': db.query(Empleado).filter(Empleado.estado == EstadoEnum.Vacaciones).count(),
        'Retirado': db.query(Empleado).filter(Empleado.estado == EstadoEnum.Retirado).count(),
        'Suspendido': db.query(Empleado).filter(Empleado.estado == EstadoEnum.Suspendido).count(),
    }

    activos = estado_counts['Activo']
    inactivos = sum(value for key, value in estado_counts.items() if key != 'Activo')
    today = datetime.utcnow()
    last_7_days = db.query(Empleado).filter(Empleado.fecha_creacion >= today - timedelta(days=7)).count()
    last_30_days = db.query(Empleado).filter(Empleado.fecha_creacion >= today - timedelta(days=30)).count()

    latest_employee = db.query(Empleado).order_by(Empleado.fecha_creacion.desc()).first()
    latest_employee_label = latest_employee.fecha_creacion.strftime('%d/%m/%Y') if latest_employee and latest_employee.fecha_creacion else 'Sin registros'
    latest_activity = {
        'nombre': latest_employee.nombre_apellido,
        'fecha': latest_employee_label,
    } if latest_employee else None

    total_departamentos = db.query(Departamento).count()
    departamentos_activas = db.query(Departamento).filter(Departamento.estado == 'Activo').count()
    departamentos_inactivas = total_departamentos - departamentos_activas

    total_gerencias = db.query(Gerencia).count()
    gerencias_activas = db.query(Gerencia).filter(Gerencia.estado == 'Activo').count()
    gerencias_inactivas = total_gerencias - gerencias_activas

    total_cargos = db.query(Cargo).count()
    cargos_activas = db.query(Cargo).filter(Cargo.estado == 'Activo').count()
    cargos_inactivas = total_cargos - cargos_activas

    unique_departments = db.query(Empleado.departamento_id).filter(Empleado.departamento_id.isnot(None)).distinct().count()
    tipos_nomina = db.query(Empleado.tipo_nomina).filter(Empleado.tipo_nomina.isnot(None)).distinct().count()

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
        'types': tipos_nomina,
        'gerencias': total_gerencias,
        'cargos': total_cargos,
        'gerencias_activas': gerencias_activas,
        'gerencias_inactivas': gerencias_inactivas,
        'departamentos_activas': departamentos_activas,
        'departamentos_inactivas': departamentos_inactivas,
        'cargos_activas': cargos_activas,
        'cargos_inactivas': cargos_inactivas,
        'last_7_days': last_7_days,
        'last_30_days': last_30_days,
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
