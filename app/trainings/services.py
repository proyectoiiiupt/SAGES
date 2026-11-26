"""
Servicios del Módulo de Formación (Trainings)
Encapsula la lógica de negocio para módulos rectores y temas formativos.
"""
import os
import re
import uuid
import unicodedata
import logging
import functools
import csv
import io
import zipfile
import openpyxl
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.training_module_model import TrainingModule
from app.models.training_model import Training
from app.models.status_model import Status
from app.models.request_model import Request

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


def _notify_module_status_changed(module: TrainingModule, user_id: int) -> None:
    """
    Emite notificación a 'state_admin' (y 'applicant' si fue reactivado)
    al cambiar el estatus operativo de un Módulo Rector.
    """
    try:
        from app.notifications.services import NotificationService
        from app.notifications.enums import NotificationEvent, NotificationType

        admin_name = "Administrador"
        try:
            from flask_login import current_user
            if current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'id', None) == user_id:
                admin_name = getattr(current_user, 'full_name', getattr(current_user, 'user_name', 'Administrador'))
            elif user_id:
                from app.models.user_model import User
                actor = User.query.get(user_id)
                if actor and actor.full_name:
                    admin_name = actor.full_name
        except Exception:
            if user_id:
                try:
                    from app.models.user_model import User
                    actor = User.query.get(user_id)
                    if actor and actor.full_name:
                        admin_name = actor.full_name
                except Exception:
                    pass

        is_now_active = module.is_active
        sev = NotificationType.SUCCESS if is_now_active else NotificationType.WARNING
        action_lbl = "reactivado y habilitado" if is_now_active else "inactivado temporalmente"
        ctx = {
            "module_name": module.name,
            "action_label": action_lbl,
            "admin_name": admin_name,
            "_display": [
                ("Módulo Formativo", module.name),
                ("Estado / Acción", action_lbl.capitalize()),
                ("Actualizado por", admin_name),
            ],
        }
        NotificationService.notify_role(
            role_name="state_admin",
            event=NotificationEvent.TRAINING_MODULE_STATUS_CHANGED,
            context=ctx,
            exclude_user_id=user_id,
            severity_override=sev,
            redirect_url="/training/",
            action_text="Ver Módulos"
        )
        if is_now_active:
            NotificationService.notify_role(
                role_name="applicant",
                event=NotificationEvent.TRAINING_MODULE_STATUS_CHANGED,
                context=ctx,
                severity_override=NotificationType.SUCCESS,
                redirect_url="/training/",
                action_text="Explorar Catálogo"
            )
    except Exception as notif_err:
        logger.warning(f"[trainings.services] No se pudo emitir notificación TRAINING_MODULE_STATUS_CHANGED: {notif_err}")


def update_training_module(
    module: TrainingModule,
    name: str,
    description: str,
    user_id: int,
    is_active: Optional[bool] = None
) -> Tuple[bool, str]:
    """
    Actualiza los datos editables de un módulo rector (nombre, descripción y opcionalmente estatus operativo).
    
    Args:
        module: Instancia de TrainingModule a actualizar.
        name: Nuevo nombre del módulo rector.
        description: Nueva descripción operativa.
        user_id: ID del usuario autenticado (Super Admin) que realiza la acción.
        is_active: Opcional. Nuevo estatus booleano del módulo rector.
        
    Returns:
        Tuple (éxito: bool, mensaje: str).
    """
    try:
        # 1. Sanitizar y normalizar datos entrantes
        clean_name = name.strip()
        clean_desc = description.strip()
        
        old_name = module.name
        old_desc = module.description
        module._skip_auto_audit = True

        status_changed = False
        estado_str = ""
        old_status = module.is_active

        # 2. Si se solicitó cambio de estatus
        if is_active is not None and is_active != module.is_active:
            if old_status and not is_active:
                # Inactivación (Desincorporación): validación estricta de temas activos
                active_count = count_active_trainings_for_module(module.id)
                if active_count > 0:
                    return (
                        False,
                        f'No se puede desincorporar el Módulo Rector "{module.name}" porque posee '
                        f"{active_count} tema(s) formativo(s) activo(s) asociado(s). "
                        f"Debe desincorporar o reasignar dichos temas antes de proceder a inactivar el módulo."
                    )
                module.is_active = False
                max_order = db.session.query(func.max(TrainingModule.order_index)).scalar() or 0
                module.order_index = max_order + 1
                status_changed = True
                estado_str = "desincorporado (inactivado)"
            elif not old_status and is_active:
                # Reactivación: posición de primero
                module.is_active = True
                db.session.query(TrainingModule).filter(TrainingModule.id != module.id).update(
                    {TrainingModule.order_index: TrainingModule.order_index + 1}
                )
                module.order_index = 1
                status_changed = True
                estado_str = "reactivado (activado)"

        # 3. Aplicar cambios de texto
        module.name = clean_name
        module.description = clean_desc
        module.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()

        # 4. Registrar en bitácora si hubo cambio de estatus o de contenido
        old_vals = {}
        new_vals = {}
        if old_name != clean_name:
            old_vals['name'] = old_name
            new_vals['name'] = clean_name
        if old_desc != clean_desc:
            old_vals['description'] = old_desc
            new_vals['description'] = clean_desc
        if status_changed:
            old_vals['is_active'] = old_status
            new_vals['is_active'] = module.is_active

        if old_vals or new_vals:
            try:
                from app.binnacle.services import BinnacleService
                from app.binnacle.types import AuditModule, AuditAction, AuditStatus

                act_type = AuditAction.CAMBIO_ESTATUS_MODULO_RECTOR.value if status_changed else AuditAction.ACTUALIZAR_MODULO_RECTOR.value
                desc_msg = (
                    f"El Módulo Rector '{module.name}' ({module.module_code}) ha sido {estado_str} y actualizado exitosamente."
                    if status_changed else
                    f"Actualización de datos del Módulo Rector '{module.name}' ({module.module_code})."
                )
                BinnacleService.create_log_entry(
                    module=AuditModule.TRAININGS.value,
                    action_type=act_type,
                    description=desc_msg,
                    target_table='sages.training_modules',
                    record_id=module.id,
                    status=AuditStatus.MODIFICADO.value,
                    old_values=old_vals,
                    new_values=new_vals
                )
            except Exception as audit_err:
                logger.error(f"[trainings.services.update_training_module] Error registrando bitácora: {audit_err}")

        # 5. Notificación al cambiar estatus operativo del módulo
        if status_changed:
            _notify_module_status_changed(module, user_id)

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

def normalize_training_name(text: Any) -> str:
    """
    Normaliza nombres de módulos y temas formativos para validación de unicidad:
    convierte a minúsculas, elimina tildes/diacríticos y conserva únicamente [a-z0-9].
    """
    if not text:
        return ""
    cleaned = unicodedata.normalize('NFKD', str(text).lower()).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-z0-9]', '', cleaned)


def _normalization_key(text: Any) -> str:
    """Retorna la clave normalizada o el texto en minúsculas si solo contiene símbolos."""
    norm = normalize_training_name(text)
    if norm:
        return norm
    return str(text or '').strip().lower()


def is_module_name_duplicated(name: str, exclude_id: Optional[int] = None) -> Optional[TrainingModule]:
    """
    Verifica si existe un módulo rector con un nombre equivalente tras normalización extrema.
    Devuelve el objeto TrainingModule si existe colisión, o None si está disponible.
    """
    if not name or not str(name).strip():
        return None

    target_key = _normalization_key(name)
    query = TrainingModule.query
    if exclude_id is not None:
        query = query.filter(TrainingModule.id != exclude_id)

    for module in query.all():
        if _normalization_key(module.name) == target_key:
            return module

    return None


def is_training_name_duplicated(
    module_id: int,
    name: str,
    exclude_id: Optional[int] = None
) -> Optional[Training]:
    """
    Verifica si existe un tema formativo con un nombre equivalente (sin tildes, signos ni espacios)
    dentro de un módulo específico, excluyendo eliminados lógicamente y opcionalmente un ID dado.
    """
    if not name or not str(name).strip():
        return None

    target_key = _normalization_key(name)
    query = Training.query.filter(Training.deleted_at.is_(None))
    if module_id:
        query = query.filter(Training.training_module_id == module_id)
    if exclude_id is not None:
        query = query.filter(Training.id != exclude_id)

    for training in query.all():
        if _normalization_key(training.name) == target_key:
            return training

    return None

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
    new_training_obj._skip_auto_audit = True
    
    db.session.add(new_training_obj)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(
            f'Ya existe un tema formativo denominado "{name}" en el módulo seleccionado.'
        ) from exc

    try:
        from app.binnacle.services import BinnacleService
        from app.binnacle.types import AuditModule, AuditAction, AuditStatus
        BinnacleService.create_log_entry(
            module=AuditModule.TRAININGS.value,
            action_type=AuditAction.REGISTRO_TEMA_FORMATIVO.value,
            description=f"Nuevo Tema Formativo registrado: '{new_training_obj.name}' ({new_training_obj.training_code})",
            target_table='sages.trainings',
            record_id=new_training_obj.id,
            new_values={
                'training_code': new_training_obj.training_code,
                'name': new_training_obj.name,
                'description': new_training_obj.description,
                'training_module_id': module_id,
                'status_code': 'STAT-001'
            },
            status=AuditStatus.COMPLETADO.value
        )
    except Exception as audit_err:
        logger.warning(f"[trainings.services.create_training] No se pudo registrar bitácora: {audit_err}")
    
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


XLSX_MAGIC_BYTES = b'\x50\x4b\x03\x04'
MAX_BULK_FILE_SIZE = 5 * 1024 * 1024           # 5 MB
MAX_XLSX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB (protección anti ZIP-bomb)
MAX_BATCH_ROWS = 500
REQUIRED_XLSX_ENTRIES = ('[Content_Types].xml', 'xl/workbook.xml')
FORBIDDEN_CSV_SIGNATURES = (
    b'\x50\x4b\x03\x04',
    b'\x50\x4b\x05\x06',
    b'\x50\x4b\x07\x08',
    b'%PDF',
    b'MZ',
    b'\x7fELF',
    b'\x89PNG',
    b'\xff\xd8\xff',
    b'GIF87a',
    b'GIF89a',
    b'\xd0\xcf\x11\xe0',
)


def _validate_bulk_file(file_storage, extension: str) -> None:
    """
    Valida tamaño máximo, Magic Bytes y estructura binaria de archivos de carga masiva.
    Lanza ValueError si el archivo es inválido, corrupto o potencialmente malicioso.
    """
    stream = getattr(file_storage, 'stream', file_storage)
    stream.seek(0, os.SEEK_END)
    file_size = stream.tell()
    stream.seek(0)

    if file_size == 0:
        raise ValueError("El archivo está vacío (0 bytes).")

    if file_size > MAX_BULK_FILE_SIZE:
        raise ValueError("El archivo supera el tamaño máximo permitido de 5 MB.")

    if extension == '.xlsx':
        header = stream.read(4)
        stream.seek(0)
        if header != XLSX_MAGIC_BYTES:
            raise ValueError(
                "El archivo no posee una firma binaria válida de Excel (.xlsx / Magic Bytes 50 4B 03 04). "
                "Verifique que no sea un archivo renombrado, corrupto o protegido con contraseña."
            )
        try:
            with zipfile.ZipFile(stream, 'r') as zf:
                entries = set(zf.namelist())
                if not all(req in entries for req in REQUIRED_XLSX_ENTRIES):
                    raise ValueError(
                        "El archivo ZIP/OOXML no corresponde a un libro de cálculo Excel (.xlsx) válido."
                    )
                infolist = zf.infolist()
                if any(info.flag_bits & 0x1 for info in infolist):
                    raise ValueError(
                        "El archivo Excel está cifrado o protegido con contraseña. Desproteja el archivo antes de cargarlo."
                    )
                total_uncompressed = sum(info.file_size for info in infolist)
                if total_uncompressed > MAX_XLSX_UNCOMPRESSED_SIZE:
                    raise ValueError(
                        "El archivo Excel excede el límite seguro de tamaño descomprimido."
                    )
        except zipfile.BadZipFile:
            raise ValueError("El archivo .xlsx está corrupto o su estructura binaria no es válida.")
        finally:
            stream.seek(0)
    elif extension == '.csv':
        sample = stream.read(8192)
        stream.seek(0)
        if any(sample.startswith(sig) for sig in FORBIDDEN_CSV_SIGNATURES) or b'\x00' in sample:
            raise ValueError(
                "El archivo .csv contiene datos binarios o una firma incompatible. "
                "Suba únicamente un archivo de texto plano CSV."
            )


def parse_training_file(file_storage) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """
    Analiza un archivo Excel (.xlsx) o CSV en memoria.
    Retorna: (filas_validas, filas_invalidas, estadisticas)
    """
    filename = (getattr(file_storage, 'filename', '') or '').strip().lower()
    stream = getattr(file_storage, 'stream', file_storage)
    raw_rows = []

    if filename.endswith('.xlsx'):
        _validate_bulk_file(file_storage, '.xlsx')
        wb = None
        sheet_missing = False
        exceeded_limit = False
        try:
            wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
            sheet = wb.active
            if sheet is None:
                sheet_missing = True
            else:
                for row in sheet.iter_rows(values_only=True):
                    if any(cell is not None and str(cell).strip() for cell in row):
                        raw_rows.append([str(c).strip() if c is not None else "" for c in row])
                        if len(raw_rows) > MAX_BATCH_ROWS + 1:
                            exceeded_limit = True
                            break
        except Exception as exc:
            logger.warning(
                f"[trainings.services.parse_training_file] Archivo .xlsx ilegible o corrupto ({type(exc).__name__}): {exc}"
            )
            raise ValueError(
                "No se pudo leer el archivo Excel (.xlsx). Verifique que sea un archivo válido y no esté dañado ni protegido con contraseña."
            ) from exc
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass
            if not getattr(stream, 'closed', False):
                stream.seek(0)

        if sheet_missing:
            raise ValueError("El archivo Excel no contiene hojas de cálculo legibles.")
        if exceeded_limit:
            raise ValueError(
                f"El archivo supera el límite permitido de {MAX_BATCH_ROWS} filas por lote."
            )
    elif filename.endswith('.csv'):
        _validate_bulk_file(file_storage, '.csv')
        raw_bytes = stream.read()
        stream.seek(0)
        try:
            raw_bytes.decode('utf-8-sig')
            csv_encoding = 'utf-8-sig'
        except UnicodeDecodeError:
            csv_encoding = 'cp1252'

        # Leer solo la primera línea para detectar el delimitador
        first_line = stream.readline().decode(csv_encoding, errors='replace')
        delimiter = ';' if ';' in first_line else ','
        stream.seek(0)

        # Procesar en stream (eficiente en memoria RAM)
        wrapper = io.TextIOWrapper(stream, encoding=csv_encoding, errors='replace')
        try:
            reader = csv.reader(wrapper, delimiter=delimiter)
            for row in reader:
                if any(cell.strip() for cell in row):
                    raw_rows.append([c.strip() for c in row])
                    if len(raw_rows) > MAX_BATCH_ROWS + 1:
                        raise ValueError(
                            f"El archivo supera el límite permitido de {MAX_BATCH_ROWS} filas por lote."
                        )
        except csv.Error as exc:
            logger.warning(f"[trainings.services.parse_training_file] CSV malformado: {exc}")
            raise ValueError(
                "No se pudo leer el archivo CSV. Verifique que el formato de columnas y comillas sea válido."
            ) from exc
        finally:
            wrapper.detach()  # Evita que el wrapper cierre el stream original
            if not getattr(stream, 'closed', False):
                stream.seek(0)
    else:
        raise ValueError("Formato no soportado. Se aceptan exclusivamente archivos .xlsx y .csv")

    if not raw_rows or len(raw_rows) < 2:
        raise ValueError("El archivo está vacío o solo contiene la fila de cabecera.")

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
        Training.name,
        Training.training_code
    ).filter(Training.deleted_at.is_(None)).all()

    existing_db_map = {(r[0], _normalization_key(r[1])): r[2] for r in existing_trainings}

    for idx, row in enumerate(data_rows, start=2):
        # Ignorar fila instructiva o de ayuda de la plantilla si está presente
        row_str_sample = " ".join(str(c).lower().strip() for c in row if c is not None)
        if (
            "ve a la pestaña" in row_str_sample
            or "ve a la pestana" in row_str_sample
            or "catalogo y copia" in row_str_sample
            or row_str_sample.startswith("->")
        ):
            continue

        # Asegurarse de que la fila tenga suficientes columnas para los índices
        max_idx_needed = max(mod_idx, name_idx, desc_idx)
        if len(row) <= max_idx_needed:
            invalid_rows.append({
                'row_number': idx,
                'module_input': sanitize_formula_injection(row[mod_idx]) if len(row) > mod_idx else '',
                'name_input': sanitize_formula_injection(row[name_idx]) if len(row) > name_idx else '',
                'desc_input': sanitize_formula_injection(row[desc_idx]) if len(row) > desc_idx else '',
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
                'module_input': sanitize_formula_injection(raw_mod),
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

        # 4. Validar duplicidad intra-archivo (normalizada)
        norm_name = _normalization_key(raw_name)
        batch_key = (module_obj.id, norm_name)
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

        # 5. Validar duplicidad contra la base de datos (Operación O(1) en RAM, normalizada)
        db_key = (module_obj.id, norm_name)
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
        'total_rows': len(valid_rows) + len(invalid_rows),
        'valid_count': len(valid_rows),
        'invalid_count': len(invalid_rows)
    }

    return valid_rows, invalid_rows, summary


# ============================================================================
# Desincorporación y Activación Lógica de Módulo Rector
# ============================================================================

def count_active_trainings_for_module(module_id: int) -> int:
    """
    Cuenta la cantidad de temas formativos activos asociados a un módulo rector.
    Un tema se considera activo si:
      - training_module_id coincide con el módulo
      - deleted_at es NULL (no está eliminado lógicamente)
      - status tiene status_code == 'STAT-001' (Activo)
    """
    try:
        count = (
            db.session.query(func.count(Training.id))
            .join(Status, Training.status_id == Status.id)
            .filter(
                Training.training_module_id == module_id,
                Training.deleted_at.is_(None),
                Status.status_code == 'STAT-001'
            )
            .scalar()
        )
        return count or 0
    except Exception as e:
        logger.error(f"[trainings.services.count_active_trainings_for_module] Error al contar temas activos para módulo {module_id}: {e}")
        return 0


ACTIVE_REQUEST_STATUS_CODES = ('STAT-003', 'STAT-004', 'STAT-005', 'STAT-006')


def count_active_requests_for_training(training_id: int) -> int:
    """
    Cuenta la cantidad de solicitudes activas o pendientes asociadas a un tema formativo.
    Se considera activa toda solicitud no histórica (historical IS FALSE) cuyo estatus
    pertenezca al ciclo operativo vigente:
      - STAT-003 (Nuevo)
      - STAT-004 (Pendiente)
      - STAT-005 (Planificada)
      - STAT-006 (En proceso)

    Diseño fail-closed: no silencia excepciones para impedir que un error de base de datos
    evada el bloqueo de integridad referencial (CU-19).
    """
    count = (
        db.session.query(func.count(Request.id))
        .join(Status, Request.status_id == Status.id)
        .filter(
            Request.training_id == training_id,
            Request.historical.is_(False),
            Status.status_code.in_(ACTIVE_REQUEST_STATUS_CODES)
        )
        .scalar()
    )
    return count or 0


def toggle_module_status(module_id: int, user_id: int) -> Tuple[bool, str, Optional[TrainingModule], int]:
    """
    Alterna el estatus operativo (is_active) de un Módulo Rector.
    
    Reglas de negocio:
      - Inactivación (Desincorporación): Si is_active es True, se valida estrictamente
        que el módulo no posea temas formativos activos asociados. Si posee al menos uno,
        se rechaza la operación informando el total de temas activos.
        Al inactivarse, su orden de visualización (order_index) se traslada a la última posición.
      - Activación (Reactivación): Si is_active es False, se reactiva inmediatamente y su
        orden de visualización (order_index) se posiciona de primero (1), desplazando a los demás.
      - Auditoría: Registra el evento en la bitácora (sages.binnacles).
      
    Returns:
      Tuple[bool (éxito), str (mensaje), Optional[TrainingModule], int (temas_activos_pendientes)]
    """
    try:
        module = TrainingModule.query.get(module_id)
        if not module:
            return False, "Módulo Rector no encontrado.", None, 0

        old_status = module.is_active
        module._skip_auto_audit = True

        if old_status:
            # 1. Validación estricta: verificar temas activos asociados
            active_topics_count = count_active_trainings_for_module(module.id)
            if active_topics_count > 0:
                return (
                    False,
                    f'No se puede desincorporar el Módulo Rector "{module.name}" porque posee '
                    f"{active_topics_count} tema(s) formativo(s) activo(s) asociado(s). "
                    f"Debe desincorporar o reasignar dichos temas antes de proceder a inactivar el módulo.",
                    module,
                    active_topics_count
                )

            # Inactivar módulo y mover su posición a la última
            module.is_active = False
            max_order = db.session.query(func.max(TrainingModule.order_index)).scalar() or 0
            module.order_index = max_order + 1
            estado_str = "desincorporado (inactivado)"

        else:
            # Reactivar módulo y mover su posición a la primera (desplazar a los demás)
            module.is_active = True
            db.session.query(TrainingModule).filter(TrainingModule.id != module.id).update(
                {TrainingModule.order_index: TrainingModule.order_index + 1}
            )
            module.order_index = 1
            estado_str = "reactivado (activado)"

        module.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Registro en bitácora de auditoría
        try:
            from app.binnacle.services import BinnacleService
            from app.binnacle.types import AuditModule, AuditAction, AuditStatus

            BinnacleService.create_log_entry(
                module=AuditModule.TRAININGS.value,
                action_type=AuditAction.CAMBIO_ESTATUS_MODULO_RECTOR.value,
                description=f"El Módulo Rector '{module.name}' ({module.module_code}) ha sido {estado_str} exitosamente.",
                target_table='sages.training_modules',
                record_id=module.id,
                status=AuditStatus.MODIFICADO.value,
                old_values={'is_active': old_status},
                new_values={'is_active': module.is_active}
            )
        except Exception as audit_err:
            logger.error(f"[trainings.services.toggle_module_status] Error registrando bitácora: {audit_err}")

        # Notificación Post-Commit: Cambio de disponibilidad de módulo rector
        _notify_module_status_changed(module, user_id)

        logger.info(
            f"[trainings.services.toggle_module_status] Módulo {module.id} ({module.module_code}) "
            f"ha sido {estado_str} por el usuario {user_id}."
        )

        return True, f"El Módulo Rector '{module.name}' ha sido {estado_str} exitosamente.", module, 0

    except Exception as e:
        db.session.rollback()
        logger.error(f"[trainings.services.toggle_module_status] Error al cambiar estatus del módulo {module_id}: {e}")
        return False, f"Ocurrió un error inesperado al cambiar el estatus del módulo: {str(e)}", None, 0
