"""
Qué puede importar cada capa: lista de PERMITIDOS, no de prohibidos (9 nov 2026).

La auditoría de arquitectura del 9 nov encontró bcrypt y `os` en el dominio y
SQLAlchemy en un caso de uso. `lint-imports` no los vio porque sus contratos
prohíben una lista fija de frameworks: lo que no está en la lista, pasa. Aquí es
al revés: lo que no está permitido, falla. Añadir una librería a estas listas es
una decisión de arquitectura, no un trámite para que pase el CI.

Y todo paquete de un módulo (o de `shared`) tiene que ser una de las tres capas:
`src/shared/security` vivía fuera de ellas y por eso ningún contrato lo miraba.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src"

CAPAS = ("domain", "application", "infrastructure")

# Librería estándar sin efectos sobre el mundo exterior: datos, tiempo, texto,
# números y criptografía pura. Fuera, a propósito: os, sys, subprocess, socket,
# asyncio, threading, pathlib, io, http, urllib, sqlite3, pickle...
ESTANDAR_PURA = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "hashlib",
        "hmac",
        "ipaddress",
        "itertools",
        "math",
        "operator",
        "re",
        "secrets",
        "statistics",
        "string",
        "types",
        "typing",
        "unicodedata",
        "uuid",
        "zoneinfo",
        # Los avisos de diagnóstico se permiten en el dominio (decidido el 9 nov):
        # una zona horaria o una sesión desconocidas se avisan donde se detectan
        "logging",
    }
)

PERMITIDOS = {
    # email_validator: la validación de formato del value object Email. Es pura
    # (sin red: se llama con check_deliverability=False) y no es un framework
    "domain": ESTANDAR_PURA | {"email_validator"},
    # Pydantic en los DTOs es una decisión del proyecto (CLAUDE.md: "DTOs siempre
    # Pydantic"); geojson_pydantic son modelos Pydantic del estándar GeoJSON.
    # Lo concurrente (asyncio, weakref, contextvars, concurrent) lo usan los
    # casos de uso para coordinar, sin tocar la red ni el disco
    "application": ESTANDAR_PURA
    | {
        "pydantic",
        "geojson_pydantic",
        "asyncio",
        "weakref",
        "contextvars",
        "concurrent",
        "html",
    },
}


def _ficheros_de(capa: str) -> list[Path]:
    raices = [p / capa for p in (SRC / "modules").iterdir() if (p / capa).is_dir()]
    raices.append(SRC / "shared" / capa)
    return sorted(f for raiz in raices if raiz.is_dir() for f in raiz.rglob("*.py"))


def _imports_externos(fichero: Path) -> set[tuple[str, int]]:
    """(paquete de primer nivel, línea) de cada import que no es de `src`."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    encontrados: set[tuple[str, int]] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:  # import relativo: es del propio paquete
                continue
            nombres = [nodo.module or ""]
        else:
            continue
        for nombre in nombres:
            raiz = nombre.split(".")[0]
            if raiz != "src":
                encontrados.add((raiz, nodo.lineno))
    return encontrados


def importa_algo_no_permitido(capa: str, fichero: Path) -> list[str]:
    """Las infracciones de un fichero, como `ruta:línea paquete`."""
    return [
        f"{fichero.relative_to(SRC.parent)}:{linea} importa {paquete}"
        for paquete, linea in sorted(_imports_externos(fichero))
        if paquete not in PERMITIDOS[capa]
    ]


@pytest.mark.parametrize("capa", ["domain", "application"])
def test_la_capa_solo_importa_lo_permitido(capa: str) -> None:
    """
    Given: todos los ficheros de la capa en todos los módulos y en shared
    When: se leen sus imports (también los que están dentro de una función)
    Then: ninguno trae un paquete que no esté en su lista de permitidos
    """
    ficheros = _ficheros_de(capa)
    assert ficheros, f"no se encontró ningún fichero de {capa}: la ruta está mal"

    infracciones = [i for f in ficheros for i in importa_algo_no_permitido(capa, f)]

    assert infracciones == [], (
        f"La capa {capa} importa fuera de su lista de permitidos "
        "(tests/unit/architecture/test_imports_permitidos_por_capa.py):\n" + "\n".join(infracciones)
    )


def test_todo_paquete_de_un_modulo_es_una_capa() -> None:
    """
    Given: los módulos de src/modules y src/shared
    When: se miran sus subpaquetes de primer nivel
    Then: todos son domain, application o infrastructure, así que todos caen
          bajo algún contrato de .importlinter
    """
    contenedores = [p for p in (SRC / "modules").iterdir() if p.is_dir()]
    contenedores.append(SRC / "shared")

    fuera = [
        str(sub.relative_to(SRC.parent))
        for contenedor in contenedores
        for sub in sorted(contenedor.iterdir())
        if sub.is_dir() and sub.name != "__pycache__" and sub.name not in CAPAS
    ]

    assert fuera == [], "Paquetes fuera de las tres capas:\n" + "\n".join(fuera)


def test_el_detector_ve_un_import_escondido_en_una_funcion(tmp_path: Path) -> None:
    """
    Given: un fichero de dominio que importa bcrypt dentro de una función
    When: se comprueba
    Then: sale la infracción (un import perezoso no se libra)
    """
    codigo = "def f():\n    import bcrypt\n    return bcrypt\n"
    falso = tmp_path / "sonda.py"
    falso.write_text(codigo, encoding="utf-8")

    encontrados = _imports_externos(falso)

    assert ("bcrypt", 2) in encontrados
    assert "bcrypt" not in PERMITIDOS["domain"]
