import os
import smtplib
from email.message import EmailMessage

def send_recovery_email(to_email: str, code: str) -> bool:
    
    smtp_user = os.getenv('SMTP_USER') or os.getenv('EMAIL_USER') or 'proyectoiiiupt@gmail.com'
    smtp_pass = os.getenv('SMTP_PASS')
    if not smtp_pass:
        print('SMTP_PASS no configurada; no se envió el correo.')
        return False

    msg = EmailMessage()
    msg['Subject'] = 'Código de recuperación'
    msg['From'] = smtp_user
    msg['To'] = to_email

    # Versión en texto plano (Respaldo)
    text_content = f"Hola,\n\nSu código de recuperación es: {code}\n\nEste código expira en 5 minutos.\n\nSi no solicitó esto, ignore este mensaje."
    msg.set_content(text_content)

    # El archivo está en app/utils/, por lo que app/ está un directorio arriba
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo_corpoelec.png')
    has_logo = os.path.exists(logo_path)

    logo_html = ""
    if has_logo:
        logo_html = '<img src="cid:logo_corpoelec" alt="CORPOELEC" style="max-width: 220px; height: auto; display: block; border: 0;">'
    else:
        logo_html = '<span style="font-size: 24px; font-weight: 800; color: #1c3d73; letter-spacing: 1px;">(⚡) CORPOELEC</span>'

    # Versión en HTML estilizado
    html_content = f"""<!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Código de Verificación</title>
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
    msg.add_alternative(html_content, subtype='html')

    if has_logo:
        try:
            with open(logo_path, 'rb') as f:
                # payload[0] es text/plain, payload[1] es text/html
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
