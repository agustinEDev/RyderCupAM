"""
La credencial del dueño de la base no llega al proceso de la API (DB-R3-01, auditoría del
18 nov 2026).

`MIGRATIONS_DATABASE_URL` (el dueño, que puede cambiar la estructura y crear roles) solo
la necesitan las migraciones. Antes, `entrypoint.sh` migraba y arrancaba uvicorn con todo
el entorno: con ejecución de código en la API se tenían permisos de dueño.

entrypoint.sh (se ejecuta el script real, con alembic, python y uvicorn falsos):
  E1 producción con las dos variables  -> alembic la recibe; uvicorn no (sí DATABASE_URL)
  E2 sin la variable de migraciones    -> igual que antes
  E3 desarrollo (--reload)             -> uvicorn tampoco la recibe
  E4 la migración falla                -> no se arranca uvicorn
  E5 configuración insegura            -> ni migra ni arranca
  E6 el resto del entorno              -> llega intacto a uvicorn

Defensa en el arranque de la app (si alguien se salta el entrypoint):
  E7 fuera de desarrollo, la ve        -> la borra y deja un evento HIGH (sin el valor)
  E8 en desarrollo, la ve              -> la borra con un aviso normal, sin evento
  E9 sin la variable (o vacía)         -> no avisa
  E10 el arranque de verdad (lifespan) lo hace
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from src.config.credencial_del_dueno import retira_la_credencial_del_dueno
from src.shared.domain.events.security_events import (
    OwnerCredentialInAppEnvironmentAuditEvent,
    SecuritySeverity,
)

RAIZ = Path(__file__).resolve().parents[3]
DUENO = "postgresql://dueno:clave-del-dueno@db.example:5432/rydercup"
API = "postgresql://rydercup_app:clave-de-la-api@db.example:5432/rydercup"
CLAVE = "k" * 48

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="hace falta bash")


def _falso(carpeta: Path, nombre: str, codigo: int = 0) -> None:
    """Un programa que apunta su entorno y sus argumentos y sale con `codigo`."""
    ruta = carpeta / nombre
    ruta.write_text(
        "#!/bin/sh\n"
        f'env > "$SALIDA/{nombre}.env"\n'
        f'echo "$@" > "$SALIDA/{nombre}.args"\n'
        f"exit {codigo}\n"
    )
    ruta.chmod(0o755)


def _ejecuta_el_entrypoint(
    tmp_path: Path,
    entorno: dict[str, str],
    *,
    alembic: int = 0,
    arranque_seguro: int = 0,
) -> subprocess.CompletedProcess[str]:
    binarios = tmp_path / "bin"
    salida = tmp_path / "salida"
    binarios.mkdir()
    salida.mkdir()
    _falso(binarios, "alembic", alembic)
    _falso(binarios, "python", arranque_seguro)
    _falso(binarios, "uvicorn")
    return subprocess.run(
        ["bash", str(RAIZ / "entrypoint.sh")],
        env={
            "PATH": f"{binarios}:/usr/bin:/bin",
            "SALIDA": str(salida),
            **entorno,
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _entorno_de(tmp_path: Path, programa: str) -> dict[str, str] | None:
    fichero = tmp_path / "salida" / f"{programa}.env"
    if not fichero.exists():
        return None
    pares = (linea.split("=", 1) for linea in fichero.read_text().splitlines() if "=" in linea)
    return dict(pares)


PRODUCCION = {
    "DATABASE_URL": API,
    "MIGRATIONS_DATABASE_URL": DUENO,
    "SECRET_KEY": CLAVE,
    "ENVIRONMENT": "production",
    "PORT": "10000",
}


def test_e1_production_migrations_get_the_owner_and_the_api_does_not(tmp_path):
    """
    Given: Producción con DATABASE_URL (la API) y MIGRATIONS_DATABASE_URL (el dueño)
    When: Se ejecuta entrypoint.sh
    Then: Alembic recibe la del dueño; uvicorn no la recibe y sí la de la API
    """
    resultado = _ejecuta_el_entrypoint(tmp_path, PRODUCCION)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    migraciones = _entorno_de(tmp_path, "alembic")
    api = _entorno_de(tmp_path, "uvicorn")
    assert migraciones is not None and migraciones["MIGRATIONS_DATABASE_URL"] == DUENO
    assert api is not None
    assert "MIGRATIONS_DATABASE_URL" not in api
    assert api["DATABASE_URL"] == API
    # Ni con otro nombre: el valor no aparece en ninguna variable de la API
    assert all("clave-del-dueno" not in valor for valor in api.values())


def test_e2_without_the_migrations_variable_nothing_changes(tmp_path):
    """
    Given: Kind o local: solo DATABASE_URL
    When: Se ejecuta entrypoint.sh
    Then: Migra y arranca la API como antes
    """
    entorno = {k: v for k, v in PRODUCCION.items() if k != "MIGRATIONS_DATABASE_URL"}

    resultado = _ejecuta_el_entrypoint(tmp_path, entorno)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert _entorno_de(tmp_path, "alembic") is not None
    api = _entorno_de(tmp_path, "uvicorn")
    assert api is not None and api["DATABASE_URL"] == API


def test_e3_development_with_reload_does_not_get_it_either(tmp_path):
    """
    Given: ENVIRONMENT=development (uvicorn con --reload) y las dos variables
    When: Se ejecuta entrypoint.sh
    Then: uvicorn arranca con --reload y sin la variable del dueño
    """
    resultado = _ejecuta_el_entrypoint(tmp_path, {**PRODUCCION, "ENVIRONMENT": "development"})

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    api = _entorno_de(tmp_path, "uvicorn")
    assert api is not None and "MIGRATIONS_DATABASE_URL" not in api
    assert "--reload" in (tmp_path / "salida" / "uvicorn.args").read_text()


def test_e4_a_failed_migration_does_not_start_the_api(tmp_path):
    """
    Given: La migración falla
    When: Se ejecuta entrypoint.sh
    Then: Sale con error y uvicorn no arranca
    """
    resultado = _ejecuta_el_entrypoint(tmp_path, PRODUCCION, alembic=1)

    assert resultado.returncode != 0
    assert _entorno_de(tmp_path, "uvicorn") is None


def test_e5_an_insecure_configuration_neither_migrates_nor_starts(tmp_path):
    """
    Given: La comprobación de seguridad falla
    When: Se ejecuta entrypoint.sh
    Then: Ni migra ni arranca
    """
    resultado = _ejecuta_el_entrypoint(tmp_path, PRODUCCION, arranque_seguro=1)

    assert resultado.returncode != 0
    assert _entorno_de(tmp_path, "alembic") is None
    assert _entorno_de(tmp_path, "uvicorn") is None


def test_e6_the_rest_of_the_environment_reaches_the_api(tmp_path):
    """
    Given: Producción con más variables
    When: Se ejecuta entrypoint.sh
    Then: Todas menos la del dueño llegan intactas a uvicorn, y el puerto es el de PORT
    """
    entorno = {**PRODUCCION, "SENTRY_DSN": "https://k@o.ingest.example/1", "RENDER": "true"}

    resultado = _ejecuta_el_entrypoint(tmp_path, entorno)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    api = _entorno_de(tmp_path, "uvicorn")
    assert api is not None
    for nombre, valor in entorno.items():
        if nombre != "MIGRATIONS_DATABASE_URL":
            assert api[nombre] == valor, nombre
    assert "--port 10000" in (tmp_path / "salida" / "uvicorn.args").read_text()


# --- Defensa en el arranque de la app ---------------------------------------------------


def test_e7_outside_development_it_is_removed_with_a_high_event():
    """
    Given: Fuera de desarrollo, la API ve MIGRATIONS_DATABASE_URL en su entorno
    When: Se retira
    Then: Ya no está, y se avisa una vez (el aviso crea el evento HIGH)
    """
    entorno = {"MIGRATIONS_DATABASE_URL": DUENO, "DATABASE_URL": API}
    avisos = []

    retirada = retira_la_credencial_del_dueno(
        entorno, en_desarrollo=False, avisa=lambda: avisos.append(1)
    )

    assert retirada is True
    assert entorno == {"DATABASE_URL": API}
    assert avisos == [1]


def test_e7_the_event_is_high_and_does_not_carry_the_value():
    """
    Given: El evento que se registra al retirarla
    When: Se crea y se serializa
    Then: Es HIGH, nombra la variable y no lleva su valor
    """
    evento = OwnerCredentialInAppEnvironmentAuditEvent.al_arrancar("MIGRATIONS_DATABASE_URL")

    assert evento.severity is SecuritySeverity.HIGH
    # Algo salió mal (alguien se saltó el entrypoint): el log lo escribe como WARNING
    assert evento.is_failure is True
    datos = evento.to_dict()
    assert datos["variable"] == "MIGRATIONS_DATABASE_URL"
    assert "clave-del-dueno" not in str(datos)
    assert "MIGRATIONS_DATABASE_URL" in (evento.resumen("Anonymous") or "")


def test_e8_in_development_it_is_removed_without_an_event(caplog):
    """
    Given: En desarrollo (el .env local puede tenerla y load_dotenv la mete)
    When: Se retira
    Then: Ya no está, con un aviso normal en el log y sin evento de seguridad
    """
    entorno = {"MIGRATIONS_DATABASE_URL": DUENO}
    avisos = []

    with caplog.at_level(logging.WARNING):
        retirada = retira_la_credencial_del_dueno(
            entorno, en_desarrollo=True, avisa=lambda: avisos.append(1)
        )

    assert retirada is True
    assert entorno == {}
    assert avisos == []
    assert "MIGRATIONS_DATABASE_URL" in caplog.text
    assert "clave-del-dueno" not in caplog.text


@pytest.mark.parametrize("entorno", [{}, {"MIGRATIONS_DATABASE_URL": ""}, {"X": "1"}])
def test_e9_without_the_variable_nothing_is_reported(entorno):
    """
    Given: Sin la variable, o vacía
    When: Se retira
    Then: No hay aviso, y una vacía tampoco se queda
    """
    avisos = []

    retirada = retira_la_credencial_del_dueno(
        entorno, en_desarrollo=False, avisa=lambda: avisos.append(1)
    )

    assert retirada is False
    assert avisos == []
    assert "MIGRATIONS_DATABASE_URL" not in entorno


@pytest.mark.asyncio
async def test_e10_the_real_startup_removes_it_and_reports_it(monkeypatch):
    """
    Given: Producción con la variable en el entorno del proceso (y TESTING=true para que
           el arranque se pare justo después, en la comprobación de seguridad)
    When: Arranca la app (su lifespan)
    Then: La variable ya no está en os.environ y se registró el evento HIGH
    """
    import main
    from src.config import credencial_del_dueno

    registrados = []

    class _Registro:
        def log_security_event(self, evento):
            registrados.append(evento)

    monkeypatch.setattr(credencial_del_dueno, "get_security_logger", _Registro)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", CLAVE)
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", DUENO)
    monkeypatch.setattr(main.settings, "SENTRY_DSN", "")

    with pytest.raises(RuntimeError, match="TESTING"):
        async with main.lifespan(main.app):
            pass

    assert "MIGRATIONS_DATABASE_URL" not in os.environ
    assert [type(e) for e in registrados] == [OwnerCredentialInAppEnvironmentAuditEvent]


def test_e7_a_failing_notice_does_not_stop_the_startup(caplog):
    """
    Given: Fuera de desarrollo con la variable, y el aviso falla (log de seguridad roto)
    When: Se retira
    Then: Se retira igual, no lanza (la API arranca, decisión del 18 nov) y queda en el log
    """
    entorno = {"MIGRATIONS_DATABASE_URL": DUENO}

    def avisa_roto():
        raise OSError("sin permiso para escribir el log")

    with caplog.at_level(logging.ERROR):
        retirada = retira_la_credencial_del_dueno(entorno, en_desarrollo=False, avisa=avisa_roto)

    assert retirada is True
    assert entorno == {}
    assert "MIGRATIONS_DATABASE_URL" in caplog.text
    assert "clave-del-dueno" not in caplog.text


@pytest.mark.asyncio
async def test_e11_a_failed_startup_drains_the_security_log(monkeypatch):
    """
    Given: El arranque falla en la comprobación de seguridad justo después del aviso
    When: Arranca la app (su lifespan)
    Then: El log de seguridad se vacía antes de salir: escribe desde un hilo y su
          vaciado normal está tras el `yield`, al que no se llega (CodeRabbit)
    """
    import main
    from src.shared.infrastructure.logging import security_logger

    vaciados = []

    def para(registro):
        vaciados.append(registro)

    monkeypatch.setattr(security_logger.SecurityLogger, "para", para)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", CLAVE)
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", DUENO)
    monkeypatch.setattr(main.settings, "SENTRY_DSN", "")

    with pytest.raises(RuntimeError, match="TESTING"):
        async with main.lifespan(main.app):
            pass

    assert len(vaciados) == 1
