"""
Email Service - Infrastructure Layer

Servicio para enviar emails usando Mailgun.
"""

import html
import logging
from datetime import datetime

import requests
from fastapi import status

from src.config.settings import settings
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.user.application.ports.email_service_interface import IEmailService

logger = logging.getLogger(__name__)


class EmailService(IEmailService, IInvitationEmailService):
    """
    Implementación de IEmailService usando Mailgun.

    Esta es una implementación concreta del puerto IEmailService.
    Puede ser reemplazada por otras implementaciones (SendGrid, AWS SES, etc.)
    sin afectar a la capa de aplicación.
    """

    def __init__(self):
        self.api_key = settings.MAILGUN_API_KEY
        self.domain = settings.MAILGUN_DOMAIN
        self.from_email = settings.MAILGUN_FROM_EMAIL
        self.api_url = settings.MAILGUN_API_URL

    def send_verification_email(
        self, to_email: str, user_name: str, verification_token: str
    ) -> bool:
        """
        Envía un email de verificación al usuario.

        Args:
            to_email: Email del destinatario
            user_name: Nombre del usuario
            verification_token: Token de verificación

        Returns:
            bool: True si el email se envió correctamente, False en caso contrario
        """
        safe_user_name = self._sanitize_name(user_name)

        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

        subject = (
            f"Bienvenido a Ryder Cup Friends, {safe_user_name}! | Welcome to Ryder Cup Friends!"
        )

        text_body = f"""
Hola {safe_user_name},

¡Bienvenido a Ryder Cup Friends!

Para completar tu registro, por favor confirma tu dirección de correo electrónico haciendo clic en el siguiente enlace:

{verification_link}

Si no te has registrado en Ryder Cup Friends, puedes ignorar este mensaje.

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_user_name},

Welcome to Ryder Cup Friends!

To complete your registration, please confirm your email address by clicking on the following link:

{verification_link}

If you did not sign up for Ryder Cup Friends, you can safely ignore this message.

Best regards,
The Ryder Cup Friends Team
        """

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .section {{
            margin-bottom: 30px;
            padding-bottom: 30px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .section:last-of-type {{
            border-bottom: none;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Español -->
        <div class="section">
            <h2>¡Bienvenido a Ryder Cup Friends, {safe_user_name}!</h2>
            <p>Gracias por registrarte en Ryder Cup Friends.</p>
            <p>Para completar tu registro y activar tu cuenta, por favor confirma tu dirección de correo electrónico:</p>
            <a href="{verification_link}" class="button">Verificar mi email</a>
            <p>O copia y pega este enlace en tu navegador:</p>
            <p style="word-break: break-all; color: #0066cc;">{verification_link}</p>
        </div>

        <!-- English -->
        <div class="section">
            <h2>Welcome to Ryder Cup Friends, {safe_user_name}!</h2>
            <p>Thank you for signing up for Ryder Cup Friends.</p>
            <p>To complete your registration and activate your account, please confirm your email address:</p>
            <a href="{verification_link}" class="button">Verify my email</a>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #0066cc;">{verification_link}</p>
        </div>

        <div class="footer">
            <p>Si no te has registrado en Ryder Cup Friends, puedes ignorar este mensaje.<br>
            If you did not sign up for Ryder Cup Friends, you can safely ignore this message.</p>
            <p>&copy; 2025 Ryder Cup Friends. Todos los derechos reservados. | All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """

        return self._send_email(
            to=f'"{safe_user_name}" <{to_email}>',  # RFC 5322 format with quotes
            subject=subject,
            text=text_body,
            html=html_body,
        )

    def _send_email(self, to: str, subject: str, text: str, html: str | None = None) -> bool:
        """
        Envía un email usando la API de Mailgun.

        Args:
            to: Destinatario del email
            subject: Asunto del email
            text: Cuerpo del email en texto plano
            html: Cuerpo del email en HTML (opcional)

        Returns:
            bool: True si el email se envió correctamente, False en caso contrario
        """
        if not self.api_key:
            logger.error("MAILGUN_API_KEY no está configurada")
            return False

        try:
            url = f"{self.api_url}/{self.domain}/messages"

            data = {"from": self.from_email, "to": to, "subject": subject, "text": text}

            if html:
                data["html"] = html

            response = requests.post(url, auth=("api", self.api_key), data=data, timeout=10)

            if response.status_code == status.HTTP_200_OK:
                logger.info("Email de verificación enviado correctamente")
                return True
            logger.error("Error al enviar email: %s - %s", response.status_code, response.text)
            return False

        except requests.exceptions.RequestException as e:
            logger.error("Error de red al enviar email: %s", str(e))
            return False
        except Exception as e:
            logger.error("Error inesperado al enviar email: %s", str(e))
            return False

    async def send_password_reset_email(
        self, to_email: str, reset_link: str, user_name: str
    ) -> bool:
        """
        Envía un email con enlace para resetear contraseña.

        Template bilingüe (ES/EN) con diseño consistente con verify_email.
        """
        safe_user_name = self._sanitize_name(user_name)

        subject = "Resetea tu contraseña - Ryder Cup Friends | Reset your password"

        text_body = f"""
Hola {safe_user_name},

Hemos recibido una solicitud para resetear la contraseña de tu cuenta en Ryder Cup Friends.

Para establecer una nueva contraseña, haz clic en el siguiente enlace (válido por 24 horas):

{reset_link}

Si no solicitaste este cambio, puedes ignorar este mensaje. Tu contraseña actual seguirá siendo válida.

Por seguridad, todas tus sesiones activas serán cerradas al cambiar la contraseña.

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_user_name},

We received a request to reset the password for your Ryder Cup Friends account.

To set a new password, click on the following link (valid for 24 hours):

{reset_link}

If you did not request this change, you can safely ignore this message. Your current password will remain valid.

For security, all your active sessions will be closed when you change your password.

Best regards,
The Ryder Cup Friends Team
        """

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .container {{
            background-color: #f9f9f9;
            border-radius: 10px;
            padding: 30px;
        }}
        .header {{
            background-color: #0066cc;
            color: white;
            padding: 20px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            padding: 15px 30px;
            background-color: #0066cc;
            color: white !important;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        .divider {{
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Reseteo de Contraseña</h1>
            <h2>Password Reset</h2>
        </div>
        <div class="content">
            <!-- Spanish -->
            <p>Hola <strong>{safe_user_name}</strong>,</p>
            <p>Hemos recibido una solicitud para resetear la contraseña de tu cuenta en Ryder Cup Friends.</p>
            <p>Para establecer una nueva contraseña, haz clic en el siguiente botón:</p>
            <center>
                <a href="{reset_link}" class="button">Resetear mi contraseña</a>
            </center>
            <p style="font-size: 12px; color: #666;">Si el botón no funciona, copia y pega este enlace en tu navegador:</p>
            <p style="font-size: 12px; word-break: break-all;">{reset_link}</p>

            <div class="warning">
                <p style="margin: 0;"><strong>⚠️ Importante:</strong></p>
                <ul style="margin: 10px 0 0 0;">
                    <li>Este enlace es válido por <strong>24 horas</strong></li>
                    <li>Todas tus sesiones activas serán cerradas al cambiar la contraseña</li>
                    <li>Si no solicitaste este cambio, ignora este mensaje</li>
                </ul>
            </div>

            <div class="divider"></div>

            <!-- English -->
            <p>Hello <strong>{safe_user_name}</strong>,</p>
            <p>We received a request to reset the password for your Ryder Cup Friends account.</p>
            <p>To set a new password, click on the following button:</p>
            <center>
                <a href="{reset_link}" class="button">Reset my password</a>
            </center>
            <p style="font-size: 12px; color: #666;">If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="font-size: 12px; word-break: break-all;">{reset_link}</p>

            <div class="warning">
                <p style="margin: 0;"><strong>⚠️ Important:</strong></p>
                <ul style="margin: 10px 0 0 0;">
                    <li>This link is valid for <strong>24 hours</strong></li>
                    <li>All your active sessions will be closed when you change your password</li>
                    <li>If you did not request this change, ignore this message</li>
                </ul>
            </div>

            <div class="footer">
                <p>Saludos | Best regards,<br>
                <strong>El equipo de Ryder Cup Friends | The Ryder Cup Friends Team</strong></p>
            </div>
        </div>
    </div>
</body>
</html>
        """

        return self._send_email(to_email, subject, text_body, html_body)

    async def send_password_changed_notification(self, to_email: str, user_name: str) -> bool:
        """
        Envía un email notificando que la contraseña fue cambiada exitosamente.

        Template bilingüe (ES/EN) con información de seguridad.
        """
        safe_user_name = self._sanitize_name(user_name)

        subject = (
            "Tu contraseña ha sido cambiada - Ryder Cup Friends | Your password has been changed"
        )

        text_body = f"""
Hola {safe_user_name},

Te confirmamos que la contraseña de tu cuenta en Ryder Cup Friends ha sido cambiada exitosamente.

Por seguridad, hemos cerrado todas tus sesiones activas. Necesitarás iniciar sesión nuevamente con tu nueva contraseña.

Si NO realizaste este cambio, tu cuenta podría estar comprometida. Por favor, contacta a nuestro equipo de soporte inmediatamente.

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_user_name},

We confirm that the password for your Ryder Cup Friends account has been successfully changed.

For security, we have closed all your active sessions. You will need to log in again with your new password.

If you did NOT make this change, your account may be compromised. Please contact our support team immediately.

Best regards,
The Ryder Cup Friends Team
        """

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .container {{
            background-color: #f9f9f9;
            border-radius: 10px;
            padding: 30px;
        }}
        .header {{
            background-color: #28a745;
            color: white;
            padding: 20px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .success-box {{
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin: 20px 0;
        }}
        .alert-box {{
            background-color: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 15px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }}
        .divider {{
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Contraseña Cambiada</h1>
            <h2>Password Changed</h2>
        </div>
        <div class="content">
            <!-- Spanish -->
            <p>Hola <strong>{safe_user_name}</strong>,</p>

            <div class="success-box">
                <p style="margin: 0;"><strong>✅ Cambio exitoso</strong></p>
                <p style="margin: 10px 0 0 0;">Tu contraseña ha sido cambiada exitosamente.</p>
            </div>

            <p><strong>Acciones de seguridad tomadas:</strong></p>
            <ul>
                <li>Todas tus sesiones activas han sido cerradas</li>
                <li>Necesitarás iniciar sesión nuevamente con tu nueva contraseña</li>
                <li>Este cambio ha sido registrado en nuestro sistema</li>
            </ul>

            <div class="alert-box">
                <p style="margin: 0;"><strong>⚠️ ¿No fuiste tú?</strong></p>
                <p style="margin: 10px 0 0 0;">Si NO realizaste este cambio, tu cuenta podría estar comprometida. Contacta a nuestro equipo de soporte inmediatamente.</p>
            </div>

            <div class="divider"></div>

            <!-- English -->
            <p>Hello <strong>{safe_user_name}</strong>,</p>

            <div class="success-box">
                <p style="margin: 0;"><strong>✅ Successful change</strong></p>
                <p style="margin: 10px 0 0 0;">Your password has been successfully changed.</p>
            </div>

            <p><strong>Security actions taken:</strong></p>
            <ul>
                <li>All your active sessions have been closed</li>
                <li>You will need to log in again with your new password</li>
                <li>This change has been logged in our system</li>
            </ul>

            <div class="alert-box">
                <p style="margin: 0;"><strong>⚠️ Wasn't you?</strong></p>
                <p style="margin: 10px 0 0 0;">If you did NOT make this change, your account may be compromised. Contact our support team immediately.</p>
            </div>

            <div class="footer">
                <p>Saludos | Best regards,<br>
                <strong>El equipo de Ryder Cup Friends | The Ryder Cup Friends Team</strong></p>
            </div>
        </div>
    </div>
</body>
</html>
        """

        return self._send_email(to_email, subject, text_body, html_body)

    def _sanitize_name(self, name: str) -> str:
        """Sanitiza un nombre para prevenir inyeccion de headers (RFC 5322)."""
        return (
            name.replace("\n", "")
            .replace("\r", "")
            .replace('"', "")
            .replace("<", "")
            .replace(">", "")
            .strip()
        )

    async def send_invitation_email(
        self,
        to_email: str,
        invitee_name: str | None,
        inviter_name: str,
        competition_name: str,
        personal_message: str | None,
        expires_at: datetime,
    ) -> bool:
        """
        Envia un email de invitacion a una competicion.

        Template bilingue (ES/EN) con diseno consistente.
        """
        safe_inviter = self._sanitize_name(inviter_name)
        safe_competition = self._sanitize_name(competition_name)
        safe_invitee = self._sanitize_name(invitee_name) if invitee_name else None

        greeting_es = f"Hola {safe_invitee}" if safe_invitee else "Hola"
        greeting_en = f"Hello {safe_invitee}" if safe_invitee else "Hello"

        expires_str = expires_at.strftime("%d/%m/%Y")

        # Mensaje personal (si existe)
        personal_es = ""
        personal_en = ""
        personal_html_es = ""
        personal_html_en = ""
        if personal_message:
            escaped_message = html.escape(personal_message)
            personal_es = f'\nMensaje de {safe_inviter}: "{personal_message}"\n'
            personal_en = f'\nMessage from {safe_inviter}: "{personal_message}"\n'
            personal_html_es = f"""
            <div style="background-color: #f0f4f8; border-left: 4px solid #0066cc; padding: 15px; margin: 15px 0;">
                <p style="margin: 0; font-style: italic;">"{escaped_message}"</p>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #666;">- {safe_inviter}</p>
            </div>"""
            personal_html_en = personal_html_es

        invitations_link = f"{settings.FRONTEND_URL}/invitations"
        register_link = f"{settings.FRONTEND_URL}/register"

        subject = (
            f"Te han invitado a {safe_competition} "
            f"| You've been invited to {safe_competition}"
        )

        # Texto para no registrados
        unregistered_es = ""
        unregistered_en = ""
        unregistered_html_es = ""
        unregistered_html_en = ""
        if not safe_invitee:
            unregistered_es = (
                f"\nAun no tienes cuenta? Registrate aqui: {register_link}\n"
            )
            unregistered_en = (
                f"\nDon't have an account yet? Register here: {register_link}\n"
            )
            unregistered_html_es = f"""
            <p>Si aun no tienes cuenta, registrate primero:</p>
            <center>
                <a href="{register_link}" class="button" style="background-color: #28a745;">Registrarme</a>
            </center>"""
            unregistered_html_en = f"""
            <p>Don't have an account yet? Register first:</p>
            <center>
                <a href="{register_link}" class="button" style="background-color: #28a745;">Register</a>
            </center>"""

        text_body = f"""
{greeting_es},

{safe_inviter} te ha invitado a participar en la competicion "{safe_competition}" en Ryder Cup Friends.
{personal_es}
La invitacion expira el {expires_str}.

Para responder a la invitacion, visita: {invitations_link}
{unregistered_es}
Saludos,
El equipo de Ryder Cup Friends

---

{greeting_en},

{safe_inviter} has invited you to join the competition "{safe_competition}" on Ryder Cup Friends.
{personal_en}
The invitation expires on {expires_str}.

To respond to the invitation, visit: {invitations_link}
{unregistered_en}
Best regards,
The Ryder Cup Friends Team
        """

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .container {{
            background-color: #f9f9f9;
            border-radius: 10px;
            padding: 30px;
        }}
        .header {{
            background-color: #0066cc;
            color: white;
            padding: 20px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            padding: 15px 30px;
            background-color: #0066cc;
            color: white !important;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .info-box {{
            background-color: #e8f4fd;
            border-left: 4px solid #0066cc;
            padding: 15px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }}
        .divider {{
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Invitacion a Competicion</h1>
            <h2>Competition Invitation</h2>
        </div>
        <div class="content">
            <!-- Spanish -->
            <p>{greeting_es},</p>
            <p><strong>{safe_inviter}</strong> te ha invitado a participar en la competicion:</p>

            <div class="info-box">
                <p style="margin: 0; font-size: 18px; font-weight: bold;">{safe_competition}</p>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #666;">Expira el {expires_str}</p>
            </div>
            {personal_html_es}
            <center>
                <a href="{invitations_link}" class="button">Ver mis invitaciones</a>
            </center>
            {unregistered_html_es}

            <div class="divider"></div>

            <!-- English -->
            <p>{greeting_en},</p>
            <p><strong>{safe_inviter}</strong> has invited you to join the competition:</p>

            <div class="info-box">
                <p style="margin: 0; font-size: 18px; font-weight: bold;">{safe_competition}</p>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #666;">Expires on {expires_str}</p>
            </div>
            {personal_html_en}
            <center>
                <a href="{invitations_link}" class="button">View my invitations</a>
            </center>
            {unregistered_html_en}

            <div class="footer">
                <p>Saludos | Best regards,<br>
                <strong>El equipo de Ryder Cup Friends | The Ryder Cup Friends Team</strong></p>
            </div>
        </div>
    </div>
</body>
</html>
        """

        recipient = f'"{safe_invitee}" <{to_email}>' if safe_invitee else to_email
        return self._send_email(recipient, subject, text_body, html_body)
