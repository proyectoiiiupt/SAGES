from flask import Flask, redirect, url_for, request, flash
from app.config import Config
from app.extensions import db, migrate, login_manager

def create_app(config_class=Config) -> Flask:

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    with app.app_context():
        from app import models

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user_model import User
        return User.query.get(int(user_id))

    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Registro del blueprint del sprint de Usuarios
    from app.users.routes import users_bp
    app.register_blueprint(users_bp, url_prefix='/users')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

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
    
    @app.route('/verify-code', methods=['GET', 'POST'])
    def verify_code():
        # Recibe 'email' por querystring y un código por POST; valida expiración
        email = request.args.get('email')

        # Import local to avoid circular imports at app import time
        from app.auth.token_store import validate_token_attempt

        if request.method == 'POST':
            entered_code = request.form.get('code')
            status = validate_token_attempt(email, entered_code)

            if status == 'VALID':
                flash('Código verificado exitosamente. Ingrese su nueva contraseña.', 'success')
                return redirect(url_for('new_password', email=email, token=entered_code))
            elif status == 'BLOCKED':
                flash('Demasiados intentos incorrectos. El código ha sido invalidado. Solicite un reenvío.', 'danger')
            elif status == 'EXPIRED':
                flash('El código ha expirado (validez de 5 min). Solicite un reenvío.', 'warning')
            else:
                flash('El código es incorrecto. Verifique e intente nuevamente.', 'danger')

        from app.auth.token_store import get_remaining_seconds
        remaining = get_remaining_seconds(email)
        return render_template('auth/verify_code.html', email=email, remaining=remaining)

    @app.route('/new-password', methods=['GET', 'POST'])
    def new_password():
        # Muestra form para cambiar la contraseña luego de verificar código
        email = request.args.get('email') or request.form.get('email')
        token = request.args.get('token') or request.form.get('token')

        from app.auth.token_store import verify_token
        from werkzeug.security import generate_password_hash
        from app.models.person_model import Person

        if request.method == 'POST':
            password = request.form.get('password')
            password2 = request.form.get('password2')
            if not password or password != password2:
                flash('Las contraseñas no coinciden o están vacías.', 'danger')
                return render_template('auth/new_password.html', email=email, token=token)

            # Verify and consume token
            if not verify_token(email, token):
                flash('Token inválido o expirado.', 'danger')
                return redirect(url_for('auth.password'))

            person = Person.query.filter_by(email=email).first()
            if not person or not person.user:
                flash('Usuario no encontrado para ese correo.', 'danger')
                return redirect(url_for('auth.password'))

            user = person.user
            from app.utils.password_utils import change_user_password
            change_user_password(user, password)

            flash('Contraseña actualizada. Inicia sesión con tu nueva contraseña.', 'success')
            return redirect(url_for('auth.login'))

        # GET
        return render_template('auth/new_password.html', email=email, token=token)

    @app.after_request
    def add_header(response):
        """
        Add headers to both force latest IE rendering engine or Chrome Frame,
        and also to cache the rendered page for 0 seconds.
        This prevents users from using the back button to view protected pages after logout.
        """
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return app 