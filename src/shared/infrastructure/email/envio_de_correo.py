"""
La pieza que manda los correos de la app (7 nov 2026, BE #148 y #563).

- **mailgun** (por defecto y el único en producción): Mailgun UE. Si responde 429
  (cupo agotado) o 5xx (caído), un respaldo según el correo:
  - **con token** (verificar, restablecer, confirmar el correo nuevo): solo **Resend**,
    que no toca los enlaces. Brevo los reescribe por su servidor y no deja quitarlo, y
    un token no pasa por un tercero (7 nov 2026, prueba real y decisión de Agustín);
  - **avisos de seguridad** (nuevo inicio de sesión, intentos fallidos, contraseña
    cambiada, cambio de correo pedido): también solo **Resend**;
  - **el resto** (invitaciones, amistad, hándicaps, contacto): **Resend**, y **Brevo**
    solo si fallan los dos.
  Sin clave de Mailgun o con su clave rechazada (401/403), lo mismo. Tras un rechazo
  4xx, un 502/504 de pasarela, una espera agotada o un fallo de red no se prueba el
  siguiente: el correo pudo salir ya. Ningún respaldo empieza pasados ~10 s de los 25
  del presupuesto de cada correo, y nada se corta a medias.
- **mailpit** (el Kind y el docker-compose): el correo se queda en un buzón local que
  no entrega a nadie, para probar sin gastar el cupo de producción.

Todo asíncrono con httpx. En los logs, nunca el destinatario ni el cuerpo de la
respuesta (podría repetir datos del correo): solo códigos y tipos de error.
"""

import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import parseaddr
from enum import Enum, auto
from functools import cache

import httpx

logger = logging.getLogger(__name__)

# 10 s por paso (5 para conectar). Un paso entero cabe en 15 s: un respaldo solo empieza
# si quedan 15 de los 25 del presupuesto, y así un proveedor lento no cuelga el registro
# ni el restablecimiento. Nada se corta a medias: el correo podría haber salido
ESPERA = httpx.Timeout(10.0, connect=5.0)
PRESUPUESTO_TOTAL = 25.0
TIEMPO_POR_PASO = 15.0
SIN_TIEMPO = "Email sending ran out of time for the backups"
# Un 429 es el cupo diario o el límite por segundo (una ráfaga de invitaciones)
CUPO_AGOTADO = "%s quota or rate limit reached (429)"
FALLAN_LOS_RESPALDOS = "Mailgun and its backups all failed"
TRANSPORTES = ("mailgun", "mailpit")
REMITENTE_POR_DEFECTO = "Ryder Cup Friends <noreply@rydercupfriends.com>"


@dataclass(frozen=True)
class CorreoSaliente:
    """Un correo listo para salir."""

    to: str
    subject: str
    text: str
    html: str | None = None
    reply_to: str | None = None
    # Brevo reescribe los enlaces: nunca un correo con token ni un aviso de seguridad.
    # Por defecto, no: un correo nuevo sin marcar nunca sale por Brevo
    puede_ir_por_brevo: bool = False


class Resultado(Enum):
    """Cómo acabó un intento, para decidir si se prueba el respaldo."""

    ENVIADO = auto()
    SIN_CLAVE = auto()
    CUPO = auto()  # 429: el respaldo puede mandarlo
    CAIDO = auto()  # 500/503, sin clave o rechazada (401/403): el respaldo puede mandarlo
    RECHAZADO = auto()  # 4xx: el respaldo lo rechazaría igual
    DUDOSO = auto()  # red o espera agotada: pudo salir ya, no se repite


def _remitente(from_email: str) -> tuple[str, str]:
    """('Ryder Cup Friends', 'noreply@…') de 'Ryder Cup Friends <noreply@…>'."""
    nombre, direccion = parseaddr(from_email)
    return nombre, direccion


def _destinatario(to: str) -> tuple[str, str]:
    """('Ana', 'ana@…') de '"Ana" <ana@…>'; ('', 'ana@…') de una dirección sola."""
    nombre, direccion = parseaddr(to)
    return nombre, direccion or to


def _por_codigo(proveedor: str, estado: int) -> Resultado:
    """Qué significa el código de la respuesta: cualquier 2xx es aceptado (CodeRabbit)."""
    if httpx.codes.OK <= estado < httpx.codes.MULTIPLE_CHOICES:
        return Resultado.ENVIADO
    if estado == httpx.codes.TOO_MANY_REQUESTS:
        return Resultado.CUPO
    logger.error("%s refused the email: %s", proveedor, estado)
    if estado in (httpx.codes.BAD_GATEWAY, httpx.codes.GATEWAY_TIMEOUT):
        # La pasarela pudo cortar con el correo ya aceptado: no se repite
        return Resultado.DUDOSO
    if estado >= httpx.codes.INTERNAL_SERVER_ERROR or estado in (
        httpx.codes.UNAUTHORIZED,
        httpx.codes.FORBIDDEN,
    ):
        return Resultado.CAIDO
    return Resultado.RECHAZADO


def _para_brevo(to: str) -> dict[str, str]:
    """El destinatario como lo quiere Brevo: dirección y nombre por separado."""
    nombre, direccion = _destinatario(to)
    return {"email": direccion, "name": nombre} if nombre else {"email": direccion}


def _para_mailpit(to: str) -> dict[str, str]:
    """El destinatario como lo quiere Mailpit: dirección y nombre por separado."""
    nombre, direccion = _destinatario(to)
    return {"Email": direccion, "Name": nombre} if nombre else {"Email": direccion}


class _TransporteHttp:
    """Lo común: el cliente con su espera máxima y los errores sin datos."""

    proveedor = ""

    def __init__(self, transporte_http: httpx.AsyncBaseTransport | None = None):
        """El transporte HTTP solo se pasa en los tests (uno falso, sin red)."""
        self._transporte_http = transporte_http

    async def _post(self, url: str, **kwargs) -> httpx.Response | None:
        """La respuesta del proveedor, o None si no la hubo (red o espera agotada)."""
        try:
            async with httpx.AsyncClient(
                timeout=ESPERA, transport=self._transporte_http
            ) as cliente:
                return await cliente.post(url, **kwargs)
        except Exception as error:
            # Solo el tipo: el mensaje podría llevar la URL o datos
            logger.error("%s call failed (%s)", self.proveedor, type(error).__name__)
            return None


class MailgunTransport(_TransporteHttp):
    """Mailgun UE, por su API HTTP."""

    proveedor = "Mailgun"

    def __init__(
        self,
        api_key: str,
        api_url: str,
        domain: str,
        from_email: str,
        transporte_http: httpx.AsyncBaseTransport | None = None,
    ):
        """Con su clave, su URL y el remitente de la configuración."""
        super().__init__(transporte_http)
        self._api_key = api_key
        self._url = f"{api_url}/{domain}/messages"
        self._from_email = from_email

    async def send(self, correo: CorreoSaliente) -> Resultado:
        """Un intento de envío, sin respaldo (eso lo decide EnvioConRespaldo)."""
        if not self._api_key:
            logger.error("MAILGUN_API_KEY is not set: email not sent")
            return Resultado.SIN_CLAVE
        datos = {
            "from": self._from_email,
            "to": correo.to,
            "subject": correo.subject,
            "text": correo.text,
        }
        if correo.html:
            datos["html"] = correo.html
        if correo.reply_to:
            datos["h:Reply-To"] = correo.reply_to
        respuesta = await self._post(self._url, auth=("api", self._api_key), data=datos)
        if respuesta is None:
            return Resultado.DUDOSO
        return _por_codigo(self.proveedor, respuesta.status_code)


class BrevoTransport(_TransporteHttp):
    """Brevo, el respaldo gratuito (300 al día) cuando Mailgun no puede."""

    proveedor = "Brevo"

    def __init__(
        self,
        api_key: str,
        api_url: str,
        from_email: str,
        transporte_http: httpx.AsyncBaseTransport | None = None,
    ):
        """Con su clave, su URL y el remitente de la configuración."""
        super().__init__(transporte_http)
        self._api_key = api_key
        self._url_base = api_url.rstrip("/")
        self._url = f"{self._url_base}/smtp/email"
        self._nombre, self._direccion = _remitente(from_email)

    @property
    def configurado(self) -> bool:
        """True si tiene clave: sin ella no se usa como respaldo."""
        return bool(self._api_key)

    async def comprueba_la_clave(self) -> int | None:
        """El código de una consulta pequeña (las estadísticas de ayer), o None si no
        hubo respuesta. Usa la clave para que Brevo no la caduque por inactividad."""
        try:
            async with httpx.AsyncClient(
                timeout=ESPERA, transport=self._transporte_http
            ) as cliente:
                respuesta = await cliente.get(
                    f"{self._url_base}/smtp/statistics/aggregatedReport",
                    params={"days": 1},
                    headers={"api-key": self._api_key, "accept": "application/json"},
                )
        except Exception as error:
            logger.warning("Brevo key check: no answer (%s)", type(error).__name__)
            return None
        return respuesta.status_code

    async def send(self, correo: CorreoSaliente) -> Resultado:
        """Un intento de envío, sin respaldo (eso lo decide EnvioConRespaldo)."""
        if not self._api_key:
            return Resultado.SIN_CLAVE
        cuerpo: dict = {
            "sender": {"name": self._nombre, "email": self._direccion},
            "to": [_para_brevo(correo.to)],
            "subject": correo.subject,
            "textContent": correo.text,
        }
        if correo.html:
            cuerpo["htmlContent"] = correo.html
        if correo.reply_to:
            cuerpo["replyTo"] = {"email": correo.reply_to}
        respuesta = await self._post(
            self._url, headers={"api-key": self._api_key, "accept": "application/json"}, json=cuerpo
        )
        if respuesta is None:
            return Resultado.DUDOSO
        return _por_codigo(self.proveedor, respuesta.status_code)


class ResendTransport(_TransporteHttp):
    """Resend (UE), el respaldo de los correos con token: no reescribe los enlaces."""

    proveedor = "Resend"

    def __init__(
        self,
        api_key: str,
        api_url: str,
        from_email: str,
        transporte_http: httpx.AsyncBaseTransport | None = None,
    ):
        """Con su clave, su URL y el remitente de la configuración."""
        super().__init__(transporte_http)
        self._api_key = api_key
        self._url = f"{api_url.rstrip('/')}/emails"
        self._from_email = from_email

    @property
    def configurado(self) -> bool:
        """True si tiene clave: sin ella no se usa como respaldo."""
        return bool(self._api_key)

    async def send(self, correo: CorreoSaliente) -> Resultado:
        """Un intento de envío, sin respaldo (eso lo decide EnvioConRespaldo)."""
        if not self._api_key:
            return Resultado.SIN_CLAVE
        cuerpo: dict = {
            "from": self._from_email,
            "to": [correo.to],
            "subject": correo.subject,
            "text": correo.text,
        }
        if correo.html:
            cuerpo["html"] = correo.html
        if correo.reply_to:
            cuerpo["reply_to"] = correo.reply_to
        respuesta = await self._post(
            self._url, headers={"Authorization": f"Bearer {self._api_key}"}, json=cuerpo
        )
        if respuesta is None:
            return Resultado.DUDOSO
        return _por_codigo(self.proveedor, respuesta.status_code)


class MailpitTransport(_TransporteHttp):
    """El buzón local del Kind y del docker-compose: guarda el correo, no lo entrega."""

    proveedor = "Mailpit"

    def __init__(
        self, url: str, from_email: str, transporte_http: httpx.AsyncBaseTransport | None = None
    ):
        """Con la URL del buzón local y el remitente de la configuración."""
        super().__init__(transporte_http)
        self._url = f"{url.rstrip('/')}/api/v1/send"
        self._nombre, self._direccion = _remitente(from_email)

    async def send(self, correo: CorreoSaliente) -> Resultado:
        """Lo deja en el buzón local de Mailpit (no se entrega a nadie)."""
        cuerpo: dict = {
            "From": {"Name": self._nombre, "Email": self._direccion},
            "To": [_para_mailpit(correo.to)],
            "Subject": correo.subject,
            "Text": correo.text,
        }
        if correo.html:
            cuerpo["HTML"] = correo.html
        if correo.reply_to:
            cuerpo["ReplyTo"] = [{"Email": correo.reply_to}]
        respuesta = await self._post(self._url, json=cuerpo)
        if respuesta is None:
            return Resultado.DUDOSO
        return _por_codigo(self.proveedor, respuesta.status_code)


class EnvioConRespaldo:
    """El envío de la app: el primario y, si no puede, el respaldo que le toca al correo."""

    def __init__(
        self,
        primario: MailgunTransport | MailpitTransport,
        brevo: BrevoTransport | None = None,
        resend: ResendTransport | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ):
        """El primario, los respaldos que haya (None sin clave) y el reloj (tests)."""
        self.primario = primario
        self.brevo = brevo
        self.resend = resend
        self._reloj = reloj

    def _respaldos(self, correo: CorreoSaliente) -> list[BrevoTransport | ResendTransport]:
        """Resend, y Brevo después solo si el correo puede ir por él. Solo con clave."""
        candidatos = [self.resend, self.brevo] if correo.puede_ir_por_brevo else [self.resend]
        return [r for r in candidatos if r is not None and r.configurado]

    async def send(self, correo: CorreoSaliente) -> bool:
        """True si el correo salió, por el primario o por un respaldo."""
        empieza = self._reloj()
        resultado = await self.primario.send(correo)
        if resultado is Resultado.ENVIADO:
            return True
        if resultado is Resultado.CUPO:
            # Su propio error en Sentry: el cupo o el límite se sabe el mismo día
            logger.error(CUPO_AGOTADO, self.primario.proveedor)
        if resultado not in (Resultado.CUPO, Resultado.CAIDO, Resultado.SIN_CLAVE):
            # Rechazado (lo rechazarían igual) o dudoso (pudo salir ya)
            return False
        respaldos = self._respaldos(correo)
        if not respaldos:
            return False
        for respaldo in respaldos:
            if self._reloj() - empieza > PRESUPUESTO_TOTAL - TIEMPO_POR_PASO:
                logger.error(SIN_TIEMPO)
                return False
            resultado = await respaldo.send(correo)
            if resultado is Resultado.ENVIADO:
                return True
            if resultado not in (Resultado.CUPO, Resultado.CAIDO):
                # La misma regla que con Mailgun: tras un rechazo o algo dudoso no se
                # prueba el siguiente
                break
        logger.error(FALLAN_LOS_RESPALDOS)
        return False


def _valor(entorno: Mapping[str, str], clave: str, por_defecto: str) -> str:
    """El valor de la variable, o su valor por defecto si falta o está vacía."""
    return (entorno.get(clave) or "").strip() or por_defecto


def _transporte(entorno: Mapping[str, str]) -> str:
    """El transporte configurado, en minúsculas (mailgun si falta o está vacío)."""
    return _valor(entorno, "EMAIL_TRANSPORT", "mailgun").lower()


def comprueba_el_envio_de_correo(entorno: Mapping[str, str]) -> None:
    """Al arrancar: en producción solo mailgun, y ningún valor desconocido.

    Así un Mailpit en producción no se traga en silencio los correos de los usuarios.
    """
    transporte = _transporte(entorno)
    if transporte not in TRANSPORTES:
        raise RuntimeError(f"EMAIL_TRANSPORT must be one of {TRANSPORTES}, got {transporte!r}")
    produccion = _valor(entorno, "ENVIRONMENT", "development").lower() == "production"
    if produccion and transporte != "mailgun":
        raise RuntimeError("EMAIL_TRANSPORT must be 'mailgun' in production")
    if produccion and not _valor(entorno, "MAILGUN_API_KEY", ""):
        raise RuntimeError("MAILGUN_API_KEY must be set in production")
    # En producción, las claves solo viajan por https: una URL mal puesta no las manda
    # a otro sitio en claro
    for clave in ("MAILGUN_API_URL", "RESEND_API_URL", "BREVO_API_URL"):
        url = _valor(entorno, clave, "")
        if produccion and url and not url.lower().startswith("https://"):
            raise RuntimeError(f"{clave} must use https in production")


def crea_el_envio(entorno: Mapping[str, str]) -> EnvioConRespaldo:
    """El envío que toca según la configuración (variables de entorno)."""
    comprueba_el_envio_de_correo(entorno)
    remitente = _valor(entorno, "MAILGUN_FROM_EMAIL", REMITENTE_POR_DEFECTO)
    if _transporte(entorno) == "mailpit":
        return EnvioConRespaldo(
            MailpitTransport(_valor(entorno, "MAILPIT_URL", "http://localhost:8025"), remitente)
        )
    mailgun = MailgunTransport(
        api_key=_valor(entorno, "MAILGUN_API_KEY", ""),
        api_url=_valor(entorno, "MAILGUN_API_URL", "https://api.eu.mailgun.net/v3"),
        domain=_valor(entorno, "MAILGUN_DOMAIN", "rydercupfriends.com"),
        from_email=remitente,
    )
    brevo = brevo_desde(entorno)
    clave_de_resend = _valor(entorno, "RESEND_API_KEY", "")
    resend = (
        ResendTransport(
            clave_de_resend, _valor(entorno, "RESEND_API_URL", "https://api.resend.com"), remitente
        )
        if clave_de_resend
        else None
    )
    return EnvioConRespaldo(mailgun, brevo, resend)


def brevo_desde(entorno: Mapping[str, str]) -> BrevoTransport | None:
    """Brevo con la configuración, o None sin clave (lo usa también su vigía diario)."""
    clave = _valor(entorno, "BREVO_API_KEY", "")
    if not clave:
        return None
    return BrevoTransport(
        clave,
        _valor(entorno, "BREVO_API_URL", "https://api.brevo.com/v3"),
        _valor(entorno, "MAILGUN_FROM_EMAIL", REMITENTE_POR_DEFECTO),
    )


def envia_por_mailgun_en_produccion(entorno: Mapping[str, str]) -> bool:
    """Producción y transporte mailgun (vacío o sin poner también)."""
    produccion = _valor(entorno, "ENVIRONMENT", "development").lower() == "production"
    return produccion and _transporte(entorno) == "mailgun"


@cache
def envio_de_la_app() -> EnvioConRespaldo:
    """Uno por proceso: la configuración no cambia sin reiniciar (/code-review)."""
    return crea_el_envio(os.environ)
