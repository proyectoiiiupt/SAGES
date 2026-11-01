import os
import smtplib
import logging
from email.message import EmailMessage
import threading
from flask import url_for

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_content: str, text_content: str, attachments: list = None) -> bool:
    """Utilidad global para el envío de correos con formato HTML, texto y soporte para archivos adjuntos."""
    smtp_user = os.getenv('SMTP_USER') or os.getenv('EMAIL_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    
    if not smtp_user or not smtp_pass:
        error_msg = "SMTP no configurado: falta SMTP_USER o SMTP_PASS en el archivo .env"
        logger.error(error_msg)
        print(f"\n[ERROR SMTP]: {error_msg}\n")
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to_email

    msg.set_content(text_content)
    
    if html_content:
        msg.add_alternative(html_content, subtype='html')
        
        # Adjuntar logo siempre que esté disponible
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo_corpoelec.png')
        if os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as f:
                    msg.get_payload()[1].add_related(f.read(), 'image', 'png', cid='logo_corpoelec')
            except Exception as e:
                logger.warning(f"Error al adjuntar imagen inline: {e}")
                
    # Procesar archivos adjuntos si existen
    if attachments:
        for att in attachments:
            msg.add_attachment(
                att['content'], 
                maintype=att.get('maintype', 'application'), 
                subtype=att.get('subtype', 'octet-stream'), 
                filename=att['filename']
            )

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
        print(f"[SMTP ÉXITO]: Correo '{subject}' enviado exitosamente a {to_email}")
        return True
    except Exception as e:
        logger.error(f"Error enviando correo a {to_email}: {e}")
        print(f"\n[ERROR SMTP]: Falló el envío a {to_email}. Causa: {e}\n")
        return False


def get_logo_html() -> str:
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo_corpoelec.png')
    if os.path.exists(logo_path):
        return '<img src="cid:logo_corpoelec" alt="CORPOELEC" style="max-width: 220px; height: auto; display: block; border: 0;">'
    return '<span style="font-size: 24px; font-weight: 800; color: #1c3d73; letter-spacing: 1px;">(⚡) CORPOELEC</span>'


def send_recovery_email(to_email: str, code: str) -> bool:
    import html
    safe_code = html.escape(str(code))
    
    subject = 'Código de recuperación'
    text_content = f"Hola,\n\nSu código de recuperación es: {safe_code}\n\nEste código expira en 5 minutos.\n\nSi no solicitó esto, ignore este mensaje."
    
    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">CÓDIGO DE VERIFICACIÓN</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Su código de seguridad es:</p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <div style="background-color: #f3f4f6; border-radius: 12px; padding: 20px 30px; display: inline-block; min-width: 200px; text-align: center; border: 1px solid #e5e7eb;">
                        <span style="font-size: 36px; font-weight: 800; color: #1c3d73; letter-spacing: 6px; font-family: monospace;">{safe_code}</span>
                    </div>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        Este es un código de seguridad autorizado únicamente para el consumo del receptor, el cual debe permanecer privado y no deberá ser compartido por ningún medio.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content, text_content)


def send_preregistration_email(to_email: str, full_name: str, institution_name: str) -> bool:
    import html
    safe_name = html.escape(full_name)
    safe_institution = html.escape(institution_name)
    
    subject = "Confirmación de Registro - Sistema UREE"
    text_content = f"""Estimado/a {safe_name},

Hemos recibido exitosamente su solicitud de registro como Representante Institucional en el Sistema para la Gestión de Solicitudes de Formación Comunitaria de Uso Racional y Eficiente de la Energía (UREE).

Actualmente, su perfil y la documentación se encuentran en fase de Revisión. Este proceso de validación institucional es estrictamente necesario para aprobar su vinculación con {safe_institution}.

Le notificaremos por esta vía una vez que su cuenta sea verificada y activada. A partir de ese momento, podrá iniciar sesión en la plataforma.

Por favor, no responda a este correo automatizado."""

    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 0 40px;">
                    <h2 style="font-size: 20px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0;">Estimado/a {safe_name},</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6;">
                        Hemos recibido exitosamente su solicitud de registro como Representante Institucional en el Sistema para la Gestión de Solicitudes de Formación Comunitaria de Uso Racional y Eficiente de la Energía (UREE).
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6;">
                        Actualmente, su perfil y la documentación se encuentran en fase de <strong>Revisión</strong>. Este proceso de validación institucional es estrictamente necesario para aprobar su vinculación con <strong>{safe_institution}</strong>.
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.6;">
                        Le notificaremos por esta vía una vez que su cuenta sea verificada y activada. A partir de ese momento, podrá iniciar sesión en la plataforma.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 10px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        Por favor, no responda a este correo automatizado.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return send_email(to_email, subject, html_content, text_content)


def send_invitation_email(to_email: str, link: str, institution_name: str) -> bool:
    """Envía un correo con el enlace de invitación para colaborador de una institución."""
    import html
    safe_institution = html.escape(institution_name)
    
    subject = "Invitación de Colaborador"
    text_content = (
        f"Hola,\n\n"
        f"Has sido invitado a colaborar en {institution_name}.\n\n"
        f"Para completar tu registro, haz clic en el siguiente enlace:\n{link}\n\n"
        f"Este enlace expira en 48 horas.\n\n"
        f"Si no solicitaste esto, ignora este mensaje."
    )

    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">INVITACIÓN DE COLABORADOR</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5;">Has sido invitado a colaborar en:</p>
                    <p style="font-size: 18px; font-weight: 600; color: #1c3d73; margin: 0 0 25px 0; line-height: 1.5;">{safe_institution}</p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Para completar tu registro, haz clic en el siguiente botón:</p>
                    <a href="{link}" style="display: inline-block; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; margin: 10px 0;">Completar Registro</a>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        Este enlace de invitación es válido únicamente por 48 horas. Si no utilizas el enlace dentro de este período, deberás solicitar una nueva invitación.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return send_email(to_email, subject, html_content, text_content)

def send_applicant_activation_email(to_email: str, token: str) -> bool:
    """Envía el enlace de activación al solicitante tras aprobar su registro (US-10)."""
    activation_url = url_for('auth.activate_account', token=token, _external=True)
    subject = "Solicitud Aprobada — Active su Cuenta en SAGES"
    
    text_content = (
        f"Estimado/a representante,\n\n"
        f"Su comprobante de vinculación ha sido validado satisfactoriamente.\n\n"
        f"Para activar su cuenta, haga clic en el siguiente enlace:\n{activation_url}\n\n"
        f"Este enlace tiene una caducidad estricta de 48 horas.\n"
    )

    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>{subject}</title></head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr><td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td></tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">VALIDACIÓN DE CUENTA EXITOSA</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6; text-align: left;">
                        Estimado/a representante, le informamos que su comprobante de vinculación con la institución educativa ha sido revisado y <strong>validado satisfactoriamente</strong> por la Coordinación de UREE.
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.6; text-align: left;">
                        Para habilitar su acceso y comenzar la carga de solicitudes, defina su contraseña de acceso seguro haciendo clic en el siguiente botón:
                    </p>
                    <a href="{activation_url}" style="display: inline-block; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; margin: 10px 0;">Activar Cuenta y Definir Contraseña</a>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        * Este enlace tiene una caducidad estricta de 48 horas por políticas de seguridad. Si no ha solicitado este registro, ignore este mensaje.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    # Despacho en hilo independiente para no bloquear el request de aprobación
    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True


def send_administrative_activation_email(to_email: str, token: str, role_display: str, place_name: str, full_name: str) -> bool:
    """Envía el enlace de activación a personal administrativo tras su registro (US-13)."""
    import html
    safe_role = html.escape(role_display)
    safe_name = html.escape(full_name)
    safe_place = html.escape(place_name)
    
    activation_url = url_for('auth.activate_account', token=token, _external=True)
    subject = "Credenciales de Acceso Administrativo — SAGES CORPOELEC"
    
    text_content = (
        f"Alta Corporativa Exitosa\n\n"
        f"Estimado {safe_name}, usted ha sido registrado en el Sistema de Gestión de Solicitudes de Formación de La Corporación Eléctrica Nacional (CORPOELEC) con un perfil administrativo.\n\n"
        f"Para activar su cuenta, haga clic en el siguiente enlace:\n{activation_url}\n\n"
        f"Este enlace tiene una caducidad estricta de 48 horas.\n"
    )

    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>{subject}</title></head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr><td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td></tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">REGISTRO CORPORATIVO CORPOELEC</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6; text-align: left;">
                        Estimado <strong>{safe_name}</strong>, usted ha sido registrado en el Sistema de Gestión de Solicitudes de Formación de La Corporación Eléctrica Nacional (CORPOELEC) con un perfil administrativo.
                    </p>
                    <div style="background-color: #f3f4f6; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: left;">
                        <p style="margin: 0 0 10px 0; font-size: 14px;"><strong>Tipo de Usuario:</strong> <span style="color: #1c3d73;">{safe_role}</span></p>
                        <p style="margin: 0; font-size: 14px;"><strong>Sede de Adscripción:</strong> <span style="color: #1c3d73;">{safe_place}</span></p>
                    </div>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.6; text-align: left;">
                        Para habilitar su acceso al panel de control, defina su contraseña haciendo clic en el siguiente botón:
                    </p>
                    <a href="{activation_url}" style="display: inline-block; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; margin: 10px 0;">Establecer Contraseña</a>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        * Este enlace es personal e intransferible, con caducidad estricta de 48 horas. Si usted no es el destinatario de este mensaje, por favor notifique al administrador del sistema.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Despacho en hilo independiente
    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True

def send_request_receipt_email(to_email: str, full_name: str, institution_name: str, request_code: str, pdf_bytes: bytes) -> bool:
    """Orquesta el contenido visual del correo de recibo y lanza el hilo asíncrono usando el estándar global."""
    import html
    safe_name = html.escape(full_name)
    safe_institution = html.escape(institution_name)
    
    subject = f"Comprobante de Solicitud {request_code} — SAGES UREE"
    text_content = (
        f"Estimado/a {safe_name},\n\n"
        f"Se ha registrado exitosamente una solicitud de formación para {safe_institution} bajo el código {request_code}.\n"
        f"Adjunto a este correo encontrará el Comprobante Digital Oficial en formato PDF.\n\n"
        f"Conserve este documento para el seguimiento de su trámite."
    )

    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>{subject}</title></head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr><td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td></tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">SOLICITUD RADICADA</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6; text-align: left;">
                        Estimado/a <strong>{safe_name}</strong>, le informamos que se ha registrado exitosamente una nueva solicitud de formación para <strong>{safe_institution}</strong>.
                    </p>
                    <div style="background-color: #f3f4f6; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
                        <p style="margin: 0; font-size: 16px;">Código de Solicitud: <span style="color: #1c3d73; font-weight: bold;">{request_code}</span></p>
                    </div>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.6; text-align: left;">
                        <strong>Adjunto a este correo electrónico</strong> encontrará su Comprobante Digital Oficial con Código QR en formato PDF. Por favor, descárguelo y consérvelo para efectos de seguimiento.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        * Este mensaje fue generado de forma automática. No responda a este correo.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Preparamos el archivo adjunto usando el estándar
    attachments = [{
        'filename': f"Comprobante_{request_code}.pdf",
        'maintype': 'application',
        'subtype': 'pdf',
        'content': pdf_bytes
    }]
    
    # Despachamos al mismo hilo genérico, pasándole los adjuntos
    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content, attachments))
    thread.start()
    return True


def send_delay_demand_email(
    to_email: str,
    recipient_name: str,
    request_code: str,
    institution_name: str,
    delay_info: str,
    phase_name: str
) -> bool:
    """
    Despacha un correo formal de intimación institucional por vencimiento de plazos normativos ANS (SLA).
    Se ejecuta de forma asíncrona mediante un hilo en segundo plano (threading.Thread).
    """
    subject = f"[URGENTE] Exigencia de Respuesta ANS - Trámite {request_code}"

    text_content = f"""
SAGES - CORPOELEC
SISTEMA AUTOMATIZADO DE GESTIÓN PARA LA EFICIENCIA SOCIAL

REQUERIMIENTO INSTITUCIONAL URGENTE
EXIGENCIA FORMAL DE JUSTIFICACIÓN DE RETRASO

Estimado(a) {recipient_name}:

La Gerencia General (Super Administrador), en ejercicio de sus funciones de fiscalización y auditoría del Acuerdo de Nivel de Servicio (ANS / SLA), ha detectado que el siguiente expediente formativo se encuentra en mora y ha vulnerado los tiempos normativos institucionales de CORPOELEC:

- Código de Trámite: {request_code}
- Institución Educativa: {institution_name}
- Fase Operativa: {phase_name}
- Tiempo de Mora Detectado: {delay_info}

Por tal motivo, se le intima a ingresar de manera INMEDIATA a la plataforma SAGES y consignar el descargo operativo y justificación técnica correspondiente para la regularización del caso.

Este mensaje fue generado automáticamente por la Gerencia de Auditoría y Fiscalización SLA.
© 2026 SAGES - CORPOELEC. Todos los derechos reservados.
"""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Exigencia de Respuesta ANS - SAGES</title>
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6; margin: 0; padding: 0;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.06); overflow: hidden; border: 1px solid #fee2e2;">
            <!-- Cabecera Institucional Roja -->
            <tr>
                <td align="center" style="background: linear-gradient(135deg, #991b1b 0%, #b91c1c 100%); padding: 30px 20px;">
                    <span style="display: inline-block; background-color: rgba(255,255,255,0.2); color: #ffffff; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; margin-bottom: 10px;">
                        AUDITORÍA NACIONAL SLA
                    </span>
                    <h1 style="color: #ffffff; font-size: 22px; margin: 0; font-weight: 700; letter-spacing: -0.5px;">
                        REQUERIMIENTO FORMAL DE RESPUESTA
                    </h1>
                    <p style="color: #fecaca; font-size: 13px; margin: 8px 0 0 0;">
                        Vencimiento de Acuerdo de Nivel de Servicio (ANS)
                    </p>
                </td>
            </tr>

            <!-- Contenido Principal -->
            <tr>
                <td style="padding: 35px 35px 20px 35px;">
                    <p style="font-size: 15px; color: #1f2937; margin: 0 0 16px 0;">
                        Estimado(a) <strong>{recipient_name}</strong>,
                    </p>
                    <p style="font-size: 14px; color: #4b5563; line-height: 1.6; margin: 0 0 24px 0;">
                        La Gerencia General, mediante el módulo de fiscalización de solicitudes de <strong>SAGES</strong>, ha emitido una <strong style="color: #991b1b;">exigencia formal e inmediata de justificación operativa</strong> debido al vencimiento de los plazos reglamentarios de atención para el siguiente trámite:
                    </p>

                    <!-- Tarjeta con Resumen del Trámite -->
                    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; margin-bottom: 25px;">
                        <tr>
                            <td style="padding: 16px 20px;">
                                <table width="100%" cellpadding="4" cellspacing="0" style="font-size: 13px;">
                                    <tr>
                                        <td style="color: #7f1d1d; font-weight: 600; width: 40%;">Expediente:</td>
                                        <td style="color: #111827; font-weight: 700;">{request_code}</td>
                                    </tr>
                                    <tr>
                                        <td style="color: #7f1d1d; font-weight: 600;">Plantel Educativo:</td>
                                        <td style="color: #111827;">{institution_name}</td>
                                    </tr>
                                    <tr>
                                        <td style="color: #7f1d1d; font-weight: 600;">Fase en Mora:</td>
                                        <td style="color: #111827;">{phase_name}</td>
                                    </tr>
                                    <tr>
                                        <td style="color: #7f1d1d; font-weight: 600;">Demora Acumulada:</td>
                                        <td style="color: #b91c1c; font-weight: 700;">{delay_info}</td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>

                    <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; margin-bottom: 25px;">
                        <p style="font-size: 13px; color: #92400e; margin: 0; line-height: 1.5;">
                            <strong>Instrucción Inmediata:</strong> Debe ingresar a la consola de gestión de solicitudes en SAGES y consignar el motivo oficial del retraso o programar la acción operativa pendiente.
                        </p>
                    </div>

                    <p style="font-size: 12px; color: #6b7280; line-height: 1.5; margin: 0;">
                        * Este requerimiento ha quedado registrado con severidad <strong>CRÍTICA</strong> en la bitácora transversal de trazabilidad del expediente y en la bitácora de auditoría forense institucional.
                    </p>
                </td>
            </tr>

            <!-- Pie de Página -->
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES - CORPOELEC. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True


def send_request_claimed_email(to_email: str, full_name: str, institution_name: str, request_code: str, admin_name: str) -> bool:
    import html
    safe_name = html.escape(full_name)
    safe_institution = html.escape(institution_name)
    safe_code = html.escape(request_code)
    safe_admin = html.escape(admin_name)
    
    subject = f"Su Solicitud {safe_code} ha sido Asignada"
    text_content = f"""Estimado/a {safe_name},

Su solicitud ({safe_code}) para {safe_institution} ha sido aceptada y asignada al Administrador Estadal {safe_admin}.

El administrador se pondrá en contacto directo con usted para coordinar requerimientos logísticos, espacio, cantidad de participantes y confirmar la fecha definitiva de la jornada.

Gracias por usar el sistema SAGES.
"""
    logo_html = get_logo_html()
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">NOTIFICACIÓN DE ASIGNACIÓN</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5; text-align: left;">Estimado/a <strong>{safe_name}</strong>,</p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5; text-align: left;">
                        Nos complace informarle que su solicitud <strong>{safe_code}</strong> ha sido aceptada y está ahora bajo la responsabilidad del Administrador Estadal <strong>{safe_admin}</strong>.
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5; text-align: left;">
                        El administrador asignado se contactará con usted próximamente para iniciar las coordinaciones pertinentes.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        Por favor, no responda a este correo automatizado.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True


def send_request_planned_email(to_email: str, full_name: str, institution_name: str, request_code: str, planned_date: str, notes: str = None) -> bool:
    """Envía notificación por correo cuando se agenda la fecha de una jornada formativa (US-41)."""
    import html
    safe_name = html.escape(full_name)
    safe_institution = html.escape(institution_name)
    safe_code = html.escape(request_code)
    safe_date = html.escape(planned_date)
    safe_notes = html.escape(notes.strip()) if notes else ""
    
    subject = f"Fecha de Jornada Formativa Agendada - Solicitud {safe_code}"
    
    notes_text = f"\n\nObservaciones del administrador:\n{safe_notes}" if safe_notes else ""
    text_content = f"""Estimado/a {safe_name},

Le informamos que su solicitud de formación ({safe_code}) para la institución {safe_institution} ha sido agendada formalmente.

Fecha de la Jornada Formativa: {safe_date}{notes_text}

Por favor, tenga en cuenta esta fecha para las coordinaciones y logística correspondientes en su institución.

Gracias por usar el sistema SAGES.
"""
    logo_html = get_logo_html()
    notes_html = f"""
    <div style="background-color: #f1f5f9; border-left: 4px solid #0ea5e9; padding: 12px 16px; margin: 20px 0; border-radius: 4px; text-align: left;">
        <strong style="color: #0f172a; font-size: 13px;">Observaciones del Coordinador:</strong>
        <p style="margin: 6px 0 0 0; color: #475569; font-size: 14px;">{safe_notes}</p>
    </div>
    """ if safe_notes else ""

    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #0ea5e9 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">JORNADA FORMATIVA AGENDADA</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5; text-align: left;">Estimado/a <strong>{safe_name}</strong>,</p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 16px 0; line-height: 1.5; text-align: left;">
                        Nos complace informarle que su solicitud <strong>{safe_code}</strong> para la institución <strong>{safe_institution}</strong> ha sido agendada con éxito.
                    </p>
                    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
                        <span style="display: block; font-size: 13px; color: #166534; font-weight: 600; text-transform: uppercase;">Fecha Oficial Agendada</span>
                        <strong style="display: block; font-size: 22px; color: #15803d; margin-top: 4px;">{safe_date}</strong>
                    </div>
                    {notes_html}
                    <p style="font-size: 14px; color: #64748b; margin: 20px 0 25px 0; line-height: 1.5; text-align: left;">
                        Agradecemos tomar las previsiones pertinentes de espacio y participantes para el óptimo desarrollo de la actividad formativa.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 30px 40px 40px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        Por favor, no responda a este correo automatizado.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True


def send_request_cancelled_email(
    to_email: str,
    recipient_name: str,
    institution_name: str,
    request_code: str,
    training_name: str,
    reason_name: str,
    justification: str,
    is_admin_cancellation: bool = True
) -> bool:
    """Envía notificación institucional por correo cuando se cancela una solicitud de formación (US-44)."""
    import html
    safe_name = html.escape(recipient_name or "Usuario")
    safe_institution = html.escape(institution_name or "Plantel Educativo")
    safe_code = html.escape(request_code or "")
    safe_training = html.escape(training_name or "Formación Solicitada")
    safe_reason = html.escape(reason_name or "Cancelación de trámite")
    safe_justification = html.escape(justification.strip() if justification else "Sin justificación registrada.")

    logo_html = get_logo_html()

    if is_admin_cancellation:
        subject = f"Aviso de Cancelación Institucional: Solicitud {safe_code} — SAGES UREE"
        banner_title = "SOLICITUD DE FORMACIÓN CANCELADA"
        intro_text = (
            f"Le informamos que la solicitud de formación <strong>'{safe_training}'</strong> vinculada al plantel "
            f"<strong>{safe_institution}</strong> ha sido <strong>cancelada administrativamente</strong> por la Coordinación de CORPOELEC."
        )
        text_content = (
            f"Estimado/a {safe_name},\n\n"
            f"Le informamos que la solicitud de formación '{safe_training}' ({safe_code}) para la institución "
            f"{safe_institution} ha sido cancelada administrativamente por la Coordinación de CORPOELEC.\n\n"
            f"Motivo Oficial: {safe_reason}\n"
            f"Justificación Consignada:\n{safe_justification}\n\n"
            f"El expediente ha sido archivado formalmente en el sistema.\n\n"
            f"* Este mensaje fue generado de forma automática por el sistema SAGES. No responda a este correo.\n\n"
            f"© 2026 SAGES — CORPOELEC. Todos los derechos reservados."
        )
    else:
        subject = f"Aviso de Desistimiento: Solicitud {safe_code} — {safe_institution}"
        banner_title = "DESISTIMIENTO DE SOLICITUD REGISTRADO"
        intro_text = (
            f"Le notificamos que el representante institucional del plantel <strong>{safe_institution}</strong> "
            f"ha <strong>desistido formalmente</strong> de la solicitud de formación <strong>'{safe_training}'</strong>."
        )
        text_content = (
            f"Estimado Administrador ({safe_name}),\n\n"
            f"Le notificamos que el representante institucional del plantel educativo {safe_institution} "
            f"ha desistido formalmente de la solicitud de formación '{safe_training}' ({safe_code}).\n\n"
            f"Motivo Oficial: {safe_reason}\n"
            f"Justificación Consignada:\n{safe_justification}\n\n"
            f"El expediente ha sido trasladado al archivo histórico del sistema.\n\n"
            f"* Este mensaje fue generado de forma automática por el sistema SAGES. No responda a este correo.\n\n"
            f"© 2026 SAGES — CORPOELEC. Todos los derechos reservados."
        )

    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">{banner_title}</h2>
                    
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5; text-align: left;">
                        Estimado/a <strong>{safe_name}</strong>,
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 20px 0; line-height: 1.6; text-align: left;">
                        {intro_text}
                    </p>

                    <!-- Tarjeta con Resumen del Trámite (Estilo Homogéneo) -->
                    <div style="background-color: #f3f4f6; border-radius: 8px; padding: 16px 20px; margin: 0 0 20px 0; text-align: left;">
                        <table width="100%" cellpadding="4" cellspacing="0" style="font-size: 14px;">
                            <tr>
                                <td style="color: #4b5563; font-weight: 600; width: 30%;">Solicitud:</td>
                                <td style="color: #1c3d73; font-weight: 700;">{safe_code}</td>
                            </tr>
                            <tr>
                                <td style="color: #4b5563; font-weight: 600;">Plantel:</td>
                                <td style="color: #1f2937;">{safe_institution}</td>
                            </tr>
                            <tr>
                                <td style="color: #4b5563; font-weight: 600;">Formación:</td>
                                <td style="color: #1f2937;">{safe_training}</td>
                            </tr>
                            <tr>
                                <td style="color: #4b5563; font-weight: 600;">Motivo:</td>
                                <td style="color: #1f2937; font-weight: 600;">{safe_reason}</td>
                            </tr>
                        </table>
                    </div>

                    <!-- Recuadro Destacado de Justificación Consignada -->
                    <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; border-radius: 4px; padding: 12px 16px; margin: 0 0 20px 0; text-align: left;">
                        <strong style="color: #991b1b; font-size: 13px;">Justificación Consignada:</strong>
                        <p style="margin: 6px 0 0 0; color: #475569; font-size: 14px; line-height: 1.5; white-space: pre-line;">{safe_justification}</p>
                    </div>

                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 25px 0 20px 0;">
                    
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0 0 30px 0; text-align: left;">
                        * Este mensaje fue generado de forma automática por el sistema SAGES. No responda a este correo.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES &mdash; CORPOELEC. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True


def send_request_rescheduled_email(
    to_email: str,
    full_name: str,
    institution_name: str,
    request_code: str,
    new_planned_date: str,
    reason_name: str,
    justification: str = None
) -> bool:
    """
    Envía notificación formal por correo electrónico cuando la fecha de una jornada formativa
    es reprogramada por causa mayor o imprevistos de fuerza mayor (US-42 / SR-F-022).
    """
    import html
    safe_name = html.escape(full_name)
    safe_institution = html.escape(institution_name)
    safe_code = html.escape(request_code)
    safe_new_date = html.escape(new_planned_date)
    safe_reason = html.escape(reason_name)
    safe_justification = html.escape(justification.strip()) if justification else ""

    subject = f"Reprogramación de Fecha: Jornada Formativa - Solicitud {safe_code}"

    text_content = f"""Estimado/a {safe_name},

Le informamos que la jornada formativa de su solicitud {safe_code} para la institución {safe_institution} ha sido REPROGRAMADA formalmente ante imprevistos sobrevenidos o de fuerza mayor.

Nueva Fecha Pautada: {safe_new_date}
Motivo Oficial: {safe_reason}
Justificación Técnica: {safe_justification}

Agradecemos actualizar su agenda institucional y coordinar la logística correspondiente para recibir al equipo facilitador en esta nueva fecha.

Sistema de Gestión de Solicitudes SAGES - CORPOELEC.
"""

    logo_html = get_logo_html()

    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 0 40px;">
                    <h2 style="font-size: 20px; font-weight: 700; color: #b45309; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px;">AVISO DE REPROGRAMACIÓN DE JORNADA</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5; text-align: left;">Estimado/a <strong>{safe_name}</strong>,</p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 16px 0; line-height: 1.5; text-align: left;">
                        Le notificamos que la jornada formativa correspondiente a la solicitud <strong>{safe_code}</strong> para el plantel <strong>{safe_institution}</strong> ha sido reprogramada formalmente en nuestro cronograma institucional.
                    </p>

                    <!-- Banner de Nueva Fecha -->
                    <div style="background-color: #fefce8; border: 1px solid #fef08a; border-radius: 8px; padding: 18px; margin: 20px 0; text-align: center;">
                        <span style="display: block; font-size: 13px; color: #854d0e; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Nueva Fecha Fijada para la Visita</span>
                        <strong style="display: block; font-size: 24px; color: #a16207; margin-top: 6px;">{safe_new_date}</strong>
                    </div>

                    <!-- Ficha del Motivo Oficial -->
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px 18px; margin: 0 0 16px 0; text-align: left;">
                        <span style="display: block; font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase;">Causa de Contingencia:</span>
                        <strong style="display: block; font-size: 14px; color: #1e293b; margin-top: 2px;">{safe_reason}</strong>
                    </div>

                    <!-- Recuadro de Justificación Técnica -->
                    {f'''
                    <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; border-radius: 4px; padding: 12px 16px; margin: 0 0 20px 0; text-align: left;">
                        <strong style="color: #92400e; font-size: 13px;">Explicación Técnica Circunstanciada:</strong>
                        <p style="margin: 6px 0 0 0; color: #475569; font-size: 14px; line-height: 1.5; white-space: pre-line;">{safe_justification}</p>
                    </div>
                    ''' if safe_justification else ''}

                    <p style="font-size: 14px; color: #64748b; margin: 20px 0 25px 0; line-height: 1.5; text-align: left;">
                        Agradecemos realizar los ajustes correspondientes en la disponibilidad de sus instalaciones y la convocatoria de los participantes.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="padding: 20px 40px 30px 40px;">
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 20px;">
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0; text-align: justify;">
                        Por favor, no responda a este correo automatizado. Para consultas operativas, contacte a su coordinación estadal de CORPOELEC.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES &mdash; CORPOELEC. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True


def send_training_completed_survey_email(
    to_email: str,
    full_name: str,
    institution_name: str,
    request_code: str,
    survey_url: str,
    training_name: str = None
) -> bool:
    """
    Envía notificación institucional por correo al solicitante tras culminar la formación (US-48 / SR-F-019).
    Agradece la participación, suministra el enlace directo a la Encuesta de Satisfacción (US-51)
    e informa sobre la disponibilidad del Informe Técnico Final en el panel institucional.
    """
    import html
    safe_name = html.escape(full_name or "Representante Institucional")
    safe_institution = html.escape(institution_name or "Plantel Educativo")
    safe_code = html.escape(request_code or "")
    safe_survey_url = html.escape(survey_url or "#")
    safe_training = html.escape(training_name or "Formación Comunitaria UREE")

    subject = f"Jornada de Formación Culminada — Encuesta de Satisfacción: Solicitud {safe_code}"

    text_content = (
        f"Estimado/a {safe_name},\n\n"
        f"Le informamos que la jornada formativa '{safe_training}' para el plantel educativo "
        f"{safe_institution} ha sido ejecutada y formalmente completada por nuestro equipo facilitador (Solicitud: {safe_code}).\n\n"
        f"En la Gerencia de Uso Racional y Eficiente de la Energía (UREE) de CORPOELEC valoramos enormemente su opinión y "
        f"compromiso con la cultura energética. Para nosotros es fundamental conocer su experiencia y nivel de satisfacción.\n\n"
        f"Por favor, tómese un minuto para evaluar la jornada ingresando en el siguiente enlace:\n"
        f"{survey_url}\n\n"
        f"Asimismo, le notificamos que el Informe Técnico Final certificado con Código QR ya se encuentra "
        f"disponible para consulta y descarga en su panel de autogestión.\n\n"
        f"* Este mensaje fue generado de forma automática por el sistema SAGES. No responda a este correo.\n\n"
        f"© 2026 SAGES — CORPOELEC. Todos los derechos reservados."
    )

    logo_html = get_logo_html()

    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f9fafb; color: #1f2937;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; overflow: hidden;">
            <tr>
                <td style="height: 6px; background: linear-gradient(90deg, #1c3d73 0%, #019577 50%, #1fcab0 100%);"></td>
            </tr>
            <tr>
                <td align="center" style="padding: 40px 20px 20px 20px;">
                    {logo_html}
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes de Formación</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 0 40px;">
                    <h2 style="font-size: 22px; font-weight: 700; color: #019577; margin: 10px 0 20px 0; text-transform: uppercase; letter-spacing: 0.5px; text-align: center;">¡JORNADA FORMATIVA CULMINADA!</h2>
                    
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 10px 0; line-height: 1.5; text-align: left;">
                        Estimado/a <strong>{safe_name}</strong>,
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 20px 0; line-height: 1.6; text-align: left;">
                        Le informamos que la capacitación <strong>'{safe_training}'</strong> solicitada para la institución <strong>{safe_institution}</strong> ha sido ejecutada y formalizada exitosamente por la Coordinación de CORPOELEC.
                    </p>

                    <!-- Tarjeta Resumen del Trámite -->
                    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px 20px; margin: 0 0 25px 0; text-align: left;">
                        <table width="100%" cellpadding="4" cellspacing="0" style="font-size: 14px;">
                            <tr>
                                <td style="color: #166534; font-weight: 600; width: 32%;">Código Trámite:</td>
                                <td style="color: #1c3d73; font-weight: 700;">{safe_code}</td>
                            </tr>
                            <tr>
                                <td style="color: #166534; font-weight: 600;">Plantel:</td>
                                <td style="color: #1f2937;">{safe_institution}</td>
                            </tr>
                            <tr>
                                <td style="color: #166534; font-weight: 600;">Formación:</td>
                                <td style="color: #1f2937;">{safe_training}</td>
                            </tr>
                            <tr>
                                <td style="color: #166534; font-weight: 600;">Estatus Final:</td>
                                <td style="color: #019577; font-weight: 700;">Completado (Archivado)</td>
                            </tr>
                        </table>
                    </div>

                    <!-- Llamado a la Acción: Encuesta de Satisfacción -->
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 25px 20px; margin: 0 0 25px 0; text-align: center;">
                        <h3 style="margin: 0 0 10px 0; font-size: 17px; color: #1e293b; font-weight: 700;">
                            Su opinión es clave para la mejora continua
                        </h3>
                        <p style="font-size: 14px; color: #64748b; line-height: 1.5; margin: 0 0 20px 0;">
                            Para la Gerencia de Uso Racional y Eficiente de la Energía (UREE) es de vital importancia conocer la calidad del taller y el desempeño del facilitador.
                        </p>
                        <a href="{safe_survey_url}" 
                           style="display: inline-block; background: linear-gradient(90deg, #019577 0%, #1fcab0 100%); color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 15px; letter-spacing: 0.5px; box-shadow: 0 4px 6px rgba(1, 149, 119, 0.25);">
                            Evaluar Jornada de Formación
                        </a>
                    </div>

                    <!-- Aviso de Informe Técnico con QR -->
                    <div style="background-color: #f1f5f9; border-left: 4px solid #1c3d73; border-radius: 4px; padding: 12px 16px; margin: 0 0 25px 0; text-align: left;">
                        <strong style="color: #1c3d73; font-size: 13px;">Informe Técnico Final Certificado:</strong>
                        <p style="margin: 4px 0 0 0; color: #475569; font-size: 13px; line-height: 1.5;">
                            El expediente digital y el Informe Técnico Oficial provisto con Código QR de verificación criptográfica ya se encuentran habilitados para consulta y descarga en su panel de solicitudes.
                        </p>
                    </div>

                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 25px 0 20px 0;">
                    
                    <p style="font-size: 12px; color: #9ca3af; line-height: 1.6; margin: 0 0 30px 0; text-align: left;">
                        * Este mensaje fue generado de forma automática por el sistema SAGES. No responda a este correo.
                    </p>
                </td>
            </tr>
            <tr>
                <td align="center" style="background-color: #f9fafb; padding: 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                    &copy; 2026 SAGES &mdash; CORPOELEC. Todos los derechos reservados.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    thread = threading.Thread(target=send_email, args=(to_email, subject, html_content, text_content))
    thread.start()
    return True




