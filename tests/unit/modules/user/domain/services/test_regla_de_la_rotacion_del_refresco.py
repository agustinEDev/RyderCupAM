"""
La regla de la rotación del refresh token, en el dominio (F-02, tras la revisión).

  #   token presentado                                  | paso
  ----|--------------------------------------------------|---------------
  D1  vigente                                            | ROTA (A1)
  D2  sustituido dentro de 60 s (usado o no el sustituto)| SOLO_ACCESO (A2)
  D3  fuera del margen, sustituto sin usar, < 1 hora     | REANUDA (A3)
  D4  fuera del margen, sustituto sin usar, > 1 hora     | ROBO
  D5  fuera del margen, sustituto ya usado               | ROBO (A4)
  D6  anulado por un A3 (nunca llegó al navegador)       | ROBO
  D7  sustituido con su sustituto revocado/caducado/ido  | YA_CERRADA
  D8  «sustituto usado» = el sustituto ya rotó
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.services.rotacion_del_refresco import (
    VENTANA_DE_LA_REANUDACION,
    PasoDelRefresco,
    paso_del_refresco,
    sustituto_usado,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId

AHORA = datetime(2026, 11, 10, 12, 0, 0)


def _cadena(hace: timedelta, usado: bool = False) -> tuple[RefreshToken, RefreshToken]:
    viejo = RefreshToken.create(
        user_id=UserId.generate(), token="viejo", device_id=UserDeviceId.generate()
    )
    sustituto = viejo.sustituye("sustituto", AHORA - hace)
    if usado:
        sustituto.sustituye("siguiente", AHORA - hace + timedelta(seconds=1))
    return viejo, sustituto


def test_d1_a_current_token_rotates():
    token = RefreshToken.create(user_id=UserId.generate(), token="t")

    assert paso_del_refresco(token, None, AHORA) is PasoDelRefresco.ROTA


@pytest.mark.parametrize("usado", [False, True])
def test_d2_within_the_margin_only_access(usado):
    viejo, sustituto = _cadena(timedelta(seconds=60), usado)

    assert paso_del_refresco(viejo, sustituto, AHORA) is PasoDelRefresco.SOLO_ACCESO


@pytest.mark.parametrize("hace", [timedelta(seconds=61), timedelta(minutes=59)])
def test_d3_a_lost_response_within_the_hour_resumes(hace):
    viejo, sustituto = _cadena(hace)

    assert paso_del_refresco(viejo, sustituto, AHORA) is PasoDelRefresco.REANUDA


def test_d4_after_one_hour_an_unused_substitute_is_a_theft():
    viejo, sustituto = _cadena(VENTANA_DE_LA_REANUDACION + timedelta(seconds=1))

    assert timedelta(hours=1) == VENTANA_DE_LA_REANUDACION
    assert paso_del_refresco(viejo, sustituto, AHORA) is PasoDelRefresco.ROBO


def test_d4_exactly_one_hour_still_resumes():
    viejo, sustituto = _cadena(VENTANA_DE_LA_REANUDACION)

    assert paso_del_refresco(viejo, sustituto, AHORA) is PasoDelRefresco.REANUDA


def test_d5_a_used_substitute_outside_the_margin_is_a_theft():
    viejo, sustituto = _cadena(timedelta(minutes=2), usado=True)

    assert paso_del_refresco(viejo, sustituto, AHORA) is PasoDelRefresco.ROBO


def test_d6_an_annulled_substitute_that_comes_back_is_a_theft():
    _viejo, sustituto = _cadena(timedelta(minutes=2))
    sustituto.anula(AHORA)

    assert sustituto.revoked and sustituto.is_annulled
    assert paso_del_refresco(sustituto, None, AHORA) is PasoDelRefresco.ROBO


@pytest.mark.parametrize("como", ["revocado", "caducado", "ido"])
def test_d7_a_substitute_closed_another_way_means_the_session_is_closed(como):
    viejo, sustituto = _cadena(timedelta(minutes=2))
    if como == "revocado":
        sustituto.revoke()
    elif como == "caducado":
        sustituto._expires_at = datetime.now() - timedelta(seconds=1)

    resultado = paso_del_refresco(viejo, None if como == "ido" else sustituto, AHORA)

    assert resultado is PasoDelRefresco.YA_CERRADA


def test_d8_a_substitute_is_used_when_it_has_rotated():
    _viejo, sustituto = _cadena(timedelta(minutes=2))
    assert not sustituto_usado(sustituto)

    sustituto.sustituye("siguiente", AHORA)

    assert sustituto_usado(sustituto)
