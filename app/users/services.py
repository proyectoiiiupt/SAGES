"""
Servicios del Módulo de Usuarios
Lógica de negocio para consulta de perfil, edición de contacto y actualización segura de credenciales.
"""
import re
from typing import Tuple, Dict, Any, Optional
from werkzeug.security import check_password_hash as werkzeug_check
from app.extensions import db, bcrypt
from app.models.user_model import User
from app.models.person_model import Person
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.company_staff_model import CompanyStaff
from app.models.location_model import Location
from app.utils.password_utils import change_user_password
from app.utils.binnacle_utils import log_action

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

    email = (email or '').strip()
    mobile = (mobile or '').strip()
    phone = (phone or '').strip()

    if not email:
        return False, "El correo electrónico es obligatorio."

    if '@' not in email or '.' not in email.split('@')[-1]:
        return False, "El correo electrónico no tiene un formato válido."

    try:
        person.email = email
        person.mobile = mobile
        person.phone = phone if phone else None
        db.session.add(person)
        db.session.commit()

        log_action(
            user_id=user.id,
            module='users',
            action_type='UPDATE',
            description='Actualización de datos de contacto realizada por el usuario en su perfil'
        )

        return True, "Los datos de contacto han sido actualizados exitosamente."
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

    # 1. Validar clave actual (compatible con bcrypt y werkzeug para migración transparente)
    password_valid = False
    try:
        password_valid = bcrypt.check_password_hash(user.password, current_password)
    except Exception:
        pass
    if not password_valid:
        try:
            password_valid = werkzeug_check(user.password, current_password)
        except Exception:
            pass
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
        log_action(
            user_id=user.id,
            module='users',
            action_type='UPDATE',
            description='Actualización de contraseña realizada por el usuario en su perfil'
        )

        return True, "Tu contraseña ha sido actualizada exitosamente."
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR CHANGE PROFILE PASSWORD]: {e}")
        return False, "Ocurrió un error inesperado al actualizar la contraseña. Por favor intente más tarde."
