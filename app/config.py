import os
from datetime import timedelta

class Config:
    """Configuración base de la aplicación."""
    # Seguridad
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key')
    
    # Base de Datos
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'postgres')
    
    # Cadena de conexión a PostgreSQL
    SQLALCHEMY_DATABASE_URI = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Desactivar el trackeo de modificaciones para ahorrar memoria
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 1. Tiempo de expiración de la sesión estándar (de sesión activa)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # 2. Tiempo de expiración de la cookie "Recordarme" (remember=True)
    REMEMBER_COOKIE_DURATION = timedelta(hours=1)

    # Configuración de CAPTCHA (Cloudflare Turnstile)
    CAPTCHA_SITE_KEY   = os.environ.get('CAPTCHA_SITE_KEY', '1x00000000000000000000AA')
    CAPTCHA_SECRET_KEY = os.environ.get('CAPTCHA_SECRET_KEY', '1x0000000000000000000000000000000AA')

    # Configuración de subida de archivos (Comprobantes)
    UPLOAD_FOLDER      = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))  # 5 MB