from app.extensions import db
from app.models.training_model import Training
from app.models.training_category_model import TrainingCategory
from app.models.status_model import Status
from sqlalchemy import or_

def get_all_trainings(filters, page=1, per_page=10):
    """
    Obtiene formaciones con filtros y paginación.

    Args:
        filters: dict con filtros (search_name, category, status)
        page: número de página (default 1)
        per_page: registros por página (default 10)

    Returns:
        dict con datos de paginación y resultados
    """
    # Obtener todos los IDs ordenados sin filtros para calcular índices originales
    all_ids_query = Training.query.order_by(Training.id.asc())
    all_ids = [training.id for training in all_ids_query.all()]
    id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}
    
    # Incluir todas las formaciones sin filtro de deleted_at
    query = Training.query
    
    # Aplicar filtros
    if filters.get('search_name'):
        search_term = f"%{filters['search_name']}%"
        query = query.filter(
            or_(
                Training.training_code.ilike(search_term),
                Training.name.ilike(search_term)
            )
        )
    
    if filters.get('category'):
        query = query.filter(Training.training_category_id == filters['category'])
    
    if filters.get('status'):
        # Buscar por nombre de estatus (activo/inactivo) en lugar de ID
        status_name = filters['status'].lower()
        query = query.join(Status).filter(
            Status.status_name.ilike(f"%{status_name}%")
        )
    
    # Ordenar por ID
    query = query.order_by(Training.id.asc())
    
    # Paginación
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Calcular índices originales para los resultados paginados
    trainings_with_index = []
    for training in pagination.items:
        original_index = id_to_index.get(training.id, 0)
        trainings_with_index.append({
            'training': training,
            'original_index': original_index
        })

    return {
        'trainings': trainings_with_index,
        'pagination': pagination,
        'total_all': len(all_ids)  # Total sin filtros
    }

def get_filter_options():
    """
    Obtiene las opciones para los filtros del catálogo.

    Returns:
        dict con categorías y estatus disponibles
    """
    # Obtener todas las categorías activas, ordenadas por nombre
    categories = TrainingCategory.query.filter().order_by(TrainingCategory.name.asc()).all()
    
    # Obtener todos los estatus para el contexto de training
    statuses = Status.query.filter(
        Status.context == 'training'
    ).order_by(Status.status_name.asc()).all()

    return {
        'categories': categories,
        'statuses': statuses
    }