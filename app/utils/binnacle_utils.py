"""
Utilidades para el registro de acciones en la bitácora
Funciones auxiliares para el logging de acciones del sistema
"""
from flask import request

def log_action(user_id, module, action_type, description, target_table=None, record_id=None, old_values=None, new_values=None):
    """
    Registra una acción en la bitácora del sistema, capturando contexto de red forense.
    
    Parámetros:
    - user_id: ID del usuario que realiza la acción
    - module: Módulo donde se realiza la acción (ej: 'institutions', 'users', 'requests')
    - action_type: Tipo de acción (ej: 'CREAR', 'ACTUALIZAR', 'LOGIN_FALLIDO')
    - description: Descripción detallada de la acción
    - target_table: (Nuevo) Tabla de la base de datos afectada
    - record_id: (Nuevo) ID del registro modificado en dicha tabla
    - old_values: Valores anteriores (opcional, para actualizaciones)
    - new_values: Nuevos valores (opcional, para actualizaciones)
    
    Retorna:
    - bool: True si el registro fue exitoso, False en caso contrario
    """
    try:
        from app.extensions import db
        from app.models.binnacle_model import Binnacle
        
        # Capturamos datos de red directamente del request de Flask si está disponible
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent') if request else None
        
        # Crear registro en bitácora
        binnacle_entry = Binnacle(
            user_id=user_id,
            module=module,
            action_type=action_type,
            description=description,
            target_table=target_table,
            record_id=record_id,
            old_values=old_values if old_values else None,
            new_values=new_values if new_values else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.session.add(binnacle_entry)
        db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error al registrar en bitácora: {e}")
        from app.extensions import db
        db.session.rollback()
        return False