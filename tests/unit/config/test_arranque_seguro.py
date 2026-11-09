"""
La app no arranca fuera de desarrollo con una configuración insegura (F-06 y F-12,
auditoría OWASP del 9 nov 2026).

Fuera de un desarrollo declarado (`ENVIRONMENT=development`: local, Kind y los tests;
sin ENVIRONMENT o con otro valor cuenta como producción, como en contrasenas.py y
rate_limit.py):

  S1 TESTING=true                         -> no arranca (apaga CSRF y más)
  S2 sin SECRET_KEY                       -> no arranca
  S3 SECRET_KEY de ejemplo                -> no arranca (las de settings, .env.example,
                                             docker y k8s)
  S4 SECRET_KEY de menos de 32 bytes      -> no arranca
  S5 configuración buena                  -> arranca
  S6 en desarrollo, todo lo anterior vale -> arranca
  S7 el mensaje no lleva la clave
  S8 el arranque de verdad (lifespan) lo comprueba
  S9 el algoritmo del JWT es HS256 aunque ALGORITHM diga otro
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.config.arranque_seguro import (
    CLAVES_DE_EJEMPLO,
    comprueba_la_configuracion_de_seguridad,
)

RAIZ = Path(__file__).resolve().parents[3]
CLAVE_BUENA = "k" * 48
PRODUCCION = {"ENVIRONMENT": "production", "SECRET_KEY": CLAVE_BUENA}


@pytest.mark.parametrize("testing", ["true", "TRUE", " true "])
def test_s1_testing_outside_development_refuses_to_start(testing):
    """
    Given: Producción con TESTING=true (apaga el CSRF y deja elegir la red)
    When: Se comprueba la configuración
    Then: RuntimeError: no arranca
    """
    with pytest.raises(RuntimeError, match="TESTING"):
        comprueba_la_configuracion_de_seguridad({**PRODUCCION, "TESTING": testing})


@pytest.mark.parametrize("clave", [None, "", "   "])
def test_s2_a_missing_secret_key_refuses_to_start(clave):
    """
    Given: Producción sin SECRET_KEY (o vacía)
    When: Se comprueba la configuración
    Then: RuntimeError: no arranca
    """
    entorno = {"ENVIRONMENT": "production"}
    if clave is not None:
        entorno["SECRET_KEY"] = clave

    with pytest.raises(RuntimeError, match="SECRET_KEY sin configurar"):
        comprueba_la_configuracion_de_seguridad(entorno)


@pytest.mark.parametrize("clave", sorted(CLAVES_DE_EJEMPLO))
def test_s3_an_example_secret_key_refuses_to_start(clave):
    """
    Given: Producción con una SECRET_KEY de ejemplo de los ficheros del repositorio
    When: Se comprueba la configuración
    Then: RuntimeError: no arranca, aunque sea larga
    """
    with pytest.raises(RuntimeError, match="valor de ejemplo"):
        comprueba_la_configuracion_de_seguridad({"ENVIRONMENT": "production", "SECRET_KEY": clave})


def test_s3_the_known_examples_are_listed():
    """
    Given: Los valores de ejemplo de settings.py, .env.example, docker y k8s
    When: Se mira la lista
    Then: Están todos
    """
    assert {
        "your-secret-key-change-in-production",
        "your-secret-key-change-me",
        "your_secret_key_here",
        "MISSING_SECRET_KEY",
        "your-super-secret-key-min-32-chars",
        "your-local-secret-key",
    } <= CLAVES_DE_EJEMPLO


def test_s3_the_settings_default_is_an_example():
    """
    Given: La SECRET_KEY por defecto de settings.py (sin variable de entorno)
    When: Se mira si es de ejemplo
    Then: Lo es: un despliegue sin la variable no arranca
    """
    codigo = (RAIZ / "src/config/settings.py").read_text(encoding="utf-8")

    assert any(f'"SECRET_KEY", "{clave}"' in codigo for clave in CLAVES_DE_EJEMPLO)


@pytest.mark.parametrize("longitud", [1, 16, 31])
def test_s4_a_short_secret_key_refuses_to_start(longitud):
    """
    Given: Producción con una SECRET_KEY de menos de 32 bytes
    When: Se comprueba la configuración
    Then: RuntimeError: no arranca
    """
    with pytest.raises(RuntimeError, match="32"):
        comprueba_la_configuracion_de_seguridad(
            {"ENVIRONMENT": "production", "SECRET_KEY": "x" * longitud}
        )


def test_s4_the_length_is_in_bytes():
    """
    Given: Una SECRET_KEY de 16 caracteres de 2 bytes (32 bytes en UTF-8)
    When: Se comprueba la configuración
    Then: Arranca: la longitud se mide en bytes, que es lo que usa el HMAC
    """
    comprueba_la_configuracion_de_seguridad({"ENVIRONMENT": "production", "SECRET_KEY": "ñ" * 16})


@pytest.mark.parametrize(
    "entorno",
    [
        PRODUCCION,
        {**PRODUCCION, "TESTING": "false"},
        {"SECRET_KEY": "x" * 32},  # sin ENVIRONMENT: producción, y la clave vale
    ],
)
def test_s5_a_good_configuration_starts(entorno):
    """
    Given: Una configuración de producción buena
    When: Se comprueba
    Then: No lanza nada
    """
    comprueba_la_configuracion_de_seguridad(entorno)


@pytest.mark.parametrize(
    "entorno",
    [
        {"ENVIRONMENT": "development", "TESTING": "true"},
        {"ENVIRONMENT": "Development", "SECRET_KEY": "your-secret-key-change-me"},
        {"ENVIRONMENT": "development", "SECRET_KEY": "corta"},
    ],
)
def test_s6_a_declared_development_starts_with_anything(entorno):
    """
    Given: ENVIRONMENT=development (local, Kind y los tests)
    When: Se comprueba con TESTING, una clave de ejemplo o corta
    Then: Arranca, como hasta ahora
    """
    comprueba_la_configuracion_de_seguridad(entorno)


@pytest.mark.parametrize("environment", [None, "staging", "produccion", "prod"])
def test_s6_an_unknown_environment_counts_as_production(environment):
    """
    Given: ENVIRONMENT ausente o desconocido, con TESTING=true
    When: Se comprueba la configuración
    Then: No arranca: solo un desarrollo declarado se libra
    """
    entorno = {"SECRET_KEY": CLAVE_BUENA, "TESTING": "true"}
    if environment is not None:
        entorno["ENVIRONMENT"] = environment

    with pytest.raises(RuntimeError):
        comprueba_la_configuracion_de_seguridad(entorno)


def test_s7_the_error_does_not_reveal_the_key():
    """
    Given: Producción con una SECRET_KEY corta
    When: Se rechaza
    Then: El mensaje no lleva la clave
    """
    with pytest.raises(RuntimeError) as error:
        comprueba_la_configuracion_de_seguridad(
            {"ENVIRONMENT": "production", "SECRET_KEY": "clave-corta-secreta"}
        )

    assert "clave-corta-secreta" not in str(error.value)


async def test_s8_the_real_startup_checks_it(monkeypatch):
    """
    Given: Producción con TESTING=true en el entorno del proceso
    When: Arranca la app (su lifespan)
    Then: No arranca
    """
    import main

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", CLAVE_BUENA)
    monkeypatch.setattr(main.settings, "SENTRY_DSN", "")

    with pytest.raises(RuntimeError, match="TESTING"):
        async with main.lifespan(main.app):
            pass


def test_s9_the_jwt_algorithm_is_always_hs256():
    """
    Given: ALGORITHM=none en el entorno (o cualquier otro)
    When: Se cargan los settings en un proceso nuevo
    Then: El algoritmo sigue siendo HS256: ya no se lee del entorno
    """
    for algoritmo in ("none", "HS512"):
        salida = subprocess.run(
            [
                sys.executable,
                "-c",
                "from src.config.settings import settings; print(settings.ALGORITHM)",
            ],
            cwd=RAIZ,
            env={**os.environ, "ALGORITHM": algoritmo},
            capture_output=True,
            text=True,
            check=True,
        )
        assert salida.stdout.strip() == "HS256"


@pytest.mark.parametrize("render", ["true", "1", "yes"])
def test_s10_development_on_render_refuses_to_start(render):
    """
    Given: ENVIRONMENT=development con RENDER definida (Render la pone siempre)
    When: Se comprueba la configuración
    Then: No arranca: un desarrollo declarado por error en Render se saltaría todo lo
          demás (revisión de la fase 2)
    """
    with pytest.raises(RuntimeError, match="RENDER"):
        comprueba_la_configuracion_de_seguridad(
            {"ENVIRONMENT": "development", "RENDER": render, "TESTING": "true"}
        )


@pytest.mark.parametrize("entorno", [{"RENDER": ""}, {}])
def test_s10_development_without_render_still_starts(entorno):
    """
    Given: ENVIRONMENT=development sin RENDER (o vacía): local, Kind y los tests
    When: Se comprueba la configuración
    Then: Arranca
    """
    comprueba_la_configuracion_de_seguridad({"ENVIRONMENT": "development", **entorno})


def test_s10_production_on_render_with_a_good_config_starts():
    """
    Given: Producción en Render con una configuración buena
    When: Se comprueba
    Then: Arranca
    """
    comprueba_la_configuracion_de_seguridad({**PRODUCCION, "RENDER": "true"})
