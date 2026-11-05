"""
El token CSRF va firmado y atado al usuario (BE #724).

Era `secrets.token_urlsafe(32)` a secas, y el middleware solo comparaba cabecera
y cookie: quien pudiera escribir una cookie en `.rydercupfriends.com` (un
subdominio de otro, uno tomado, HTTP en claro a cualquier subdominio: «cookie
tossing») elegía los dos valores. Ahora el token es `aleatorio.firma`, con la
firma HMAC-SHA256 del usuario y el aleatorio, y una clave DERIVADA de SECRET_KEY
con su propia etiqueta (Agustín, 4 nov: sin variable nueva que configurar).

  #  caso                                              | ¿vale para el usuario A?
  ---|------------------------------------------------|---------------------------
  13 recién emitido para A                           | sí; dos seguidos, distintos
  14 emitido para B                                  | no
  15 la firma tocada (un carácter)                   | no
  16 el aleatorio tocado                             | no
  17 formato antiguo, sin firma                      | no
  18 vacío, con dos puntos, sin firma tras el punto  | no
  19 la clave                                        | ni es SECRET_KEY ni sale igual con otra
  20 rutas exentas                                   | SOLO exactas: con «/» detrás,
                                                       `/google/link` colgaría de `/google`
                                                       (las subrutas de `/docs` son GET:
                                                       las exime el método)
"""

import hashlib
import hmac

import pytest

from src.config import csrf_config
from src.config.csrf_config import (
    csrf_token_belongs_to,
    es_ruta_exenta,
    generate_csrf_token,
)

A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"


def test_13_recien_emitido_vale_para_su_usuario_y_no_se_repite():
    """Caso 13 de la tabla de la cabecera: recien emitido vale para su usuario y no se repite."""
    uno = generate_csrf_token(A)
    dos = generate_csrf_token(A)

    assert csrf_token_belongs_to(uno, A)
    assert csrf_token_belongs_to(dos, A)
    assert uno != dos
    aleatorio, firma = uno.split(".")
    assert len(aleatorio) >= 43  # 256 bits en base64 url
    assert firma


def test_14_el_de_otro_usuario_no_vale():
    """Caso 14 de la tabla de la cabecera: el de otro usuario no vale."""
    assert not csrf_token_belongs_to(generate_csrf_token(B), A)


def _cambia_un_caracter(texto: str) -> str:
    """Ayudante del test: cambia un caracter."""
    return texto[:-1] + ("A" if texto[-1] != "A" else "B")


def test_15_con_la_firma_tocada_no_vale():
    """Caso 15 de la tabla de la cabecera: con la firma tocada no vale."""
    aleatorio, firma = generate_csrf_token(A).split(".")

    assert not csrf_token_belongs_to(f"{aleatorio}.{_cambia_un_caracter(firma)}", A)


def test_16_con_el_aleatorio_tocado_no_vale():
    """Caso 16 de la tabla de la cabecera: con el aleatorio tocado no vale."""
    aleatorio, firma = generate_csrf_token(A).split(".")

    assert not csrf_token_belongs_to(f"{_cambia_un_caracter(aleatorio)}.{firma}", A)


def test_17_el_formato_antiguo_sin_firma_no_vale():
    """Caso 17 de la tabla de la cabecera: el formato antiguo sin firma no vale."""
    import secrets

    assert not csrf_token_belongs_to(secrets.token_urlsafe(32), A)


@pytest.mark.parametrize("token", ["", ".", "a.b.c", "solo-aleatorio.", ".solo-firma", "ñandú.ñ"])
def test_18_formatos_raros_no_valen(token):
    """Caso 18 de la tabla de la cabecera: formatos raros no valen."""
    assert not csrf_token_belongs_to(token, A)


def test_19_la_clave_es_derivada_y_depende_de_secret_key(monkeypatch):
    """Caso 19 de la tabla de la cabecera: la clave es derivada y depende de secret key."""
    original = csrf_config._clave()
    assert original != csrf_config.settings.SECRET_KEY.encode()
    assert len(original) == hashlib.sha256().digest_size

    token = generate_csrf_token(A)
    monkeypatch.setattr(csrf_config.settings, "SECRET_KEY", "otra-clave-de-prueba")
    csrf_config._clave.cache_clear()
    try:
        assert csrf_config._clave() != original
        assert not csrf_token_belongs_to(token, A)
    finally:
        monkeypatch.undo()
        csrf_config._clave.cache_clear()


def test_19b_la_firma_es_hmac_sha256_del_usuario_y_el_aleatorio():
    """Caso 19b de la tabla de la cabecera: la firma es hmac sha256 del usuario y el aleatorio."""
    aleatorio, firma = generate_csrf_token(A).split(".")
    esperada = hmac.new(csrf_config._clave(), f"{A}!{aleatorio}".encode(), hashlib.sha256)

    assert firma == csrf_config._en_base64(esperada.digest())


@pytest.mark.parametrize(
    ("ruta", "exenta"),
    [
        ("/api/v1/auth/login", True),
        ("/api/v1/auth/google", True),
        ("/health", True),
        ("/docs/oauth2-redirect", False),
        # Un parecido por delante ya no se cuela
        ("/api/v1/auth/login-x", False),
        ("/healthz", False),
        # Las de Google con sesión: vincular y desvincular SÍ se validan
        ("/api/v1/auth/google/link", False),
        ("/api/v1/auth/google/unlink", False),
        ("/api/v1/users/profile", False),
        # Con la barra final, lo mismo que sin ella (code-review)
        ("/api/v1/auth/login/", True),
        ("/api/v1/auth/google/link/", False),
        ("/", False),
    ],
)
def test_20_las_rutas_exentas_se_comparan_exactas(ruta, exenta):
    """Caso 20 de la tabla de la cabecera: las rutas exentas se comparan exactas."""
    assert es_ruta_exenta(ruta) is exenta
