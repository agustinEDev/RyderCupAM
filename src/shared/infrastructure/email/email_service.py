"""
Email Service - Infrastructure Layer

Servicio para enviar emails usando Mailgun.
"""

import asyncio
import logging
from datetime import datetime

import requests
from fastapi import status

from src.config.settings import settings
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.social.application.ports.social_email_service_interface import (
    ISocialEmailService,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.shared.infrastructure.email.email_layout import (
    Boton,
    Ingles,
    aviso,
    cita,
    correo,
    frase,
    negrita,
    parrafo,
    recuadro,
)

logger = logging.getLogger(__name__)


class EmailService(IEmailService, IInvitationEmailService, ISocialEmailService):
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

        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Confirma tu correo para activar tu cuenta · Confirm your email to activate your account",
            etiqueta="Bienvenida",
            titulo="Confirma tu correo y empieza a jugar",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", gracias por registrarte en RyderCupFriends. Solo falta un paso: "
                    "confirma que este correo es tuyo para activar la cuenta.",
                ),
            ],
            boton=Boton("Confirmar mi correo", verification_link),
            ingles=Ingles(
                frase(
                    "Hi ",
                    negrita(safe_user_name),
                    ", confirm your email to activate your RyderCupFriends account.",
                ),
                Boton("Confirm my email", verification_link),
            ),
            pie="Si no te has registrado en RyderCupFriends, ignora este correo. "
            "If you didn't sign up, ignore this email.",
        )

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

        Bilingüe (ES/EN), con la plantilla común de los correos (BE #389).
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

        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Restablece tu contraseña · Reset your password",
            etiqueta="Seguridad",
            titulo="Restablece tu contraseña",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", hemos recibido una petición para restablecer la contraseña de tu cuenta.",
                ),
                parrafo(
                    "El enlace vale durante 24 horas. Al cambiar la contraseña se cierran "
                    "todas tus sesiones abiertas."
                ),
                parrafo(
                    "Si no lo has pedido tú, ignora este correo: tu contraseña actual sigue valiendo.",
                    pequeno=True,
                ),
            ],
            boton=Boton("Restablecer mi contraseña", reset_link),
            ingles=Ingles(
                frase(
                    "Hi ",
                    negrita(safe_user_name),
                    ", use this link within 24 hours to set a new password. "
                    "If you didn't ask for it, ignore this email.",
                ),
                Boton("Reset my password", reset_link),
            ),
            pie="Te llega porque alguien pidió restablecer la contraseña de esta cuenta. "
            "You get this because a password reset was requested for this account.",
        )

        return await asyncio.to_thread(self._send_email, to_email, subject, text_body, html_body)

    async def send_password_changed_notification(self, to_email: str, user_name: str) -> bool:
        """
        Envía un email notificando que la contraseña fue cambiada exitosamente.

        Bilingüe (ES/EN), con la plantilla común de los correos (BE #389).
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

        restablecer = f"{settings.FRONTEND_URL}/forgot-password"
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="La contraseña de tu cuenta ha cambiado · Your password was changed",
            etiqueta="Seguridad",
            titulo="Tu contraseña ha cambiado",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", la contraseña de tu cuenta acaba de cambiar. Por seguridad hemos "
                    "cerrado todas tus sesiones: vuelve a entrar con la nueva.",
                ),
                aviso(
                    negrita("¿No has sido tú? "),
                    "Restablece la contraseña ahora: alguien puede estar usando tu cuenta.",
                ),
            ],
            boton=Boton("Restablecer la contraseña", restablecer),
            ingles=Ingles(
                frase(
                    negrita("Your password was changed"),
                    " and all your sessions were closed. If it wasn't you, reset it now.",
                ),
                Boton("Reset my password", restablecer),
            ),
            pie="Este aviso se envía siempre que cambia la contraseña. "
            "We always send this when the password changes.",
        )

        return await asyncio.to_thread(self._send_email, to_email, subject, text_body, html_body)

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

        Bilingüe (ES/EN), con la plantilla común de los correos (BE #389).
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
        if personal_message:
            personal_es = f'\nMensaje de {safe_inviter}: "{personal_message}"\n'
            personal_en = f'\nMessage from {safe_inviter}: "{personal_message}"\n'

        # El buzón del jugador: «/invitations» no existe y dejaba una página en blanco
        invitations_link = f"{settings.FRONTEND_URL}/player/invitations"
        register_link = f"{settings.FRONTEND_URL}/register"

        subject = (
            f"Te han invitado a {safe_competition} | You've been invited to {safe_competition}"
        )

        # Texto para no registrados
        unregistered_es = ""
        unregistered_en = ""
        if not safe_invitee:
            unregistered_es = f"\nAun no tienes cuenta? Registrate aqui: {register_link}\n"
            unregistered_en = f"\nDon't have an account yet? Register here: {register_link}\n"

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

        saludo = ("Hola ", negrita(safe_invitee), ", ") if safe_invitee else ("Hola, ",)
        cuerpo = [
            parrafo(*saludo, negrita(safe_inviter), " te ha invitado a esta competición:"),
            recuadro(safe_competition, f"Responde antes del {expires_str}"),
        ]
        if personal_message:
            cuerpo.append(cita(personal_message, safe_inviter))
        otros_botones = []
        if not safe_invitee:
            cuerpo.append(
                parrafo(
                    "¿Aún no tienes cuenta? Créala con este mismo correo y la invitación "
                    "te estará esperando.",
                    pequeno=True,
                )
            )
            otros_botones.append(Boton("Crear mi cuenta", register_link))
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen=f"{safe_inviter} te invita a {safe_competition} · "
            f"{safe_inviter} invites you to {safe_competition}",
            etiqueta="Invitación",
            titulo=f"{safe_inviter} te invita a jugar",
            cuerpo=cuerpo,
            boton=Boton("Ver la invitación", invitations_link),
            otros_botones=otros_botones,
            ingles=Ingles(
                frase(
                    negrita(f"{safe_inviter} invites you to play {safe_competition}"),
                    f". Reply before {expires_str}.",
                ),
                Boton("View invitation", invitations_link),
            ),
            pie="Te llega porque alguien te invitó en RyderCupFriends. "
            "You get this because someone invited you on RyderCupFriends.",
        )

        recipient = f'"{safe_invitee}" <{to_email}>' if safe_invitee else to_email
        return await asyncio.to_thread(self._send_email, recipient, subject, text_body, html_body)

    async def send_friend_request_email(
        self,
        to_email: str,
        addressee_name: str,
        requester_name: str,
    ) -> bool:
        """
        Envia un email notificando una nueva solicitud de amistad.

        Bilingüe (ES/EN), con la plantilla común de los correos (BE #389).
        """
        safe_addressee = self._sanitize_name(addressee_name)
        safe_requester = self._sanitize_name(requester_name)

        friends_link = f"{settings.FRONTEND_URL}/friends"

        subject = f"{safe_requester} quiere ser tu amigo | {safe_requester} wants to be your friend"

        text_body = f"""
Hola {safe_addressee},

{safe_requester} te ha enviado una solicitud de amistad en Ryder Cup Friends.

Para aceptarla o rechazarla, visita: {friends_link}

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_addressee},

{safe_requester} has sent you a friend request on Ryder Cup Friends.

To accept or decline it, visit: {friends_link}

Best regards,
The Ryder Cup Friends Team
        """

        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen=f"{safe_requester} quiere ser tu amigo · "
            f"{safe_requester} wants to be your friend",
            etiqueta="Amigos",
            titulo=f"{safe_requester} quiere ser tu amigo",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_addressee),
                    ", ",
                    negrita(safe_requester),
                    " te ha enviado una solicitud de amistad en RyderCupFriends. "
                    "Acéptala o recházala desde tu lista de amigos.",
                ),
            ],
            boton=Boton("Ver la solicitud", friends_link),
            ingles=Ingles(
                frase(
                    negrita(f"{safe_requester} sent you a friend request."),
                    " Accept or decline it from your friends list.",
                ),
                Boton("View request", friends_link),
            ),
            pie="Te llega porque alguien quiere añadirte como amigo en RyderCupFriends. "
            "You get this because someone wants to add you as a friend on RyderCupFriends.",
        )

        recipient = f'"{safe_addressee}" <{to_email}>'
        return await asyncio.to_thread(self._send_email, recipient, subject, text_body, html_body)
