from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.models.attendance import AttendanceRecord
from app.models.employee import Empleado, EstadoEnum
from app.models.organization import Departamento
from app.schemas.attendance import AttendanceHistoryPage, AttendanceOrigin, AttendanceRecordOut, AttendanceSummary, AttendanceType
from app.services.audit_service import add_audit
from app.core.datetime_utils import LOCAL_TIMEZONE, as_utc, local_day_start_as_utc, to_local, utc_now


DEBOUNCE_SECONDS = 60


class AttendanceError(ValueError):
    pass


def _register_employee(
    db: Session,
    employee: Empleado,
    origen: AttendanceOrigin,
    usuario_id: int | None = None,
    marked_at: datetime | None = None,
) -> AttendanceRecordOut:
    employee_query = db.query(Empleado).filter(Empleado.id == employee.id)
    with_hint = getattr(employee_query, 'with_hint', None)
    if with_hint:
        locked_employee = with_hint(Empleado, 'WITH (UPDLOCK, ROWLOCK)', 'mssql').populate_existing().first()
        if locked_employee:
            employee = locked_employee
    if employee.estado != EstadoEnum.Activo:
        raise AttendanceError('El empleado no está activo.')

    now = as_utc(marked_at or utc_now())
    if now > utc_now():
        raise AttendanceError('La hora del marcaje no puede ser futura.')
    last_record = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.empleado_id == employee.id, AttendanceRecord.fecha_hora <= now)
        .order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc())
        .first()
    )
    if last_record:
        last_time = last_record.fecha_hora
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        if now - last_time < timedelta(seconds=DEBOUNCE_SECONDS):
            raise AttendanceError('Lectura duplicada. Espera unos segundos antes de volver a marcar.')

    next_type = AttendanceType.SALIDA if last_record and last_record.tipo == AttendanceType.ENTRADA.value else AttendanceType.ENTRADA
    record = AttendanceRecord(empleado_id=employee.id, tipo=next_type.value, fecha_hora=now, origen=origen.value)
    db.add(record)
    try:
        db.flush()
        add_audit(db, usuario_id, 'marcaje', 'marcajes_asistencia', record.id, despues={
            'empleado_id': record.empleado_id, 'tipo': record.tipo, 'origen': record.origen,
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AttendanceError('No se pudo registrar el marcaje.')
    db.refresh(record)
    return _to_output(record, employee)


def _to_output(record: AttendanceRecord, employee: Empleado) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=record.id, empleado_id=employee.id, empleado_nombre=employee.nombre_apellido,
        codigo_tarjeta=employee.codigo_tarjeta or '', tipo=record.tipo, fecha_hora=to_local(record.fecha_hora),
        origen=record.origen, cedula=employee.cedula, departamento=employee.departamento,
        cargo=employee.cargo, gerencia=employee.gerencia, foto_url=employee.foto_url,
    )


def register_scan(db: Session, codigo_tarjeta: str, origen: AttendanceOrigin) -> AttendanceRecordOut:
    card_code = codigo_tarjeta.strip()
    employee = db.query(Empleado).filter(Empleado.codigo_tarjeta == card_code).first()
    if not employee:
        raise AttendanceError('Tarjeta no asociada a un empleado.')
    return _register_employee(db, employee, origen)


def register_manual(
    db: Session,
    empleado_id: int,
    usuario_id: int | None = None,
    marked_at: datetime | None = None,
) -> AttendanceRecordOut:
    employee = db.query(Empleado).filter(Empleado.id == empleado_id).first()
    if not employee:
        raise AttendanceError('Empleado no encontrado.')
    if marked_at is not None and marked_at.tzinfo is None:
        marked_at = marked_at.replace(tzinfo=LOCAL_TIMEZONE)
    return _register_employee(db, employee, AttendanceOrigin.MANUAL_ADMIN, usuario_id, marked_at)


def register_manual_batch(db: Session, marks, usuario_id: int | None = None):
    results = []
    errors = []
    for mark in marks:
        try:
            results.append(register_manual(db, mark.empleado_id, usuario_id, mark.fecha_hora))
        except AttendanceError as exc:
            errors.append({'empleado_id': mark.empleado_id, 'detail': str(exc)})
        except SQLAlchemyError:
            db.rollback()
            errors.append({'empleado_id': mark.empleado_id, 'detail': 'No se pudo consultar la base de datos.'})
    return {'items': results, 'errors': errors}


def preview_manual_batch(db: Session, marks):
    preview = {}
    for mark in marks:
        marked_at = mark.fecha_hora
        if marked_at is not None and marked_at.tzinfo is None:
            marked_at = marked_at.replace(tzinfo=LOCAL_TIMEZONE)
        marked_at = as_utc(marked_at or utc_now())
        last_record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.empleado_id == mark.empleado_id, AttendanceRecord.fecha_hora <= marked_at)
            .order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc())
            .first()
        )
        preview[str(mark.empleado_id)] = (
            AttendanceType.SALIDA.value if last_record and last_record.tipo == AttendanceType.ENTRADA.value
            else AttendanceType.ENTRADA.value
        )
    return preview


def get_attendance_since(
    db: Session,
    after_id: int | None = None,
    origen: AttendanceOrigin | None = None,
) -> list[AttendanceRecordOut]:
    query = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.departamento_rel),
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.cargo_rel),
    ).order_by(AttendanceRecord.id.asc())
    if after_id is not None:
        query = query.filter(AttendanceRecord.id > after_id)
    if origen is not None:
        query = query.filter(AttendanceRecord.origen == origen.value)
    return [_to_output(record, record.empleado) for record in query.limit(100).all()]


def list_attendance(db: Session, page: int = 1, page_size: int = 25, date_from=None, date_to=None, empleado_q=None, departamento_ids=None, gerencia_ids=None):
    query = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.departamento_rel),
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.cargo_rel),
    )
    if date_from:
        query = query.filter(AttendanceRecord.fecha_hora >= date_from)
    if date_to:
        query = query.filter(AttendanceRecord.fecha_hora < date_to + timedelta(days=1))
    if empleado_q:
        term = f'%{empleado_q.strip()}%'
        query = query.join(AttendanceRecord.empleado).filter(or_(Empleado.nombre_apellido.like(term), Empleado.cedula.like(term)))
    if departamento_ids:
        query = query.join(AttendanceRecord.empleado).filter(Empleado.departamento_id.in_(departamento_ids))
    if gerencia_ids:
        query = query.join(AttendanceRecord.empleado).join(Empleado.departamento_rel).filter(Departamento.gerencia_id.in_(gerencia_ids))
    total = query.count()
    records = query.order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AttendanceHistoryPage(items=[_to_output(record, record.empleado) for record in records], total=total, page=page, page_size=page_size)


def attendance_summary(db: Session):
    start = local_day_start_as_utc()
    records_today = db.query(AttendanceRecord).filter(AttendanceRecord.fecha_hora >= start).order_by(
        AttendanceRecord.fecha_hora.asc(), AttendanceRecord.id.asc()
    ).all()
    last_by_employee = {}
    for record in records_today:
        last_by_employee[record.empleado_id] = record
    entradas = sum(1 for record in records_today if record.tipo == AttendanceType.ENTRADA.value)
    salidas = sum(1 for record in records_today if record.tipo == AttendanceType.SALIDA.value)
    present_records = [record for record in last_by_employee.values() if record.tipo == AttendanceType.ENTRADA.value]
    present_employee_ids = [record.empleado_id for record in present_records]
    employees_by_id = {
        employee.id: employee
        for employee in db.query(Empleado).options(
            joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia)
        ).filter(Empleado.id.in_(present_employee_ids)).all()
    } if present_employee_ids else {}
    area_counts = {}
    for record in present_records:
        employee = employees_by_id.get(record.empleado_id)
        area = employee.departamento_rel.nombre if employee and employee.departamento_rel else 'Sin departamento'
        gerencia = employee.departamento_rel.gerencia.nombre if employee and employee.departamento_rel and employee.departamento_rel.gerencia else 'Sin gerencia'
        key = (gerencia, area)
        area_counts[key] = area_counts.get(key, 0) + 1
    return AttendanceSummary(
        presentes=len(present_records), entradas_hoy=entradas, salidas_hoy=salidas,
        marcajes_hoy=len(records_today),
        presentes_por_area=[
            {'gerencia': gerencia, 'departamento': departamento, 'total': total}
            for (gerencia, departamento), total in sorted(area_counts.items())
        ],
    )


def list_present_employees(db: Session):
    start = local_day_start_as_utc()
    records_today = db.query(AttendanceRecord).filter(AttendanceRecord.fecha_hora >= start).order_by(
        AttendanceRecord.fecha_hora.asc(), AttendanceRecord.id.asc()
    ).all()
    last_by_employee = {}
    for record in records_today:
        last_by_employee[record.empleado_id] = record
    present_ids = [employee_id for employee_id, record in last_by_employee.items() if record.tipo == AttendanceType.ENTRADA.value]
    if not present_ids:
        return []

    employees = db.query(Empleado).options(
        joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia),
        joinedload(Empleado.cargo_rel),
    ).filter(Empleado.id.in_(present_ids)).order_by(Empleado.nombre_apellido.asc()).all()
    return [
        {
            'id': employee.id,
            'nombre_apellido': employee.nombre_apellido,
            'cedula': employee.cedula,
            'gerencia': employee.gerencia or 'Sin gerencia',
            'departamento': employee.departamento or 'Sin departamento',
            'cargo': employee.cargo or 'Sin cargo',
            'entrada': to_local(last_by_employee[employee.id].fecha_hora),
            'foto_url': employee.foto_url,
        }
        for employee in employees
    ]