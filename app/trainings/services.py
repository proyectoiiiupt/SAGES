"""
Servicios del Módulo de Formación (Trainings)
Encapsula la lógica de negocio para módulos rectores y temas formativos.
"""
import uuid
import logging
import functools
from typing import Optional, Tuple
from sqlalchemy import select, func
from app.extensions import db
from app.models.training_module_model import TrainingModule
from app.models.training_model import Training
from app.models.status_model import Status

logger = logging.getLogger(__name__)

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
        logger.error(f"[trainings.services.get_module_by_id] Error al buscar módulo {module_id}: {e}")
        return None


def update_training_module(
    module: TrainingModule,
    name: str,
    description: str,
    user_id: int
) -> Tuple[bool, str]:
    """
    Actualiza los datos editables de un módulo rector (nombre y descripción).
    
    Args:
        module: Instancia de TrainingModule a actualizar.
        name: Nuevo nombre del módulo rector.
        description: Nueva descripción operativa.
        user_id: ID del usuario autenticado (Super Admin) que realiza la acción.
        
    Returns:
        Tuple (éxito: bool, mensaje: str).
    """
    try:
        # 1. Sanitizar y normalizar datos entrantes
        clean_name = name.strip()
        clean_desc = description.strip()
        
        # 2. Aplicar cambios en la entidad
        module.name = clean_name
        module.description = clean_desc
        
        db.session.commit()
        
        logger.info(
            f"[trainings.services.update_training_module] Módulo {module.id} ({module.module_code}) "
            f"actualizado exitosamente por usuario {user_id}."
        )
        return True, "Módulo rector actualizado exitosamente."
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[trainings.services.update_training_module] Error al actualizar módulo {module.id}: {e}")
        return False, f"Error al guardar los cambios: {str(e)}"

def generate_training_code() -> str:
    """
    Genera un código único en formato TRN-XXXXXX utilizando un sufijo hexadecimal aleatorio.
    """
    prefix = 'TRN'
    model_class = Training
    code_field = 'training_code'
    
    for _ in range(10):
        candidates = [f'{prefix}-{uuid.uuid4().hex[:6].upper()}' for _ in range(5)]
        used = {r[0] for r in db.session.execute(
            select(getattr(model_class, code_field))
            .where(getattr(model_class, code_field).in_(candidates))
        ).all()}
        for cand in candidates:
            if cand not in used:
                return cand
                
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

@functools.lru_cache(maxsize=1)
def get_active_status_id() -> int:
    """Obtiene el ID del estatus activo (STAT-001) y lo almacena en caché para evitar múltiples consultas a BD."""
    status_active = Status.query.filter_by(status_code='STAT-001').first()
    return status_active.id if status_active else 1

def is_training_name_duplicated(module_id: int, name: str) -> Training:
    """
    Verifica si existe un tema formativo con el mismo nombre en un módulo específico.
    Devuelve el objeto Training si existe, None si está disponible.
    """
    if not name:
        return None
        
    query = Training.query.filter(
        Training.name.ilike(name),
        Training.deleted_at.is_(None)
    )
    if module_id:
        query = query.filter(Training.training_module_id == module_id)
        
    return query.first()

def create_training(module_id: int, name: str, description: str) -> Training:
    """
    Crea un nuevo Tema Formativo, inyectando el código y estatus activo.
    Retorna el objeto creado o lanza una excepción en caso de error.
    """
    # 1. Validación de negocio
    existing = is_training_name_duplicated(module_id, name)
    if existing:
        raise ValueError(f'Ya existe un tema formativo denominado "{name}" en el módulo seleccionado.')

    # 2. Asignación de Estatus (con caché)
    status_id = get_active_status_id()

    # 3. Generación de Código
    final_code = generate_training_code()

    # 4. Inserción
    new_training_obj = Training(
        training_module_id=module_id,
        training_code=final_code,
        name=name,
        description=description,
        status_id=status_id
    )
    
    db.session.add(new_training_obj)
    db.session.commit()
    
    return new_training_obj
