"""
Email Service Interface - Application Layer Port

Define el contrato para servicios de envío de emails.
La capa de aplicación depende de esta abstracción, no de implementaciones concretas.
"""

from abc import ABC, abstractmethod


class IEmailService(ABC):
    """
    Puerto para servicios de envío de email.

    Esta interfaz vive en la capa de APPLICATION, pero es implementada
    por la capa de INFRASTRUCTURE.

    Implementaciones posibles:
    - MailgunEmailService (producción)
    - SendGridEmailService (alternativa)
    - MockEmailService (testing)
    """

    @abstractmethod
    async def send_verification_email(
        self, to_email: str, user_name: str, verification_token: str
    ) -> bool:
        """
        Envía un email de verificación al usuario.

        Args:
            to_email: Email del destinatario
            user_name: Nombre del usuario para personalizar
            verification_token: Token único de verificación

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        pass

    @abstractmethod
    async def send_password_reset_email(
        self, to_email: str, reset_link: str, user_name: str
    ) -> bool:
        """
        Envía un email con enlace para resetear contraseña.

        Args:
            to_email: Email del destinatario
            reset_link: Enlace completo para resetear contraseña (incluye token)
            user_name: Nombre del usuario para personalizar

        Returns:
            True si se envió correctamente, False en caso contrario

        Security:
            - reset_link incluye token de 256 bits válido durante 1 hora
            - Email enviado solo si el usuario existe (previene enumeración)
            - Plantilla bilingüe (ES/EN)
        """
        pass

    @abstractmethod
    async def send_new_login_notification(
        self, to_email: str, user_name: str, dispositivo: str, cuando: str, pais: str | None
    ) -> bool:
        """
        Avisa al usuario de que alguien ha entrado en su cuenta desde un dispositivo
        nuevo (BE #737), con un botón para revisar sus dispositivos.

        Args:
            to_email: El email del usuario
            user_name: Su nombre
            dispositivo: Lo que es, ya en texto («iPhone · Safari»)
            cuando: La fecha y la hora, ya en texto y en hora de España
            pais: El país aproximado, o None
        """

    @abstractmethod
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
        Avisa al usuario de que alguien está fallando su contraseña (BE #732): una red
        quedó bloqueada para su cuenta («red») o saltó el respaldo («respaldo»).

        Args:
            to_email: El email del usuario
            user_name: Su nombre
            motivo: «red» o «respaldo»
            cuando: La fecha y la hora, ya en texto y en hora de España
            pais: El país aproximado, o None
            fallos: Cuántos fallos lo bloquearon (los del freno o los del respaldo)
            minutos: Cuánto dura el bloqueo
        """

    @abstractmethod
    async def send_password_changed_notification(
        self, to_email: str, user_name: str, google_unlinked: bool = False
    ) -> bool:
        """
        Envía un email notificando que la contraseña fue cambiada exitosamente.

        Args:
            to_email: Email del destinatario
            user_name: Nombre del usuario para personalizar
            google_unlinked: Si al cambiarla se le quitó el Google (restablecer una cuenta
                verificada): el correo lo dice y cómo volver a vincularlo

        Returns:
            True si se envió correctamente, False en caso contrario

        Security:
            - Notifica al usuario de cambios de seguridad importantes
            - Permite detectar cambios de contraseña no autorizados
            - Plantilla bilingüe (ES/EN)
        """
        pass

    @abstractmethod
    async def send_email_change_confirmation(
        self, to_email: str, user_name: str, token: str
    ) -> bool:
        """
        Envía al correo NUEVO el enlace que confirma el cambio (#749). Hasta pulsarlo,
        la cuenta sigue con el correo de antes. Caduca en 24 horas.

        Returns:
            True si se envió correctamente
        """

    @abstractmethod
    async def send_google_account_notice(self, to_email: str, user_name: str, linked: bool) -> bool:
        """
        Avisa a la cuenta de que se ha vinculado (o desvinculado) un Google (BE #753): un
        Google vinculado da acceso a la cuenta.

        Returns:
            True si se envió correctamente
        """

    @abstractmethod
    async def send_register_attempt_notice(self, to_email: str, user_name: str) -> bool:
        """
        Avisa al buzón de una cuenta de que alguien intentó registrarse con su correo
        (fase 3, B2/B3): si fue él, que inicie sesión o restablezca la contraseña. Sin
        token ni nada que dé acceso. Como mucho uno al día por cuenta (lo decide el caso
        de uso).

        Returns:
            True si se envió correctamente
        """

    @abstractmethod
    async def send_account_secured_notice(self, to_email: str, user_name: str, via: str) -> bool:
        """
        Avisa al dueño de una cuenta SIN verificar que se la ha quedado (BE #753): lo que
        dejó quien la creó, fuera. `via`: "google" (queda sin contraseña) o "reset" (la
        contraseña es la que acaba de elegir).

        Returns:
            True si se envió correctamente
        """

    @abstractmethod
    async def send_email_changed_notice(
        self, to_email: str, user_name: str, new_email: str
    ) -> bool:
        """
        Avisa al correo de ANTES de que el cambio se ha confirmado (BE #753): desde
        ahora la cuenta usa el nuevo, que va tapado, y dice a quién escribir.

        Returns:
            True si se envió correctamente
        """

    @abstractmethod
    async def send_email_change_requested_notice(
        self, to_email: str, user_name: str, new_email: str
    ) -> bool:
        """
        Avisa al correo de ANTES de que se ha pedido cambiarlo (#749): si no fue el
        dueño, alguien entró en su cuenta. El correo nuevo va tapado.

        Returns:
            True si se envió correctamente
        """
