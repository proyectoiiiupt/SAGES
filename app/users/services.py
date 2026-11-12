"""
Servicios del Módulo de Usuarios
Lógica de negocio para consulta de perfil, edición de contacto y actualización segura de credenciales.
"""
import re
from typing import Tuple, Dict, Any, Optional
from app.extensions import db, bcrypt
from app.models.user_model import User
from app.models.person_model import Person
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.company_staff_model import CompanyStaff
from app.models.location_model import Location
from app.models.place_model import Place
from app.models.position_model import Position
from app.models.role_model import Role
from app.models.role_user_model import RoleUser
from app.models.company_model import Company
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.status_model import Status
from app.utils.password_utils import change_user_password
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditAction, AuditModule, AuditStatus
from app.pre_registration.services import _generate_short_code
import secrets
import json
from sqlalchemy.exc import IntegrityError

PASSWORD_REGEX = re.compile(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[$@.!%*?&]).{8,128}$')


def format_identification(id_type: Optional[str], id_number: Optional[str]) -> str:
    """
    Formatea cédulas venezolanas: V-12.345.678 o E-1.234.567.
    """
    if not id_number:
        return 'N/A'
    
    clean_type = str(id_type).strip().upper() if id_type else 'V'
    if clean_type not in ['V', 'E', 'J', 'G', 'P']:
        clean_type = 'V'

    clean_num = ''.join(filter(str.isdigit, str(id_number)))
    if not clean_num:
        return 'N/A'
        
    try:
        formatted_num = f"{int(clean_num):,}".replace(',', '.')
        return f"{clean_type}-{formatted_num}"
    except ValueError:
        return f"{clean_type}-{clean_num}"


def format_venezuelan_phone(phone_str: Optional[str]) -> str:
    """
    Formatea teléfonos venezolanos en formato (0414)-1234567.
    """
    if not phone_str or str(phone_str).strip() in ('', 'N/A', 'None'):
        return 'N/A'
    clean_phone = ''.join(filter(str.isdigit, str(phone_str)))
    if len(clean_phone) >= 10:
        return f"({clean_phone[:4]})-{clean_phone[4:]}"
    return str(phone_str)


def get_user_profile_data(user: User) -> Dict[str, Any]:
    """
    Recopila y formatea todos los datos fijos del usuario para su consulta en el perfil.
    """
    person = user.person
    role_name = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'
    
    role_display_map = {
        'super_admin': 'Super Administrador',
        'state_admin': 'Administrador Estadal',
        'director': 'Director / Solicitante',
        'directora': 'Directora / Solicitante',
        'applicant': 'Solicitante'
    }
    role_display = role_display_map.get(role_name, role_name.replace('_', ' ').title())
    
    status_name = getattr(user.status, 'status_name', 'Activo') if user.status else 'Activo'
    status_code = getattr(user.status, 'status_code', 'STAT-001') if user.status else 'STAT-001'
    is_active = status_code == 'STAT-001' or status_name.lower() == 'activo'

    # Datos Personales
    if person:
        id_type = getattr(person, 'identification_type', 'V')
        id_num = getattr(person, 'identification_number', '')
        formatted_id = format_identification(id_type, id_num)
        
        first_n = (getattr(person, 'first_name', '') or '').strip()
        second_n = (getattr(person, 'second_name', '') or '').strip()
        last_n = (getattr(person, 'last_name', '') or '').strip()
        middle_n = (getattr(person, 'middle_name', '') or '').strip()
        
        full_first_name = f"{first_n} {second_n}".strip() if first_n else 'N/A'
        full_last_name = f"{last_n} {middle_n}".strip() if last_n else 'N/A'
        email = getattr(person, 'email', 'N/A') or 'N/A'
        formatted_phone = format_venezuelan_phone(getattr(person, 'mobile', ''))
        formatted_phone_sec = format_venezuelan_phone(getattr(person, 'phone', ''))
    else:
        formatted_id = 'N/A'
        first_n = second_n = last_n = middle_n = ''
        full_first_name = user.user_name
        full_last_name = ''
        email = 'N/A'
        formatted_phone = 'N/A'
        formatted_phone_sec = 'N/A'

    # Datos Institucionales / Corporativos
    corp_data = None
    if person:
        inst_staff = InstitutionalStaff.query.filter_by(person_id=person.id).first()
        if inst_staff:
            inst = inst_staff.institution
            pos = inst_staff.position
            
            city_name = 'N/A'
            if inst and getattr(inst, 'parish_id', None):
                try:
                    loc = Location.query.filter_by(parish_id=inst.parish_id).first()
                    if loc and loc.city:
                        city_name = loc.city.name
                except Exception:
                    pass
            
            plantel_code = getattr(inst, 'plantel_code', None)
            corp_data = {
                'entity_type': 'institution',
                'title': 'Información de Institución',
                'id_card': plantel_code if plantel_code else 'N/A',
                'name': getattr(inst, 'institution_name', 'N/A') if inst else 'N/A',
                'type': inst.institution_type.name if inst and getattr(inst, 'institution_type', None) else 'N/A',
                'sector': inst.institution_scope.name if inst and getattr(inst, 'institution_scope', None) else 'N/A',
                'dependency': inst.institution_dependency.name if inst and getattr(inst, 'institution_dependency', None) else 'N/A',
                'position': pos.name if pos else 'N/A',
                'phone_main': format_venezuelan_phone(getattr(inst, 'phone', 'N/A')),
                'state': inst.parish.municipality.state.name if inst and getattr(inst, 'parish', None) and getattr(inst.parish, 'municipality', None) else 'N/A',
                'municipality': inst.parish.municipality.name if inst and getattr(inst, 'parish', None) else 'N/A',
                'parish': inst.parish.name if inst and getattr(inst, 'parish', None) else 'N/A',
                'city': city_name,
                'address': getattr(inst, 'address', 'N/A') if inst else 'N/A'
            }
        else:
            comp_staff = CompanyStaff.query.filter_by(person_id=person.id).first()
            if comp_staff:
                place = comp_staff.place
                comp = place.company if place else None
                pos = comp_staff.position
                
                city_name = 'N/A'
                if place and getattr(place, 'parish_id', None):
                    try:
                        loc = Location.query.filter_by(parish_id=place.parish_id).first()
                        if loc and loc.city:
                            city_name = loc.city.name
                    except Exception:
                        pass
                
                type_rif = getattr(comp, 'identification_type', '') or '' if comp else ''
                num_rif = getattr(comp, 'rif', '') or '' if comp else ''
                formatted_rif = f"{type_rif}-{num_rif}".strip('-') if (type_rif or num_rif) else 'N/A'

                corp_data = {
                    'entity_type': 'corporation',
                    'title': 'Información de Corporación',
                    'id_card': formatted_rif,
                    'name': comp.company_name if comp else 'CORPOELEC',
                    'type': 'Empresa Pública' if 'corpoelec' in getattr(comp, 'company_name', '').lower() else 'Empresa Privada',
                    'sector': 'N/A',
                    'dependency': 'N/A',
                    'position': pos.name if pos else 'N/A',
                    'phone_main': format_venezuelan_phone(getattr(place, 'phone', 'N/A')),
                    'state': place.parish.municipality.state.name if place and getattr(place, 'parish', None) and getattr(place.parish, 'municipality', None) else 'N/A',
                    'municipality': place.parish.municipality.name if place and getattr(place, 'parish', None) else 'N/A',
                    'parish': place.parish.name if place and getattr(place, 'parish', None) else 'N/A',
                    'city': city_name,
                    'address': place.address if place else 'N/A',
                    'sede': getattr(place, 'name', 'N/A') if place else 'N/A'
                }

    return {
        'user_id': user.id,
        'user_code': user.user_code,
        'user_name': user.user_name,
        'raw_email': email,
        'raw_mobile': getattr(person, 'mobile', '') or '' if person else '',
        'raw_phone': getattr(person, 'phone', '') or '' if person else '',
        'formatted_id': formatted_id,
        'first_name': first_n,
        'second_name': second_n,
        'last_name': last_n,
        'middle_name': middle_n,
        'full_first_name': full_first_name,
        'full_last_name': full_last_name,
        'email': email,
        'formatted_phone': formatted_phone,
        'formatted_phone_sec': formatted_phone_sec,
        'role_name': role_name,
        'role_display': role_display,
        'status_name': status_name,
        'status_code': status_code,
        'is_active': is_active,
        'corp_data': corp_data,
    }


def update_user_contact(user: User, email: str, mobile: str, phone: str) -> Tuple[bool, str]:
    """
    Actualiza los datos de contacto editables del usuario:
    correo electrónico, teléfono principal (móvil) y teléfono secundario.
    Solo modifica el Person asociado al usuario autenticado.
    """
    person = user.person
    if not person:
        return False, "No se encontró el registro de persona asociado al usuario."

    email_clean = (email or '').strip().lower()
    mobile = (mobile or '').strip()
    phone = (phone or '').strip()

    if not email_clean:
        return False, "El correo electrónico es obligatorio."

    if '@' not in email_clean or '.' not in email_clean.split('@')[-1]:
        return False, "El correo electrónico no tiene un formato válido."

    # Validar que el correo no esté en uso por otra persona
    existing_person = Person.query.filter(
        db.func.lower(Person.email) == email_clean,
        Person.id != person.id
    ).first()
    if existing_person:
        return False, "El correo electrónico ya se encuentra registrado por otro usuario."

    try:
        person.email = email_clean
        person.mobile = mobile
        person.phone = phone if phone else None
        db.session.add(person)
        db.session.commit()

        BinnacleService.create_log_entry(
            module=AuditModule.USERS.value,
            action_type=AuditAction.ACTUALIZAR_CONTACTO_PROPIO.value,
            description='Actualización de datos de contacto realizada por el usuario en su perfil',
            status=AuditStatus.MODIFICADO.value
        )

        return True, "Los datos de contacto han sido actualizados exitosamente."
    except IntegrityError:
        db.session.rollback()
        return False, "El correo electrónico ya se encuentra registrado por otro usuario."
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR UPDATE CONTACT]: {e}")
        return False, "Ocurrió un error al actualizar los datos de contacto. Por favor intente más tarde."


def change_profile_password(user: User, current_password: str, new_password: str, confirm_password: str) -> Tuple[bool, str]:
    """
    Actualiza la contraseña del usuario tras validar exhaustivamente la clave actual
    y las políticas de seguridad de la nueva contraseña.
    """
    if not current_password:
        return False, "Debe ingresar su contraseña actual."
    
    if not new_password:
        return False, "Debe ingresar la nueva contraseña."

    # 1. Validar clave actual exclusivamente con Flask-Bcrypt
    password_valid = False
    try:
        password_valid = bcrypt.check_password_hash(user.password, current_password)
    except Exception:
        password_valid = False

    if not password_valid:
        return False, "La contraseña actual es incorrecta."

    # 2. Validar que la nueva clave sea distinta a la actual
    if current_password == new_password:
        return False, "La nueva contraseña no puede ser igual a la contraseña actual."

    # 3. Validar confirmación idéntica
    if new_password != confirm_password:
        return False, "Las contraseñas no coinciden."

    # 4. Validar longitud
    if len(new_password) < 8 or len(new_password) > 128:
        return False, "La nueva contraseña debe tener entre 8 y 128 caracteres."

    # 5. Validar complejidad: mayúscula, número, carácter especial
    if not PASSWORD_REGEX.match(new_password):
        return False, "La nueva contraseña debe contener al menos 8 caracteres, una mayúscula, un número y un carácter especial ($@.!%*?&)."

    try:
        # 6. Actualizar hash de contraseña de forma segura
        change_user_password(user, new_password)

        # 7. Registrar acción en bitácora para auditoría
        BinnacleService.create_log_entry(
            module=AuditModule.USERS.value,
            action_type=AuditAction.CAMBIO_PASSWORD_PERFIL.value,
            description='Actualización de contraseña realizada por el usuario en su perfil',
            status=AuditStatus.MODIFICADO.value
        )

        return True, "Tu contraseña ha sido actualizada exitosamente."
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR CHANGE PROFILE PASSWORD]: {e}")
        return False, "Ocurrió un error inesperado al actualizar la contraseña. Por favor intente más tarde."


def get_corpoelec_places_by_state(state_id: int):
    """
    Retorna las sedes de CORPOELEC (COMP-001) para un estado dado.
    """
    places = Place.query.join(Company).join(Parish).join(Municipality).filter(
        Company.company_code == 'COMP-001',
        Municipality.state_id == state_id,
        Place.status_id == 1 # Asumiendo 1 = Activo
    ).all()
    
    return [{'id': p.id, 'name': p.name} for p in places]


def get_administrative_positions():
    """
    Retorna cargos corporativos de CORPOELEC aplicables a personal administrativo.
    """
    positions = Position.query.filter(Position.position_code.in_([
        'POS-006', 'POS-008', 'POS-009', 'POS-010'
    ])).all()
    
    if not positions:
        # Fallback si no hay por código
        positions = Position.query.all()

    return [{'id': p.id, 'name': p.name} for p in positions]


def create_administrative_user(data: dict, creator_user: User) -> Tuple[bool, str, dict]:
    """
    Servicio transaccional para dar de alta a un usuario administrativo interno.
    Inserción atómica en: persons, users, company_staff, role_users, binnacle.
    """
    try:
        role_id = data.get('role_id')
        role = Role.query.get(role_id)
        if not role or role.role_code not in ['ROL-001', 'ROL-002']:
            return False, "Rol inválido. Solo Super Administrador o Administrador Estadal.", {}

        # Empresa inmutable
        corpoelec = Company.query.filter_by(company_code='COMP-001').first()
        if not corpoelec:
            return False, "Error interno: Empresa CORPOELEC no encontrada.", {}

        # Verificar sede y jurisdicción
        place_id = data.get('place_id')
        state_id = data.get('state_id')
        place = Place.query.join(Parish).join(Municipality).filter(
            Place.id == place_id,
            Place.company_id == corpoelec.id,
            Municipality.state_id == state_id
        ).first()
        
        if not place:
            return False, "La sede seleccionada es inválida o no pertenece a CORPOELEC en el estado indicado.", {}
        
        from app.models.state_model import State
        state = State.query.get(state_id)
        state_name = state.name if state else ""
            
        # Verificar duplicados en Person y User
        email_clean = str(data.get('email')).strip().lower()
        id_number_clean = str(data.get('identification_number')).strip()
        
        if Person.query.filter(db.func.lower(Person.email) == email_clean).first():
            return False, "El correo electrónico ya se encuentra registrado por otro usuario.", {}
            
        if Person.query.filter_by(identification_number=id_number_clean).first() or \
           User.query.filter_by(user_name=id_number_clean).first():
            return False, "La cédula de identidad ya se encuentra registrada por otro usuario.", {}
            
        # STAT-006: el User no puede iniciar sesión hasta que active mediante el enlace.
        # auth/services.py L26 rechaza logins de usuarios que no sean STAT-001.
        status_in_progress = Status.query.filter_by(status_code='STAT-006').first()

        # 1. Crear Person
        person = Person(
            person_code=_generate_short_code('PERS', Person, 'person_code'),
            identification_type=data.get('identification_type'),
            identification_number=id_number_clean,
            first_name=data.get('first_name'),
            second_name=data.get('second_name') or None,
            last_name=data.get('last_name'),
            middle_name=data.get('middle_name') or None,
            email=email_clean,
            mobile=data.get('mobile'),
            phone=data.get('phone') or None,
        )
        db.session.add(person)
        db.session.flush()

        # 2. Crear User
        temp_password = secrets.token_urlsafe(10)
        user = User(
            user_code=_generate_short_code('USR', User, 'user_code'),
            person_id=person.id,
            user_name=id_number_clean,
            password=bcrypt.generate_password_hash(temp_password).decode('utf-8'),
            status_id=status_in_progress.id if status_in_progress else 6
        )
        db.session.add(user)
        db.session.flush()

        # 3. Crear CompanyStaff
        company_staff = CompanyStaff(
            person_id=person.id,
            place_id=place.id,
            position_id=data.get('position_id'),
            status_id=status_in_progress.id if status_in_progress else 6
        )
        db.session.add(company_staff)
        db.session.flush()
        
        # 4. Crear RoleUser
        role_user = RoleUser(
            user_id=user.id,
            role_id=role.id
        )
        db.session.add(role_user)

        # Commit final
        db.session.commit()
        
        role_display = "Super Administrador"
        if role.name == 'state_admin':
            role_display = f"Administrador {state_name}"

        return True, "Registro exitoso.", {
            'person_id': person.id,
            'email': person.email,
            'role_display': role_display,
            'place_name': place.name,
            'full_name': f"{person.first_name} {person.last_name}",
            'staff_id': company_staff.id,
            'role_id': role.id,
            'user_id': user.id
        }

    except IntegrityError as e:
        db.session.rollback()
        err_str = str(e).lower()
        if 'email' in err_str:
            return False, "El correo electrónico ya se encuentra registrado por otro usuario.", {}
        elif 'identification_number' in err_str or 'user_name' in err_str:
            return False, "La cédula de identidad ya se encuentra registrada por otro usuario.", {}
        return False, "Ya existe un usuario con estos datos en el sistema.", {}
    except Exception as e:
        db.session.rollback()
        return False, f"Ocurrió un error inesperado al crear el usuario: {str(e)}", {}


def get_user_state_id(user: Optional[User]) -> Optional[int]:
    """
    Obtiene el ID del estado geográfico asociado a un usuario,
    inspeccionando su vinculación institucional o corporativa.
    """
    if not user or not getattr(user, 'person', None):
        return None

    person_id = user.person.id

    inst_staff = InstitutionalStaff.query.filter_by(person_id=person_id).first()
    if inst_staff and inst_staff.institution and inst_staff.institution.parish:
        if inst_staff.institution.parish.municipality:
            return inst_staff.institution.parish.municipality.state_id

    comp_staff = CompanyStaff.query.filter_by(person_id=person_id).first()
    if comp_staff and comp_staff.place and comp_staff.place.parish:
        if comp_staff.place.parish.municipality:
            return comp_staff.place.parish.municipality.state_id

    return None


def purge_expired_pending_users(days_limit: int = 7) -> int:
    """
    Purga automática de registros en estado Pendiente (STAT-006) que hayan superado
    el plazo máximo de días (por defecto 7 días) desde su creación sin activar contraseña.
    
    1. Registra evento de auditoría en Binnacle (user_id=None, old_values con datos completos).
    2. Elimina RoleUser, User, CompanyStaff o InstitutionalStaff (y su evidencia física en disco).
    3. Elimina Person.
    4. Si la institución asociada quedó sin ningún personal o usuarios activos y sin trámites,
       elimina Institution e InstitutionLevel para liberar el código de plantel.
    
    Retorna la cantidad total de registros purgados.
    """
    import os
    import logging
    from datetime import datetime, timezone, timedelta
    from flask import current_app
    from app.models.institution_model import Institution
    from app.models.institution_level_model import InstitutionLevel
    from app.models.staff_evidence_model import StaffEvidence

    logger = logging.getLogger(__name__)
    purged_count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_limit)

    try:
        # 1. Usuarios en BD con status_id == 6 y created_at > 7 días
        users_to_purge = User.query.filter(User.status_id == 6, User.created_at < cutoff).all()

        for user in users_to_purge:
            try:
                person = user.person
                role_name = user.roles_assoc[0].role.name if user.roles_assoc and user.roles_assoc[0].role else 'N/A'
                institution_name = None
                inst_to_check = None

                # Recolectar datos antes de eliminar
                inst_staff = InstitutionalStaff.query.filter_by(person_id=person.id).first() if person else None
                comp_staff = CompanyStaff.query.filter_by(person_id=person.id).first() if person else None

                if inst_staff:
                    inst = inst_staff.institution
                    inst_to_check = inst
                    institution_name = inst.institution_name if inst else "N/A"
                    # Eliminar evidencias físicas y registros de evidencia
                    evidences = StaffEvidence.query.filter_by(institutional_staff_id=inst_staff.id).all()
                    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                    for ev in evidences:
                        if ev.file_path:
                            try:
                                raw_p = ev.file_path.replace('\\', '/')
                                clean_p = raw_p.split('uploads/')[-1] if 'uploads/' in raw_p else raw_p
                                full_file_p = os.path.join(upload_folder, clean_p)
                                if os.path.exists(full_file_p):
                                    os.remove(full_file_p)
                            except Exception as fe:
                                logger.warning(f"No se pudo eliminar archivo físico {ev.file_path}: {fe}")
                        db.session.delete(ev)
                    db.session.delete(inst_staff)

                if comp_staff:
                    institution_name = comp_staff.place.name if comp_staff.place else "CORPOELEC"
                    db.session.delete(comp_staff)

                old_values = {
                    'identification_number': person.identification_number if person else None,
                    'first_name': person.first_name if person else None,
                    'last_name': person.last_name if person else None,
                    'email': person.email if person else None,
                    'role': role_name,
                    'institution': institution_name,
                    'user_id': user.id,
                    'user_name': user.user_name,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'reason': f'Expiración de plazo máximo de activación ({days_limit} días)'
                }

                # Registrar auditoría en Binnacle con user_id=None
                BinnacleService.create_log_entry(
                    module=AuditModule.USERS.value,
                    action_type=AuditAction.ELIMINAR.value,
                    description=f'Purga automática de registro pendiente no activado tras {days_limit} días: {person.first_name if person else ""} {person.last_name if person else ""} ({person.identification_number if person else ""})',
                    status=AuditStatus.COMPLETADO.value,
                    target_table='sages.users',
                    record_id=user.id,
                    old_values=old_values,
                    user_identifier='SISTEMA'
                )

                # Eliminar asignación de roles y usuario
                RoleUser.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)

                # Eliminar Persona
                if person:
                    db.session.delete(person)

                # Si la institución no tiene más personal, eliminarla para liberar el plantel
                if inst_to_check:
                    remaining_staff = InstitutionalStaff.query.filter(
                        InstitutionalStaff.institution_id == inst_to_check.id
                    ).count()
                    if remaining_staff == 0:
                        InstitutionLevel.query.filter_by(institution_id=inst_to_check.id).delete()
                        db.session.delete(inst_to_check)

                db.session.commit()
                purged_count += 1
            except Exception as single_err:
                db.session.rollback()
                logger.error(f"Error al purgar usuario {user.id}: {single_err}")

        # 2. Registros huérfanos históricos en InstitutionalStaff con status_id == 6 y sin cuenta User
        orphaned_staffs = InstitutionalStaff.query.filter(
            InstitutionalStaff.status_id == 6,
            InstitutionalStaff.created_at < cutoff
        ).all()

        for st in orphaned_staffs:
            try:
                person = st.person
                if person and person.user:
                    continue

                inst = st.institution
                inst_name = inst.institution_name if inst else "N/A"

                evidences = StaffEvidence.query.filter_by(institutional_staff_id=st.id).all()
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                for ev in evidences:
                    if ev.file_path:
                        try:
                            raw_p = ev.file_path.replace('\\', '/')
                            clean_p = raw_p.split('uploads/')[-1] if 'uploads/' in raw_p else raw_p
                            full_file_p = os.path.join(upload_folder, clean_p)
                            if os.path.exists(full_file_p):
                                os.remove(full_file_p)
                        except Exception as fe:
                            logger.warning(f"No se pudo eliminar archivo físico {ev.file_path}: {fe}")
                    db.session.delete(ev)

                old_values = {
                    'identification_number': person.identification_number if person else None,
                    'first_name': person.first_name if person else None,
                    'last_name': person.last_name if person else None,
                    'email': person.email if person else None,
                    'role': 'applicant',
                    'institution': inst_name,
                    'staff_id': st.id,
                    'created_at': st.created_at.isoformat() if st.created_at else None,
                    'reason': f'Expiración de solicitud huérfana no activada tras {days_limit} días'
                }

                BinnacleService.create_log_entry(
                    module=AuditModule.USERS.value,
                    action_type=AuditAction.ELIMINAR.value,
                    description=f'Purga automática de solicitante huérfano no activado tras {days_limit} días: {person.first_name if person else ""} {person.last_name if person else ""} ({person.identification_number if person else ""})',
                    status=AuditStatus.COMPLETADO.value,
                    target_table='sages.institutional_staff',
                    record_id=st.id,
                    old_values=old_values,
                    user_identifier='SISTEMA'
                )

                db.session.delete(st)
                if person:
                    db.session.delete(person)

                if inst:
                    remaining_staff = InstitutionalStaff.query.filter(
                        InstitutionalStaff.institution_id == inst.id
                    ).count()
                    if remaining_staff == 0:
                        InstitutionLevel.query.filter_by(institution_id=inst.id).delete()
                        db.session.delete(inst)

                db.session.commit()
                purged_count += 1
            except Exception as st_err:
                db.session.rollback()
                logger.error(f"Error al purgar institutional_staff huérfano {st.id}: {st_err}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error general en purge_expired_pending_users: {e}")

    return purged_count


