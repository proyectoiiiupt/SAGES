"""
Rutas del Módulo de Formación (Trainings)
Bloque 1: Hub de Navegación por Módulos – Vista Principal / Landing.

Endpoints:
  GET  /training/              → index()            – Renderiza el Hub
  GET  /training/api/counts    → get_module_counts() – Conteos asíncronos por módulo y rol
"""

import re
import io
from datetime import datetime, time
from flask import render_template, jsonify, abort, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from sqlalchemy import func
from app.trainings import trainings_bp
import unicodedata
from app.trainings.forms import TrainingModuleForm, TrainingForm, ModuleEditForm, TrainingEditForm
from app.models.training_module_model import TrainingModule
from app.models.training_model import Training
from app.models.status_model import Status
from app.models.request_model import Request
from app.trainings.services import (
    get_module_by_id, 
    update_training_module,
    generate_training_code, 
    is_training_name_duplicated, 
    create_training,
    parse_training_file
)
from app.decorators import check_permissions, role_required
from app.extensions import db, limiter


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _get_user_role() -> str:
    """Devuelve el nombre del primer rol del usuario en sesión o 'applicant'."""
    if current_user.is_authenticated and getattr(current_user, 'roles_assoc', None):
        return current_user.roles_assoc[0].role.name
    return 'applicant'


def _is_super_admin() -> bool:
    return _get_user_role() == 'super_admin'


def _is_admin() -> bool:
    """True para super_admin y state_admin."""
    return _get_user_role() in ('super_admin', 'state_admin')


# ---------------------------------------------------------------------------
# Ruta principal: Hub de Navegación
# ---------------------------------------------------------------------------

@trainings_bp.route('/', methods=['GET'])
@login_required
@check_permissions('view_training_catalog')
def index():
    """
    Vista de entrada al catálogo de Formación.
    Renderiza los 4 Módulos Rectores de la UREE en una cuadrícula responsiva.
    """
    modules = (
        TrainingModule.query
        .filter_by(is_active=True)
        .order_by(TrainingModule.order_index)
        .all()
    )

    return render_template(
        'trainings/hub.html',
        modules=modules,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role(),
    )


# ---------------------------------------------------------------------------
# Endpoint API: Conteos asíncronos de temas por módulo
# ---------------------------------------------------------------------------

@trainings_bp.route('/api/counts', methods=['GET'])
@login_required
def get_module_counts():
    """
    Devuelve el conteo de temas formativos por módulo rector, adaptado al rol.

    Lógica de filtrado:
      – Base obligatoria: Training.deleted_at IS NULL (borrado lógico).
      – Rol applicant    → Solo temas con status_code == 'STAT-001' (Activos).
      – Roles admin      → Temas activos (STAT-001) + total no eliminado.

    Respuesta JSON:
    {
      "success": true,
      "is_admin": <bool>,
      "counts": {
        "<module_id>": { "active": <int>, "total": <int> }
      }
    }
    """
    role = _get_user_role()
    is_admin = role in ('super_admin', 'state_admin')

    try:
        # Sub-consulta base: temas no eliminados
        base_q = (
            db.session.query(
                Training.training_module_id,
                func.count(Training.id).label('total')
            )
            .filter(Training.deleted_at.is_(None))
            .group_by(Training.training_module_id)
        )

        # Sub-consulta de temas activos (STAT-001) sin eliminar
        active_q = (
            db.session.query(
                Training.training_module_id,
                func.count(Training.id).label('active')
            )
            .join(Status, Training.status_id == Status.id)
            .filter(
                Training.deleted_at.is_(None),
                Status.status_code == 'STAT-001'
            )
            .group_by(Training.training_module_id)
        )

        total_rows = {row.training_module_id: row.total for row in base_q.all()}
        active_rows = {row.training_module_id: row.active for row in active_q.all()}

        # Obtener todos los módulos activos para incluirlos (aunque tengan 0 temas)
        module_ids = [
            m.id for m in TrainingModule.query.filter_by(is_active=True).all()
        ]

        counts = {}
        for mid in module_ids:
            active_count = active_rows.get(mid, 0)
            total_count = total_rows.get(mid, 0)

            if is_admin:
                counts[str(mid)] = {
                    'active': active_count,
                    'total': total_count
                }
            else:
                # Para solicitantes solo se exponen los temas activos
                counts[str(mid)] = {
                    'active': active_count,
                    'total': active_count
                }

        return jsonify({
            'success': True,
            'is_admin': is_admin,
            'counts': counts
        }), 200

    except Exception as e:
        current_app.logger.error(f"[trainings.get_module_counts] Error al calcular conteos: {e}")
        return jsonify({
            'success': False,
            'message': 'No se pudieron cargar los contadores en este momento.',
            'counts': {}
        }), 500


# ---------------------------------------------------------------------------
# Bloque 2: Edición de Módulo Rector (Exclusivo Super Administrador)
# ---------------------------------------------------------------------------

@trainings_bp.route('/module/edit/<int:module_id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def edit_module(module_id: int):
    """
    Vista exclusiva para Super Administrador.
    Permite actualizar nombre, descripción u orden de visualización del módulo rector.
    Ruta canónica: /training/module/edit/<id> (con alias en /module/edit/<id>).
    """
    module = get_module_by_id(module_id)
    if not module:
        abort(404)

    form = ModuleEditForm(module_id=module.id)

    if request.method == 'GET':
        form.name.data = module.name
        form.description.data = module.description

    elif form.validate_on_submit():
        success, message = update_training_module(
            module=module,
            name=form.name.data,
            description=form.description.data,
            user_id=current_user.id
        )
        if success:
            flash(f'Módulo rector "{module.name}" actualizado correctamente.', 'success')
            return redirect(url_for('trainings.index'))
        else:
            flash(message, 'danger')

    return render_template(
        'trainings/edit_module.html',
        form=form,
        module=module,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )


# ---------------------------------------------------------------------------
# Vista Tabular Maestra: Listado Administrativo de Formaciones
# Bloque 3: Gestión Administrativa Centralizada
# ---------------------------------------------------------------------------

@trainings_bp.route('/list', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def list_all():
    """
    Vista alternativa tabular accesible para Super Administrador y Administradores Estadales.
    Permite buscar por término, filtrar por Módulo, Estatus (Activo/Inactivo) y Fecha de creación,
    con paginación de 10 en 10 registros.

    Nota de alcance:
      - La ejecución de acciones de edición y borrado lógico está reservada para una tarea posterior.
      - La consulta filtra temas no eliminados mediante la cláusula Training.deleted_at.is_(None).
    """
    # 1. Validación de tipos numéricos para paginación
    page = request.args.get('page', 1, type=int)
    if not page or page < 1:
        page = 1

    per_page = request.args.get('per_page', 10, type=int)
    if not per_page or per_page < 1 or per_page > 50:
        per_page = 10

    # 2. Parámetros de búsqueda y filtros
    search_query = request.args.get('search', '').strip()
    filter_module = request.args.get('module_id', '').strip()
    filter_status = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    filters = {
        'search': search_query,
        'module_id': filter_module,
        'status': filter_status,
        'date_from': date_from,
        'date_to': date_to,
        'per_page': per_page
    }

    try:
        # Consulta base: temas no eliminados (borrado lógico: Training.deleted_at IS NULL)
        # Nota: La ejecución de borrado lógico y edición se implementará en una tarea posterior.
        query = (
            Training.query
            .join(TrainingModule, Training.training_module_id == TrainingModule.id)
            .join(Status, Training.status_id == Status.id)
            .filter(Training.deleted_at.is_(None))
        )

        # Búsqueda por nombre del tema formativo
        if search_query:
            sanitized_term = search_query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_pattern = f"%{sanitized_term}%"
            query = query.filter(Training.name.ilike(search_pattern))

        # Filtro por Módulo Rector
        if filter_module and filter_module.isdigit():
            query = query.filter(Training.training_module_id == int(filter_module))

        # Filtro por Estatus (Activo/Inactivo: STAT-001 / STAT-002 o status_id)
        if filter_status:
            if filter_status.isdigit():
                query = query.filter(Training.status_id == int(filter_status))
            else:
                query = query.filter(Status.status_code == filter_status)

        # Filtro por Rango de Fecha de Creación
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Training.created_at >= dt_from)
            except ValueError:
                pass

        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d')
                dt_to = datetime.combine(dt_to.date(), time.max)
                query = query.filter(Training.created_at <= dt_to)
            except ValueError:
                pass

        # Ordenamiento natural secuencial por número de formación
        query = query.order_by(Training.id.asc())

        # Paginación optimizada usando SQLAlchemy con offset y limit (mediante paginate)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        trainings = pagination.items

        # Catálogos de opciones para filtros
        modules = (
            TrainingModule.query
            .filter_by(is_active=True)
            .order_by(TrainingModule.order_index)
            .all()
        )
        statuses = (
            Status.query
            .filter(Status.status_code.in_(['STAT-001', 'STAT-002']))
            .order_by(Status.id)
            .all()
        )

        return render_template(
            'trainings/list.html',
            trainings=trainings,
            pagination=pagination,
            modules=modules,
            statuses=statuses,
            filters=filters,
            is_super_admin=_is_super_admin(),
            is_admin=_is_admin(),
            user_role=_get_user_role()
        )

    except Exception as e:
        current_app.logger.error(f"[trainings.list_all] Error al obtener listado de formaciones: {e}")
        return render_template(
            'trainings/list.html',
            trainings=[],
            pagination=None,
            modules=TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all(),
            statuses=Status.query.filter(Status.status_code.in_(['STAT-001', 'STAT-002'])).all(),
            filters=filters,
            is_super_admin=_is_super_admin(),
            is_admin=_is_admin(),
            user_role=_get_user_role(),
            error_message="No se pudo cargar el listado de formaciones en este momento."
        )


# ---------------------------------------------------------------------------
# Registro de Nuevo Módulo Rector
# ---------------------------------------------------------------------------

def _generate_next_module_code() -> str:
    """
    Genera el siguiente código correlativo MOD-XXX en backend.
    Extrae la secuencia numérica de códigos existentes con prefijo 'MOD-' y genera el próximo (ej. MOD-005).
    """
    all_codes = db.session.query(TrainingModule.module_code).all()
    max_num = 0
    for (code,) in all_codes:
        if code and code.startswith('MOD-'):
            suffix = code[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    next_num = max_num + 1
    return f"MOD-{next_num:03d}"


def _get_next_order_index() -> int:
    """Calcula el siguiente índice de orden disponible."""
    max_order = db.session.query(func.max(TrainingModule.order_index)).scalar()
    return (max_order or 0) + 1


@trainings_bp.route('/module/new', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def new_module():
    """
    Ruta para registrar un nuevo Módulo Rector.
    - Captura: nombre, descripción y orden de visualización.
    - El código MOD-XXX es generado internamente por la base de datos/backend.
    - Solo accesible para usuarios con rol 'super_admin'.
    """
    form = TrainingModuleForm()

    # Pre-calcular sugerencia de código para el formulario
    suggested_code = _generate_next_module_code()

    if request.method == 'GET':
        form.module_code.data = suggested_code

    if form.validate_on_submit():
        try:
            # Siempre se autogenera el código en backend para evitar manipulación manual
            final_code = _generate_next_module_code()

            new_mod = TrainingModule(
                module_code=final_code,
                name=form.name.data.strip(),
                description=form.description.data.strip(),
                order_index=_get_next_order_index(),
                is_active=True
            )
            db.session.add(new_mod)
            db.session.commit()

            flash(f'Módulo Rector "{new_mod.name}" registrado exitosamente.', "success")
            return redirect(url_for('trainings.index'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[trainings.new_module] Error al registrar módulo: {e}")
            flash("Ocurrió un error inesperado al registrar el Módulo Rector. Intente nuevamente.", "danger")
    elif request.method == 'POST':
        flash("Por favor, verifica los campos obligatorios del formulario.", "warning")

    return render_template(
        'trainings/module_new.html',
        form=form,
        suggested_code=suggested_code,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )

# ---------------------------------------------------------------------------
# Registro de Nuevo Tema Formativo
# ---------------------------------------------------------------------------

@trainings_bp.route('/api/validate-name', methods=['GET'])
@login_required
@role_required('super_admin')
def validate_training_name_api():
    """
    Endpoint AJAX para validar duplicidad con normalización extrema (ignora tildes, puntuación y espacios)
    """
    name = request.args.get('name', '').strip()
    module_id = request.args.get('module_id', type=int)
    exclude_id = request.args.get('exclude_id', type=int)

    if not name or not module_id:
        return jsonify({'valid': False, 'exists': False, 'message': 'Faltan parámetros requeridos.'}), 400

    # 1. Traemos todos los temas del módulo seleccionado (excluyendo el actual si estamos editando)
    query = Training.query.filter(
        Training.training_module_id == module_id,
        Training.deleted_at.is_(None)
    )

    if exclude_id:
        query = query.filter(Training.id != exclude_id)
        
    all_module_trainings = query.all()

    # 2. Función de normalización extrema (se queda solo con letras minúsculas y números)
    def normalize_text(text):
        if not text: 
            return ""
        # Pasar a minúsculas
        t = text.lower()
        # Eliminar tildes/acentos
        t = unicodedata.normalize('NFKD', t).encode('ASCII', 'ignore').decode('utf-8')
        # Eliminar TODO lo que no sea una letra o número (espacios, comas, puntos, etc.)
        t = re.sub(r'[^a-z0-9]', '', t)
        return t

    name_to_check = normalize_text(name)
    existing = None
    
    # 3. Comparamos
    for t in all_module_trainings:
        if normalize_text(t.name) == name_to_check:
            existing = t
            break

    if existing:
        return jsonify({
            'valid': False,
            'exists': True,
            'message': f'Ya existe un tema formativo con este título ({existing.training_code}).'
        })

    return jsonify({'valid': True, 'exists': False, 'message': 'Título disponible.'})


@trainings_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
@limiter.limit("20 per minute", methods=["POST"], key_func=lambda: str(current_user.id))
def new_training():
    """
    Ruta para registrar un nuevo Tema Formativo.
    """
    form = TrainingForm()

    if request.method == 'GET':
        preselected_module = request.args.get('module_id', type=int)
        if preselected_module:
            form.training_module_id.data = preselected_module

    if form.validate_on_submit():
        module_id = form.training_module_id.data
        name_clean = form.name.data.strip()
        desc_clean = form.description.data.strip()

        try:
            new_training_obj = create_training(
                module_id=module_id,
                name=name_clean,
                description=desc_clean
            )
            flash(f'Tema Formativo "{new_training_obj.name}" registrado exitosamente.', 'success')
            return redirect(url_for('trainings.index'))

        except ValueError as ve:
            flash(str(ve), 'danger')
            return render_template(
                'trainings/training_new.html',
                form=form,
                is_super_admin=_is_super_admin(),
                is_admin=_is_admin(),
                user_role=_get_user_role()
            )
        except Exception as e:
            current_app.logger.error(f"[trainings.new_training] Error al registrar tema: {e}")
            flash('Ocurrió un error inesperado al registrar el tema formativo. Intente nuevamente.', 'danger')

    return render_template(
        'trainings/training_new.html',
        form=form,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )


@trainings_bp.route('/api/active-modules', methods=['GET'])
@login_required
def api_active_modules():
    """
    Endpoint API para cargar dinámicamente los Módulos Rectores activos en el frontend.
    """
    modules = TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all()
    return jsonify([{'id': m.id, 'name': f"{m.module_code} – {m.name}"} for m in modules])


# ---------------------------------------------------------------------------
# Detalle de Tema Formativo
# ---------------------------------------------------------------------------

@trainings_bp.route('/detail/<int:id>', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin', 'applicant')
def view_training_detail(id: int):
    training = (
        Training.query
        .join(TrainingModule, Training.training_module_id == TrainingModule.id)
        .join(Status, Training.status_id == Status.id)
        .filter(Training.id == id, Training.deleted_at.is_(None))
        .first_or_404()
    )

    atendidas_calculadas = (
        db.session.query(func.count(Request.id))
        .join(Status, Request.status_id == Status.id)
        .filter(
            Request.training_id == id,
            Status.status_code == 'STAT-007'
        ).scalar() or 0
    )

    return render_template(
        'trainings/detail.html',
        training=training,
        atendidas=atendidas_calculadas,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )


# ---------------------------------------------------------------------------
# Edición de Tema Formativo
# ---------------------------------------------------------------------------

@trainings_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def edit_training(id: int):
    """
    Ruta para editar un tema formativo existente.
    Si el tema posee solicitudes/preinscripciones asociadas, bloquea el 
    cambio de Módulo Rector para proteger la integridad de los datos.
    """
    # Obtener el tema formativo asegurando que no esté eliminado lógicamente
    training = (
        Training.query
        .filter(Training.id == id, Training.deleted_at.is_(None))
        .first_or_404()
    )

    form = TrainingEditForm(obj=training, training_id=training.id)

    # Cargar las opciones del selector de Módulos Rectores activos
    modules = TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all()
    form.training_module_id.choices = [(m.id, f"{m.module_code} - {m.name}") for m in modules]

    # Verificar si el tema formativo tiene solicitudes asociadas
    has_requests = (
        db.session.query(func.count(Request.id))
        .filter(Request.training_id == id)
        .scalar()
    ) > 0



    if form.validate_on_submit():
        # Regla estricta: Si tiene solicitudes, se bloquea el cambio de módulo rector
        if has_requests and form.training_module_id.data != training.training_module_id:
            flash('No se puede cambiar el Módulo Rector porque este tema ya posee solicitudes asociadas.', 'danger')
            return redirect(url_for('trainings.edit_training', id=id))

        # --- CANDADO DE SEGURIDAD EXTREMA ANTES DE GUARDAR ---
        import unicodedata, re
        def normalize_text(text):
            if not text: return ""
            t = unicodedata.normalize('NFKD', text.lower()).encode('ASCII', 'ignore').decode('utf-8')
            return re.sub(r'[^a-z0-9]', '', t)
            
        # Determinar en qué módulo se va a guardar
        target_module_id = training.training_module_id if has_requests else form.training_module_id.data
        name_to_check = normalize_text(form.name.data.strip())
        
        # Traer todos los temas de ese módulo (excepto el que estamos editando)
        duplicates = Training.query.filter(
            Training.training_module_id == target_module_id,
            Training.id != id,
            Training.deleted_at.is_(None)
        ).all()
        
        # Si encuentra coincidencia, aborta el guardado
        if any(normalize_text(t.name) == name_to_check for t in duplicates):
            flash('No se pudo actualizar: El título ingresado ya está en uso en este Módulo Rector.', 'danger')
            return redirect(url_for('trainings.edit_training', id=id))
        # --- FIN DEL CANDADO ---

        # Si pasa la prueba, actualizamos los campos de texto limpios de espacios extra
        training.name = form.name.data.strip()
        training.description = form.description.data.strip()
        
        # Solo actualizar el módulo foráneo si no hay restricciones
        if not has_requests:
            training.training_module_id = form.training_module_id.data

        db.session.commit()
        flash('Tema formativo actualizado exitosamente.', 'success')
        return redirect(url_for('trainings.view_training_detail', id=training.id))
    
    return render_template(
        'trainings/training_edit.html',
        form=form,
        training=training,
        has_requests=has_requests,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )



# ---------------------------------------------------------------------------
# Carga Masiva de Temas Formativos
# ---------------------------------------------------------------------------

@trainings_bp.route('/bulk', methods=['GET'])
@login_required
@role_required('super_admin')
def bulk_upload_view():
    """Renderiza la interfaz de carga masiva."""
    modules = TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all()
    return render_template(
        'trainings/training_bulk.html',
        modules=modules,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )


@trainings_bp.route('/bulk/template', methods=['GET'])
@login_required
@role_required('super_admin')
def bulk_upload_template():
    """Genera y descarga la plantilla oficial de Excel para la carga masiva."""
    import openpyxl
    from openpyxl.worksheet.datavalidation import DataValidation
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla Temas"
    
    # Cabeceras requeridas
    headers = ["codigo_modulo", "nombre_tema", "descripcion"]
    ws.append(headers)
    
    # Datos de ejemplo e instrucciones directas
    ws.append([
        "-> Ve a la pestaña 'Catalogo' y copia un valor", 
        "Tema de Ejemplo", 
        "Descripción de ejemplo del tema formativo."
    ])
    
    # Ajuste básico de ancho
    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 50

    # Crear pestaña de Catálogo (sin espacios ni acentos para evitar bugs en la fórmula de Validación)
    ws_catalog = wb.create_sheet(title="Catalogo")
    ws_catalog.append(["Selección", "Nombre", "Descripción"])
    
    # Obtener módulos activos de BD
    modules = TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all()
    
    # Llenar el catálogo y preparar Data Validation
    row_count = 2
    for m in modules:
        code_name = f"{m.module_code} - {m.name}"
        ws_catalog.append([code_name, m.name, m.description])
        row_count += 1
        
    # Ajustar anchos del catálogo
    ws_catalog.column_dimensions['A'].width = 40
    ws_catalog.column_dimensions['B'].width = 40
    ws_catalog.column_dimensions['C'].width = 80
    
    # Aplicar validación de datos apuntando al catálogo (si hay módulos disponibles)
    if row_count > 2:
        # Rango en el catálogo: ej. Catalogo!$A$2:$A$5
        formula = f"=Catalogo!$A$2:$A${row_count - 1}"
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.error = 'Su selección no es válida'
        dv.errorTitle = 'Módulo Inválido'
        dv.prompt = 'Seleccione un Módulo de la lista desplegable'
        dv.promptTitle = 'Selección de Módulo'
        
        # Aplicar a las filas de la columna A en la Plantilla (desde fila 2 hasta la 1000)
        dv.add(f"A2:A1000")
        ws.add_data_validation(dv)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    
    return send_file(
        out,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Plantilla_Carga_Masiva_Temas.xlsx'
    )


@trainings_bp.route('/bulk/preview', methods=['POST'])
@login_required
@role_required('super_admin')
@limiter.limit("10 per minute", key_func=lambda: str(current_user.id))
def bulk_upload_preview():
    """Ejecuta el Dry-Run (análisis) del archivo y retorna resultados en JSON."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se envió ningún archivo.'}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': 'Archivo vacío.'}), 400
        
    try:
        valid_rows, invalid_rows, stats = parse_training_file(file)
        
        valid_preview = []
        for r in valid_rows:
            valid_preview.append({
                'row_index': r['row_number'],
                'module_code': r['module_code'],
                'name': r['name'],
                'description': r['description']
            })
            
        return jsonify({
            'success': True,
            'stats': stats,
            'valid_rows': valid_preview,
            'invalid_rows': invalid_rows
        })
        
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"[bulk_upload_preview] Error: {e}")
        return jsonify({'success': False, 'message': 'Error al procesar el archivo.'}), 500


@trainings_bp.route('/bulk/process', methods=['POST'])
@login_required
@role_required('super_admin')
@limiter.limit("5 per minute", key_func=lambda: str(current_user.id))
def bulk_upload_process():
    """Procesa el archivo y guarda las filas válidas en base de datos."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se envió ningún archivo.'}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': 'Archivo vacío.'}), 400
        
    try:
        valid_rows, invalid_rows, stats = parse_training_file(file)
        
        if not valid_rows:
            return jsonify({
                'success': False, 
                'message': 'No hay filas válidas para procesar.',
                'stats': stats
            }), 400
            
        from app.trainings.services import get_active_status_id, generate_training_code
        
        status_id = get_active_status_id()
        inserted_count = 0
        
        for row in valid_rows:
            new_code = generate_training_code()
            new_training = Training(
                training_code=new_code,
                name=row['name'],
                description=row['description'],
                training_module_id=row['module_id'],
                status_id=status_id
            )
            db.session.add(new_training)
            inserted_count += 1
            
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Se han registrado {inserted_count} temas formativos correctamente.',
            'inserted_count': inserted_count,
            'invalid_count': len(invalid_rows)
        })
        
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[bulk_upload_process] Error guardando carga masiva: {e}")
        return jsonify({'success': False, 'message': 'Ocurrió un error al guardar los registros en BD.'}), 500


@trainings_bp.route('/bulk/download_errors', methods=['POST'])
@login_required
@role_required('super_admin')
@limiter.limit("5 per minute", key_func=lambda: str(current_user.id))
def bulk_download_errors():
    """Recibe la plantilla de carga masiva y devuelve un Excel únicamente con las filas inválidas y su motivo de error."""
    import openpyxl
    from openpyxl.styles import Font, Alignment
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se envió ningún archivo.'}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': 'Archivo vacío.'}), 400
        
    try:
        _, invalid_rows, _ = parse_training_file(file)
        
        if not invalid_rows:
            return jsonify({'success': False, 'message': 'No se detectaron errores en el archivo.'}), 400

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reporte de Errores"
        
        headers = ["codigo_modulo", "nombre_tema", "descripcion", "ERRORES_ENCONTRADOS"]
        ws.append(headers)
        
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center")
            cell.fill = openpyxl.styles.PatternFill(start_color="EF4444", end_color="EF4444", fill_type="solid")

        for row in invalid_rows:
            ws.append([
                row.get('module_input', ''),
                row.get('name_input', ''),
                row.get('desc_input', ''),
                f"[Fila Original: {row.get('row_number', '')}] - {row.get('error', '')}"
            ])
            
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 40
        ws.column_dimensions['C'].width = 50
        ws.column_dimensions['D'].width = 80

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        
        return send_file(
            out,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='Reporte_Errores_Carga_Masiva.xlsx'
        )
        
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"[bulk_download_errors] Error generando reporte: {e}")
        return jsonify({'success': False, 'message': 'Ocurrió un error al generar el archivo de errores.'}), 500