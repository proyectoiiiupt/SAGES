"""
Servicios del Módulo de Formación (Trainings)
Encapsula la lógica de negocio para módulos rectores y temas formativos.
"""
import uuid
import logging
import functools
import csv
import io
import openpyxl
from typing import Optional, Tuple, List, Dict, Any
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

# ============================================================================
# Carga Masiva (Bulk Upload)
# ============================================================================

def sanitize_formula_injection(value: Any) -> str:
    """Previene inyección de fórmulas (CSV/Excel Formula Injection / DDE)."""
    if not value:
        return ""
    val_clean = str(value).strip()
    if val_clean.startswith(('=', '+', '-', '@', '\t', '\r')):
        return f"'{val_clean}"
    return val_clean


def get_active_modules_dict() -> Dict[str, TrainingModule]:
    """Retorna un mapeo normalizado de código y nombre de módulos activos (acepta sinónimos en cabeceras)."""
    modules = TrainingModule.query.filter_by(is_active=True).all()
    mapping = {}
    for m in modules:
        mapping[m.module_code.upper().strip()] = m
        mapping[m.name.lower().strip()] = m
        # Soporte para la nueva opción del dropdown "MOD-XXX - Nombre"
        mapping[f"{m.module_code} - {m.name}".lower().strip()] = m
    return mapping


def parse_training_file(file_storage) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """
    Analiza un archivo Excel (.xlsx) o CSV en memoria.
    Retorna: (filas_validas, filas_invalidas, estadisticas)
    """
    filename = file_storage.filename.lower()
    raw_rows = []

    if filename.endswith('.xlsx'):
        wb = openpyxl.load_workbook(file_storage, read_only=True, data_only=True)
        sheet = wb.active
        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                raw_rows.append([str(c).strip() if c is not None else "" for c in row])
    elif filename.endswith('.csv'):
        # Leer solo la primera línea para detectar el delimitador
        first_line = file_storage.stream.readline().decode('utf-8-sig', errors='replace')
        delimiter = ';' if ';' in first_line else ','
        file_storage.stream.seek(0)
        
        # Procesar en stream (eficiente en memoria RAM)
        wrapper = io.TextIOWrapper(file_storage.stream, encoding='utf-8-sig', errors='replace')
        reader = csv.reader(wrapper, delimiter=delimiter)
        for row in reader:
            if any(cell.strip() for cell in row):
                raw_rows.append([c.strip() for c in row])
        
        wrapper.detach() # Evita que el wrapper cierre el stream original
    else:
        raise ValueError("Formato no soportado. Se aceptan exclusivamente archivos .xlsx y .csv")

    if not raw_rows or len(raw_rows) < 2:
        raise ValueError("El archivo está vacío o solo contiene la fila de cabecera.")

    MAX_BATCH_ROWS = 500
    if len(raw_rows) - 1 > MAX_BATCH_ROWS:
        raise ValueError(f"El archivo supera el límite permitido de {MAX_BATCH_ROWS} filas por lote.")

    headers = [str(h).strip().lower() for h in raw_rows[0]]
    data_rows = raw_rows[1:]
    
    # Auto-mapeo: encontrar índices de columnas clave
    mod_idx = -1
    name_idx = -1
    desc_idx = -1
    
    # Sinónimos para cabeceras
    mod_synonyms = ['codigo_modulo', 'modulo', 'cod modulo', 'código de módulo', 'mod']
    name_synonyms = ['nombre_tema', 'titulo_tema', 'nombre', 'titulo', 'título']
    desc_synonyms = ['descripcion_programatica', 'descripcion', 'descripción']
    
    for i, header in enumerate(headers):
        if mod_idx == -1 and any(syn in header for syn in mod_synonyms):
            mod_idx = i
        elif name_idx == -1 and any(syn in header for syn in name_synonyms):
            name_idx = i
        elif desc_idx == -1 and any(syn in header for syn in desc_synonyms):
            desc_idx = i

    # Fallback si no encuentra cabeceras claras, usar los primeros 3 (ignora extras)
    if mod_idx == -1 or name_idx == -1 or desc_idx == -1:
        mod_idx, name_idx, desc_idx = 0, 1, 2

    modules_map = get_active_modules_dict()

    valid_rows = []
    invalid_rows = []
    seen_in_batch = set()

    # Pre-cargar temas formativos existentes en memoria (RAM) para evitar consultas N+1
    existing_trainings = db.session.query(
        Training.training_module_id,
        db.func.lower(Training.name),
        Training.training_code
    ).filter(Training.deleted_at.is_(None)).all()
    
    existing_db_map = {(r[0], r[1]): r[2] for r in existing_trainings}

    for idx, row in enumerate(data_rows, start=2):
        # Asegurarse de que la fila tenga suficientes columnas para los índices
        max_idx_needed = max(mod_idx, name_idx, desc_idx)
        if len(row) <= max_idx_needed:
             invalid_rows.append({
                 'row_number': idx,
                 'module_input': row[mod_idx] if len(row) > mod_idx else '',
                 'name_input': row[name_idx] if len(row) > name_idx else '',
                 'desc_input': row[desc_idx] if len(row) > desc_idx else '',
                 'error': 'Fila incompleta: no se encontraron todas las columnas requeridas.'
             })
             continue

        raw_mod = row[mod_idx].strip()
        raw_name = sanitize_formula_injection(row[name_idx])
        raw_desc = sanitize_formula_injection(row[desc_idx])

        # 1. Validar existencia del módulo rector
        module_obj = modules_map.get(raw_mod.upper()) or modules_map.get(raw_mod.lower())
        if not module_obj:
            invalid_rows.append({
                'row_number': idx,
                'module_input': raw_mod,
                'name_input': raw_name,
                'desc_input': raw_desc,
                'error': f'Módulo Rector "{raw_mod}" no reconocido o inactivo.'
            })
            continue

        # 2. Validar longitud del título
        if len(raw_name) < 5 or len(raw_name) > 200:
            invalid_rows.append({
                'row_number': idx,
                'module_input': module_obj.module_code,
                'name_input': raw_name,
                'desc_input': raw_desc,
                'error': f'El nombre debe tener entre 5 y 200 caracteres (actual: {len(raw_name)}).'
            })
            continue

        # 3. Validar longitud de la descripción
        if len(raw_desc) < 15 or len(raw_desc) > 1000:
            invalid_rows.append({
                'row_number': idx,
                'module_input': module_obj.module_code,
                'name_input': raw_name,
                'desc_input': raw_desc,
                'error': f'La descripción debe tener entre 15 y 1000 caracteres (actual: {len(raw_desc)}).'
            })
            continue

        # 4. Validar duplicidad intra-archivo
        batch_key = (module_obj.id, raw_name.lower())
        if batch_key in seen_in_batch:
            invalid_rows.append({
                'row_number': idx,
                'module_input': module_obj.module_code,
                'name_input': raw_name,
                'desc_input': raw_desc,
                'error': 'Tema duplicado en este mismo archivo.'
            })
            continue
        seen_in_batch.add(batch_key)

        # 5. Validar duplicidad contra la base de datos (Operación O(1) en RAM)
        db_key = (module_obj.id, raw_name.lower())
        if db_key in existing_db_map:
            existing_code = existing_db_map[db_key]
            invalid_rows.append({
                'row_number': idx,
                'module_input': module_obj.module_code,
                'name_input': raw_name,
                'desc_input': raw_desc,
                'error': f'Ya existe registrado en la BD con código {existing_code}.'
            })
            continue

        valid_rows.append({
            'row_number': idx,
            'module_id': module_obj.id,
            'module_code': module_obj.module_code,
            'module_name': module_obj.name,
            'name': raw_name,
            'description': raw_desc
        })

    summary = {
        'total_rows': len(data_rows),
        'valid_count': len(valid_rows),
        'invalid_count': len(invalid_rows)
    }

    return valid_rows, invalid_rows, summary
