"""
Email Service - Infrastructure Layer

Servicio para enviar emails usando Mailgun.
"""

import logging

import requests
from fastapi import status

from src.config.settings import settings
from src.modules.user.application.ports.email_service_interface import IEmailService

logger = logging.getLogger(__name__)


class EmailService(IEmailService):
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
        self,
        to_email: str,
        user_name: str,
        verification_token: str
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
        # Sanitizar user_name para prevenir inyección de headers (RFC 5322)
        # Eliminar caracteres especiales que podrían romper el formato de email headers
        safe_user_name = (
            user_name
            .replace('\n', '')
            .replace('\r', '')
            .replace('"', '')
            .replace('<', '')
            .replace('>', '')
            .strip()
        )

        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

        subject = f"Bienvenido a Ryder Cup Friends, {safe_user_name}! | Welcome to Ryder Cup Friends!"

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
            html=html_body
        )

    def _send_email(
        self,
        to: str,
        subject: str,
        text: str,
        html: str | None = None
    ) -> bool:
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

            data = {
                "from": self.from_email,
                "to": to,
                "subject": subject,
                "text": text
            }

            if html:
                data["html"] = html

            response = requests.post(
                url,
                auth=("api", self.api_key),
                data=data,
                timeout=10
            )

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
