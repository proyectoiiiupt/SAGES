# IMPORTACIONES Y CONFIGURACIÓN INICIAL DEL SISTEMA SMTP (Líneas 1-10)
# Importa librerías para manejo de fechas, protocolo SMTP, creación de emails MIME y variables de entorno.
# Configura almacenamiento en memoria para tokens de recuperación temporal.
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from flask import current_app

_tokens = {}


# FUNCIÓN DE GENERACIÓN DE TOKENS (Líneas 14-20)
# Genera y almacena un token temporal con expiración de 5 minutos por defecto.
def set_token(email: str, code: str, minutes: int = 5):
    key = email.lower()
    _tokens[key] = {
        'code': code,
        'expires_at': datetime.utcnow() + timedelta(minutes=minutes),
        'attempts': 0
    }


# FUNCIÓN DE VERIFICACIÓN Y CONSUMO DE TOKENS (Líneas 25-35)
# Verifica si el token es válido y lo elimina después de usarlo.
def verify_token(email: str, code: str) -> bool:
    key = email.lower()
    entry = _tokens.get(key)
    if not entry:
        return False
    if entry['code'] != code:
        return False
    if datetime.utcnow() > entry['expires_at']:
        _tokens.pop(key, None)
        return False
    _tokens.pop(key, None)
    return True


# FUNCIÓN DE VALIDACIÓN DE INTENTOS (Líneas 40-61)
# Valida token con manejo de intentos fallidos y bloqueo después de 3 intentos incorrectos.
# Retorna estados: VALID, INVALID, EXPIRED, BLOCKED.
def validate_token_attempt(email: str, code: str, max_attempts: int = 3) -> str:
    key = email.lower()
    entry = _tokens.get(key)
    if not entry:
        return 'EXPIRED'

    if datetime.utcnow() > entry['expires_at']:
        _tokens.pop(key, None)
        return 'EXPIRED'

    if entry.get('attempts', 0) >= max_attempts:
        _tokens.pop(key, None)
        return 'BLOCKED'

    if entry['code'] != code:
        entry['attempts'] = entry.get('attempts', 0) + 1
        if entry['attempts'] >= max_attempts:
            _tokens.pop(key, None)
            return 'BLOCKED'
        return 'INVALID'

    return 'VALID'


# FUNCIÓN DE CÁLCULO DE TIEMPO RESTANTE (Líneas 66-71)
# Calcula los segundos restantes antes de que expire el token para mostrar cuenta regresiva en la UI.
def get_remaining_seconds(email: str) -> int:
    key = email.lower()
    entry = _tokens.get(key)
    if not entry:
        return 0
    remaining = entry['expires_at'] - datetime.utcnow()
    return max(0, int(remaining.total_seconds()))


# FUNCIÓN PRINCIPAL DE ENVÍO DE EMAILS SMTP (Líneas 79-184)
# Envía correo con código de recuperación usando SMTP directo (Gmail).
# Configura conexión SMTP, crea mensaje MIME con versión texto plano y HTML, y maneja errores con fallback para desarrollo.
def send_recovery_email(email: str, code: str) -> bool:
    try:
        # Configuración SMTP desde variables de entorno
        mail_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        mail_port = int(os.environ.get('MAIL_PORT', 587))
        mail_use_tls = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
        mail_username = os.environ.get('MAIL_USERNAME')
        mail_password = os.environ.get('MAIL_PASSWORD')

        # Fallback para desarrollo sin configuración de correo
        if not mail_username or not mail_password:
            if os.environ.get('FLASK_ENV') == 'development':
                print(f"=== SIMULACIÓN DE ENVÍO DE CORREO ===")
                print(f"Para: {email}")
                print(f"Código: {code}")
                print(f"=====================================")
                return True
            return False

        # Crear mensaje MIME con versión texto plano y HTML
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'SAGES - Código de Recuperación de Contraseña'
        msg['From'] = mail_username
        msg['To'] = email

        # Versión texto plano
        text_part = MIMEText(f'''Hola,

Tu código de recuperación de contraseña es: {code}

Este código expirará en 5 minutos.

Si no solicitaste este código, por favor ignora este correo.

---
Sistema SAGES - CORPOELEC
Gestión de Solicitudes de Servicios de Formación Comunitaria UREE''', 'plain')

        # Versión HTML con estilos
        html_part = MIMEText(f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1a73e8; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f8f9fa; }}
        .code {{ font-size: 24px; font-weight: bold; background: #e8f0fe; padding: 15px; text-align: center; margin: 20px 0; border-radius: 5px; letter-spacing: 3px; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>SAGES - CORPOELEC</h2>
            <p>Sistema de Gestión de Solicitudes</p>
        </div>
        <div class="content">
            <h3>Código de Recuperación de Contraseña</h3>
            <p>Hola,</p>
            <p>Tu código de recuperación de contraseña es:</p>
            <div class="code">{code}</div>
            <p><strong>Este código expirará en 5 minutos.</strong></p>
            <p>Si no solicitaste este código, por favor ignora este correo.</p>
        </div>
        <div class="footer">
            <p>Sistema Automatizado de Gestión de Solicitudes de Servicios de Formación Comunitaria UREE (CORPOELEC)</p>
        </div>
    </div>
</body>
</html>''', 'html')

        msg.attach(text_part)
        msg.attach(html_part)

        # Conexión y envío por SMTP
        with smtplib.SMTP(mail_server, mail_port) as server:
            if mail_use_tls:
                server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)

        return True

    except smtplib.SMTPAuthenticationError as e:
        # Fallback para desarrollo con error de autenticación
        if os.environ.get('FLASK_ENV') == 'development':
            print(f"❌ ERROR DE AUTENTICACIÓN SMTP: {e}")
            print(f"❌ La contraseña de aplicación de Gmail no es válida o ha expirado.")
            print(f"❌ Genera una nueva contraseña en: https://myaccount.google.com/apppasswords")
            print(f"=== SIMULACIÓN DE ENVÍO DE CORREO (FALLBACK) ===")
            print(f"Para: {email}")
            print(f"Código: {code}")
            print(f"=====================================")
            return True
        return False
    except Exception as e:
        # Fallback para desarrollo con errores generales
        if os.environ.get('FLASK_ENV') == 'development':
            print(f"Error enviando correo: {e}")
            print(f"Código generado: {code} para {email}")
            print(f"=== SIMULACIÓN DE ENVÍO DE CORREO (FALLBACK) ===")
            print(f"Para: {email}")
            print(f"Código: {code}")
            print(f"=====================================")
            return True
        return False
