import os
from datetime import timedelta

class Config:
    """Configuración base de la aplicación."""
    # Seguridad
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key')
    
    # CSRF Protection para Flask-WTF
    WTF_CSRF_ENABLED = True
    
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