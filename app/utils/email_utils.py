import os
import smtplib
from email.message import EmailMessage

def send_email(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Utilidad global para el envío de correos con formato HTML y texto."""
    smtp_user = os.getenv('SMTP_USER') or os.getenv('EMAIL_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    if not smtp_pass:
        print('SMTP_PASS no configurada; no se envió el correo.')
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
                print(f"Error al adjuntar imagen inline: {e}")

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f'Error enviando correo: {e}')
        return False

def get_logo_html() -> str:
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo_corpoelec.png')
    if os.path.exists(logo_path):
        return '<img src="cid:logo_corpoelec" alt="CORPOELEC" style="max-width: 220px; height: auto; display: block; border: 0;">'
    return '<span style="font-size: 24px; font-weight: 800; color: #1c3d73; letter-spacing: 1px;">(⚡) CORPOELEC</span>'

def send_recovery_email(to_email: str, code: str) -> bool:
    subject = 'Código de recuperación'
    text_content = f"Hola,\n\nSu código de recuperación es: {code}\n\nEste código expira en 5 minutos.\n\nSi no solicitó esto, ignore este mensaje."
    
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
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes</h1>
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
                        <span style="font-size: 36px; font-weight: 800; color: #1c3d73; letter-spacing: 6px; font-family: monospace;">{code}</span>
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
    subject = "Confirmación de Registro - Sistema UREE"
    text_content = f"""Estimado/a {full_name},

Hemos recibido exitosamente su solicitud de registro como Representante Institucional en el Sistema para la Gestión de Solicitudes de Formación Comunitaria de Uso Racional y Eficiente de la Energía (UREE).

Actualmente, su perfil y la documentación se encuentran en fase de Revisión. Este proceso de validación institucional es estrictamente necesario para aprobar su vinculación con {institution_name}.

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
                    <h1 style="font-size: 15px; color: #4b5563; margin: 0 0 25px 0; line-height: 1.5;">Sistema de Gestión de Solicitudes</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 0 40px;">
                    <h2 style="font-size: 20px; font-weight: 700; color: #1f2937; margin: 10px 0 20px 0;">Estimado/a {full_name},</h2>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6;">
                        Hemos recibido exitosamente su solicitud de registro como Representante Institucional en el Sistema para la Gestión de Solicitudes de Formación Comunitaria de Uso Racional y Eficiente de la Energía (UREE).
                    </p>
                    <p style="font-size: 15px; color: #4b5563; margin: 0 0 15px 0; line-height: 1.6;">
                        Actualmente, su perfil y la documentación se encuentran en fase de <strong>Revisión</strong>. Este proceso de validación institucional es estrictamente necesario para aprobar su vinculación con <strong>{institution_name}</strong>.
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
