"""El adaptador de bcrypt del puerto PasswordHasher (auditoría del 9 nov 2026, B2)."""

import bcrypt
import pytest

from src.config.contrasenas import rondas_de_bcrypt
from src.modules.user.domain.services import password_hasher
from src.modules.user.infrastructure.security.bcrypt_password_hasher import (
    BcryptPasswordHasher,
)


def test_hashes_with_the_given_cost_and_checks_it():
    """
    Given: el adaptador con 12 rondas, las de producción
    When: se calcula un hash y se comprueba
    Then: el hash es bcrypt de coste 12 y solo casa con su contraseña
    """
    hasher = BcryptPasswordHasher(rounds=12)

    hashed = hasher.hash("V@l1dP@ss123!")

    assert hashed.startswith("$2b$12$")
    assert hasher.matches("V@l1dP@ss123!", hashed) is True
    assert hasher.matches("V@l1dP@ss124!", hashed) is False


def test_cuts_to_72_bytes_like_bcrypt_4_did():
    """
    Given: una contraseña de más de 72 bytes (bcrypt 5 lanza ValueError con ella)
    When: se calcula el hash y se comprueba
    Then: se recorta a 72 bytes, como hacía bcrypt 4, y los hashes guardados
          con bcrypt 4 siguen valiendo
    """
    hasher = BcryptPasswordHasher(rounds=4)
    larga = "Ñ" * 40 + "a1!A"  # 84 bytes en UTF-8

    guardado_con_bcrypt_4 = bcrypt.hashpw(larga.encode()[:72], bcrypt.gensalt(4)).decode()

    assert hasher.matches(larga, hasher.hash(larga)) is True
    assert hasher.matches(larga, guardado_con_bcrypt_4) is True


@pytest.mark.parametrize("rondas", [3, 32])
def test_rejects_a_cost_bcrypt_does_not_accept(rondas):
    """
    Given: un coste fuera del rango de bcrypt (4 a 31)
    When: se crea el adaptador
    Then: falla al crearlo, no al primer login
    """
    with pytest.raises(ValueError):
        BcryptPasswordHasher(rounds=rondas)


def test_production_cost_is_12_when_nothing_is_configured():
    """
    Given: un entorno sin BCRYPT_ROUNDS (producción)
    When: se leen las rondas
    Then: son 12
    """
    assert rondas_de_bcrypt({}) == 12
    assert rondas_de_bcrypt({"ENVIRONMENT": "development", "BCRYPT_ROUNDS": "4"}) == 4


def test_the_testing_flag_no_longer_lowers_the_cost():
    """
    Given: TESTING=true en el entorno, sin BCRYPT_ROUNDS
    When: se leen las rondas
    Then: siguen siendo 12: un TESTING olvidado en Render ya no abarata los
          hashes (F-06 de la auditoría de seguridad)
    """
    assert rondas_de_bcrypt({"TESTING": "true"}) == 12


def test_the_composition_root_installs_bcrypt():
    """
    Given: la app cargada (los tests importan main)
    When: se mira el hasher instalado
    Then: es el de bcrypt
    """
    import src.config.dependencies  # noqa: F401 - la composition root lo instala

    assert isinstance(password_hasher.hasher_de_contrasenas(), BcryptPasswordHasher)


@pytest.mark.parametrize("rondas", ["4", "11"])
def test_production_refuses_fewer_than_12_rounds(rondas):
    """
    Given: ENVIRONMENT=production con BCRYPT_ROUNDS por debajo de 12
    When: se leen las rondas al arrancar
    Then: la app no arranca: un 4 puesto por error en Render abarataría los
          hashes sin avisar (revisión de la PR, F-06)
    """
    with pytest.raises(RuntimeError, match="BCRYPT_ROUNDS"):
        rondas_de_bcrypt({"ENVIRONMENT": "production", "BCRYPT_ROUNDS": rondas})
    with pytest.raises(RuntimeError, match="BCRYPT_ROUNDS"):
        rondas_de_bcrypt({"ENVIRONMENT": "Production", "BCRYPT_ROUNDS": rondas})


def test_production_accepts_12_or_more():
    """
    Given: ENVIRONMENT=production con 12 o 13 rondas
    When: se leen
    Then: valen
    """
    assert rondas_de_bcrypt({"ENVIRONMENT": "production", "BCRYPT_ROUNDS": "13"}) == 13
    assert rondas_de_bcrypt({"ENVIRONMENT": "production"}) == 12


@pytest.mark.parametrize("valor", ["", "doce", "  "])
def test_an_unusable_value_falls_back_to_12(valor):
    """
    Given: BCRYPT_ROUNDS vacía o con una errata
    When: se leen las rondas
    Then: se usan las 12 de producción (vaciar la variable en Render es la forma
          natural de quitarla), no un error al arrancar
    """
    assert rondas_de_bcrypt({"BCRYPT_ROUNDS": valor}) == 12


@pytest.mark.parametrize("entorno", [None, "prod", "production ", "staging"])
def test_low_rounds_are_refused_unless_the_environment_says_development(entorno):
    """
    Given: BCRYPT_ROUNDS=4 con ENVIRONMENT ausente, mal escrito o desconocido
    When: se leen las rondas
    Then: la app no arranca: solo un desarrollo declarado admite menos de 12
          (como rate_limit, un entorno desconocido cuenta como producción)
    """
    valores = {"BCRYPT_ROUNDS": "4"}
    if entorno is not None:
        valores["ENVIRONMENT"] = entorno
    with pytest.raises(RuntimeError, match="BCRYPT_ROUNDS"):
        rondas_de_bcrypt(valores)


def test_development_admits_low_rounds():
    """
    Given: ENVIRONMENT=development (local, Kind y la configuración de los tests)
    When: BCRYPT_ROUNDS=4
    Then: valen 4
    """
    assert rondas_de_bcrypt({"ENVIRONMENT": "development", "BCRYPT_ROUNDS": "4"}) == 4


@pytest.mark.parametrize("valor", ["0", "3", "16", "40"])
def test_an_out_of_range_cost_falls_back_to_12(valor):
    """
    Given: un coste que bcrypt no acepta (menos de 4) o que tumbaría el login por
           CPU (más de 15: cada hash tardaría segundos)
    When: se leen las rondas
    Then: se usan las 12, igual que con una errata, sin tumbar el arranque
    """
    assert rondas_de_bcrypt({"ENVIRONMENT": "development", "BCRYPT_ROUNDS": valor}) == 12
