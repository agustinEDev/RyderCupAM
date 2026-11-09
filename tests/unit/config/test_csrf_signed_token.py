"""
El token CSRF va firmado y atado al usuario (BE #724).

Era `secrets.token_urlsafe(32)` a secas, y el middleware solo comparaba cabecera
y cookie: quien pudiera escribir una cookie en `.rydercupfriends.com` (un
subdominio de otro, uno tomado, HTTP en claro a cualquier subdominio: «cookie
tossing») elegía los dos valores. Ahora el token es `aleatorio.emitido.firma`, con
la firma HMAC-SHA256 del usuario, el aleatorio y la hora de emisión, y una clave
DERIVADA de SECRET_KEY con su propia etiqueta (Agustín, 4 nov: sin variable nueva que
configurar). Desde F-19 (auditoría OWASP del 9 nov 2026) caduca: más viejo que la vida
del refresh token (7 días) más una hora de margen, no vale.

  #  caso                                              | ¿vale para el usuario A?
  ---|------------------------------------------------|---------------------------
  13 recién emitido para A                           | sí; dos seguidos, distintos
  14 emitido para B                                  | no
  15 la firma tocada (un carácter)                   | no
  16 el aleatorio tocado                             | no
  17 formato antiguo, sin firma                      | no
  17b formato de BE #724, sin hora (`aleatorio.firma`)| no: el front refresca y repite
  21 de hace 8 días                                  | no
  22 de hace 7 días y media hora (dentro del margen) | sí
  23 la hora tocada (más reciente)                    | no
  24 con hora del futuro, más allá del margen        | no
  25 hora que no es un número                        | no
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


def test_generate_csrf_token_for_user_belongs_to_that_user_and_is_unique():
    """
    Given: Un usuario
    When: Se emiten dos tokens para él
    Then: Los dos le pertenecen y son distintos
    """
    uno = generate_csrf_token(A)
    dos = generate_csrf_token(A)

    assert csrf_token_belongs_to(uno, A)
    assert csrf_token_belongs_to(dos, A)
    assert uno != dos
    aleatorio, emitido, firma = uno.split(".")
    assert len(aleatorio) >= 43  # 256 bits en base64 url
    assert emitido.isdigit()
    assert firma


def test_csrf_token_belongs_to_other_user_is_false():
    """
    Given: Un token emitido para A
    When: Se comprueba contra B
    Then: No le pertenece
    """
    assert not csrf_token_belongs_to(generate_csrf_token(B), A)


def _cambia_un_caracter(texto: str) -> str:
    """Ayudante del test: cambia un caracter."""
    return texto[:-1] + ("A" if texto[-1] != "A" else "B")


def test_csrf_token_with_tampered_signature_is_rejected():
    """
    Given: Un token de A con la firma modificada
    When: Se comprueba contra A
    Then: No le pertenece
    """
    aleatorio, emitido, firma = generate_csrf_token(A).split(".")

    assert not csrf_token_belongs_to(f"{aleatorio}.{emitido}.{_cambia_un_caracter(firma)}", A)


def test_csrf_token_with_tampered_random_is_rejected():
    """
    Given: Un token de A con la parte aleatoria modificada
    When: Se comprueba contra A
    Then: No le pertenece
    """
    aleatorio, emitido, firma = generate_csrf_token(A).split(".")

    assert not csrf_token_belongs_to(f"{_cambia_un_caracter(aleatorio)}.{emitido}.{firma}", A)


def test_csrf_token_in_legacy_unsigned_format_is_rejected():
    """
    Given: Un token del formato antiguo, sin firma
    When: Se comprueba contra A
    Then: No le pertenece
    """
    import secrets

    assert not csrf_token_belongs_to(secrets.token_urlsafe(32), A)


AHORA = 1_800_000_000.0  # una hora fija: los tests no dependen del reloj
DIA = 24 * 60 * 60


def _firma_legacy(user_id: str, aleatorio: str) -> str:
    """La firma del formato de BE #724, sin hora: HMAC(usuario!aleatorio)."""
    mensaje = f"{user_id}!{aleatorio}".encode()
    return csrf_config._en_base64(hmac.new(csrf_config._clave(), mensaje, hashlib.sha256).digest())


def test_csrf_token_signed_without_issue_time_is_rejected():
    """
    Given: Un token del formato de BE #724 (`aleatorio.firma`), bien firmado para A
    When: Se comprueba contra A
    Then: No vale: no se sabe cuándo se emitió. El front, ante el 403 CSRF, refresca
          (que emite uno nuevo) y repite la petición una vez (hotfix FE 2.63.1)
    """
    import secrets

    aleatorio = secrets.token_urlsafe(32)

    assert not csrf_token_belongs_to(f"{aleatorio}.{_firma_legacy(A, aleatorio)}", A)


def test_csrf_token_issued_8_days_ago_is_rejected():
    """
    Given: Un token de A emitido hace 8 días
    When: Se comprueba contra A ahora
    Then: No vale: ninguna sesión vive tanto sin refrescar, que emite otro
    """
    token = generate_csrf_token(A, ahora=AHORA - 8 * DIA)

    assert not csrf_token_belongs_to(token, A, ahora=AHORA)


def test_csrf_token_just_inside_its_lifetime_is_accepted():
    """
    Given: Un token de A emitido hace 7 días y media hora (vida del refresh + margen)
    When: Se comprueba contra A ahora
    Then: Vale
    """
    token = generate_csrf_token(A, ahora=AHORA - 7 * DIA - 30 * 60)

    assert csrf_token_belongs_to(token, A, ahora=AHORA)


def test_csrf_token_fresh_is_accepted_with_the_real_clock():
    """
    Given: Un token de A recién emitido (reloj de verdad)
    When: Se comprueba contra A
    Then: Vale
    """
    assert csrf_token_belongs_to(generate_csrf_token(A), A)


def test_csrf_lifetime_is_the_refresh_lifetime_plus_one_hour():
    """
    Given: La configuración
    When: Se mira la vida del token CSRF
    Then: La del refresh token (REFRESH_TOKEN_EXPIRE_DAYS) más una hora
    """
    dias = csrf_config.settings.REFRESH_TOKEN_EXPIRE_DAYS

    assert csrf_config.vida_del_token_csrf() == dias * DIA + 60 * 60


def test_csrf_token_with_tampered_issue_time_is_rejected():
    """
    Given: Un token de A de hace 8 días con la hora cambiada a ahora
    When: Se comprueba contra A
    Then: No vale: la hora va firmada
    """
    aleatorio, _, firma = generate_csrf_token(A, ahora=AHORA - 8 * DIA).split(".")

    assert not csrf_token_belongs_to(f"{aleatorio}.{int(AHORA)}.{firma}", A, ahora=AHORA)


def test_csrf_token_from_the_future_is_rejected():
    """
    Given: Un token de A con hora de dentro de dos horas (más que el margen)
    When: Se comprueba contra A
    Then: No vale
    """
    token = generate_csrf_token(A, ahora=AHORA + 2 * 60 * 60)

    assert not csrf_token_belongs_to(token, A, ahora=AHORA)


_HORA = str(int(AHORA))
# Lo que int() aceptaría como la hora de AHORA, pero no son sus cifras ASCII
_ARABIGAS = _HORA.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


@pytest.mark.parametrize(
    "emitido",
    ["-1", "1e9", f" {_HORA}", f"{_HORA} ", "1_800_000_000", _ARABIGAS, "0" * 30 + _HORA],
)
def test_csrf_token_with_a_non_canonical_issue_time_is_rejected(emitido):
    """
    Given: Un token BIEN FIRMADO cuya hora no son solo cifras ASCII (int() aceptaría
           espacios, guiones bajos, cifras arábigas o ceros sin fin)
    When: Se comprueba contra A, a la hora que diría
    Then: No vale y no lanza: el servidor solo emite cifras ASCII
    """
    aleatorio = "x" * 43
    token = f"{aleatorio}.{emitido}.{csrf_config._firma(A, aleatorio, emitido)}"

    assert not csrf_token_belongs_to(token, A, ahora=AHORA)


def test_csrf_token_with_the_canonical_issue_time_is_accepted():
    """
    Given: El mismo token, con la hora en cifras ASCII y bien firmado
    When: Se comprueba contra A a esa hora
    Then: Vale (el test anterior no rechaza por la firma)
    """
    aleatorio = "x" * 43
    token = f"{aleatorio}.{_HORA}.{csrf_config._firma(A, aleatorio, _HORA)}"

    assert csrf_token_belongs_to(token, A, ahora=AHORA)


@pytest.mark.parametrize(
    "token",
    ["", ".", "..", "a.b.c", "a.b.c.d", "solo-aleatorio.", ".solo-firma", "ñandú.ñ", "a..c"],
)
def test_csrf_token_with_malformed_shape_is_rejected(token):
    """
    Given: Un token mal formado
    When: Se comprueba contra A
    Then: No le pertenece y no lanza
    """
    assert not csrf_token_belongs_to(token, A)


def test_csrf_key_is_derived_from_secret_key(monkeypatch):
    """
    Given: Dos SECRET_KEY distintas
    When: Se firma el mismo usuario y aleatorio
    Then: La firma cambia: la clave sale de SECRET_KEY
    """
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


def test_csrf_signature_is_hmac_sha256_of_user_random_and_issue_time():
    """
    Given: Un usuario y un token emitido
    When: Se recalcula HMAC-SHA256(clave, usuario!aleatorio!emitido)
    Then: Coincide con la firma del token
    """
    aleatorio, emitido, firma = generate_csrf_token(A).split(".")
    mensaje = f"{A}!{aleatorio}!{emitido}".encode()
    esperada = hmac.new(csrf_config._clave(), mensaje, hashlib.sha256)

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
def test_es_ruta_exenta_matches_exact_paths_only(ruta, exenta):
    """
    Given: Una ruta
    When: Se pregunta si está exenta
    Then: Solo lo está si coincide exacta, sin contar la barra final
    """
    assert es_ruta_exenta(ruta) is exenta
