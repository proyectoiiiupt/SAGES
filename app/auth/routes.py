from flask import request, jsonify, redirect, url_for, flash, render_template, session
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.auth.services import authenticate_user
from app.extensions import login_manager, limiter
from flask_limiter.errors import RateLimitExceeded
from urllib.parse import urlparse, urljoin
import secrets
import time
from app.utils.email_utils import send_recovery_email
from app.models.person_model import Person
from app.auth.token_store import set_token, get_remaining_seconds, invalidate_token
from app.auth.forms import ActivationPasswordForm
from app.utils.activation_utils import verify_activation_token
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
        return redirect(url_for(f'home_{role_name}'))

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
                remember_me = data.get('remember', False)
            else:
                remember_me = request.form.get('remember') == 'true'

            login_user(user, remember=remember_me)
            
            role_name = 'applicant'
            if user.roles_assoc and len(user.roles_assoc) > 0:
                role_name = user.roles_assoc[0].role.name
            
            if is_api:
                return jsonify({
                    "message": msg, 
                    "user_id": user.id, 
                    "role": role_name,
                    "redirect_url": url_for(f'home_{role_name}')
                }), 200
            else:
                flash(msg, 'success')
                next_page = request.args.get('next')
                if next_page and not is_safe_url(next_page):
                    next_page = None
                return redirect(next_page or url_for(f'home_{role_name}'))
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
@login_required
def logout():
    BinnacleService.log_security_event(
        action_type=AuditAction.LOGOUT.value,
        description='Cierre de sesión manual',
        user=current_user,
        status=AuditStatus.COMPLETADO.value
    )
    logout_user()
    if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
        return jsonify({"message": "Sesión cerrada correctamente."}), 200
        
    flash("Has cerrado sesión.", 'success')
    return redirect(url_for('auth.login'))

@login_manager.unauthorized_handler
def handle_unauthorized():

    if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
        return jsonify({"error": "Authentication required."}), 401
    

    return render_template('auth/unauthorized.html'), 401

@auth_bp.app_errorhandler(403)
def handle_forbidden(e):

    if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
        return jsonify({"error": "Forbidden: You do not have permission."}), 403
    
    return render_template('auth/forbidden.html'), 403

@auth_bp.route('/password', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def password():

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
    payload = verify_activation_token(token)
    if not payload:
        BinnacleService.log_security_event(
            action_type=AuditAction.ACTIVACION_TOKEN_INVALIDO.value,
            description='Intento de activación con token inválido o expirado',
            status=AuditStatus.FALLIDO.value
        )
        flash('El enlace de activación es inválido o ha expirado.', 'danger')
        return redirect(url_for('auth.login'))

    person = Person.query.get_or_404(payload['person_id'])
    
    flow = payload.get('flow', 'applicant')

    # Para el flujo de solicitantes, si ya tiene usuario, significa que ya se activó
    if flow == 'applicant' and person.user:
        flash('Esta cuenta ya fue activada previamente. Por favor inicie sesión.', 'info')
        return redirect(url_for('auth.login'))

    # Guard de un solo uso para el flujo administrative
    if flow == 'administrative':
        admin_user = person.user
        if not admin_user:
            flash('El usuario administrativo no fue encontrado. Contacte a soporte.', 'danger')
            return redirect(url_for('auth.login'))
        _active_check = Status.query.filter_by(status_code='STAT-001').first()
        if _active_check and admin_user.status_id == _active_check.id:
            flash('Esta cuenta ya fue activada previamente. Por favor inicie sesión.', 'info')
            return redirect(url_for('auth.login'))

    if flow == 'applicant':
        staff = InstitutionalStaff.query.get_or_404(payload['staff_id'])
    else:
        staff = CompanyStaff.query.get_or_404(payload['staff_id'])

    form = ActivationPasswordForm()

    if form.validate_on_submit():
        try:
            if flow == 'applicant':
                # 2. Crear la cuenta de usuario vinculada
                new_user = User(
                    user_code=_generate_short_code('USR', User, 'user_code'),
                    user_name=person.identification_number,
                    person_id=person.id,
                    status_id=1,
                    password=hash_password(form.password.data)
                )
                db.session.add(new_user)
                db.session.flush()

                # 3. Asignar rol por defecto (applicant)
                applicant_role = Role.query.filter_by(name='applicant').first()
                if applicant_role:
                    user_role = RoleUser(user_id=new_user.id, role_id=applicant_role.id)
                    db.session.add(user_role)

                # 4. Actualizar el estatus institucional a Activo/Aprobado
                staff.status_id = 1
            elif flow == 'administrative':
                # El User fue pre-creado en services.py con STAT-006 (En proceso).
                # El guard anterior garantiza que person.user existe y está en STAT-006.
                user = person.user
                # 1. Contraseña definitiva con bcrypt (utilitario centralizado)
                user.password = hash_password(form.password.data)
                # 2. Activar User: STAT-006 -> STAT-001
                active_status = Status.query.filter_by(status_code='STAT-001').first()
                if active_status:
                    user.status_id = active_status.id
                    # 3. Activar CompanyStaff: STAT-006 -> STAT-001
                    staff.status_id = active_status.id

            db.session.commit()

            if flow == 'applicant':
                BinnacleService.log_security_event(
                    action_type=AuditAction.ACTIVACION_CUENTA.value,
                    description=f'Activación de cuenta y creación de credenciales para solicitante {person.first_name} {person.last_name}',
                    user=new_user,
                    status=AuditStatus.COMPLETADO.value
                )
            elif flow == 'administrative':
                sede_name = staff.place.name if hasattr(staff, 'place') else staff.institution.institution_name
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

