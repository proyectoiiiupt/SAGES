from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ──────────────────────────────────────────────────────────
# Instancias de extensiones (sin app aún).
# Se inicializan en la factory con extension.init_app(app).
# ──────────────────────────────────────────────────────────
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()          # Protección CSRF global para formularios y AJAX
limiter = Limiter(
    key_func=get_remote_address, # Rate Limiting por IP
    storage_uri="memory://"  # ¡Esta es la línea que quita el warning!
)

# Configuración del manager de sesiones
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning' 