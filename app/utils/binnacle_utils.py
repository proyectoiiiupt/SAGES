"""
Utilidades para el registro de acciones en la bitácora
Funciones auxiliares para el logging de acciones del sistema
"""

def log_action(user_id, module, action_type, description, old_values=None, new_values=None):
    """
    Registra una acción en la bitácora del sistema.
    
    Parámetros:
    - user_id: ID del usuario que realiza la acción
    - module: Módulo donde se realiza la acción (ej: 'institutions', 'users', 'requests')
    - action_type: Tipo de acción (ej: 'CREATE', 'UPDATE', 'DELETE', 'VIEW')
    - description: Descripción detallada de la acción
    - old_values: Valores anteriores (opcional, para actualizaciones)
    - new_values: Nuevos valores (opcional, para actualizaciones)
    
    Retorna:
    - bool: True si el registro fue exitoso, False en caso contrario
    """
    try:
        from app.extensions import db
        from app.models.binnacle_model import Binnacle
        from sqlalchemy.dialects.postgresql import JSONB
        
        # Crear registro en bitácora
        binnacle_entry = Binnacle(
            user_id=user_id,
            module=module,
            action_type=action_type,
            description=description,
            old_values=old_values if old_values else None,
            new_values=new_values if new_values else None
        )
        
        db.session.add(binnacle_entry)
        db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error al registrar en bitácora: {e}")
        from app.extensions import db
        db.session.rollback()
        return False