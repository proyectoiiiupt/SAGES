"""
pre_registration/services.py
-----------------------------
Lógica de negocio para el flujo de pre-registro público.

Maneja la generación de códigos únicos, comprobaciones de duplicados, formateo
defensivo de nombres y la persistencia transaccional en base de datos.
Concentra todas las interacciones con los modelos SQLAlchemy para 
mantener los controladores (rutas) limpios.
"""

import os
import uuid
import secrets
import threading
import logging
from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.extensions import db
from app.utils.email_utils import send_preregistration_email

logger = logging.getLogger(__name__)

PENDING_STATUS_CODE = 'STAT-004'
ACTIVE_STATUS_CODE  = 'STAT-001'

# Matriz de reglas de negocio: niveles educativos permitidos por tipo de institución
ALLOWED_EDUCATIONAL_LEVELS = {
    'INST-001': {'EDUL-005', 'EDUL-006'},
    'INST-002': {'EDUL-005'},
    'INST-003': {'EDUL-003', 'EDUL-004'},
    'INST-004': {'EDUL-001', 'EDUL-002'},
    'INST-006': {'EDUL-001', 'EDUL-002', 'EDUL-003', 'EDUL-004'},
    'INST-005': set()
}


def _generate_short_code(prefix: str, model_class, code_field: str) -> str:
    """
    Genera un código único en formato PREFIJO-XXXXXX utilizando un sufijo hexadecimal aleatorio.

    Intenta generar un código único hasta 10 veces para evitar colisiones. Si falla, 
    utiliza un código de respaldo (fallback) con un token seguro más largo.

    Args:
        prefix (str): Prefijo del código (ej. 'INST' o 'PERS').
        model_class: Modelo de SQLAlchemy donde se buscará el código.
        code_field (str): Nombre de la columna que almacena el código en la tabla.

    Returns:
        str: Código único generado.
    """
    for _ in range(10):
        candidates = [f'{prefix}-{uuid.uuid4().hex[:6].upper()}' for _ in range(5)]
        used = {r[0] for r in db.session.execute(
            select(getattr(model_class, code_field))
            .where(getattr(model_class, code_field).in_(candidates))
        ).all()}
        
        for code in candidates:
            if code not in used:
                return code
    
    fallback_code = f'{prefix}-{secrets.token_hex(4).upper()}'
    logger.warning(
        "Code generator exhausted 10 attempts for prefix '%s'. "
        "Using fallback: %s. Consider reviewing collision rate.",
        prefix, fallback_code
    )
    return fallback_code


def generate_institution_code() -> str:
    """
    Genera un código corto único para una nueva institución.

    Returns:
        str: Código generado con prefijo 'INST'.
    """
    from app.models.institution_model import Institution
    return _generate_short_code('INST', Institution, 'institution_code')


def generate_person_code() -> str:
    """
    Genera un código corto único para una nueva persona/representante.

    Returns:
        str: Código generado con prefijo 'PERS'.
    """
    from app.models.person_model import Person
    return _generate_short_code('PERS', Person, 'person_code')


def is_plantel_code_available(plantel_code: str) -> bool:
    """
    Verifica si el código de plantel está disponible para registro.

    Args:
        plantel_code (str): Código de plantel a consultar.

    Returns:
        bool: True si el código NO existe en la base de datos, False si ya está registrado.
    """
    from app.models.institution_model import Institution
    return not Institution.query.filter_by(plantel_code=plantel_code).first()


def is_identification_available(identification_number: str) -> bool:
    """
    Verifica si el número de cédula/identificación está disponible para registro.

    Args:
        identification_number (str): Número de identificación a consultar.

    Returns:
        bool: True si no existe en BD, False en caso contrario.
    """
    from app.models.person_model import Person
    return not Person.query.filter_by(identification_number=identification_number).first()


def is_email_available(email: str) -> bool:
    """
    Verifica si la dirección de correo electrónico está disponible.

    Args:
        email (str): Correo electrónico a consultar.

    Returns:
        bool: True si no existe en BD, False en caso contrario.
    """
    from app.models.person_model import Person
    return not Person.query.filter_by(email=email.lower()).first()


def get_institution_by_plantel_code(plantel_code: str):
    """
    Obtiene los datos completos de una institución y sus relaciones mediante un JOIN optimizado.

    Args:
        plantel_code (str): Código de plantel a consultar.

    Returns:
        Institution o None: Instancia de la institución con relaciones cargadas si se encuentra.
    """
    from app.models.institution_model import Institution
    from app.models.parish_model import Parish
    from app.models.municipality_model import Municipality
    from sqlalchemy.orm import joinedload
    stmt = (select(Institution)
            .options(
                joinedload(Institution.status),
                joinedload(Institution.institution_type),
                joinedload(Institution.institution_scope),
                joinedload(Institution.institution_dependency),
                joinedload(Institution.parish).joinedload(Parish.municipality)
                                             .joinedload(Municipality.state),
            )
            .filter_by(plantel_code=plantel_code))
    return db.session.execute(stmt).scalar()


def get_institution_types() -> list[dict]:
    """
    Obtiene la lista de tipos de institución ordenados por nombre.

    Returns:
        list[dict]: Lista de diccionarios con 'id' (código de negocio) y 'name'.
    """
    from app.models.institution_type_model import InstitutionType
    rows = InstitutionType.query.order_by(InstitutionType.name).all()
    return [{'id': r.institution_type_code, 'name': r.name} for r in rows]


def get_institution_scopes() -> list[dict]:
    """
    Obtiene la lista de sectores institucionales ordenados por nombre.

    Returns:
        list[dict]: Lista de diccionarios con 'id' y 'name'.
    """
    from app.models.institution_scope_model import InstitutionScope
    rows = InstitutionScope.query.order_by(InstitutionScope.name).all()
    return [{'id': r.id, 'name': r.name} for r in rows]


def get_institution_dependencies() -> list[dict]:
    """
    Obtiene la lista de dependencias institucionales ordenadas por nombre.

    Returns:
        list[dict]: Lista de diccionarios con 'id' y 'name'.
    """
    from app.models.institution_dependency_model import InstitutionDependency
    rows = InstitutionDependency.query.order_by(InstitutionDependency.name).all()
    return [{'id': r.id, 'name': r.name} for r in rows]


def get_states() -> list[dict]:
    """
    Obtiene la lista de estados del país ordenados por nombre.

    Returns:
        list[dict]: Lista de diccionarios con 'id' (código de estado) y 'name'.
    """
    from app.models.state_model import State
    rows = State.query.order_by(State.name).all()
    return [{'id': r.state_code, 'name': r.name} for r in rows]


def get_educational_levels() -> list[dict]:
    """
    Obtiene la lista de niveles educativos ordenados por nombre.

    Returns:
        list[dict]: Lista de diccionarios con 'id' (código de negocio) y 'name'.
    """
    from app.models.educational_level_model import EducationalLevel
    rows = EducationalLevel.query.order_by(EducationalLevel.name).all()
    return [{'id': r.level_code, 'name': r.name} for r in rows]


def get_municipalities_by_state(state_code: str) -> list[dict]:
    """
    Obtiene los municipios de un estado específico.

    Args:
        state_code (str): Código string del estado.

    Returns:
        list[dict]: Lista de diccionarios con 'id' (código municipal) y 'name'.
    """
    from app.models.municipality_model import Municipality
    from app.models.state_model import State
    rows = (Municipality.query
            .join(State, Municipality.state_id == State.id)
            .filter(State.state_code == state_code)
            .order_by(Municipality.name)
            .all())
    return [{'id': r.municipality_code, 'name': r.name} for r in rows]


def get_parishes_by_municipality(municipality_code: str) -> list[dict]:
    """
    Obtiene las parroquias de un municipio específico.

    Args:
        municipality_code (str): Código string del municipio.

    Returns:
        list[dict]: Lista de diccionarios con 'id' (PK numérico) y 'name'.
    """
    from app.models.parish_model import Parish
    from app.models.municipality_model import Municipality
    rows = (Parish.query
            .join(Municipality, Parish.municipality_id == Municipality.id)
            .filter(Municipality.municipality_code == municipality_code)
            .order_by(Parish.name)
            .all())
    return [{'id': r.id, 'name': r.name} for r in rows]


def get_positions() -> list[dict]:
    """
    Obtiene la lista de cargos de representantes ordenados por nombre.

    Returns:
        list[dict]: Lista de diccionarios con 'id' y 'name'.
    """
    from app.models.position_model import Position
    rows = Position.query.order_by(Position.name).all()
    return [{'id': r.id, 'name': r.name} for r in rows]


_NO_PREFIX_TYPES = {'INST-001', 'INST-002', 'INST-005'}
_NO_ACRONYM_TYPES = {'INST-003', 'INST-004', 'INST-005', 'INST-006'}


def format_institution_name(
    inst_type_code: str,
    raw_name: str,
    prefix: str | None = None,
    acronym: str | None = None,
) -> str:
    """
    Formatea y ensambla el nombre oficial de la institución aplicando reglas de negocio estrictas.

    Previene manipulaciones del cliente ignorando prefijos o acrónimos si el tipo 
    de institución no los requiere de acuerdo al diseño establecido.

    Args:
        inst_type_code (str): Código del tipo de institución.
        raw_name (str): Nombre base de la institución ingresado por el usuario.
        prefix (str | None): Prefijo seleccionado (opcional).
        acronym (str | None): Siglas ingresadas por el usuario (opcional).

    Returns:
        str: Nombre completo formateado de la institución.
    """
    base_name = (raw_name or '').strip()
    code = (inst_type_code or '').strip().upper()

    # Procesar prefijos defensivamente
    if code in _NO_PREFIX_TYPES:
        clean_prefix = ''
    else:
        clean_prefix = f"{prefix.strip()} " if prefix and prefix.strip() else ''

    full_name = f"{clean_prefix}{base_name}".strip()

    # Agregar acrónimo si aplica
    if code not in _NO_ACRONYM_TYPES and acronym and acronym.strip():
        full_name = f"{full_name} ({acronym.strip().upper()})"

    return full_name


def _create_person_and_staff(person_data: dict, institution_id: int, pending_status_id: int):
    """
    Genera los registros del representante (Person) y su vinculación (InstitutionalStaff).

    Realiza un flush para obtener los IDs generados por BD y armar las relaciones.

    Args:
        person_data (dict): Datos personales del representante.
        institution_id (int): ID de la institución a la que se vincula.
        pending_status_id (int): ID del estado "Pendiente".

    Returns:
        InstitutionalStaff: El registro de vinculación (en estado de sesión, sin commit).
    """
    from app.models.person_model import Person
    from app.models.institutional_staff_model import InstitutionalStaff

    person = Person(
        person_code           = generate_person_code(),
        identification_type   = person_data['identification_type'],
        identification_number = person_data['identification_number'],
        first_name            = person_data['first_name'],
        second_name           = person_data.get('second_name') or None,
        last_name             = person_data['last_name'],
        middle_name           = person_data.get('middle_name') or None,
        email                 = person_data['email'],
        mobile                = person_data['mobile'],
        phone                 = person_data.get('phone') or None,
    )
    db.session.add(person)
    db.session.flush()  # Obtiene el PK person.id generado

    staff = InstitutionalStaff(
        person_id      = person.id,
        institution_id = institution_id,
        position_id    = person_data['position_id'],
        status_id      = pending_status_id,
    )
    db.session.add(staff)
    db.session.flush()  # Obtiene el PK staff.id generado

    return staff


def _send_registration_email_async(app, email: str, full_name: str, inst_name: str) -> None:
    """
    Envía el correo de confirmación de registro de forma asíncrona usando hilos.

    Args:
        app: Objeto de la aplicación Flask actual (necesario para el contexto del hilo).
        email (str): Correo destinatario.
        full_name (str): Nombre completo del usuario.
        inst_name (str): Nombre de la institución registrada.
    """
    def _target():
        with app.app_context():
            try:
                send_preregistration_email(email, full_name, inst_name)
            except Exception as e:
                logger.error("Error enviando correo de pre-registro a %s: %s", email, e, exc_info=True)
    try:
        threading.Thread(target=_target, daemon=True).start()
    except Exception as e:
        logger.error("Error al iniciar hilo para correo: %s", e)


def _save_staff_evidence(staff_id: int, evidence_file, document_type: str, identification_number: str):
    """
    Guarda el documento comprobante de vinculación en disco y crea el registro en BD.

    Args:
        staff_id (int): ID de la vinculación del representante a la institución.
        evidence_file: Objeto de archivo binario (FileStorage de Werkzeug).
        document_type (str): Tipo de documento (ej. 'Nombramiento').
        identification_number (str): Cédula del representante (usada en la nomenclatura).

    Returns:
        str: Ruta relativa del archivo guardado en el servidor.
    """
    from app.models.staff_evidence_model import StaffEvidence
    from app.utils.file_handler import save_evidence_file
    from datetime import datetime, timezone

    timestamp   = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    custom_name = f'{document_type}_{identification_number}_{timestamp}'

    # Se guarda físicamente en disco usando el helper
    evidence_data = save_evidence_file(
        file_obj    = evidence_file,
        sub_folder  = f'staff_evidences/{staff_id}',
        custom_name = custom_name,
    )

    evidence = StaffEvidence(
        institutional_staff_id = staff_id,
        file_name              = evidence_data['file_name'],
        file_path              = evidence_data['file_path'],
        format                 = evidence_data['format'],
        file_weight            = evidence_data['file_weight'],
    )
    db.session.add(evidence)
    return evidence_data['file_path']


def create_pre_registration(
    inst_data: dict,
    person_data: dict,
    evidence_file,
    document_type: str
) -> tuple[bool, str, int]:
    """
    Registra de forma transaccional una nueva Institución y su Representante inicial.

    Implementa un Rollback completo en caso de colisión (IntegrityError) o falla
    inesperada, asegurando consistencia referencial y borrado físico del 
    comprobante en caso de error.

    Args:
        inst_data (dict): Datos completos de la nueva institución.
        person_data (dict): Datos personales del representante.
        evidence_file: Objeto binario del comprobante adjunto.
        document_type (str): Tipo de comprobante.

    Returns:
        tuple: (éxito: bool, mensaje: str, código_http: int)
    """
    from app.models.institution_model    import Institution
    from app.models.status_model         import Status
    from app.models.institution_type_model import InstitutionType
    from app.models.educational_level_model import EducationalLevel
    from app.models.institution_level_model import InstitutionLevel

    evidence_path = None
    try:
        pending_status = Status.query.filter_by(status_code=PENDING_STATUS_CODE).first()
        if not pending_status:
            return False, 'No fue posible procesar la solicitud en este momento. Por favor, intente más tarde.', 500

        # Verificación doble de seguridad para evitar colisiones
        if not is_plantel_code_available(inst_data['plantel_code']):
            return False, 'El código de plantel ya se encuentra registrado en el sistema.', 409

        if not is_identification_available(person_data['identification_number']):
            return False, 'Este número de identificación no está disponible para registro. Si cree que esto es un error o ya tiene cuenta, contacte a soporte.', 409

        if not is_email_available(person_data['email']):
            return False, 'Este correo no está disponible para un nuevo registro. Si ya posee una cuenta, por favor inicie sesión o utilice la opción de recuperar contraseña.', 409

        # Inserción Institucional
        institution = Institution(
            institution_code          = generate_institution_code(),
            institution_type_id       = inst_data['institution_type_id'],
            institution_name          = inst_data['institution_name'],
            plantel_code              = inst_data['plantel_code'],
            institution_scope_id      = inst_data['institution_scope_id'],
            institution_dependency_id = inst_data['institution_dependency_id'],
            parish_id                 = inst_data['parish_id'],
            address                   = inst_data['address'],
            phone                     = inst_data.get('phone') or None,
            status_id                 = pending_status.id,
        )
        db.session.add(institution)
        db.session.flush()

        staff = _create_person_and_staff(
            person_data      = person_data,
            institution_id   = institution.id,
            pending_status_id= pending_status.id,
        )

        # Inserción de relación pivote (Niveles Educativos)
        inst_type = db.session.get(InstitutionType, inst_data['institution_type_id'])
        if inst_type:
            type_code     = inst_type.institution_type_code
            allowed_codes = ALLOWED_EDUCATIONAL_LEVELS.get(type_code, set())
            requested_levels  = inst_data.get('educational_levels', [])
            valid_level_codes = [code for code in requested_levels if code in allowed_codes]

            if valid_level_codes:
                db_levels = EducationalLevel.query.filter(
                    EducationalLevel.level_code.in_(valid_level_codes)
                ).all()
                for level_obj in db_levels:
                    inst_level = InstitutionLevel(
                        institution_id       = institution.id,
                        educational_level_id = level_obj.id
                    )
                    db.session.add(inst_level)

        # Inserción física y lógica del comprobante
        evidence_path = _save_staff_evidence(
            staff_id              = staff.id,
            evidence_file         = evidence_file,
            document_type         = document_type,
            identification_number = person_data.get('identification_number', '00000000'),
        )

        db.session.commit()

        # Desencadenar notificaciones
        try:
            full_name = f"{person_data.get('first_name', '')} {person_data.get('last_name', '')}".strip()
            inst_name = institution.institution_name
            app = current_app._get_current_object()
            
            _send_registration_email_async(app, person_data.get('email'), full_name, inst_name)
        except Exception as e:
            logger.error("Error al iniciar el hilo de correo: %s", e, exc_info=True)

        return True, 'Su solicitud ha sido recibida. Verificaremos los datos de la institución y le notificaremos por correo electrónico.', 201

    except IntegrityError as e:
        db.session.rollback()
        # Borrar rastro físico del archivo en caso de colisión SQL
        if evidence_path:
            try:
                os.remove(evidence_path)
            except OSError:
                pass
        err_str = str(e.orig).lower()
        if 'plantel_code' in err_str:
            return False, 'El código de plantel ya se encuentra registrado en el sistema.', 409
        if 'identification_number' in err_str:
            return False, 'Este número de identificación no está disponible para registro. Si cree que esto es un error o ya tiene cuenta, contacte a soporte.', 409
        if 'email' in err_str:
            return False, 'Este correo no está disponible para un nuevo registro. Si ya posee una cuenta, por favor inicie sesión o utilice la opción de recuperar contraseña.', 409
        return False, 'Datos duplicados. Verifique la información e intente nuevamente.', 409
    except Exception:
        db.session.rollback()
        if evidence_path:
            try:
                os.remove(evidence_path)
            except OSError:
                pass
        logger.error("Error al crear pre-registro", exc_info=True)
        return False, 'Ocurrió un error interno. Por favor intente nuevamente o contacte al administrador.', 500


def join_existing_institution(
    plantel_code: str,
    person_data: dict,
    evidence_file,
    document_type: str,
) -> tuple[bool, str, int]:
    """
    Registra un nuevo representante vinculado a una institución que ya existe en el sistema.

    No altera la tabla de instituciones. Solo inserta al usuario (Person),
    establece su vinculación (InstitutionalStaff) e inserta el comprobante físico.

    Args:
        plantel_code (str): Código de plantel de la institución existente.
        person_data (dict): Datos personales del nuevo solicitante.
        evidence_file: Objeto binario del comprobante adjunto.
        document_type (str): Tipo de comprobante.

    Returns:
        tuple: (éxito: bool, mensaje: str, código_http: int)
    """
    from app.models.institution_model import Institution
    from app.models.status_model      import Status

    evidence_path = None
    try:
        institution = Institution.query.filter_by(plantel_code=plantel_code).first()
        if not institution:
            return False, 'La institución indicada no se encuentra registrada en el sistema.', 404

        pending_status = Status.query.filter_by(status_code=PENDING_STATUS_CODE).first()
        if not pending_status:
            return False, 'No fue posible procesar la solicitud en este momento. Por favor, intente más tarde.', 500

        if not is_identification_available(person_data['identification_number']):
            return False, 'Este número de identificación no está disponible para registro. Si cree que esto es un error o ya tiene cuenta, contacte a soporte.', 409

        if not is_email_available(person_data['email']):
            return False, 'Este correo no está disponible para un nuevo registro. Si ya posee una cuenta, por favor inicie sesión o utilice la opción de recuperar contraseña.', 409

        staff = _create_person_and_staff(
            person_data       = person_data,
            institution_id    = institution.id,
            pending_status_id = pending_status.id,
        )

        evidence_path = _save_staff_evidence(
            staff_id              = staff.id,
            evidence_file         = evidence_file,
            document_type         = document_type,
            identification_number = person_data.get('identification_number', '00000000'),
        )

        db.session.commit()

        try:
            full_name = f"{person_data.get('first_name', '')} {person_data.get('last_name', '')}".strip()
            inst_name = institution.institution_name
            app = current_app._get_current_object()
            
            _send_registration_email_async(app, person_data.get('email'), full_name, inst_name)
        except Exception as e:
            logger.error(f"Error al iniciar el hilo de correo: {e}", exc_info=True)

        return True, 'Su solicitud ha sido recibida. Verificaremos los datos de la institución y le notificaremos por correo electrónico.', 201

    except IntegrityError as e:
        db.session.rollback()
        if evidence_path:
            import os
            try:
                os.remove(evidence_path)
            except OSError:
                pass
        err_str = str(e.orig).lower()
        if 'identification_number' in err_str:
            return False, 'Este número de identificación no está disponible para registro. Si cree que esto es un error o ya tiene cuenta, contacte a soporte.', 409
        if 'email' in err_str:
            return False, 'Este correo no está disponible para un nuevo registro. Si ya posee una cuenta, por favor inicie sesión o utilice la opción de recuperar contraseña.', 409
        return False, 'Datos duplicados. Verifique la información e intente nuevamente.', 409
    except Exception:
        db.session.rollback()
        if evidence_path:
            import os
            try:
                os.remove(evidence_path)
            except OSError:
                pass
        logger.error("Error en join_existing_institution", exc_info=True)
        return False, 'Ocurrió un error interno. Por favor intente nuevamente o contacte al administrador.', 500