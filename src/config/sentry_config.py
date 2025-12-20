"""
Sentry Configuration Module (v1.8.0 - Task 10)

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
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event, Hint

from src.config.settings import settings

logger = logging.getLogger(__name__)


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
    # Filtrar health checks del endpoint "/"
    if event.get("request", {}).get("url", "").endswith("/"):
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


def init_sentry() -> None:
    """
    Inicializa Sentry SDK con configuración para FastAPI.

    Solo se inicializa si SENTRY_DSN está configurado en variables de entorno.
    En desarrollo local, es opcional (útil para debug sin enviar datos).

    """
    if not settings.SENTRY_DSN:
        logger.info("🔕 Sentry disabled - SENTRY_DSN not configured")
        return

    # Configurar integración de logging
    # Captura automáticamente logs de nivel ERROR o superior
    logging_integration = LoggingIntegration(
        level=logging.INFO,  # Captura breadcrumbs de nivel INFO+
        event_level=logging.ERROR  # Envía eventos solo para ERROR+
    )

    # Inicializar Sentry SDK
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

        # Metadata
        release="rydercup-backend@1.8.0",  # Versión actual del backend

        # Request data (incluir en eventos)
        send_default_pii=False,  # NO enviar PII automáticamente (GDPR compliance)
        max_breadcrumbs=50,  # Máximo de breadcrumbs por evento

        # Debug mode (solo para desarrollo)
        debug=(settings.SENTRY_ENVIRONMENT == "development"),
    )

    logger.info(
        f"✅ Sentry initialized - "
        f"env={settings.SENTRY_ENVIRONMENT}, "
        f"traces={settings.SENTRY_TRACES_SAMPLE_RATE:.0%}, "
        f"profiles={settings.SENTRY_PROFILES_SAMPLE_RATE:.0%}"
    )
