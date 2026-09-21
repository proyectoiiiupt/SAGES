class AuditableMixin:
    """
    Mixin declarativo para modelos de SQLAlchemy que requieren auditoría.
    Los modelos que hereden de esta clase serán interceptados por el listener
    antes de cada flush (before_flush) para calcular los deltas de cambios y
    registrarlos en la tabla binnacle.
    """

    # Módulo de auditoría por defecto. Los modelos pueden sobreescribirlo.
    __audit_module__ = 'GENERAL'

    # Campos que deben ser ignorados al calcular los deltas (ej. timestamps de modificación interna)
    __audit_exclude_fields__ = {'updated_at', 'created_at'}

    # Nota: No requiere que implemente propiedades, es meramente una interfaz/bandera
    # para que los listeners detecten si deben procesarlo o no.