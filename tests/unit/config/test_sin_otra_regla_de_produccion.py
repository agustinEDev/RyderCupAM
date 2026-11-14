"""
Nadie decide «producción» con otra regla que la del arranque (auditoría de la
fase 6, B-09).

La regla es `en_desarrollo_declarado`: solo ENVIRONMENT=development es
desarrollo. Comparar ENVIRONMENT con "production" daba lo contrario con un valor
mal escrito o ausente: cookies sin Secure, CORS abierto a localhost, el
middleware que imprime cabeceras montado o el correo de pruebas en producción.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
OTRA_REGLA = re.compile(r"""[!=]=\s*["']production["']""")


def test_ningun_fichero_compara_environment_con_production():
    ficheros = [RAIZ / "main.py", *sorted((RAIZ / "src").rglob("*.py"))]
    usos = [
        f"{f.relative_to(RAIZ)}:{n}"
        for f in ficheros
        for n, linea in enumerate(f.read_text().splitlines(), 1)
        if OTRA_REGLA.search(linea)
    ]

    assert usos == []


def test_el_escaner_ve_las_dos_formas():
    assert OTRA_REGLA.search('if env == "production":')
    assert OTRA_REGLA.search("if ENV != 'production':")
    assert not OTRA_REGLA.search('SENTRY_ENVIRONMENT = "production"')
