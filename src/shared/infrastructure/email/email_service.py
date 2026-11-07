"""
Email Service - Infrastructure Layer

Los correos de la app: su texto y su HTML. El envío lo hace `envio_de_correo`
(Mailgun, con Resend y Brevo de respaldo, o Mailpit en el Kind).
"""

import logging
from datetime import datetime

from src.config.settings import settings
from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.social.application.ports.social_email_service_interface import (
    ISocialEmailService,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.shared.domain.services.email_masking import mask_email
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
from src.shared.infrastructure.email.envio_de_correo import (
    CorreoSaliente,
    EnvioConRespaldo,
    envio_de_la_app,
)

logger = logging.getLogger(__name__)

MINUTOS_POR_HORA = 60


class EmailService(
    IEmailService, IInvitationEmailService, ISocialEmailService, IHandicapUpdateEmailService
):
    """
    Implementación de IEmailService usando Mailgun.

    Esta es una implementación concreta del puerto IEmailService.
    Puede ser reemplazada por otras implementaciones (SendGrid, AWS SES, etc.)
    sin afectar a la capa de aplicación.
    """

    def __init__(self, envio: EnvioConRespaldo | None = None):
        """Con el envío de la configuración, salvo el que se pase (tests)."""
        self._envio = envio or envio_de_la_app()

    async def send_verification_email(
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

Si no has creado esta cuenta, no pulses: usa "Olvidé mi contraseña" en {settings.FRONTEND_URL}/forgot-password para quedártela.

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_user_name},

Welcome to Ryder Cup Friends!

To complete your registration, please confirm your email address by clicking on the following link:

{verification_link}

If you did not create this account, do not click: use "Forgot password" at {settings.FRONTEND_URL}/forgot-password to take it over.

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
                aviso(
                    negrita("Si no has creado esta cuenta, no pulses: "),
                    'usa "Olvidé mi contraseña" y será tuya.',
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
            pie="Si no has creado esta cuenta, no pulses el botón. "
            "If you didn't create this account, don't click.",
        )

        return await self._send_email(
            to=f'"{safe_user_name}" <{to_email}>',  # RFC 5322 format with quotes
            subject=subject,
            text=text_body,
            html=html_body,
        )

    async def _send_email(
        self,
        to: str,
        subject: str,
        text: str,
        html: str | None = None,
        puede_ir_por_brevo: bool = False,
    ) -> bool:
        """Lo manda; True si salió (ver `envio_de_correo`).

        `puede_ir_por_brevo=True` solo en los correos sin token que no son de seguridad:
        Brevo reescribe los enlaces por su servidor (7 nov 2026).
        """
        return await self._envio.send(
            CorreoSaliente(
                to=to,
                subject=subject,
                text=text,
                html=html,
                puede_ir_por_brevo=puede_ir_por_brevo,
            )
        )

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

        return await self._send_email(to_email, subject, text_body, html_body)

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

        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_email_change_confirmation(
        self, to_email: str, user_name: str, token: str
    ) -> bool:
        """
        El enlace que confirma el correo nuevo (#749), al correo NUEVO. Hasta pulsarlo
        (desde la sesión de la cuenta, en 24 horas), la cuenta sigue con el de antes.
        """
        safe_user_name = self._sanitize_name(user_name)
        enlace = f"{settings.FRONTEND_URL}/confirm-email-change?token={token}"
        subject = "Confirma tu correo nuevo - Ryder Cup Friends | Confirm your new email"
        text_body = f"""
Hola {safe_user_name},

Has pedido usar esta dirección en tu cuenta de Ryder Cup Friends. Para confirmarla, abre
este enlace con tu sesión iniciada (caduca en 24 horas):

{enlace}

Hasta que lo hagas, tu cuenta sigue con su correo de antes. Si no lo has pedido tú,
ignora este correo.

---

Hello {safe_user_name},

You asked to use this address in your Ryder Cup Friends account. To confirm it, open
this link while signed in (it expires in 24 hours):

{enlace}

Until then your account keeps its previous email. If you didn't ask for this, ignore it.
        """
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Confirma tu correo nuevo · Confirm your new email",
            etiqueta="Seguridad",
            titulo="Confirma tu correo nuevo",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", has pedido usar esta dirección en tu cuenta. Confírmala con tu "
                    "sesión iniciada: el enlace caduca en 24 horas.",
                ),
                aviso(
                    negrita("Hasta entonces "),
                    "tu cuenta sigue con su correo de antes. Si no lo has pedido tú, "
                    "ignora este correo.",
                ),
            ],
            boton=Boton("Confirmar el correo", enlace),
            ingles=Ingles(
                frase(
                    negrita("Confirm your new email"),
                    " while signed in. The link expires in 24 hours.",
                ),
                Boton("Confirm my email", enlace),
            ),
            pie="Lo enviamos porque se pidió cambiar el correo de una cuenta a esta "
            "dirección. We sent this because this address was requested for an account.",
        )
        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_email_change_requested_notice(
        self, to_email: str, user_name: str, new_email: str
    ) -> bool:
        """
        El aviso, al correo de ANTES, de que se ha pedido cambiarlo (#749). El nuevo va
        tapado: el aviso puede leerlo quien no es el dueño de esa dirección nueva.
        """
        safe_user_name = self._sanitize_name(user_name)
        nuevo = mask_email(new_email)
        restablecer = f"{settings.FRONTEND_URL}/forgot-password"
        subject = "Se ha pedido cambiar tu correo - Ryder Cup Friends | Email change requested"
        text_body = f"""
Hola {safe_user_name},

Se ha pedido cambiar el correo de tu cuenta de Ryder Cup Friends a {nuevo}. No cambiará
hasta que se confirme desde esa dirección.

Si no has sido tú, cambia tu contraseña: {restablecer}

---

Hello {safe_user_name},

Someone asked to change your Ryder Cup Friends account email to {nuevo}. It won't change
until it is confirmed from that address.

If it wasn't you, change your password: {restablecer}
        """
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Se ha pedido cambiar tu correo · Email change requested",
            etiqueta="Seguridad",
            titulo="Se ha pedido cambiar tu correo",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", se ha pedido cambiar el correo de tu cuenta a ",
                    negrita(nuevo),
                    ". No cambiará hasta que se confirme desde esa dirección.",
                ),
                aviso(
                    negrita("¿No has sido tú? "),
                    "Cambia tu contraseña ahora: alguien puede estar usando tu cuenta.",
                ),
            ],
            boton=Boton("Cambiar la contraseña", restablecer),
            ingles=Ingles(
                frase(
                    negrita("Someone asked to change your email"),
                    f" to {nuevo}. If it wasn't you, change your password.",
                ),
                Boton("Change my password", restablecer),
            ),
            pie="Este aviso se envía siempre que se pide cambiar el correo. "
            "We always send this when an email change is requested.",
        )
        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_google_account_notice(self, to_email: str, user_name: str, linked: bool) -> bool:
        """El aviso de un Google vinculado o desvinculado (BE #753)."""
        safe_user_name = self._sanitize_name(user_name)
        restablecer = f"{settings.FRONTEND_URL}/forgot-password"
        if linked:
            titulo, title = "Google vinculado a tu cuenta", "Google linked to your account"
            hecho = "se ha vinculado una cuenta de Google a tu cuenta: con ella se puede entrar."
            done = "a Google account was linked to your account: it can be used to sign in."
        else:
            titulo, title = "Google desvinculado de tu cuenta", "Google unlinked from your account"
            hecho = "se ha desvinculado la cuenta de Google de tu cuenta."
            done = "the Google account was unlinked from your account."
        subject = f"{titulo} - Ryder Cup Friends | {title}"
        text_body = f"""
Hola {safe_user_name},

{titulo}: {hecho}

Si no has sido tú, cambia tu contraseña: {restablecer}

---

Hello {safe_user_name},

{title}: {done}

If it wasn't you, change your password: {restablecer}
        """
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen=f"{titulo} · {title}",
            etiqueta="Seguridad",
            titulo=titulo,
            cuerpo=[
                parrafo("Hola ", negrita(safe_user_name), f", {hecho}"),
                aviso(
                    negrita("¿No has sido tú? "),
                    "Cambia tu contraseña ahora: alguien puede estar usando tu cuenta.",
                ),
            ],
            boton=Boton("Cambiar la contraseña", restablecer),
            ingles=Ingles(
                frase(negrita(title), f": {done} If it wasn't you, change your password."),
                Boton("Change my password", restablecer),
            ),
            pie="Este aviso se envía siempre que se vincula o desvincula Google. "
            "We always send this when Google is linked or unlinked.",
        )
        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_account_secured_notice(self, to_email: str, user_name: str, via: str) -> bool:
        """
        El aviso de que se ha asegurado una cuenta sin verificar (BE #753). Con Google
        se quitó la contraseña; al restablecer, la que vale es la que acaba de elegir.
        """
        safe_user_name = self._sanitize_name(user_name)
        restablecer = f"{settings.FRONTEND_URL}/forgot-password"
        por_google = via == "google"
        if por_google:
            que_es = (
                "Como no estaba verificada, quitamos la contraseña y cerramos sus sesiones. "
                'Si quieres contraseña, usa "Olvidé mi contraseña".'
            )
            que_es_en = (
                "As it was not verified, we removed its password and closed its sessions. "
                'To have a password, use "Forgot password".'
            )
        else:
            que_es = (
                "Como no estaba verificada, tu contraseña es ahora la que acabas de elegir "
                "y cerramos las demás sesiones."
            )
            que_es_en = (
                "As it was not verified, your password is now the one you just chose and "
                "we closed the other sessions."
            )
        subject = "Hemos asegurado tu cuenta - Ryder Cup Friends | Your account is secured"
        text_body = f"""
Hola {safe_user_name},

Hemos asegurado tu cuenta de Ryder Cup Friends. {que_es}

---

Hello {safe_user_name},

We have secured your Ryder Cup Friends account. {que_es_en}
        """
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Hemos asegurado tu cuenta · Your account is secured",
            etiqueta="Seguridad",
            titulo="Hemos asegurado tu cuenta",
            cuerpo=[
                parrafo("Hola ", negrita(safe_user_name), ", hemos asegurado tu cuenta."),
                aviso(que_es),
            ],
            boton=Boton("Olvidé mi contraseña", restablecer)
            if por_google
            else Boton("Abrir la aplicación", settings.FRONTEND_URL),
            ingles=Ingles(
                frase(negrita("We have secured your account."), f" {que_es_en}"),
                Boton("Forgot password", restablecer)
                if por_google
                else Boton("Open the app", settings.FRONTEND_URL),
            ),
            pie="Este aviso se envía cuando se asegura una cuenta sin verificar. "
            "We send this when an unverified account is secured.",
        )
        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_email_changed_notice(
        self, to_email: str, user_name: str, new_email: str
    ) -> bool:
        """
        El aviso, al correo de ANTES, de que el cambio ya está hecho (BE #753). El nuevo
        va tapado, y dice a quién escribir: con el correo cambiado, el dueño ya no puede
        recuperar la cuenta por su cuenta.
        """
        safe_user_name = self._sanitize_name(user_name)
        nuevo = mask_email(new_email)
        contacto = "admin@rydercupfriends.com"
        subject = "Tu correo ha cambiado - Ryder Cup Friends | Your email has changed"
        text_body = f"""
Hola {safe_user_name},

El correo de tu cuenta de Ryder Cup Friends es ahora {nuevo}.

Si no has sido tú, escríbenos a {contacto}.

---

Hello {safe_user_name},

Your Ryder Cup Friends account email is now {nuevo}.

If it wasn't you, write to us at {contacto}.
        """
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Tu correo ha cambiado · Your email has changed",
            etiqueta="Seguridad",
            titulo="Tu correo ha cambiado",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", el correo de tu cuenta es ahora ",
                    negrita(nuevo),
                    ".",
                ),
                aviso(
                    negrita("¿No has sido tú? "),
                    "Escríbenos a ",
                    negrita(contacto),
                    " y la recuperamos.",
                ),
            ],
            boton=Boton("Escríbenos", f"mailto:{contacto}"),
            ingles=Ingles(
                frase(
                    negrita("Your account email is now"),
                    f" {nuevo}. If it wasn't you, write to us at {contacto}.",
                ),
                Boton("Write to us", f"mailto:{contacto}"),
            ),
            pie="Este aviso se envía siempre que cambia el correo de una cuenta. "
            "We always send this when an account email changes.",
        )
        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_new_login_notification(
        self, to_email: str, user_name: str, dispositivo: str, cuando: str, pais: str | None
    ) -> bool:
        """
        Aviso de un inicio de sesión desde un dispositivo nuevo (BE #737).

        Bilingüe (ES/EN), con la plantilla común. El botón lleva a la lista de
        dispositivos, donde se puede revocar el que no reconozca.
        """
        safe_user_name = self._sanitize_name(user_name)
        donde = f"{dispositivo} · {pais}" if pais else dispositivo
        subject = (
            "Nuevo inicio de sesión en tu cuenta - Ryder Cup Friends | New sign-in to your account"
        )

        text_body = f"""
Hola {safe_user_name},

Alguien ha entrado en tu cuenta de Ryder Cup Friends desde un dispositivo nuevo:

{donde}
{cuando}

Si has sido tú, no tienes que hacer nada.

Si NO has sido tú, revoca ese dispositivo y cambia tu contraseña:
{settings.FRONTEND_URL}/profile/devices

---

Hello {safe_user_name},

Someone signed in to your Ryder Cup Friends account from a new device: {donde}, {cuando}.
If it wasn't you, revoke it and change your password: {settings.FRONTEND_URL}/profile/devices
        """

        mis_dispositivos = f"{settings.FRONTEND_URL}/profile/devices"
        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Nuevo inicio de sesión en tu cuenta · New sign-in to your account",
            etiqueta="Seguridad",
            titulo="Nuevo inicio de sesión",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_user_name),
                    ", alguien ha entrado en tu cuenta desde un dispositivo nuevo:",
                ),
                parrafo(negrita(donde), " · ", cuando),
                parrafo("Si has sido tú, no tienes que hacer nada."),
                aviso(
                    negrita("¿No has sido tú? "),
                    "Revoca ese dispositivo y cambia tu contraseña ahora.",
                ),
            ],
            boton=Boton("Revisar mis dispositivos", mis_dispositivos),
            ingles=Ingles(
                frase(
                    negrita("New sign-in to your account"),
                    f" from {donde}. If it wasn't you, revoke it and change your password.",
                ),
                Boton("Review my devices", mis_dispositivos),
            ),
            pie="Te avisamos cada vez que se entra desde un dispositivo nuevo. "
            "We let you know whenever a new device signs in.",
        )

        return await self._send_email(to_email, subject, text_body, html_body)

    async def send_failed_logins_notification(
        self,
        to_email: str,
        user_name: str,
        motivo: str,
        cuando: str,
        pais: str | None,
        fallos: int,
        minutos: int,
    ) -> bool:
        """
        Aviso de intentos fallidos de entrar en la cuenta (BE #732).

        Bilingüe (ES/EN), con la plantilla común. Dice que el dueño puede seguir
        entrando desde sus dispositivos, y el botón lleva a cambiar la contraseña.
        """
        safe_user_name = self._sanitize_name(user_name)
        donde = f"desde {pais}" if pais else "desde otra red"
        from_where = f"from {pais}" if pais else "from another network"
        if minutos >= MINUTOS_POR_HORA:
            horas = minutos // MINUTOS_POR_HORA
            dura, lasts = f"{horas} horas", f"{horas} hours"
        else:
            dura, lasts = f"{minutos} minutos", f"{minutos} minutes"
        if motivo == "aviso":
            que_pasa = (
                f"alguien ha fallado tu contraseña {fallos} veces en la última hora desde "
                "varias redes. Todavía no hemos bloqueado nada: si sigue, pararemos la "
                "entrada desde dispositivos nuevos."
            )
            en = (
                f"{fallos} times in the last hour from several networks. Nothing is blocked "
                "yet; if it goes on, sign-ins from new devices will be paused."
            )
        elif motivo == "dia":
            que_pasa = (
                f"alguien ha fallado tu contraseña {fallos} veces en las últimas 24 horas "
                f"desde varias redes. Hemos bloqueado {dura} la entrada desde dispositivos "
                "nuevos."
            )
            en = (
                f"{fallos} times in the last 24 hours from several networks. Sign-ins from "
                f"new devices are paused for {lasts}."
            )
        elif motivo == "respaldo":
            que_pasa = (
                f"alguien ha fallado tu contraseña {fallos} veces desde muchas redes a la "
                f"vez. Hemos bloqueado {dura} la entrada desde dispositivos nuevos."
            )
            en = (
                f"{fallos} times from many networks. Sign-ins from new devices are paused "
                f"for {lasts}."
            )
        else:
            que_pasa = (
                f"alguien ha fallado tu contraseña {fallos} veces {donde}. Hemos bloqueado "
                f"esos intentos {dura}."
            )
            en = f"{fallos} times {from_where}. Those attempts are blocked for {lasts}."
        subject = (
            "Intentos fallidos de entrar en tu cuenta - Ryder Cup Friends | "
            "Failed sign-in attempts to your account"
        )
        cambiar = f"{settings.FRONTEND_URL}/profile/edit"

        text_body = f"""
Hola {safe_user_name},

{que_pasa[0].upper() + que_pasa[1:]}
{cuando}

Tú puedes seguir entrando con normalidad desde tus dispositivos de siempre.

Si sospechas que alguien conoce tu contraseña, cámbiala:
{cambiar}

---

Hello {safe_user_name},

Someone failed your Ryder Cup Friends password {en}
You can still sign in from your usual devices. If you think someone knows your
password, change it: {cambiar}
        """

        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen="Intentos fallidos de entrar en tu cuenta · Failed sign-in attempts",
            etiqueta="Seguridad",
            titulo="Intentos fallidos",
            cuerpo=[
                parrafo("Hola ", negrita(safe_user_name), ", ", que_pasa),
                parrafo(cuando),
                parrafo(
                    "Tú puedes seguir entrando con normalidad desde tus dispositivos de siempre."
                ),
                aviso(
                    negrita("¿Crees que alguien conoce tu contraseña? "),
                    "Cámbiala ahora.",
                ),
            ],
            boton=Boton("Cambiar mi contraseña", cambiar),
            ingles=Ingles(
                frase(
                    negrita("Failed sign-in attempts"),
                    f": someone failed your password {en} You can still sign in from your usual devices.",
                ),
                Boton("Change my password", cambiar),
            ),
            pie="Te avisamos como mucho una vez por hora. We let you know at most once an hour.",
        )

        return await self._send_email(to_email, subject, text_body, html_body)

    def _sanitize_name(self, name: str) -> str:
        """Sanitiza un nombre para prevenir inyeccion de headers (RFC 5322)."""
        return (
            name.replace("\n", "")
            .replace("\r", "")
            .replace('"', "")
            # La barra invertida escaparía la comilla de '"nombre" <correo>' (auditoría)
            .replace("\\", "")
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
        return await self._send_email(
            recipient, subject, text_body, html_body, puede_ir_por_brevo=True
        )

    async def send_handicaps_pending_email(
        self,
        to_email: str,
        organizer_name: str,
        competition_name: str,
        competition_id: str,
        pending_names: list[str],
    ) -> bool:
        """
        Avisa al organizador de que hay hándicaps sin actualizar con la RFEG (#251).

        Bilingüe (ES/EN), con la plantilla común de los correos (BE #389).
        """
        safe_organizer = self._sanitize_name(organizer_name)
        safe_competition = self._sanitize_name(competition_name)
        nombres = [self._sanitize_name(n) for n in pending_names if n]
        lista = ", ".join(nombres)
        enlace = f"{settings.FRONTEND_URL}/competitions/{competition_id}"

        subject = (
            f"Hándicaps sin actualizar en {safe_competition} | "
            f"Handicaps not updated in {safe_competition}"
        )
        text_body = f"""
Hola {safe_organizer},

En "{safe_competition}" no se pudo actualizar con la RFEG el hándicap de: {lista}.

Siguen con el hándicap que tenían. Puedes volver a intentarlo con el botón «Actualizar hándicaps» de la competición: {enlace}

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_organizer},

In "{safe_competition}", the RFEG handicap could not be updated for: {lista}.

They keep their previous handicap. You can try again with the "Update handicaps" button on the competition: {enlace}

Best regards,
The Ryder Cup Friends Team
        """

        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen=f"Hándicaps sin actualizar en {safe_competition} · "
            f"Handicaps not updated in {safe_competition}",
            etiqueta="Hándicaps",
            titulo="Hay hándicaps sin actualizar",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_organizer),
                    ", no se pudo actualizar con la RFEG el hándicap de estos jugadores:",
                ),
                recuadro(safe_competition, *nombres),
                parrafo(
                    "Siguen con el hándicap que tenían. Puedes volver a intentarlo con el "
                    "botón «Actualizar hándicaps» de la competición."
                ),
            ],
            boton=Boton("Ver la competición", enlace),
            ingles=Ingles(
                frase(
                    negrita(f"Handicaps not updated in {safe_competition}"),
                    f": {lista}. Try again with the Update handicaps button.",
                ),
                Boton("View competition", enlace),
            ),
            pie="Te llega porque organizas esta competición en RyderCupFriends. "
            "You get this because you organise this competition on RyderCupFriends.",
        )

        recipient = f'"{safe_organizer}" <{to_email}>'
        return await self._send_email(
            recipient, subject, text_body, html_body, puede_ir_por_brevo=True
        )

    async def send_scheduled_handicaps_update_skipped_email(
        self,
        to_email: str,
        organizer_name: str,
        competition_name: str,
        competition_id: str,
        reason: str,
    ) -> bool:
        """
        Avisa al organizador de que su actualización programada no se lanzó (#251).

        Bilingüe (ES/EN), con la plantilla común de los correos (BE #389).
        """
        safe_organizer = self._sanitize_name(organizer_name)
        safe_competition = self._sanitize_name(competition_name)
        enlace = f"{settings.FRONTEND_URL}/competitions/{competition_id}"

        subject = (
            f"No se actualizaron los hándicaps de {safe_competition} | "
            f"Handicaps of {safe_competition} were not updated"
        )
        text_body = f"""
Hola {safe_organizer},

La actualización de hándicaps que programaste en "{safe_competition}" no se lanzó: {reason}

Puedes programarla de nuevo o usar el botón «Actualizar hándicaps» de la competición cuando se pueda: {enlace}

Saludos,
El equipo de Ryder Cup Friends

---

Hello {safe_organizer},

The handicap update you scheduled for "{safe_competition}" did not run. The reason is in the Spanish part above.

You can schedule it again or use the "Update handicaps" button on the competition: {enlace}

Best regards,
The Ryder Cup Friends Team
        """

        html_body = correo(
            web=settings.FRONTEND_URL,
            resumen=f"No se actualizaron los hándicaps de {safe_competition} · "
            f"Handicaps of {safe_competition} were not updated",
            etiqueta="Hándicaps",
            titulo="Tu actualización programada no se lanzó",
            cuerpo=[
                parrafo(
                    "Hola ",
                    negrita(safe_organizer),
                    ", la actualización de hándicaps que programaste no se lanzó:",
                ),
                recuadro(safe_competition, reason),
                parrafo(
                    "Puedes programarla de nuevo o usar el botón «Actualizar hándicaps» "
                    "de la competición cuando se pueda."
                ),
            ],
            boton=Boton("Ver la competición", enlace),
            ingles=Ingles(
                frase(
                    negrita(f"The scheduled handicap update for {safe_competition} did not run"),
                    ". The reason is in the Spanish part above.",
                ),
                Boton("View competition", enlace),
            ),
            pie="Te llega porque organizas esta competición en RyderCupFriends. "
            "You get this because you organise this competition on RyderCupFriends.",
        )

        recipient = f'"{safe_organizer}" <{to_email}>'
        return await self._send_email(
            recipient, subject, text_body, html_body, puede_ir_por_brevo=True
        )

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
        return await self._send_email(
            recipient, subject, text_body, html_body, puede_ir_por_brevo=True
        )
