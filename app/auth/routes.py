from flask import request, jsonify, redirect, url_for, flash, render_template, abort
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.auth.services import authenticate_user
from app.extensions import login_manager
import random
# IMPORTACIÓN DE FUNCIONES SMTP (Línea 8)
# Importa funciones del sistema de email SMTP para recuperación de contraseña
from app.utils.email_utils import send_recovery_email, set_token

@auth_bp.route('/login', methods=['GET', 'POST'])
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
            error_msg = "Usuario y/o Contraseña inválidos."
            if is_api:
                return jsonify({"error": error_msg}), 400
            else:
                flash(error_msg, 'danger')
                return render_template('auth/login.html')

        success, user, msg = authenticate_user(identifier, password)

        if success and user:
            login_user(user, remember=True)
            
            role_name = 'applicant'
            if user.roles_assoc and len(user.roles_assoc) > 0:
                role_name = user.roles_assoc[0].role.name
            
            if is_api:
                return jsonify({"message": msg, "user_id": user.id, "role": role_name}), 200
            else:
                flash(msg, 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for(f'home_{role_name}'))
        else:
            if is_api:
                return jsonify({"error": msg}), 401
            else:
                flash("Usuario y/o Contraseña inválidos.", 'danger')
                return render_template('auth/login.html')

    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
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

@auth_bp.route('/admin-test')
@login_required
def admin_test():

    user_roles = [assoc.role.name for assoc in current_user.roles_assoc]

    print(f"DEBUG - Usuario ID {current_user.id} tiene los roles: {user_roles}")
    
    if 'super_admin' not in user_roles:
        abort(403)
        
    return f"<h1>Éxito</h1><p>Bienvenido {current_user.user_name}, tienes acceso de Super Administrador.</p>"

# RUTA DE RECUPERACIÓN DE CONTRASEÑA (Líneas 103-158)
# Flujo completo de recuperación de contraseña con envío de email SMTP.
# Paso 1: Validar cédula, Paso 2: Confirmar email, Generar código y enviar por SMTP.
@auth_bp.route('/password', methods=['GET', 'POST'])
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
            from app.models.person_model import Person
            person = Person.query.filter_by(identification_number=id_card).first()
            if not person:
                flash('Cédula no encontrada.', 'danger')
                return render_template('auth/password.html', step=1)

            return render_template('auth/password.html', step=2, id_card=id_card, person_first_name=person.first_name, person_last_name=person.last_name)

        if id_card and email:
            from app.models.person_model import Person
            person = Person.query.filter_by(identification_number=id_card).first()
            if not person:
                flash('Cédula no encontrada.', 'danger')
                return render_template('auth/password.html', step=1)
            if person.email.lower() != email.lower():
                flash('El correo no coincide con la cédula proporcionada.', 'danger')
                return render_template('auth/password.html', step=2, id_card=id_card, person_first_name=person.first_name, person_last_name=person.last_name)

            code = str(random.randint(100000, 999999))

            set_token(person.email, code, minutes=5)

            try:
                sent = send_recovery_email(person.email, code)
            except Exception:
                sent = False

            if sent:
                flash('Se envió un código al correo registrado.', 'success')
            else:
                flash('No se pudo enviar el correo. El código fue generado; contacte al administrador o solicite reenvío.', 'warning')

            return redirect(url_for('verify_code', email=person.email))

        flash('Ingrese su cédula.', 'danger')
        return render_template('auth/password.html', step=1)

    return render_template('auth/password.html', step=1)


# RUTA DE REENVÍO DE CÓDIGO (Líneas 161-185)
# Regenera y reenvía el código de recuperación por SMTP cuando el usuario solicita un nuevo código.
@auth_bp.route('/resend-code', methods=['GET'])
def resend_code():
    email = request.args.get('email')
    if not email:
        flash('Email ausente para reenviar código.', 'danger')
        return redirect(url_for('auth.password'))

    from app.models.person_model import Person
    person = Person.query.filter_by(email=email).first()
    if not person:
        flash('Si el correo está registrado, se enviará el código.', 'info')
        return redirect(url_for('verify_code', email=email))

    code = str(random.randint(100000, 999999))
    set_token(email, code, minutes=5)

    sent = False
    try:
        sent = send_recovery_email(email, code)
    except Exception:
        sent = False

    if sent:
        flash('Se reenvió código al correo registrado.', 'success')
    else:
        flash('No se pudo enviar el correo. El código fue regenerado; contacte al administrador.', 'warning')

    return redirect(url_for('verify_code', email=email))