from datetime import datetime, timedelta, timezone, date
import hashlib
import uuid

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_

from app.models.attendance import AttendanceRecord
from app.models.employee import Empleado, EstadoEnum
from app.models.manual_frequent_employee import ManualFrequentEmployee
from app.models.alert_dismissal import AlertDismissal
from app.models.organization import Departamento
from app.schemas.attendance import AttendanceHistoryPage, AttendanceOrigin, AttendanceRecordOut, AttendanceSummary, AttendanceType
from app.services.audit_service import add_audit
from app.services.notification_service import publish_attendance_corrected, publish_exception_mark
from app.core.datetime_utils import LOCAL_TIMEZONE, as_utc, local_day_start_as_utc, to_local, utc_now
from app.core.config import ATTENDANCE_HISTORY_DEFAULT_DAYS, PRESENT_EMPLOYEES_LIMIT, PROLONGED_STAY_HOURS


DEBOUNCE_SECONDS = 15


class AttendanceError(ValueError):
    pass


class EmployeeAccessDeniedError(AttendanceError):
    def __init__(self, employee: Empleado, marked_at: datetime | None = None):
        self.employee_id = employee.id
        self.employee_name = employee.nombre_apellido
        self.employee_status = employee.estado.value if isinstance(employee.estado, EstadoEnum) else str(employee.estado)
        self.marked_at = marked_at
        super().__init__('El empleado no está activo.')


def attendance_records_are_too_close(previous_time: datetime, current_time: datetime) -> bool:
    return timedelta(0) <= current_time - previous_time < timedelta(seconds=DEBOUNCE_SECONDS)


def format_alert_time(value: datetime | None) -> str:
    local_value = to_local(value)
    return local_value.strftime('%d/%m/%Y a las %H:%M') if local_value else 'fecha no disponible'


def build_attendance_alerts(today_records, overnight_records, employee_label, present_records, now):
    records_by_employee = {}
    for record in overnight_records:
        records_by_employee[record.empleado_id] = [record]
    for record in today_records:
        records_by_employee.setdefault(record.empleado_id, []).append(record)

    alerts = []
    today_employee_ids = {record.empleado_id for record in today_records}
    for employee_id, records in records_by_employee.items():
        records.sort(key=lambda record: (record.fecha_hora, record.id))
        previous = records[0]
        for record in records[1:]:
            if record.fecha_hora < today_records[0].fecha_hora if today_records else False:
                previous = record
                continue
            interval = (record.fecha_hora - previous.fecha_hora).total_seconds()
            same_type = previous.tipo == record.tipo
            if same_type:
                alerts.append({
                    'kind': 'sequence',
                    'message': f'El empleado {employee_label(employee_id)} tiene dos marcajes de {record.tipo.lower()} consecutivos. Entre {format_alert_time(previous.fecha_hora)} y {format_alert_time(record.fecha_hora)}.',
                })
            elif 0 <= interval < DEBOUNCE_SECONDS:
                alerts.append({
                    'kind': 'sequence',
                    'message': f'El empleado {employee_label(employee_id)} tiene dos marcajes en {interval:.1f} segundos. Entre {format_alert_time(previous.fecha_hora)} y {format_alert_time(record.fecha_hora)}.',
                })
            if record.tipo == AttendanceType.SALIDA.value and not any(
                item.tipo == AttendanceType.ENTRADA.value for item in records[:records.index(record)]
            ):
                alerts.append({
                    'kind': 'sequence',
                    'message': f'El empleado {employee_label(employee_id)} tiene una salida sin entrada previa ({format_alert_time(record.fecha_hora)}).',
                })
            previous = record

        if employee_id not in today_employee_ids and records[-1].tipo == AttendanceType.ENTRADA.value:
            alerts.append({
                'kind': 'sequence',
                'message': f'El empleado {employee_label(employee_id)} podría permanecer dentro desde el día anterior. Último marcaje: {format_alert_time(records[-1].fecha_hora)}.',
            })

    for record in present_records:
        entry_time = record['entrada']
        if entry_time and now - as_utc(entry_time) >= timedelta(hours=PROLONGED_STAY_HOURS):
            alerts.append({
                'kind': 'sequence',
                'message': f'El empleado {record["nombre_apellido"]} supera {PROLONGED_STAY_HOURS} horas dentro. Entrada: {format_alert_time(entry_time)}.',
            })
    return alerts


def _register_employee(
    db: Session,
    employee: Empleado,
    origen: AttendanceOrigin,
    usuario_id: int | None = None,
    marked_at: datetime | None = None,
    attendance_type: AttendanceType | None = None,
    operation_id: str | None = None,
) -> AttendanceRecordOut:
    employee_query = db.query(Empleado).filter(Empleado.id == employee.id)
    with_hint = getattr(employee_query, 'with_hint', None)
    if with_hint:
        locked_employee = with_hint(Empleado, 'WITH (UPDLOCK, ROWLOCK)', 'mssql').populate_existing().first()
        if locked_employee:
            employee = locked_employee
    if operation_id:
        existing = db.query(AttendanceRecord).filter(AttendanceRecord.operacion_id == operation_id).first()
        if existing:
            if existing.empleado_id != employee.id:
                raise AttendanceError('La operación ya fue utilizada para otro empleado.')
            return _to_output(existing, employee)

    now = as_utc(marked_at or utc_now())
    if now > utc_now():
        raise AttendanceError('La hora del marcaje no puede ser futura.')
    last_record, next_record = _attendance_neighbors(db, employee.id, now)
    if last_record:
        last_time = last_record.fecha_hora
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        if now - last_time < timedelta(seconds=DEBOUNCE_SECONDS):
            raise AttendanceError('Lectura duplicada. Espera unos segundos antes de volver a marcar.')

    next_type = attendance_type or (AttendanceType.SALIDA if last_record and last_record.tipo == AttendanceType.ENTRADA.value else AttendanceType.ENTRADA)
    if employee.estado in (EstadoEnum.Retirado, EstadoEnum.Suspendido):
        has_open_entry = last_record and last_record.tipo == AttendanceType.ENTRADA.value
        if next_type != AttendanceType.SALIDA or not has_open_entry:
            raise EmployeeAccessDeniedError(employee, now)
    _validate_attendance_sequence(next_type, last_record, next_record)
    record = AttendanceRecord(empleado_id=employee.id, tipo=next_type.value, fecha_hora=now, origen=origen.value, operacion_id=operation_id)
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


def _attendance_neighbors(db: Session, employee_id: int, marked_at: datetime, exclude_id: int | None = None):
    previous_query = db.query(AttendanceRecord).filter(
        AttendanceRecord.empleado_id == employee_id,
        AttendanceRecord.fecha_hora < marked_at,
    ).order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc())
    next_query = db.query(AttendanceRecord).filter(
        AttendanceRecord.empleado_id == employee_id,
        AttendanceRecord.fecha_hora > marked_at,
    ).order_by(AttendanceRecord.fecha_hora.asc(), AttendanceRecord.id.asc())
    if exclude_id is not None:
        previous_query = previous_query.filter(AttendanceRecord.id != exclude_id)
        next_query = next_query.filter(AttendanceRecord.id != exclude_id)
    return previous_query.first(), next_query.first()


def _validate_attendance_sequence(attendance_type: AttendanceType, previous_record, next_record) -> None:
    if previous_record and previous_record.tipo == attendance_type.value:
        raise AttendanceError(
            f'El registro anterior ya es una {attendance_type.value.lower()}. '
            f'Debes registrar una {"salida" if attendance_type == AttendanceType.ENTRADA else "entrada"}.'
        )
    if next_record and next_record.tipo == attendance_type.value:
        raise AttendanceError(
            f'El registro posterior ya es una {attendance_type.value.lower()}. '
            f'No se puede insertar otra {attendance_type.value.lower()} en ese momento.'
        )


def _to_output(record: AttendanceRecord, employee: Empleado) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=record.id, empleado_id=employee.id, empleado_nombre=employee.nombre_apellido,
        codigo_tarjeta=employee.codigo_tarjeta or '', tipo=record.tipo, fecha_hora=to_local(record.fecha_hora),
        origen=record.origen, cedula=employee.cedula, departamento=employee.departamento,
        cargo=employee.cargo, gerencia=employee.gerencia, foto_url=employee.foto_url,
        estado=employee.estado.value if isinstance(employee.estado, EstadoEnum) else str(employee.estado),
    )


def register_scan(
    db: Session,
    codigo_tarjeta: str,
    origen: AttendanceOrigin,
    marked_at: datetime | None = None,
    operation_id: str | None = None,
) -> AttendanceRecordOut:
    card_code = codigo_tarjeta.strip()
    employee = db.query(Empleado).filter(Empleado.codigo_tarjeta == card_code).first()
    if not employee:
        raise AttendanceError('Tarjeta no asociada a un empleado.')
    return _register_employee(db, employee, origen, marked_at=marked_at, operation_id=operation_id)


def register_manual(
    db: Session,
    empleado_id: int,
    usuario_id: int | None = None,
    marked_at: datetime | None = None,
    attendance_type: AttendanceType | None = None,
    operation_id: str | None = None,
) -> AttendanceRecordOut:
    employee = db.query(Empleado).filter(Empleado.id == empleado_id).first()
    if not employee:
        raise AttendanceError('Empleado no encontrado.')
    if marked_at is not None and marked_at.tzinfo is None:
        marked_at = marked_at.replace(tzinfo=LOCAL_TIMEZONE)
    return _register_employee(db, employee, AttendanceOrigin.MANUAL_ADMIN, usuario_id, marked_at, attendance_type, operation_id)


def register_manual_batch(db: Session, marks, usuario_id: int | None = None):
    results = []
    errors = []
    for mark in marks:
        try:
            operation_id = mark.operacion_id or str(uuid.uuid4())
            result = register_manual(db, mark.empleado_id, usuario_id, mark.fecha_hora, mark.tipo, operation_id)
            results.append(result)
            if not result.codigo_tarjeta:
                publish_exception_mark(db, result.empleado_nombre, result.empleado_id)
                db.commit()
        except EmployeeAccessDeniedError as exc:
            errors.append({
                'empleado_id': exc.employee_id,
                'empleado_nombre': exc.employee_name,
                'estado': exc.employee_status,
                'code': 'employee_access_denied',
                'detail': str(exc),
            })
        except AttendanceError as exc:
            employee = db.query(Empleado).filter(Empleado.id == mark.empleado_id).first()
            errors.append({
                'empleado_id': mark.empleado_id,
                'empleado_nombre': employee.nombre_apellido if employee else 'Empleado no encontrado',
                'estado': employee.estado.value if employee and isinstance(employee.estado, EstadoEnum) else (str(employee.estado) if employee else None),
                'code': 'attendance_error',
                'detail': str(exc),
            })
        except SQLAlchemyError:
            db.rollback()
            errors.append({'empleado_id': mark.empleado_id, 'detail': 'No se pudo consultar la base de datos.'})
    return {'items': results, 'errors': errors}


def list_manual_frequent_employees(db: Session, usuario_id: int):
    entries = db.query(ManualFrequentEmployee).options(
        joinedload(ManualFrequentEmployee.empleado),
    ).filter(
        ManualFrequentEmployee.usuario_id == usuario_id,
    ).order_by(ManualFrequentEmployee.posicion.asc(), ManualFrequentEmployee.id.asc()).all()
    return [entry.empleado for entry in entries if entry.empleado]


def add_manual_frequent_employee(db: Session, usuario_id: int, empleado_id: int, posicion: int = 0):
    employee = db.query(Empleado).filter(Empleado.id == empleado_id).first()
    if not employee:
        raise AttendanceError('Empleado no encontrado.')
    if employee.estado in (EstadoEnum.Retirado, EstadoEnum.Suspendido):
        raise EmployeeAccessDeniedError(employee)
    existing = db.query(ManualFrequentEmployee).filter(
        ManualFrequentEmployee.usuario_id == usuario_id,
        ManualFrequentEmployee.empleado_id == empleado_id,
    ).first()
    if existing:
        existing.posicion = posicion
    else:
        db.add(ManualFrequentEmployee(usuario_id=usuario_id, empleado_id=empleado_id, posicion=posicion))
    db.commit()
    return employee


def remove_manual_frequent_employee(db: Session, usuario_id: int, empleado_id: int) -> bool:
    entry = db.query(ManualFrequentEmployee).filter(
        ManualFrequentEmployee.usuario_id == usuario_id,
        ManualFrequentEmployee.empleado_id == empleado_id,
    ).first()
    if not entry:
        return False
    db.delete(entry)
    db.commit()
    return True


def correct_attendance(
    db: Session,
    record_id: int,
    usuario_id: int,
    motivo: str,
    empleado_id: int | None = None,
    marked_at: datetime | None = None,
    attendance_type: AttendanceType | None = None,
) -> AttendanceRecordOut:
    reason = motivo.strip()
    if len(reason) < 5:
        raise AttendanceError('El motivo de la corrección es obligatorio.')
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise AttendanceError('Marcaje no encontrado.')
    employee = record.empleado
    if empleado_id is not None and empleado_id != record.empleado_id:
        employee = db.query(Empleado).filter(Empleado.id == empleado_id).first()
        if not employee:
            raise AttendanceError('Empleado no encontrado.')
    if marked_at is not None and marked_at.tzinfo is None:
        marked_at = marked_at.replace(tzinfo=LOCAL_TIMEZONE)
    normalized_time = as_utc(marked_at) if marked_at is not None else record.fecha_hora
    if normalized_time > utc_now():
        raise AttendanceError('La hora del marcaje no puede ser futura.')
    new_type = attendance_type.value if attendance_type is not None else record.tipo
    new_employee_id = employee.id
    old_values = {'empleado_id': record.empleado_id, 'tipo': record.tipo, 'fecha_hora': record.fecha_hora, 'origen': record.origen}
    old_type = record.tipo
    new_values = {'empleado_id': new_employee_id, 'tipo': new_type, 'fecha_hora': normalized_time, 'origen': record.origen, 'motivo': reason}
    if old_values == {key: value for key, value in new_values.items() if key != 'motivo'}:
        raise AttendanceError('Debes cambiar al menos un valor del marcaje.')
    previous_record, next_record = _attendance_neighbors(db, new_employee_id, normalized_time, record.id)
    _validate_attendance_sequence(AttendanceType(new_type), previous_record, next_record)
    record.empleado_id = new_employee_id
    record.tipo = new_type
    record.fecha_hora = normalized_time
    try:
        add_audit(db, usuario_id, 'correccion_marcaje', 'marcajes_asistencia', record.id, antes=old_values, despues=new_values)
        publish_attendance_corrected(db, employee.nombre_apellido, old_type, new_type, reason, usuario_id)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise AttendanceError('No se pudo guardar la corrección.')
    db.refresh(record)
    return _to_output(record, employee)


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


def list_attendance(db: Session, page: int = 1, page_size: int = 25, date_from=None, date_to=None, empleado_q=None, empleado_ids=None, departamento_ids=None, gerencia_ids=None, tipo=None, tipo_nomina=None):
    reference_date = date_to or datetime.now(LOCAL_TIMEZONE).date()
    if date_from is None:
        date_from = reference_date - timedelta(days=ATTENDANCE_HISTORY_DEFAULT_DAYS - 1)
    if date_to is None:
        date_to = reference_date
    query = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.departamento_rel),
        joinedload(AttendanceRecord.empleado).joinedload(Empleado.cargo_rel),
    )
    if date_from:
        query = query.filter(AttendanceRecord.fecha_hora >= date_from)
    if date_to:
        query = query.filter(AttendanceRecord.fecha_hora < date_to + timedelta(days=1))
    if tipo:
        query = query.filter(AttendanceRecord.tipo == tipo)
    if tipo_nomina:
        query = query.join(AttendanceRecord.empleado).filter(Empleado.tipo_nomina == tipo_nomina)
    if empleado_q:
        term = f'%{empleado_q.strip()}%'
        query = query.join(AttendanceRecord.empleado).filter(or_(Empleado.nombre_apellido.like(term), Empleado.cedula.like(term)))
    if empleado_ids:
        query = query.filter(AttendanceRecord.empleado_id.in_(empleado_ids))
    if departamento_ids:
        query = query.join(AttendanceRecord.empleado).filter(Empleado.departamento_id.in_(departamento_ids))
    if gerencia_ids:
        query = query.join(AttendanceRecord.empleado).join(Empleado.departamento_rel).filter(Departamento.gerencia_id.in_(gerencia_ids))
    total = query.count()
    records = query.order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AttendanceHistoryPage(items=[_to_output(record, record.empleado) for record in records], total=total, page=page, page_size=page_size)


def normalize_attendance_summary_counts(payload):
    normalized = {
        'presentes': 0,
        'entradas_hoy': 0,
        'salidas_hoy': 0,
        'marcajes_hoy': 0,
        'presentes_por_area': [],
    }
    if not isinstance(payload, dict):
        return normalized

    for key, default in [('presentes', 0), ('entradas_hoy', 0), ('salidas_hoy', 0), ('marcajes_hoy', 0)]:
        value = payload.get(key, default)
        try:
            normalized[key] = int(value or 0)
        except (TypeError, ValueError):
            normalized[key] = 0

    raw_area = payload.get('presentes_por_area') or []
    normalized_area = []
    for item in raw_area:
        if not isinstance(item, dict):
            continue
        gerencia = item.get('gerencia') or 'Sin gerencia'
        departamento = item.get('departamento') or 'Sin departamento'
        try:
            total = int(item.get('total') or 0)
        except (TypeError, ValueError):
            total = 0
        normalized_area.append({'gerencia': str(gerencia), 'departamento': str(departamento), 'total': total})
    normalized['presentes_por_area'] = normalized_area
    return normalized


def attendance_summary(db: Session):
    start = local_day_start_as_utc()
    type_counts = dict(
        db.query(AttendanceRecord.tipo, func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.fecha_hora >= start)
        .group_by(AttendanceRecord.tipo)
        .all()
    )
    latest_by_employee = db.query(
        AttendanceRecord.empleado_id,
        func.max(AttendanceRecord.fecha_hora).label('last_time'),
    ).filter(AttendanceRecord.fecha_hora >= start).group_by(AttendanceRecord.empleado_id).subquery()
    present_rows = db.query(AttendanceRecord, Empleado).join(
        latest_by_employee,
        and_(
            AttendanceRecord.empleado_id == latest_by_employee.c.empleado_id,
            AttendanceRecord.fecha_hora == latest_by_employee.c.last_time,
        ),
    ).join(Empleado, Empleado.id == AttendanceRecord.empleado_id).options(
        joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia)
    ).filter(AttendanceRecord.tipo == AttendanceType.ENTRADA.value).all()
    present_records = [record for record, _employee in present_rows]
    employees_by_id = {employee.id: employee for _record, employee in present_rows}
    area_counts = {}
    for record in present_records:
        employee = employees_by_id.get(record.empleado_id)
        if employee is None:
            continue
        department = employee.departamento_rel if employee.departamento_rel else None
        area = department.nombre if department and department.nombre else 'Sin departamento'
        gerencia = department.gerencia.nombre if department and department.gerencia and department.gerencia.nombre else 'Sin gerencia'
        key = (gerencia, area)
        area_counts[key] = area_counts.get(key, 0) + 1

    summary = {
        'presentes': len(present_records),
        'entradas_hoy': int(type_counts.get(AttendanceType.ENTRADA.value, 0) or 0),
        'salidas_hoy': int(type_counts.get(AttendanceType.SALIDA.value, 0) or 0),
        'marcajes_hoy': int(sum(int(value or 0) for value in type_counts.values()) or 0),
        'presentes_por_area': [
            {'gerencia': gerencia, 'departamento': departamento, 'total': int(total or 0)}
            for (gerencia, departamento), total in sorted(area_counts.items())
        ],
    }
    return AttendanceSummary(**normalize_attendance_summary_counts(summary))


def build_daily_report_payload(summary: AttendanceSummary, recent_records: list[dict], recent_audit: list[dict], *, report_date: str | None = None) -> dict:
    return {
        'date': report_date or date.today().isoformat(),
        'summary': summary.model_dump(mode='json') if hasattr(summary, 'model_dump') else summary,
        'recent_records': recent_records,
        'recent_audit': recent_audit,
    }


def list_present_employees(db: Session):
    start = local_day_start_as_utc()
    latest_by_employee = db.query(
        AttendanceRecord.empleado_id,
        func.max(AttendanceRecord.fecha_hora).label('last_time'),
    ).filter(AttendanceRecord.fecha_hora >= start).group_by(AttendanceRecord.empleado_id).subquery()
    present_records = db.query(AttendanceRecord).join(
        latest_by_employee,
        and_(
            AttendanceRecord.empleado_id == latest_by_employee.c.empleado_id,
            AttendanceRecord.fecha_hora == latest_by_employee.c.last_time,
        ),
    ).filter(AttendanceRecord.tipo == AttendanceType.ENTRADA.value).order_by(AttendanceRecord.fecha_hora.desc()).limit(PRESENT_EMPLOYEES_LIMIT).all()
    last_by_employee = {record.empleado_id: record for record in present_records}
    present_ids = list(last_by_employee)
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


def alert_id(kind: str, message: str) -> str:
    return hashlib.sha256(f'{kind}:{message}'.encode('utf-8')).hexdigest()


def dismiss_alert(db: Session, user_id: int, alert_identifier: str) -> bool:
    existing = db.query(AlertDismissal).filter(
        AlertDismissal.alerta_id == alert_identifier,
    ).first()
    if existing:
        return False
    db.add(AlertDismissal(usuario_id=user_id, alerta_id=alert_identifier))
    db.commit()
    return True


def normalize_inspector_dashboard_payload(summary=None, present=None, recent_records=None, expected_employees=None, alerts=None):
    normalized_summary = summary.model_dump(mode='json') if hasattr(summary, 'model_dump') else {
        'presentes': 0,
        'entradas_hoy': 0,
        'salidas_hoy': 0,
        'marcajes_hoy': 0,
        'presentes_por_area': [],
    }
    normalized_present = present or []
    recent = []
    for record in recent_records or []:
        employee = getattr(record, 'empleado', None)
        if employee is not None:
            recent.append(_to_output(record, employee).model_dump(mode='json'))
        else:
            recent.append({
                'id': getattr(record, 'id', None),
                'empleado_id': getattr(record, 'empleado_id', None),
                'empleado_nombre': 'Empleado no identificado',
                'codigo_tarjeta': '',
                'tipo': getattr(record, 'tipo', 'DESCONOCIDO'),
                'fecha_hora': getattr(record, 'fecha_hora', None).isoformat() if getattr(record, 'fecha_hora', None) else None,
                'origen': getattr(record, 'origen', 'PUERTO_COM'),
                'cedula': '',
                'departamento': None,
                'gerencia': None,
                'cargo': None,
                'foto_url': None,
                'estado': 'Desconocido',
            })
    normalized_expected = []
    for employee in expected_employees or []:
        normalized_expected.append({
            'id': getattr(employee, 'id', None),
            'nombre_apellido': getattr(employee, 'nombre_apellido', 'Empleado sin nombre'),
            'departamento': getattr(employee, 'departamento', None) or 'Sin departamento',
            'gerencia': getattr(employee, 'gerencia', None) or 'Sin gerencia',
        })
    return {
        'summary': normalized_summary,
        'present': normalized_present,
        'recent': recent,
        'expected': normalized_expected,
        'alerts': alerts or [],
    }


def inspector_dashboard(db: Session, user_id: int | None = None):
    start = local_day_start_as_utc()
    now = utc_now()
    try:
        summary = attendance_summary(db).model_dump()
        present = list_present_employees(db)
        recent_records = db.query(AttendanceRecord).options(
            joinedload(AttendanceRecord.empleado).joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia),
            joinedload(AttendanceRecord.empleado).joinedload(Empleado.cargo_rel),
        ).filter(AttendanceRecord.fecha_hora >= start).order_by(
            AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc()
        ).limit(5).all()
        alert_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.fecha_hora >= start
        ).order_by(AttendanceRecord.fecha_hora.asc(), AttendanceRecord.id.asc()).limit(100).all()
        alert_employee_ids = {record.empleado_id for record in alert_records}
        overnight_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.fecha_hora < start,
        ).order_by(AttendanceRecord.fecha_hora.desc(), AttendanceRecord.id.desc()).limit(PRESENT_EMPLOYEES_LIMIT * 3).all()
        latest_overnight = {}
        for record in overnight_records:
            latest_overnight.setdefault(record.empleado_id, record)
        alert_employee_ids.update(latest_overnight)
        alert_employees = {
            employee.id: employee for employee in db.query(Empleado).filter(Empleado.id.in_(alert_employee_ids)).all()
        } if alert_employee_ids else {}
        overnight_employee_ids = set(latest_overnight) - set(alert_employees)
        if overnight_employee_ids:
            alert_employees.update(
                (employee.id, employee)
                for employee in db.query(Empleado).filter(Empleado.id.in_(overnight_employee_ids)).all()
            )
        def employee_label(employee_id):
            employee = alert_employees.get(employee_id)
            return employee.nombre_apellido if employee else f'#{employee_id}'

        employee_types = {}
        employee_last_times = {}
        employee_has_entry = {}
        alerts = []
        for employee_id, record in latest_overnight.items():
            employee_has_entry[employee_id] = record.tipo == AttendanceType.ENTRADA.value
            employee_types[employee_id] = record.tipo
            employee_last_times[employee_id] = record.fecha_hora
        for record in alert_records:
            previous_type = employee_types.get(record.empleado_id)
            if previous_type == record.tipo:
                alerts.append({'kind': 'sequence', 'message': f'El empleado {employee_label(record.empleado_id)} tiene dos marcajes de {record.tipo.lower()} consecutivos. Último: {format_alert_time(record.fecha_hora)}.'})
            previous_time = employee_last_times.get(record.empleado_id)
            if previous_time is not None and attendance_records_are_too_close(previous_time, record.fecha_hora):
                interval = (record.fecha_hora - previous_time).total_seconds()
                alerts.append({'kind': 'sequence', 'message': f'El empleado {employee_label(record.empleado_id)} tiene marcajes demasiado cercanos: {interval:.1f} segundos entre {format_alert_time(previous_time)} y {format_alert_time(record.fecha_hora)}.'})
            if record.tipo == AttendanceType.SALIDA.value and not employee_has_entry.get(record.empleado_id, False):
                alerts.append({'kind': 'sequence', 'message': f'El empleado {employee_label(record.empleado_id)} tiene una salida sin entrada previa ({format_alert_time(record.fecha_hora)}).'})
            employee_has_entry[record.empleado_id] = record.tipo == AttendanceType.ENTRADA.value
            employee_last_times[record.empleado_id] = record.fecha_hora
            employee_types[record.empleado_id] = record.tipo
        today_employee_ids = {record.empleado_id for record in alert_records}
        for record in latest_overnight.values():
            if record.tipo == AttendanceType.ENTRADA.value and record.empleado_id not in today_employee_ids:
                alerts.append({'kind': 'sequence', 'message': f'El empleado {employee_label(record.empleado_id)} podría permanecer dentro desde el día anterior. Último marcaje: {format_alert_time(record.fecha_hora)}.'})
        for record in list_present_employees(db):
            entry_time = record['entrada']
            if entry_time and now - as_utc(entry_time) >= timedelta(hours=PROLONGED_STAY_HOURS):
                alerts.append({'kind': 'sequence', 'message': f'El empleado {record["nombre_apellido"]} supera {PROLONGED_STAY_HOURS} horas dentro. Entrada: {format_alert_time(entry_time)}.'})
        marked_employee_ids = db.query(AttendanceRecord.empleado_id).filter(AttendanceRecord.fecha_hora >= start).distinct().subquery()
        expected_employees = db.query(Empleado).options(
            joinedload(Empleado.departamento_rel).joinedload(Departamento.gerencia),
            joinedload(Empleado.cargo_rel),
        ).filter(
            Empleado.estado == EstadoEnum.Activo,
            ~Empleado.id.in_(db.query(marked_employee_ids.c.empleado_id)),
        ).order_by(Empleado.nombre_apellido.asc()).limit(PRESENT_EMPLOYEES_LIMIT).all()
        visible_alerts = []
        dismissed_ids = set()
        if user_id is not None:
            dismissed_ids = {item.alerta_id for item in db.query(AlertDismissal.alerta_id).all()}
        for alert in alerts:
            alert['id'] = alert_id(alert['kind'], alert['message'])
            if alert['id'] not in dismissed_ids:
                visible_alerts.append(alert)
        payload = normalize_inspector_dashboard_payload(
            summary,
            present,
            recent_records,
            expected_employees,
            visible_alerts[:10],
        )
        return payload
    except SQLAlchemyError:
        return normalize_inspector_dashboard_payload()
    except Exception:
        return normalize_inspector_dashboard_payload()