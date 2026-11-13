"""
Sentry Configuration Module

Configuración centralizada de Sentry para error tracking y performance monitoring.

Características:
- Integración automática con FastAPI
- Captura de contexto HTTP (request, user, headers)
- Performance monitoring (APM)
- Profiling de código
- Breadcrumbs automáticos
- Filtrado de datos sensibles (PII)

OWASP Coverage:
- A09: Logging & Monitoring Failures (+2.0 pts)
  → Error tracking automático con stack traces
  → Performance monitoring con métricas de latencia
  → Contexto completo de requests fallidos
  → Alertas configurables en dashboard Sentry

Configuración requerida:
- SENTRY_DSN: URL del proyecto Sentry (obligatorio)
- ENVIRONMENT: development, staging, production
- SENTRY_TRACES_SAMPLE_RATE: % de transacciones a capturar (default: 0.1 = 10%)
- SENTRY_PROFILES_SAMPLE_RATE: % de perfiles a capturar (default: 0.1 = 10%)
"""

import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint

from src.config import version
from src.config.settings import settings
from src.shared.infrastructure.logging.security_logger import ETIQUETA_DE_EVENTO_DE_SEGURIDAD

logger = logging.getLogger(__name__)

# Los loggers del log de auditoría (`security.audit` y uno por fichero). Sus eventos
# HIGH y CRITICAL ya los manda el propio log, filtrados (F-05b); por la integración
# irían enteros —el correo de un login, en las migas de pan— y el CRITICAL dos veces
LOGGERS_DE_AUDITORIA = "security.audit*"


# Lo que el SDK no quita solo (BE #466): el secreto de la regla de Cloudflare y
# la IP del usuario. `send_default_pii=False` solo conoce Authorization, Cookie,
# X-Forwarded-For y pocas más
_CABECERAS_QUE_NO_SALEN = frozenset({"x-origin-verify", "cf-connecting-ip", "true-client-ip"})


def _quita_cabeceras_de_origen(event: Event) -> Event:
    """Borra del evento las cabeceras del secreto y de la IP, en cualquier grafía."""
    cabeceras = (event.get("request") or {}).get("headers")
    if isinstance(cabeceras, dict):
        for nombre in [n for n in cabeceras if n.lower() in _CABECERAS_QUE_NO_SALEN]:
            del cabeceras[nombre]
    return event


# El cuerpo de estas rutas lleva datos de quien escribe (nombre, correo, mensaje), y
# el SDK lo adjunta a cada error aunque send_default_pii=False (auditoría OWASP, A09).
# También el registro (fase 3): nombre, correo y contraseña. Y el canje con Google:
# lleva el código de autorización y el code_verifier de PKCE, que juntos valen una
# sesión mientras el código no caduque (F8, fase 3)
_RUTAS_SIN_CUERPO = (
    "/api/v1/support/contact",
    "/api/v1/auth/register",
    "/api/v1/auth/google",
    "/api/v1/auth/google/link",
)


def _quita_el_cuerpo_de_las_rutas_con_datos(event: Event) -> Event:
    """Borra el cuerpo de la petición en las rutas de _RUTAS_SIN_CUERPO."""
    peticion = event.get("request") or {}
    url = str(peticion.get("url") or "").split("?")[0]
    if url.endswith(_RUTAS_SIN_CUERPO):
        peticion.pop("data", None)
    return event


# Lo único de la petición que lleva un evento de seguridad (revisión de la fase 2)
_DE_LA_PETICION_EN_LOS_EVENTOS_DE_SEGURIDAD = ("method", "url")


def _recorta_los_eventos_de_seguridad(event: Event) -> Event:
    """
    Un evento del log de seguridad sale con el método y la ruta de la petición y sin IP.

    La integración de FastAPI adjunta el cuerpo de la petición a lo que se capture
    dentro de ella (el correo tecleado en un login o en un cambio de correo), y la IP
    no debe salir (BE #466): el log de seguridad (stdout) ya la guarda. Tampoco van
    las migas ni los extras: los de otro logger de la misma petición pueden llevar
    el correo (/code-review de la fase 2).
    """
    if ETIQUETA_DE_EVENTO_DE_SEGURIDAD not in (event.get("tags") or {}):
        return event
    peticion = event.get("request")
    if isinstance(peticion, dict):
        # La URL del SDK ya va sin la query (esa va aparte, en query_string)
        event["request"] = {
            clave: peticion[clave]
            for clave in _DE_LA_PETICION_EN_LOS_EVENTOS_DE_SEGURIDAD
            if clave in peticion
        }
    event.pop("breadcrumbs", None)
    event.pop("extra", None)
    usuario = event.get("user")
    if isinstance(usuario, dict):
        usuario.pop("ip_address", None)
    contexto = (event.get("contexts") or {}).get(ETIQUETA_DE_EVENTO_DE_SEGURIDAD)
    if isinstance(contexto, dict):
        contexto.pop("ip_address", None)
    return event


def before_send_transaction(event: Event, _hint: Hint) -> Event | None:
    """Las transacciones también llevan la petición: salen sin el secreto ni la IP."""
    return _quita_el_cuerpo_de_las_rutas_con_datos(_quita_cabeceras_de_origen(event))


def before_send(event: Event, hint: Hint) -> Event | None:
    """
    Hook ejecutado antes de enviar eventos a Sentry.

    Permite:
    - Filtrar eventos específicos (ej. health checks)
    - Modificar datos antes de enviarlos
    - Añadir contexto adicional
    - Prevenir envío de datos sensibles (PII)

    Args:
        event: Evento de Sentry a enviar
        hint: Información adicional sobre el evento (exception, log_record, etc.)

    Returns:
        Event modificado (o None para descartarlo)
    """
    _quita_cabeceras_de_origen(event)
    _quita_el_cuerpo_de_las_rutas_con_datos(event)
    _recorta_los_eventos_de_seguridad(event)

    # Filtrar health checks del endpoint "/"
    url = event.get("request", {}).get("url")
    if isinstance(url, str) and url.endswith("/"):
        return None

    # Filtrar requests OPTIONS (CORS preflight)
    if event.get("request", {}).get("method") == "OPTIONS":
        return None

    # Filtrar 404 Not Found (ruido común)
    # Acceso robusto: verificar que exception.values existe y no está vacía
    exception_values = event.get("exception", {}).get("values")
    if exception_values and len(exception_values) > 0:
        exception_type = exception_values[0].get("type")

        # Acceso robusto: verificar que exc_info es tupla/lista con suficientes elementos
        exc_info = hint.get("exc_info")
        if exc_info and isinstance(exc_info, (tuple, list)) and len(exc_info) > 1:
            exception_instance = exc_info[1]

            # Filtrar HTTPException 404
            if exception_type == "HTTPException" and "404" in str(exception_instance):
                return None

    return event


def build_release() -> str:
    """
    Release que se declara a Sentry: `rydercup-backend@<versión>`.

    La versión sale de la misma fuente que `GET /health` (`APP_VERSION`), sin
    una segunda copia a mano. Se lee al llamar, no al importar, para que siga
    siempre a esa fuente. Si está vacía, se dice `unknown`: nunca un número
    inventado.
    """
    app_version = version.APP_VERSION.strip()
    return f"rydercup-backend@{app_version or 'unknown'}"


def init_sentry() -> None:
    """
    Inicializa Sentry SDK con configuración para FastAPI.

    Solo se inicializa si SENTRY_DSN está configurado en variables de entorno.
    En desarrollo local, es opcional (útil para debug sin enviar datos).

    """
    if not settings.SENTRY_DSN:
        logger.info("🔕 Sentry disabled - SENTRY_DSN not configured")
        return

    ignore_logger(LOGGERS_DE_AUDITORIA)

    # Configurar integración de logging
    # Captura automáticamente logs de nivel ERROR o superior
    logging_integration = LoggingIntegration(
        level=logging.INFO,  # Captura breadcrumbs de nivel INFO+
        event_level=logging.ERROR,  # Envía eventos solo para ERROR+
    )

    # Inicializar Sentry SDK
    release = build_release()
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        # Integraciones automáticas
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint"  # Agrupar por endpoint (/users/{id} vs /users/123)
            ),
            SqlalchemyIntegration(),
            logging_integration,
        ],
        # Performance Monitoring (APM)
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        # Profiling (código CPU/memoria)
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        # Hook para filtrar/modificar eventos
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        # Metadata
        release=release,  # Misma versión que expone /health
        # Request data (incluir en eventos)
        send_default_pii=False,  # NO enviar PII automáticamente (GDPR compliance)
        # SECURITY: send_default_pii=False NO cubre las variables locales de cada frame
        # del stack trace -- el SDK las adjunta por defecto. Cualquier logger.error()
        # dentro de un except que tenga en scope un secreto (p.ej. self.api_key en
        # los transportes de envio_de_correo) lo habría mandado a Sentry
        # íntegro. Causa raíz del incidente de fuga de la API key de Mailgun (Jul 2026).
        include_local_variables=False,
        max_breadcrumbs=50,  # Máximo de breadcrumbs por evento
        # Debug mode (solo para desarrollo)
        debug=(settings.SENTRY_ENVIRONMENT == "development"),
    )

    logger.info(
        f"✅ Sentry initialized - "
        f"release={release}, "
        f"env={settings.SENTRY_ENVIRONMENT}, "
        f"traces={settings.SENTRY_TRACES_SAMPLE_RATE:.0%}, "
        f"profiles={settings.SENTRY_PROFILES_SAMPLE_RATE:.0%}"
    )
