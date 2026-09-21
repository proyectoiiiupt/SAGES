"""
Servicios del Módulo de Formación (Trainings)
Encapsula la lógica de negocio para módulos rectores y temas formativos.
"""
import logging
from typing import Optional, Tuple
from app.extensions import db
from app.models.training_module_model import TrainingModule
from app.utils.binnacle_utils import log_action


def get_module_by_id(module_id: int) -> Optional[TrainingModule]:
    """
    Obtiene un módulo rector por su identificador primario.
    
    Args:
        module_id: ID del módulo rector.
        
    Returns:
        TrainingModule si existe, None en caso contrario.
    """
    try:
        return TrainingModule.query.get(module_id)
    except Exception as e:
        logging.error(f"[trainings.services.get_module_by_id] Error al buscar módulo {module_id}: {e}")
        return None


def update_training_module(
    module: TrainingModule,
    name: str,
    description: str,
    user_id: int
) -> Tuple[bool, str]:
    """
    Actualiza los datos editables de un módulo rector (nombre y descripción)
    y registra la operación en la bitácora de auditoría.
    
    Args:
        module: Instancia de TrainingModule a actualizar.
        name: Nuevo nombre del módulo rector.
        description: Nueva descripción operativa.
        user_id: ID del usuario autenticado (Super Admin) que realiza la acción.
        
    Returns:
        Tuple (éxito: bool, mensaje: str).
    """
    try:
        # 1. Capturar valores previos para trazabilidad de auditoría
        old_values = {
            'name': module.name,
            'description': module.description
        }
        
        # 2. Sanitizar y normalizar datos entrantes
        clean_name = name.strip()
        clean_desc = description.strip()
        
        new_values = {
            'name': clean_name,
            'description': clean_desc
        }
        
        # 3. Aplicar cambios en la entidad
        module.name = clean_name
        module.description = clean_desc
        
        db.session.commit()
        
        # 4. Registrar en la bitácora del sistema
        log_action(
            user_id=user_id,
            module='trainings',
            action_type='UPDATE',
            description=f"Edición de Módulo Rector '{module.module_code}' ({module.name})",
            old_values=old_values,
            new_values=new_values
        )
        
        logging.info(
            f"[trainings.services.update_training_module] Módulo {module.id} ({module.module_code}) "
            f"actualizado exitosamente por usuario {user_id}."
        )
        return True, "Módulo rector actualizado exitosamente."
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"[trainings.services.update_training_module] Error al actualizar módulo {module.id}: {e}")
        return False, f"Error al guardar los cambios: {str(e)}"
