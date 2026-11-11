from flask import request, jsonify, redirect, url_for, flash, render_template, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.auth.services import authenticate_user
from app.extensions import login_manager, limiter
from flask_limiter.errors import RateLimitExceeded
from urllib.parse import urlparse, urljoin
import secrets
import time
from datetime import datetime, timezone, timedelta
from app.utils.email_utils import (
    send_recovery_email,
    send_applicant_activation_email,
    send_administrative_activation_email
)
from app.models.person_model import Person
from app.auth.token_store import set_token, get_remaining_seconds, invalidate_token
from app.auth.forms import ActivationPasswordForm
from app.utils.activation_utils import (
    verify_activation_token,
    inspect_activation_token,
    generate_activation_token
)
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.user_model import User
from app.models.role_user_model import RoleUser  # Cambiado a RoleUser
from app.models.role_model import Role
from app.extensions import db
from app.utils.password_utils import hash_password
from app.models.status_model import Status
from app.models.company_staff_model import CompanyStaff
from app.pre_registration.services import _generate_short_code
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditAction, AuditStatus, AuditModule

def is_safe_url(target: str) -> bool:
    """Verifica que la URL de redirección sea del mismo host."""
    ref_url  = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth_bp.errorhandler(RateLimitExceeded)
def ratelimit_handler(e):
    if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
        return jsonify({"error": "Demasiados intentos. Intente más tarde."}), 429
    flash("Demasiados intentos. Por favor espere antes de continuar.", 'danger')
    return render_template('auth/login.html'), 429

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({"message": "Ya estás autenticado."}), 200
        role_name = 'applicant'
        if current_user.roles_assoc and len(current_user.roles_assoc) > 0:
            role_name = current_user.roles_assoc[0].role.name
        next_page = request.args.get('next')
        if next_page and not is_safe_url(next_page):
            next_page = None
        return redirect(next_page or url_for(f'home_{role_name}'))

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            identifier = data.get('identifier')
            password = data.get('password')
            is_api = True
        else:
            identifier = request.form.get('identifier')
            password = request.form.get('password')
            is_api = False

        if not identifier or not password:
            BinnacleService.log_security_event(
                action_type=AuditAction.LOGIN_FALLIDO.value,
                description=f'Intento de autenticación fallido (credenciales vacías) para: {identifier}',
                user_identifier=identifier,
                status=AuditStatus.FALLIDO.value
            )
            error_msg = "Usuario y/o Contraseña inválidos."
            if is_api:
                return jsonify({"error": error_msg}), 400
            else:
                flash(error_msg, 'danger')
                return render_template('auth/login.html')

        success, user, msg = authenticate_user(identifier, password)

        if success and user:
            BinnacleService.log_security_event(
                action_type=AuditAction.LOGIN_EXITOSO.value,
                description='Inicio de sesión satisfactorio en la plataforma',
                user=user,
                status=AuditStatus.COMPLETADO.value
            )
            remember_me = False
            if is_api:
                remember_me = bool(data.get('remember', False))
            else:
                remember_val = request.form.get('remember', '')
                remember_me = str(remember_val).lower() in ['true', 'on', '1']

            session_token = secrets.token_hex(32)
            session['session_token'] = session_token
            session.permanent = remember_me
            login_user(user, remember=remember_me)

            from app.auth.session_store import set_active_session
            set_active_session(user.id, session_token)
            
            # Extraer rol tempranamente para evitar UnboundLocalError en caso de fallo en notificaciones
            role_name = 'applicant'
            if user.roles_assoc and len(user.roles_assoc) > 0:
                role_name = user.roles_assoc[0].role.name

            try:
                from app.notifications.services import NotificationService
                from app.notifications.enums import NotificationEvent
                from app.models.notification_model import Notification
                
                # Evitar SPAM: Verificar si ya se le envió la bienvenida previamente
                has_welcomed = Notification.query.filter_by(
                    user_id=user.id, 
                    event_code=NotificationEvent.USER_WELCOME_FIRST_LOGIN.value
                ).first()
                    
                role_instructions = {
                    'super_admin': 'Como Super Administrador tienes acceso total a la configuración del sistema, gestión de planteles, y auditoría general.',
                    'state_admin': 'Como Administrador Estadal podrás validar registros de tu estado, ver planteles y consultar estadísticas regionales.',
                    'applicant': 'Como Solicitante puedes hacer seguimiento al estado de tu registro y consignar recaudos faltantes.'
                }
                
                role_translations = {
                    'super_admin': 'Super Administrador',
                    'state_admin': 'Administrador Estadal',
                    'applicant': 'Solicitante'
                }
                
                user_name_str = f"{user.person.first_name} {user.person.last_name}".strip() if hasattr(user, 'person') and user.person else "Usuario"
                
                if not has_welcomed:
                    NotificationService.notify_user(
                        user_id=user.id,
                        event=NotificationEvent.USER_WELCOME_FIRST_LOGIN,
                        context={
                            "user_name": user_name_str,
                            "_display": {
                                "Nivel de Acceso": role_translations.get(role_name, role_name.title()),
                                "Instrucciones": role_instructions.get(role_name, "Explora los módulos disponibles en tu panel de control.")
                            }
                        }
                    )
            except Exception as e:
                print(f"Error enviando notificacion de bienvenida: {e}")
            
            next_page = request.args.get('next')
            if next_page and not is_safe_url(next_page):
                next_page = None

            redirect_target = next_page or url_for(f'home_{role_name}')

            if is_api:
                response = jsonify({
                    "message": msg, 
                    "user_id": user.id, 
                    "role": role_name,
                    "redirect_url": redirect_target
                })
            else:
                flash(msg, 'success')
                response = redirect(redirect_target)

            if remember_me:
                max_age = int(current_app.config.get('REMEMBER_COOKIE_DURATION', timedelta(hours=1)).total_seconds())
                response.set_cookie(
                    'sages_session_token',
                    session_token,
                    max_age=max_age,
                    httponly=True,
                    samesite=current_app.config.get('REMEMBER_COOKIE_SAMESITE', 'Lax'),
                    secure=current_app.config.get('REMEMBER_COOKIE_SECURE', False)
                )

            return response
        else:
            BinnacleService.log_security_event(
                action_type=AuditAction.LOGIN_FALLIDO.value,
                description=f'Intento de autenticación fallido para: {identifier}',
                user_identifier=identifier,
                status=AuditStatus.FALLIDO.value
            )
            if is_api:
                return jsonify({"error": msg}), 401
            else:
                flash("Usuario y/o Contraseña inválidos.", 'danger')
                return render_template('auth/login.html')

    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        from app.auth.session_store import clear_active_session
        user_real = None
        try:
            user_real = current_user._get_current_object()
        except Exception:
            pass
        clear_token = session.get('session_token') or request.cookies.get('sages_session_token')
        if clear_token:
            clear_active_session(current_user.id, token=clear_token)
        BinnacleService.log_security_event(
            action_type=AuditAction.LOGOUT.value,
            description='Cierre de sesión manual',
            user=user_real,
            status=AuditStatus.COMPLETADO.value
        )
    session.clear()
    logout_user()

    if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
        response = jsonify({"message": "Sesión cerrada correctamente."})
    else:
        flash("Has cerrado sesión.", 'success')
        response = redirect(url_for('auth.login'))

    response.delete_cookie(
        current_app.config.get('REMEMBER_COOKIE_NAME', 'remember_token'),
        path=current_app.config.get('REMEMBER_COOKIE_PATH', '/'),
        domain=current_app.config.get('REMEMBER_COOKIE_DOMAIN')
    )
    response.delete_cookie(
        'sages_session_token',
        path=current_app.config.get('REMEMBER_COOKIE_PATH', '/'),
        domain=current_app.config.get('REMEMBER_COOKIE_DOMAIN')
    )
    return response

@login_manager.unauthorized_handler
def handle_unauthorized():
    is_api = (
        request.is_json
        or request.path.startswith('/api/')
        or '/api/' in request.path
        or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html)
    )
    if is_api:
        return jsonify({"error": "Authentication required.", "session_expired": True}), 401
    
    return render_template('auth/unauthorized.html'), 401

@auth_bp.app_errorhandler(403)
def handle_forbidden(e):

    if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
        return jsonify({"error": "Forbidden: You do not have permission."}), 403
    
    return render_template('auth/forbidden.html'), 403

@auth_bp.route('/password', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def password():
    # Si el código ya fue verificado, evitar volver atrás; avanzar a nueva contraseña
    if session.get('pw_reset_verified'):
        return redirect(url_for('new_password'))

    if current_user.is_authenticated:
        role_name = 'applicant'
        if current_user.roles_assoc and len(current_user.roles_assoc) > 0:
            role_name = current_user.roles_assoc[0].role.name
        return redirect(url_for(f'home_{role_name}'))

    if request.method == 'POST':
        id_card = request.form.get('id_card')
        email = request.form.get('email')

        if id_card and not email:
            import re
            if not re.fullmatch(r'\d{7,8}', id_card):
                flash('El formato de la cédula es inválido.', 'danger')
                return render_template('auth/password.html', step=1)
            # Guardamos la cédula en sesión y avanzamos al paso 2
            session['pw_reset_id_card'] = id_card
            return render_template('auth/password.html', step=2)

        if email:
            # Recuperamos la cédula desde la sesión, no del formulario
            id_card = session.pop('pw_reset_id_card', None)
            if not id_card:
                flash('La sesión ha expirado o los datos son inválidos. Por favor, intente de nuevo.', 'danger')
                return redirect(url_for('auth.password'))

            start = time.monotonic()
            person = Person.query.filter_by(identification_number=id_card).first()
            
            if person and person.email.lower() == email.lower():
                code = str(secrets.randbelow(900000) + 100000)
                set_token(person.email, code, minutes=5)
                send_recovery_email(person.email, code)
                session['pw_reset_pending_email'] = person.email
                session['pw_reset_initiated_at'] = time.time()

                BinnacleService.log_security_event(
                    action_type=AuditAction.RECUPERACION_SOLICITADA.value,
                    description='Solicitud de recuperación de contraseña enviada al correo',
                    user_identifier=id_card,
                    status=AuditStatus.COMPLETADO.value
                )

            elapsed = time.monotonic() - start
            time.sleep(max(0, 0.5 - elapsed))
            
            flash('Si los datos coinciden con nuestros registros, recibirás un correo en breve. Si no lo recibes en 5 minutos, verifica que la cédula y el correo ingresados sean los correctos y vuelve a intentarlo.', 'info')
            return redirect(url_for('verify_code'))

        flash('Ingrese su cédula.', 'danger')
        return render_template('auth/password.html', step=1)

    return render_template('auth/password.html', step=1)


@auth_bp.route('/resend-code', methods=['POST'])
@limiter.limit("3 per 10 minutes")
def resend_code():
    """Regenera y reenvía el código de recuperación para el correo en sesión."""
    email = session.get('pw_reset_pending_email')
    
    if not email:
        flash('Sesión expirada para reenviar código.', 'danger')
        return redirect(url_for('auth.password'))

    remaining = get_remaining_seconds(email)
    if remaining > 60:
        flash(f'Ya tienes un código activo que expira en {remaining} segundos. Espera antes de reenviar.', 'warning')
        return redirect(url_for('verify_code'))

    person = Person.query.filter_by(email=email).first()
    if not person:
        session.pop('pw_reset_pending_email', None)
        session.pop('pw_reset_initiated_at', None)
        flash('Si los datos coinciden con nuestros registros, recibirás un correo en breve.', 'info')
        return redirect(url_for('auth.password'))
    
    code = str(secrets.randbelow(900000) + 100000)
    set_token(email, code, minutes=5)

    # La función ya maneja y loguea sus propias excepciones de forma segura
    send_recovery_email(email, code)

    # Mensaje unificado para evitar enumeración de correos
    flash('Si los datos coinciden con nuestros registros, recibirás un correo en breve.', 'info')

    return redirect(url_for('verify_code'))

@auth_bp.route('/cancel-reset', methods=['POST'])
def cancel_reset():
    """Permite al usuario cancelar el flujo de recuperación y destruye el token."""
    email = session.get('pw_reset_pending_email')
    if not email:
        return redirect(url_for('auth.login'))
        
    invalidate_token(email)

    BinnacleService.log_security_event(
        action_type=AuditAction.CANCELACION_RECUPERACION.value,
        description='Proceso de recuperación de contraseña cancelado',
        user_identifier=email,
        status=AuditStatus.COMPLETADO.value
    )
    
    # Limpiamos todas las variables de sesión asociadas a la recuperación
    session.pop('pw_reset_id_card', None)
    session.pop('pw_reset_pending_email', None)
    session.pop('pw_reset_initiated_at', None)
    session.pop('pw_reset_verified', None)
    
    flash('El proceso de recuperación de contraseña ha sido cancelado por su seguridad.', 'info')
    return redirect(url_for('auth.login'))



@auth_bp.route('/activate/<token>', methods=['GET', 'POST'])
def activate_account(token):
    # 1. Validar la firma y expiración del token
    token_status, payload = inspect_activation_token(token)

    # Si el token es legítimo pero expiró (>48h) y el usuario aún está pendiente de activación
    if token_status == 'expired' and payload:
        person = Person.query.get(payload.get('person_id'))
        flow = payload.get('flow', 'applicant')
        is_pending = False
        is_within_7_days = True

        if person:
            if person.user:
                if person.user.status_id == 6:
                    is_pending = True
                    if person.user.created_at:
                        if (datetime.now(timezone.utc) - person.user.created_at).total_seconds() > 7 * 86400:
                            is_within_7_days = False
            else:
                staff_chk = InstitutionalStaff.query.filter_by(person_id=person.id).first()
                if staff_chk and staff_chk.status_id == 6:
                    is_pending = True
                    if staff_chk.created_at:
                        if (datetime.now(timezone.utc) - staff_chk.created_at).total_seconds() > 7 * 86400:
                            is_within_7_days = False

        if is_pending:
            if not is_within_7_days:
                flash('El plazo máximo de 7 días para activar la cuenta ha expirado. Por razones de seguridad el registro ha sido anulado. Por favor, realice una nueva solicitud.', 'warning')
                return redirect(url_for('auth.login'))

            raw_email = payload.get('email') or (person.email if person else '')
            parts = raw_email.split('@') if '@' in raw_email else [raw_email, '']
            u_part = parts[0]
            masked_u = (u_part[:2] + '*' * (len(u_part) - 2)) if len(u_part) > 2 else (u_part + '*')
            masked_email = f"{masked_u}@{parts[1]}" if len(parts) > 1 else raw_email

            return render_template(
                'auth/activate_expired.html',
                token=token,
                person=person,
                flow=flow,
                masked_email=masked_email
            )

    if token_status != 'valid' or not payload:
        BinnacleService.log_security_event(
            action_type=AuditAction.ACTIVACION_TOKEN_INVALIDO.value,
            description='Intento de activación con token inválido o expirado',
            status=AuditStatus.FALLIDO.value
        )
        flash('El enlace de activación es inválido o ha expirado.', 'danger')
        return redirect(url_for('auth.login'))

    person = Person.query.get_or_404(payload['person_id'])
    flow = payload.get('flow', 'applicant')

    # Guard: verificar si la cuenta ya fue activada previamente
    if person.user and person.user.status_id == 1:
        flash('Esta cuenta ya fue activada previamente. Por favor inicie sesión.', 'info')
        return redirect(url_for('auth.login'))

    # Guard de vigencia máxima de 7 días
    ref_date = person.user.created_at if person.user else None
    if ref_date and (datetime.now(timezone.utc) - ref_date).total_seconds() > 7 * 86400:
        flash('El plazo máximo de 7 días para activar la cuenta ha expirado. El registro ha sido anulado. Por favor solicite un nuevo registro.', 'warning')
        return redirect(url_for('auth.login'))

    if flow == 'applicant':
        staff = InstitutionalStaff.query.get_or_404(payload['staff_id'])
    else:
        staff = CompanyStaff.query.get_or_404(payload['staff_id'])

    form = ActivationPasswordForm()

    if form.validate_on_submit():
        try:
            active_status = Status.query.filter_by(status_code='STAT-001').first()
            active_id = active_status.id if active_status else 1

            user = person.user
            if not user:
                # Fallback para registros históricos que no hayan sido pre-creados
                user = User(
                    user_code=_generate_short_code('USR', User, 'user_code'),
                    user_name=person.identification_number,
                    person_id=person.id,
                    status_id=active_id,
                    password=hash_password(form.password.data)
                )
                db.session.add(user)
                db.session.flush()

                applicant_role = Role.query.filter_by(name='applicant').first()
                if applicant_role:
                    user_role = RoleUser(user_id=user.id, role_id=applicant_role.id)
                    db.session.add(user_role)
            else:
                user.password = hash_password(form.password.data)
                user.status_id = active_id

            if flow == 'applicant':
                staff.status_id = active_id
                if staff.institution and staff.institution.status_id != active_id:
                    staff.institution.status_id = active_id
            elif flow == 'administrative':
                staff.status_id = active_id

            db.session.commit()

            if flow == 'applicant':
                BinnacleService.log_security_event(
                    action_type=AuditAction.ACTIVACION_CUENTA.value,
                    description=f'Activación de cuenta y asignación de credenciales para solicitante {person.first_name} {person.last_name}',
                    user=user,
                    status=AuditStatus.COMPLETADO.value
                )
            elif flow == 'administrative':
                sede_name = staff.place.name if hasattr(staff, 'place') else "CORPOELEC"
                BinnacleService.log_security_event(
                    action_type=AuditAction.ACTIVACION_CUENTA.value,
                    description=f'Activación de cuenta administrativa para {person.first_name} {person.last_name} (Sede: {sede_name})',
                    user=user,
                    status=AuditStatus.COMPLETADO.value
                )

            flash('¡Tu cuenta ha sido activada exitosamente! Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR ACTIVATION]: {e}")
            flash('Ocurrió un error al intentar activar la cuenta.', 'danger')

    return render_template('auth/activate.html', form=form, person=person, staff=staff, flow=flow)


@auth_bp.route('/activate/resend/<token>', methods=['POST'])
@limiter.limit("5 per hour")
def resend_activation_from_token(token):
    """
    Permite al usuario con token expirado regenerar y reenviar un nuevo enlace de activación.
    """
    token_status, payload = inspect_activation_token(token)
    if token_status != 'expired' or not payload:
        flash('No se pudo verificar el enlace para renovación. Por favor contacte al administrador.', 'danger')
        return redirect(url_for('auth.login'))

    person = Person.query.get(payload.get('person_id'))
    if not person:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('auth.login'))

    flow = payload.get('flow', 'applicant')

    # Guard: verificar si ya completó su activación
    if person.user and person.user.status_id == 1:
        flash('Esta cuenta ya fue activada previamente. Por favor inicie sesión.', 'info')
        return redirect(url_for('auth.login'))

    # Guard de vigencia máxima de 7 días
    ref_date = person.user.created_at if person.user else None
    if ref_date and (datetime.now(timezone.utc) - ref_date).total_seconds() > 7 * 86400:
        flash('El plazo máximo de 7 días para activar la cuenta ha expirado. Por razones de seguridad el registro ha sido anulado. Por favor solicite un nuevo registro.', 'warning')
        return redirect(url_for('auth.login'))

    # Generar un nuevo token fresco con vigencia de 48h
    payload['user_id'] = person.user.id if person.user else None
    new_token = generate_activation_token(payload)
    full_name = f"{person.first_name} {person.last_name}".strip()

    if flow == 'applicant':
        staff = InstitutionalStaff.query.get(payload.get('staff_id'))
        inst_name = staff.institution.institution_name if staff and staff.institution else ""
        send_applicant_activation_email(
            to_email=person.email,
            token=new_token,
            full_name=full_name,
            institution_name=inst_name
        )
    else:
        staff = CompanyStaff.query.get(payload.get('staff_id'))
        place_name = staff.place.name if staff and staff.place else "CORPOELEC"
        role_display = "Personal Administrativo"
        if person.user and person.user.roles_assoc:
            r_name = person.user.roles_assoc[0].role.name
            role_display = "Super Administrador" if r_name == 'super_admin' else "Administrador Estadal"
        send_administrative_activation_email(
            to_email=person.email,
            token=new_token,
            role_name=role_display,
            place_name=place_name,
            full_name=full_name
        )

    BinnacleService.log_security_event(
        action_type=AuditAction.ACTIVACION_CUENTA.value,
        description=f'Regeneración y reenvío de enlace de activación para {full_name} ({person.email})',
        status=AuditStatus.COMPLETADO.value
    )

    flash(f'Hemos enviado un nuevo enlace de activación a su correo registrado. Revise su bandeja de entrada o carpeta de spam.', 'success')
    return redirect(url_for('auth.login'))

