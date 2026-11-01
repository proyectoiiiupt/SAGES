import qrcode
import io
import hmac
import hashlib
from flask import current_app

def generate_verification_token(request_code: str, request_id: int) -> str:
    """
    Genera un token criptográfico único para validar la autenticidad del trámite.
    Utiliza HMAC-SHA256 combinando el SECRET_KEY del servidor con los datos de la solicitud.
    """
    # Se recomienda que SECRET_KEY esté configurado en el entorno. Fallback de emergencia.
    secret_key = current_app.config.get('SECRET_KEY', 'sages_default_secret_key').encode('utf-8')
    message = f"{request_code}-{request_id}".encode('utf-8')
    
    # Genera el hash seguro y lo retorna en formato hexadecimal
    return hmac.new(secret_key, message, hashlib.sha256).hexdigest()

def generate_qr_buffer(url: str) -> io.BytesIO:
    """
    Genera un Código QR apuntando a una URL y lo exporta puramente en memoria (RAM).
    Nivel de corrección de error Alto (30%) para garantizar escaneo incluso en impresiones dañadas.
    No escribe archivos en el disco duro (Previene I/O bottlenecks y fugas de datos).
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% de redundancia (H)
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Crear imagen PNG en memoria usando PIL
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer

def create_receipt_qr(request_code: str, request_id: int) -> tuple[str, io.BytesIO]:
    """
    Función orquestadora que se llamará durante la radicación: 
    1. Genera el token de verificación seguro.
    2. Construye la URL oficial (Absoluta).
    3. Retorna el token (para guardarlo en BD si se requiere) y el stream binario del QR.
    """
    # Se espera que APP_BASE_URL esté definido en .env, fallback a localhost para dev
    base_url = current_app.config.get('APP_BASE_URL', 'http://127.0.0.1:5000')
    
    token = generate_verification_token(request_code, request_id)
    canonical_url = f"{base_url}/requests/verify/{token}"
    
    qr_buffer = generate_qr_buffer(canonical_url)
    
    return token, qr_buffer
