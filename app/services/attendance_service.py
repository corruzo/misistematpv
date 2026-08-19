from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.attendance import AttendanceRecord
from app.models.employee import Empleado, EstadoEnum
from app.schemas.attendance import AttendanceHistoryPage, AttendanceOrigin, AttendanceRecordOut, AttendanceSummary, AttendanceType


DEBOUNCE_SECONDS = 60


class AttendanceError(ValueError):
    pass


def _register_employee(db: Session, employee: Empleado, origen: AttendanceOrigin) -> AttendanceRecordOut:
    if employee.estado != EstadoEnum.Activo:
        raise AttendanceError('El empleado no está activo.')

    now = datetime.now(timezone.utc)
    last_record = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.empleado_id == employee.id)
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AttendanceError('No se pudo registrar el marcaje.')
    db.refresh(record)
    return _to_output(record, employee)


def _to_output(record: AttendanceRecord, employee: Empleado) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=record.id, empleado_id=employee.id, empleado_nombre=employee.nombre_apellido,
        codigo_tarjeta=employee.codigo_tarjeta or '', tipo=record.tipo, fecha_hora=record.fecha_hora,
        origen=record.origen, cedula=employee.cedula, departamento=employee.departamento,
        cargo=employee.cargo, foto_url=employee.foto_url,
    )


def register_scan(db: Session, codigo_tarjeta: str, origen: AttendanceOrigin) -> AttendanceRecordOut:
    card_code = codigo_tarjeta.strip()
    employee = db.query(Empleado).filter(Empleado.codigo_tarjeta == card_code).first()
    if not employee:
        raise AttendanceError('Tarjeta no asociada a un empleado.')
    return _register_employee(db, employee, origen)


def register_manual(db: Session, empleado_id: int) -> AttendanceRecordOut:
    employee = db.query(Empleado).filter(Empleado.id == empleado_id).first()
    if not employee:
        raise AttendanceError('Empleado no encontrado.')
    return _register_employee(db, employee, AttendanceOrigin.MANUAL_ADMIN)


def list_attendance(db: Session, page: int = 1, page_size: int = 25, date_from=None, date_to=None, empleado_id=None, departamento_id=None):
    query = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.departamento_rel),
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.cargo_rel),
    )
    if date_from:
        query = query.filter(AttendanceRecord.fecha_hora >= date_from)
    if date_to:
        query = query.filter(AttendanceRecord.fecha_hora < date_to + timedelta(days=1))
    if empleado_id:
        query = query.filter(AttendanceRecord.empleado_id == empleado_id)
    if departamento_id:
        query = query.join(AttendanceRecord.empleado).filter(Empleado.departamento_id == departamento_id)
    total = query.count()
    records = query.order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AttendanceHistoryPage(items=[_to_output(record, record.empleado) for record in records], total=total, page=page, page_size=page_size)


def attendance_summary(db: Session):
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    total_active = db.query(Empleado).filter(Empleado.estado == EstadoEnum.Activo).count()
    records_today = db.query(AttendanceRecord).filter(AttendanceRecord.fecha_hora >= start).all()
    last_by_employee = {}
    for record in records_today:
        last_by_employee[record.empleado_id] = record
    return AttendanceSummary(
        presentes=sum(1 for record in last_by_employee.values() if record.tipo == AttendanceType.ENTRADA.value),
        marcajes_hoy=len(records_today),
        empleados_sin_registro=max(total_active - len(last_by_employee), 0),
    )