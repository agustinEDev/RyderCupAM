"""
Lo que la app comprueba al arrancar fuera de desarrollo (F-06 y F-12, auditoría OWASP
del 9 nov 2026).

Fuera de un desarrollo declarado (`ENVIRONMENT=development`: local, Kind y los tests)
no arranca con:

- `TESTING=true`: apaga el CSRF de los tests de integración y deja a quien llama
  elegir su red con `X-Test-Client-ID`.
- `SECRET_KEY` vacía, de ejemplo (las que vienen en settings.py, `.env.example`,
  docker y k8s) o de menos de 32 bytes: firma los JWT, el CSRF y los contadores.

Como en `contrasenas.py` y `rate_limit.py`, un ENVIRONMENT ausente o desconocido
cuenta como producción. Y `development` con `RENDER` definida (Render la pone) no
arranca: un desarrollo declarado por error en Render se saltaría todo lo anterior. La comprobación va en el `lifespan` y no al importar: el CI
genera el OpenAPI importando `main` sin ninguna variable (job «API contract»).
"""

import os
from collections.abc import Mapping

ENTORNO_DE_DESARROLLO = "development"
LONGITUD_MINIMA_DE_LA_CLAVE = 32  # bytes: 256 bits para el HMAC-SHA256 de los JWT

# Los valores de ejemplo de los ficheros del repositorio: cualquiera puede leerlos
CLAVES_DE_EJEMPLO = frozenset(
    {
        "your-secret-key-change-in-production",  # settings.py y los .env.example
        "your-secret-key-change-me",  # k8s/api-secret.yaml
        "your_secret_key_here",  # docker/scripts
        "MISSING_SECRET_KEY",  # docker/docker-compose.yml
        "your-super-secret-key-min-32-chars",  # docs
        "your-local-secret-key",  # docs
    }
)


def en_desarrollo_declarado(entorno: Mapping[str, str] = os.environ) -> bool:
    """Si ENVIRONMENT dice expresamente `development`; ausente o raro, producción."""
    return (entorno.get("ENVIRONMENT") or "").strip().lower() == ENTORNO_DE_DESARROLLO


def testing_activado(entorno: Mapping[str, str] = os.environ) -> bool:
    """Si TESTING dice `true`, el valor con el que el código cambia de comportamiento."""
    return (entorno.get("TESTING") or "").strip().lower() == "true"


def modo_de_tests(entorno: Mapping[str, str] = os.environ) -> bool:
    """
    La suite de tests: TESTING=true Y ENVIRONMENT=development (ADR-047). Solo así se
    salta el CSRF de los tests de integración y vale X-Test-Client-ID.
    """
    return testing_activado(entorno) and en_desarrollo_declarado(entorno)


def comprueba_la_configuracion_de_seguridad(entorno: Mapping[str, str] = os.environ) -> None:
    """
    No deja arrancar fuera de desarrollo con TESTING ni con una SECRET_KEY mala.

    El mensaje dice el motivo, nunca la clave.

    Raises:
        RuntimeError: con el motivo; la app no arranca
    """
    if en_desarrollo_declarado(entorno):
        # Render pone RENDER en todos sus servicios: un desarrollo ahí es un error de
        # configuración que se saltaría todo lo demás (revisión de la fase 2)
        if (entorno.get("RENDER") or "").strip():
            raise RuntimeError("ENVIRONMENT=development con RENDER definida; no se arranca")
        return
    if testing_activado(entorno):
        raise RuntimeError("TESTING=true fuera de desarrollo: apaga el CSRF; no se arranca")
    clave = (entorno.get("SECRET_KEY") or "").strip()
    if not clave:
        raise RuntimeError("SECRET_KEY sin configurar fuera de desarrollo; no se arranca")
    if clave in CLAVES_DE_EJEMPLO:
        raise RuntimeError("SECRET_KEY es un valor de ejemplo del repositorio; no se arranca")
    if len(clave.encode()) < LONGITUD_MINIMA_DE_LA_CLAVE:
        raise RuntimeError(
            f"SECRET_KEY de menos de {LONGITUD_MINIMA_DE_LA_CLAVE} bytes fuera de desarrollo;"
            " no se arranca"
        )


def main() -> int:
    """
    `python -m src.config.arranque_seguro`: lo ejecuta entrypoint.sh ANTES de migrar
    (/code-review de la fase 2). Si la comprobación fallara solo en el lifespan, la base
    de datos ya estaría migrada y la versión anterior seguiría sirviendo con el esquema
    nuevo. Sale con 1 y el motivo (nunca la clave) si la configuración no vale.
    """
    import sys  # noqa: PLC0415 - solo al ejecutarse como script

    try:
        comprueba_la_configuracion_de_seguridad(os.environ)
    except RuntimeError as error:
        print(f"Configuración insegura: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
