from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history
from app.binnacle.mixins import AuditableMixin
from app.binnacle.services import BinnacleService
from app.binnacle.sanitizers import sanitize_payload
from app.binnacle.types import AuditAction, AuditStatus

def extract_entity_delta(instance):
    """
    Extrae los cambios de una instancia de SQLAlchemy, calculando los
    valores viejos y nuevos y aplicándoles el proceso de sanitización.
    """
    old_values = {}
    new_values = {}

    exclude_fields = getattr(instance, '__audit_exclude_fields__', set())

    # Recorremos todas las columnas definidas en el mapeo de la entidad
    for attr in instance.__mapper__.columns.keys():
        if attr in exclude_fields:
            continue

        history = get_history(instance, attr)
        # history.has_changes() verifica si realmente hubo modificaciones
        if history.has_changes():
            # history.added devuelve una lista con el nuevo valor (si hay)
            if history.added:
                new_values[attr] = history.added[0]
            # history.deleted devuelve una lista con el valor anterior
            if history.deleted:
                old_values[attr] = history.deleted[0]

    return sanitize_payload(old_values), sanitize_payload(new_values)

def get_entity_identity(instance):
    """Intenta extraer la clave primaria (ID) del registro, incluso si acaba de insertarse."""
    from sqlalchemy import inspect
    insp = inspect(instance)
    if insp.identity:
        return insp.identity[0]
    # Si es nuevo, tal vez aún no tenga el identity asignado,
    # pero podemos intentarlo mediante su atributo principal si se definió.
    return getattr(instance, 'id', None)

def before_flush_listener(session, flush_context, instances):
    """
    Interceptor que captura los objetos mutados justo antes de que se envíen
    las consultas SQL a la base de datos (flush).
    """

    # Iterar sobre las inserciones nuevas
    for instance in session.new:
        if isinstance(instance, AuditableMixin):
            # En inserts, todo es new_values
            new_vals = {
                c.key: getattr(instance, c.key)
                for c in instance.__mapper__.columns
                if c.key not in getattr(instance, '__audit_exclude_fields__', set())
            }
            new_vals = sanitize_payload(new_vals)

            target_table = instance.__tablename__
            module = getattr(instance, '__audit_module__', 'GENERAL')

            # Nota: 'record_id' puede ser None aquí porque aún no hay flush.
            # Podría asignarse en after_flush si es estrictamente necesario, pero usualmente 
            # se tolera None en registros de creación si son auto-increment.
            record_id = get_entity_identity(instance)

            BinnacleService.create_log_entry(
                module=module,
                action_type=AuditAction.REGISTRO_NUEVO.value,
                description=f"Registro creado en {target_table}",
                status=AuditStatus.COMPLETADO.value,
                target_table=target_table,
                record_id=record_id,
                old_values=None,
                new_values=new_vals,
                session_instance=session  # Añadir a la misma sesión antes del flush
            )

    # Iterar sobre las actualizaciones
    for instance in session.dirty:
        if isinstance(instance, AuditableMixin):
            old_vals, new_vals = extract_entity_delta(instance)

            # Solo registrar si efectivamente hubo cambios en campos no excluidos
            if not old_vals and not new_vals:
                continue

            target_table = instance.__tablename__
            module = getattr(instance, '__audit_module__', 'GENERAL')
            record_id = get_entity_identity(instance)

            BinnacleService.create_log_entry(
                module=module,
                action_type=AuditAction.ACTUALIZAR.value,
                description=f"Registro modificado en {target_table} (ID: {record_id})",
                status=AuditStatus.COMPLETADO.value,
                target_table=target_table,
                record_id=record_id,
                old_values=old_vals,
                new_values=new_vals,
                session_instance=session
            )

    # Iterar sobre las eliminaciones
    for instance in session.deleted:
        if isinstance(instance, AuditableMixin):
            old_vals = {
                c.key: getattr(instance, c.key)
                for c in instance.__mapper__.columns
                if c.key not in getattr(instance, '__audit_exclude_fields__', set())
            }
            old_vals = sanitize_payload(old_vals)

            target_table = instance.__tablename__
            module = getattr(instance, '__audit_module__', 'GENERAL')
            record_id = get_entity_identity(instance)

            BinnacleService.create_log_entry(
                module=module,
                action_type='ELIMINAR',  # Puedes agregarlo a ActionType si lo prefieres
                description=f"Registro eliminado en {target_table} (ID: {record_id})",
                status=AuditStatus.COMPLETADO.value,
                target_table=target_table,
                record_id=record_id,
                old_values=old_vals,
                new_values=None,
                session_instance=session
            )

def register_audit_listeners(db):
    """Suscribe el listener a la sesión global de SQLAlchemy"""
    event.listen(db.session, 'before_flush', before_flush_listener)