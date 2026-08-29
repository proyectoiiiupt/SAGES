"""
pre_registration/routes.py
---------------------------
Rutas públicas para el flujo de pre-registro institucional.
No requieren autenticación. Todos los endpoints devuelven JSON para
ser consumidos via AJAX, excepto el GET principal que renderiza el HTML.

Cómo funciona la validación con WTForms:
  1. Se extrae el payload JSON del request con request.get_json().
  2. Se instancia el formulario correspondiente con Form(data=payload).
     El argumento `data` (dict) alimenta los campos directamente,
     sin necesidad de pasar un objeto request.form multipart.
  3. Se llama form.validate() → True si todo es válido.
  4. Si falla, collect_errors(form) aplana form.errors a lista de strings.

Protección CSRF:
  - Flask-WTF valida automáticamente el header X-CSRFToken en cada
    request POST no-exento. El token es inyectado en el HTML como
    meta tag y leído por pre_registration.js.
  - Los endpoints GET de catálogos están exentos (@csrf.exempt) porque
    son de solo lectura y no modifican estado del servidor.
"""

from flask import request, jsonify, render_template, current_app
import json
import time
import requests as http_requests
import threading
from app.models.institution_type_model import InstitutionType
from app.pre_registration import pre_registration_bp
from app.pre_registration.forms import (
    PlantelCodeForm,
    EmailCheckForm,
    CedulaCheckForm,
    InstitutionForm,
    PersonForm,
    collect_errors,
)
from app.pre_registration import services
from app.extensions import csrf, limiter
from app.utils.file_handler import save_evidence_file, FileValidationError


# ─────────────────────────────────────────────
# Vista principal (renderiza el template HTML)
# ─────────────────────────────────────────────
# Cache simple en memoria para los catálogos
_catalogs_cache = {}
_catalogs_cache_time = 0
_catalogs_lock = threading.Lock()

def get_all_catalogs():
    """
    Obtiene todos los catálogos estáticos necesarios para el formulario de pre-registro.
    
    Utiliza un caché en memoria simple para evitar consultas recurrentes a la base 
    de datos durante una hora. Si el caché expira o está vacío, recarga los datos 
    desde los servicios correspondientes de forma segura mediante un hilo (lock).

    Returns:
        dict: Diccionario que contiene listas de diccionarios para 'institution_types', 
              'institution_scopes', 'institution_deps', 'states', 'positions', y 'educational_levels'.
    """
    global _catalogs_cache, _catalogs_cache_time
    # Cache por 1 hora
    with _catalogs_lock:
        if time.time() - _catalogs_cache_time > 3600 or not _catalogs_cache:
            _catalogs_cache = {
                'institution_types': services.get_institution_types(),
                'institution_scopes': services.get_institution_scopes(),
                'institution_deps': services.get_institution_dependencies(),
                'states': services.get_states(),
                'positions': services.get_positions(),
                'educational_levels': services.get_educational_levels(),
            }
            _catalogs_cache_time = time.time()
    return _catalogs_cache

@pre_registration_bp.route('/', methods=['GET'])
def register():
    """
    Renderiza el formulario multi-paso de pre-registro.
    
    Inyecta los catálogos estáticos directamente en el template HTML para
    evitar múltiples peticiones AJAX al momento de cargar la página inicial.

    Returns:
        str: El HTML renderizado de la vista de pre-registro.
    """
    catalogs = get_all_catalogs()
    return render_template('public/pre_registration.html', catalogs=catalogs)


# ─────────────────────────────────────────────
# Paso 0 — Validación del código de plantel
# ─────────────────────────────────────────────
@pre_registration_bp.route('/validar-plantel', methods=['POST'])
@limiter.limit("5 per minute")
def validate_plantel():
    """
    Verifica que el código de plantel tenga formato válido y evalúa su disponibilidad.

    Flujo:
      1. WTForms valida X-CSRFToken. Retorna 400 si falta o es inválido.
      2. PlantelCodeForm valida el formato estructural del código.
      3. Consulta la base de datos para verificar si la institución ya existe y 
         evalúa su estado actual.

    Returns:
        tuple: Respuesta JSON y código de estado HTTP.
            - 200: Si el código es válido y está disponible.
            - 400: Si el formato es inválido, el CSRF está ausente, o la institución 
                   no está activa ni disponible para registros.
            - 409: Si la institución ya existe y está disponible para vinculación.
    """
    payload = request.get_json(silent=True) or {}

    # Instanciar form con los datos JSON (data= acepta dict directamente)
    form = PlantelCodeForm(data=payload)

    if not form.validate():
        errors = collect_errors(form)
        first_error = errors[0] if errors else 'Datos inválidos.'
        return jsonify({'error': first_error}), 400

    # Usar el valor limpio que WTForms procesó (strip aplicado por el field)
    clean_code = form.plantel_code.data.strip()

    inst = services.get_institution_by_plantel_code(clean_code)

    if inst:
        # Validar el estatus de la institución (solo se permiten asociaciones a instituciones Activas)
        status_code = inst.status.status_code if inst.status else None
        
        if status_code == 'STAT-004': # Pendiente
            return jsonify({
                'error': 'El código de plantel ingresado no está disponible para nuevos registros en este momento. Verifique con su coordinación.'
            }), 400
            
        elif status_code != 'STAT-001': # Cualquier otro estatus que no sea Activo (ej. Inactivo)
            return jsonify({
                'error': 'El código de plantel ingresado no está disponible para nuevos registros en este momento. Verifique con su coordinación.'
            }), 400

        parish = inst.parish
        muni = parish.municipality if parish else None
        state = muni.state if muni else None
        
        geo_parts = [p.name for p in [state, muni, parish] if p]
        geo_str = ' / '.join(geo_parts)
        address_str = f"{geo_str} — {inst.address}" if geo_str and inst.address else (inst.address or '—')

        return jsonify({
            'error': 'Esta institución ya está registrada. Puede solicitar acceso como representante, o iniciar sesión si ya posee cuenta.',
            'institution': {
                'name': inst.institution_name,
                'type': inst.institution_type.name if inst.institution_type else '—',
                'scope': inst.institution_scope.name if inst.institution_scope else '—',
                'dependency': inst.institution_dependency.name if inst.institution_dependency else '—',
                'address': address_str
            }
        }), 409

    return jsonify({'available': True, 'plantel_code': clean_code}), 200


# ─────────────────────────────────────────────
# Paso 2 — Validación previa del correo
# ─────────────────────────────────────────────
@pre_registration_bp.route('/validar-correo', methods=['POST'])
@limiter.limit("10 per minute")
def validate_email():
    """
    Verifica que el correo electrónico tenga un formato válido y no exista previamente en BD.
    
    Se invoca de forma asíncrona antes del envío (submit) final para proporcionar
    retroalimentación inmediata al usuario en la interfaz.

    Returns:
        tuple: Respuesta JSON y código de estado HTTP.
            - 200: Si el correo electrónico es válido y está disponible.
            - 400: Si el formato del correo es inválido.
            - 409: Si el correo electrónico ya se encuentra registrado.
    """
    payload = request.get_json(silent=True) or {}

    form = EmailCheckForm(data=payload)

    if not form.validate():
        errors = collect_errors(form)
        first_error = errors[0] if errors else 'Datos inválidos.'
        return jsonify({'error': first_error}), 400

    clean_email = form.email.data.strip().lower()

    if not services.is_email_available(clean_email):
        return jsonify({
            'error': 'Este correo no está disponible para un nuevo registro. Si ya posee una cuenta, por favor inicie sesión o utilice la opción de recuperar contraseña.'
        }), 409

    return jsonify({'available': True, 'email': clean_email}), 200


# ─────────────────────────────────────────────
# Paso 2 — Validación previa de la cédula
# ─────────────────────────────────────────────
@pre_registration_bp.route('/validar-cedula', methods=['POST'])
@limiter.limit("10 per minute")
def validate_cedula():
    """
    Verifica que el número de cédula tenga un formato válido y no exista previamente en BD.
    
    Se invoca de forma asíncrona antes del envío (submit) final para proporcionar
    retroalimentación inmediata al usuario en la interfaz.

    Returns:
        tuple: Respuesta JSON y código de estado HTTP.
            - 200: Si el número de identificación es válido y está disponible.
            - 400: Si el formato del número de identificación es inválido.
            - 409: Si el número de identificación ya se encuentra registrado.
    """
    payload = request.get_json(silent=True) or {}
    form = CedulaCheckForm(data=payload)

    if not form.validate():
        errors = collect_errors(form)
        first_error = errors[0] if errors else 'Datos inválidos.'
        return jsonify({'error': first_error}), 400

    clean_cedula = form.identification_number.data.strip()

    if not services.is_identification_available(clean_cedula):
        return jsonify({
            'error': 'Este número de identificación no está disponible para registro. Si cree que esto es un error o ya tiene cuenta, contacte a soporte.'
        }), 409

    return jsonify({'available': True, 'identification_number': clean_cedula}), 200


# ─────────────────────────────────────────────
# Catálogos dinámicos (GET, sin CSRF)
# Los catálogos estáticos se inyectan en el HTML. Solo mantenemos los
# que dependen de una selección previa (cascada).
# ─────────────────────────────────────────────


@pre_registration_bp.route('/catalog/municipios/<string:state_code>', methods=['GET'])
@csrf.exempt
def catalog_municipalities(state_code: str):
    """
    Devuelve los municipios correspondientes al estado indicado.

    Args:
        state_code (str): Código de estado (ej: 'VEN-DC'). No confundir con el ID de la base de datos.

    Returns:
        tuple: Respuesta JSON con la lista de municipios y el código de estado HTTP (200).
               Retorna 400 si no se provee un código de estado válido.
    """
    if not state_code:
        return jsonify([]), 400
    return jsonify(services.get_municipalities_by_state(state_code)), 200


@pre_registration_bp.route('/catalog/parroquias/<string:municipality_code>', methods=['GET'])
@csrf.exempt
def catalog_parishes(municipality_code: str):
    """
    Devuelve las parroquias correspondientes al municipio indicado.

    Args:
        municipality_code (str): Código del municipio a consultar.

    Returns:
        tuple: Respuesta JSON con la lista de parroquias y el código de estado HTTP (200).
               El campo 'id' de la respuesta corresponde al ID primario en base de datos.
               Retorna 400 si no se provee un código de municipio válido.
    """
    if not municipality_code:
        return jsonify([]), 400
    return jsonify(services.get_parishes_by_municipality(municipality_code)), 200



# ─────────────────────────────────────────────
# Submit final — Persistencia del pre-registro
# ─────────────────────────────────────────────
@pre_registration_bp.route('/completar', methods=['POST'])
@limiter.limit("2 per hour")
def complete_registration():
    """
    Orquesta la validación y persistencia del formulario completo de pre-registro.

    Flujo:
      1. Flask-WTF verifica X-CSRFToken. Si falla o falta, aborta con 400 automáticamente.
      2. Extrae el payload JSON y el archivo binario del multipart/form-data.
      3. Valida el CAPTCHA con el servicio Cloudflare Turnstile.
      4. Ejecuta InstitutionForm y PersonForm para validar las respectivas secciones lógicas.
      5. Según la bandera 'join_existing', se bifurca para unirse a una institución o 
         crear una nueva (llamando a la capa de servicios).

    Returns:
        tuple: Respuesta JSON y código de estado HTTP.
            - 201: Pre-registro completado e insertado exitosamente.
            - 400: Errores de validación o datos faltantes.
            - 409: Conflicto por datos duplicados (plantel, cédula, email).
            - 500: Error interno del servidor en BD o conexión externa.
    """
    # ── Parsear payload JSON embebido en el multipart ─────────────────
    raw_payload = request.form.get('payload', '{}')
    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        return jsonify({'errors': ['Datos del formulario inválidos.']}), 400

    # ── Extraer archivo y tipo de documento ───────────────────────────────
    evidence_file = request.files.get('evidence')
    document_type = request.form.get('document_type')
    if not evidence_file or not document_type:
        return jsonify({'errors': ['Por favor, seleccione el tipo de documento y adjunte su comprobante para poder continuar.']}), 400

    # ── Validación de CAPTCHA (Cloudflare Turnstile) ──────────────────
    captcha_token = payload.get('captcha_token')
    if not captcha_token:
        return jsonify({'errors': ['Falta el token de seguridad CAPTCHA.']}), 400

    secret_key = current_app.config.get('CAPTCHA_SECRET_KEY')
    verify_url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    try:
        cf_response = http_requests.post(verify_url, data={
            'secret': secret_key,
            'response': captcha_token
        }, timeout=5)
        cf_result = cf_response.json()
        if not cf_result.get('success'):
            return jsonify({'errors': ['No pudimos verificar su validación de seguridad (CAPTCHA). Por favor, marque la casilla nuevamente.']}), 400
    except http_requests.exceptions.RequestException:
        return jsonify({'errors': ['Error de comunicación con el servicio de seguridad. Intente más tarde.']}), 400

    # ── Determinar la ruta según el flag del frontend ──────────────────────
    join_existing = payload.get('join_existing', False)

    if join_existing:
        # ── RUTA B: Unirse a una institución existente ────────────────
        plantel_code_existing = payload.get('plantel_code_existing', '').strip()
        if not plantel_code_existing:
            return jsonify({'errors': ['El código de plantel de la institución es requerido.']}), 400

        # Validar solo la sección de persona
        person_raw  = payload.get('person', {})
        person_form = PersonForm(data=person_raw)

        person_errors: list[str] = []
        if not person_form.validate():
            person_errors.extend(collect_errors(person_form))
        if person_errors:
            return jsonify({'errors': person_errors}), 400

        person_data = {
            'identification_type':   person_form.identification_type.data,
            'identification_number': person_form.identification_number.data.strip(),
            'first_name':            person_form.first_name.data.strip(),
            'second_name':           (person_form.second_name.data or '').strip(),
            'last_name':             person_form.last_name.data.strip(),
            'middle_name':           (person_form.middle_name.data or '').strip(),
            'email':                 person_form.email.data.strip().lower(),
            'mobile':                person_form.mobile.data.strip(),
            'phone':                 (person_form.phone.data or '').strip() or None,
            'position_id':           person_form.position_id.data,
        }

        ok, message, status_code = services.join_existing_institution(
            plantel_code=plantel_code_existing,
            person_data=person_data,
            evidence_file=evidence_file,
            document_type=document_type,
        )

    else:
        # ── RUTA A: Registrar nueva institución (flujo original) ──────────
        inst_raw   = payload.get('institution', {})
        person_raw = payload.get('person', {})

        # Validar ambas secciones con WTForms
        inst_form   = InstitutionForm(data=inst_raw)
        person_form = PersonForm(data=person_raw)

        all_errors: list[str] = []
        if not inst_form.validate():
            all_errors.extend(collect_errors(inst_form))
        if not person_form.validate():
            all_errors.extend(collect_errors(person_form))

        if all_errors:
            return jsonify({'errors': all_errors}), 400

        # Resolver tipo de institución
        inst_type_code = inst_form.institution_type_id.data.strip().upper()
        inst_type_obj = InstitutionType.query.filter_by(
            institution_type_code=inst_type_code
        ).first()
        if not inst_type_obj:
            return jsonify({'errors': ['El tipo de institución seleccionado no es válido.']}), 400

        # Validar niveles educativos
        educational_levels = inst_raw.get('educational_levels', [])
        if inst_type_code not in ('INST-005', 'INST-002') and not educational_levels:
            return jsonify({'errors': ['Debe seleccionar al menos un nivel educativo.']}), 400

        # Formatear nombre
        raw_name    = inst_form.institution_name.data.strip()
        raw_prefix  = (inst_form.institution_prefix.data or '').strip() or None
        raw_acronym = (inst_form.institution_acronym.data or '').strip() or None
        formatted_name = services.format_institution_name(
            inst_type_code=inst_type_code,
            raw_name=raw_name,
            prefix=raw_prefix,
            acronym=raw_acronym,
        )

        inst_data = {
            'plantel_code':              inst_form.plantel_code.data.strip(),
            'institution_name':          formatted_name,
            'institution_type_id':       inst_type_obj.id,
            'institution_scope_id':      inst_form.institution_scope_id.data,
            'institution_dependency_id': inst_form.institution_dependency_id.data,
            'phone':                     (inst_form.phone.data or '').strip() or None,
            'parish_id':                 inst_form.parish_id.data,
            'address':                   inst_form.address.data.strip(),
            'educational_levels':        inst_raw.get('educational_levels', []),
        }

        person_data = {
            'identification_type':   person_form.identification_type.data,
            'identification_number': person_form.identification_number.data.strip(),
            'first_name':            person_form.first_name.data.strip(),
            'second_name':           (person_form.second_name.data or '').strip(),
            'last_name':             person_form.last_name.data.strip(),
            'middle_name':           (person_form.middle_name.data or '').strip(),
            'email':                 person_form.email.data.strip().lower(),
            'mobile':                person_form.mobile.data.strip(),
            'phone':                 (person_form.phone.data or '').strip() or None,
            'position_id':           person_form.position_id.data,
        }

        ok, message, status_code = services.create_pre_registration(inst_data, person_data, evidence_file, document_type)

    if not ok:
        return jsonify({'error': message}), status_code

    return jsonify({'message': message}), status_code


# ─────────────────────────────────────────────
# Manejo de Errores (Rate Limit)
# ─────────────────────────────────────────────
@pre_registration_bp.errorhandler(429)
def ratelimit_handler(e):
    """
    Captura y maneja la excepción 429 Too Many Requests de Flask-Limiter.

    Args:
        e: Objeto de la excepción capturada.

    Returns:
        tuple: Respuesta JSON amigable para el frontend (AJAX) y código HTTP 429.
    """
    return jsonify({
        'error': "Ha superado el límite de intentos permitidos. Por favor, espere unos minutos antes de volver a intentar."
    }), 429