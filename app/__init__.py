from flask import Flask, redirect, url_for, request, flash, render_template, session, jsonify
from flask_limiter.errors import RateLimitExceeded
from app.config import Config
from app.extensions import db, migrate, login_manager, csrf, limiter

def create_app(config_class=Config) -> Flask:

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)          # Activa protección CSRF global; exige X-CSRFToken en POSTs
    limiter.init_app(app)       # Activa Rate Limiting global
    
    with app.app_context():
        from app import models

    @app.before_request
    def make_session_permanent():
        session.permanent = True

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user_model import User
        from app.models.role_user_model import RoleUser
        from app.models.role_model import Role
        from sqlalchemy.orm import joinedload
        return User.query.options(
            joinedload(User.roles_assoc).joinedload(RoleUser.role).joinedload(Role.permissions_assoc)
        ).get(int(user_id))

    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Registro del blueprint de Instituciones
    from app.institutions import institutions_bp
    app.register_blueprint(institutions_bp, url_prefix='/institutions')

    # Registro del blueprint del sprint de Usuarios
    from app.users.routes import users_bp
    app.register_blueprint(users_bp, url_prefix='/users')

    # Registro del blueprint de Pre Registro
    from app.pre_registration import pre_registration_bp
    app.register_blueprint(pre_registration_bp, url_prefix='/pre-registration')

    @app.route('/')
    def index():
        return render_template('public/index.html')

    from flask import render_template
    from flask_login import login_required, current_user
    from app.decorators import check_permissions, role_required

    @app.route('/home/super_admin')
    @login_required
    @role_required('super_admin')
    @check_permissions('view_home')
    def home_super_admin():
        return render_template('home.html')

    @app.route('/home/state_admin')
    @login_required
    @role_required('state_admin')
    @check_permissions('view_home')
    def home_state_admin():
        return render_template('home.html')

    @app.route('/home/applicant')
    @login_required
    @role_required('applicant')
    @check_permissions('view_home')
    def home_applicant():
        return render_template('home.html')

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
            return jsonify({"error": "Demasiados intentos. Intente más tarde."}), 429
        flash("Demasiados intentos. Por favor espere antes de continuar.", 'danger')
        return render_template('auth/login.html'), 429
    
    @app.route('/verify-code', methods=['GET', 'POST'])
    @limiter.limit("10 per 5 minutes", methods=["POST"])
    def verify_code():
        import re
        import time
        # Recibe 'email' desde la sesión y un código por POST; valida expiración
        email = session.get('pw_reset_pending_email', '').strip()
        
        if request.method == 'GET' and not email:
            flash('No hay un proceso de recuperación activo.', 'warning')
            return redirect(url_for('auth.password'))
            
        initiated_at = session.get('pw_reset_initiated_at', 0)
        if time.time() - initiated_at > 600:  # 10 minutos máximo
            session.clear()
            flash('La sesión de recuperación ha expirado. Inicie el proceso de nuevo.', 'danger')
            return redirect(url_for('auth.password'))

        EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
        if not email or not EMAIL_RE.match(email):
            flash('Sesión de recuperación inválida o expirada.', 'danger')
            return redirect(url_for('auth.password'))

        # Import local to avoid circular imports at app import time
        from app.auth.token_store import validate_token_attempt

        if request.method == 'POST':
            entered_code = request.form.get('code')
            status = validate_token_attempt(email, entered_code)

            if status == 'VALID':
                # El token ya fue consumido de forma atómica en validate_token_attempt

                # Prevenir Session Fixation regenerando la sesión antes de elevar privilegios
                old_email = email
                session.clear()

                # Guardar estado en sesión
                session['pw_reset_email']     = old_email
                session['pw_reset_verified']  = True
                session['_fresh']             = True
                session.modified = True

                flash('Código verificado exitosamente. Ingrese su nueva contraseña.', 'success')
                return redirect(url_for('new_password'))
            elif status == 'BLOCKED':
                flash('Demasiados intentos incorrectos. El código ha sido invalidado. Solicite un reenvío.', 'danger')
            elif status == 'EXPIRED':
                flash('El código ha expirado (validez de 5 min). Solicite un reenvío.', 'warning')
            else:
                flash('El código es incorrecto. Verifique e intente nuevamente.', 'danger')

        from app.auth.token_store import get_remaining_seconds
        remaining = get_remaining_seconds(email) if email else 0
        
        if request.method == 'GET' and remaining == 0:
            flash('Tu código ha expirado o no existe. Solicita un reenvío.', 'warning')
        
        # Enmascarar correo para privacidad
        masked_email = ""
        if email and "@" in email:
            parts = email.split("@")
            username = parts[0]
            domain = parts[1]
            if len(username) > 2:
                masked_username = username[0] + "*" * (len(username) - 2) + username[-1]
            else:
                masked_username = "*" * len(username)
            masked_email = f"{masked_username}@{domain}"
            
        from markupsafe import escape
        safe_masked_email = str(escape(masked_email))
            
        return render_template('auth/verify_code.html', email=safe_masked_email, remaining=remaining)

    @app.route('/new-password', methods=['GET', 'POST'])
    @limiter.limit("5 per 10 minutes", methods=["POST"])
    def new_password():
        # Verificar estado en sesión
        if not session.get('pw_reset_verified'):
            flash('Debe verificar su código antes de cambiar la contraseña.', 'danger')
            return redirect(url_for('auth.password'))

        email = session.get('pw_reset_email')
        if not email:
            flash('Sesión de recuperación inválida.', 'danger')
            return redirect(url_for('auth.password'))
        
        from werkzeug.security import generate_password_hash
        from app.models.person_model import Person
        import re

        if request.method == 'POST':
            password = request.form.get('password')
            password2 = request.form.get('password2')
            if not password or password != password2:
                flash('Las contraseñas no coinciden o están vacías.', 'danger')
                return render_template('auth/new_password.html')
                
            if len(password) > 128:
                flash('La contraseña no puede exceder 128 caracteres.', 'danger')
                return render_template('auth/new_password.html')

            pattern = re.compile(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[$@.!%*?&]).{8,128}$')
            if not pattern.match(password):
                flash('La contraseña no cumple los requisitos de seguridad.', 'danger')
                return render_template('auth/new_password.html')

            person = Person.query.filter_by(email=email).first()
            if not person or not person.user:
                flash('Usuario no encontrado para ese correo.', 'danger')
                return redirect(url_for('auth.password'))

            user = person.user
            from app.utils.password_utils import change_user_password
            change_user_password(user, password)

            # Limpiar sesión
            session.pop('pw_reset_verified', None)
            session.pop('pw_reset_email', None)

            flash('Contraseña actualizada. Inicia sesión con tu nueva contraseña.', 'success')
            return redirect(url_for('auth.login'))

        return render_template('auth/new_password.html')

    @app.after_request
    def add_security_headers(response):
        """
        Añadir cabeceras de seguridad y prevenir caché.
        """
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: cid:; "
            "font-src 'self'; "
            "frame-ancestors 'self';"
        )
        return response

    return app 