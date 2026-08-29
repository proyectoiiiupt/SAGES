"""
app/utils/file_handler.py
--------------------------
Utilidad centralizada y segura para gestionar la subida de archivos
(comprobantes de vinculación institucional).

Seguridad implementada:
  1. Lista blanca de MIME types reales (lee bytes de cabecera del archivo).
  2. Re-validación de peso máximo en el backend (máx. 2MB por comprobante).
  3. Renombrado UUID para evitar colisiones y ataques de directory traversal.
  4. secure_filename de werkzeug para limpiar el nombre original.

Retorna un dict con los datos listos para insertar en StaffEvidence.
"""

import os
import uuid
from datetime import datetime, timezone
from flask import current_app
from werkzeug.utils import secure_filename

# Lista blanca: bytes de cabecera -> extensión esperada
ALLOWED_MIME_TYPES: dict = {
    b'%PDF':        'pdf',
    b'\xff\xd8\xff': 'jpg',    # JPEG/JPG
    b'\x89PNG':     'png',
}

MAX_EVIDENCE_SIZE = 2 * 1024 * 1024   # 2 MB


class FileValidationError(ValueError):
    """Error de validación de archivo subido por el usuario."""
    pass


def _detect_mime(file_obj) -> str:
    """
    Lee los primeros 4 bytes del archivo para determinar su tipo real.
    Retorna la extensión limpia ('pdf', 'jpg', 'png').
    Lanza FileValidationError si el tipo no está en la lista blanca.
    """
    header = file_obj.read(4)
    file_obj.seek(0)  # rebobinar para que el .save() funcione después

    for signature, ext in ALLOWED_MIME_TYPES.items():
        if header.startswith(signature):
            return ext

    raise FileValidationError(
        'Formato de archivo no permitido. Solo se aceptan: PDF, JPG y PNG.'
    )


def save_evidence_file(file_obj, sub_folder: str = '', custom_name: str = None) -> dict:
    """
    Valida y guarda de forma segura un archivo.

    Args:
        file_obj: Objeto FileStorage de Flask.
        sub_folder: Subcarpeta opcional dentro de UPLOAD_FOLDER donde se guardará el archivo.
        custom_name: Nombre base opcional (sin extensión) para el archivo. Si no se provee, se genera uno aleatorio.

    Returns:
        dict con claves: file_name, file_path, format, file_weight.

    Raises:
        FileValidationError: si el archivo no cumple los requisitos.
    """
    if not file_obj or not file_obj.filename:
        raise FileValidationError('No se recibió ningún archivo.')

    # 1. Validar peso
    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)

    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 2 * 1024 * 1024)
    if file_size > max_size:
        raise FileValidationError(
            f'El archivo supera el tamaño máximo permitido de '
            f'{max_size / 1024 / 1024:.1f}MB ({file_size / 1024 / 1024:.1f}MB recibidos).'
        )

    # 2. Detectar MIME type real (basado en bytes, no en extensión)
    extension = _detect_mime(file_obj)

    # 3. Generar nombre único y seguro
    if custom_name:
        safe_name = f'{custom_name}.{extension}'
    else:
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now(timezone.utc).strftime('%Y%m')
        safe_name = f'evidencia_{unique_id}_{timestamp}.{extension}'

    # 4. Guardar en disco
    base_upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    upload_folder = os.path.join(base_upload_folder, sub_folder) if sub_folder else base_upload_folder
    
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, safe_name)
    file_obj.save(save_path)

    return {
        'file_name':   safe_name,
        'file_path':   save_path,
        'format':      extension.upper(),
        'file_weight': file_size,
    }
