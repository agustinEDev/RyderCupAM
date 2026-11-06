"""
El refresco usa el dispositivo de su token (BE #737), y un token sin dispositivo se
rechaza (BE #738).

Hasta el 6 nov 2026 un token anterior a los dispositivos se ataba al que se reconocía.
En PRO ya no queda ninguno vivo (consulta de solo lectura del 6 nov: 0), así que esa
rama se quita: un token sin dispositivo es un token que no puede existir.

  #   caso                                              | esperado
  ----|------------------------------------------------|----------------------------------
  T3  refresca un token atado a su dispositivo, desde  | sigue en su dispositivo: no se
      otro navegador                                    |   cambia ni se crea otro
  T5  refresca sin la cookie del dispositivo y desde   | el mismo dispositivo: uno solo
      otra red                                          |
  T7  refresca un token sin dispositivo                | rechazado: REFRESH_TOKEN_INVALID
"""

from unittest.mock import Mock

import pytest

from src.modules.user.application.dto.user_dto import RefreshAccessTokenRequestDTO
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
    RefreshRejectedError,
    RefreshRejection,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from tests.unit.modules.user.application.use_cases._sesion_al_registrar import (
    uow_con_sesion_al_registrar,
)

pytestmark = pytest.mark.asyncio

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.1 Safari/605.1.15"
JWT = "refresco-de-prueba"


async def _escena(con_dispositivo=True):
    uow = uow_con_sesion_al_registrar()
    usuario = User.create(
        first_name="Ana",
        last_name="Pérez",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    await uow.users.save(usuario)
    dispositivo = None
    if con_dispositivo:
        dispositivo = UserDevice.create(usuario.id, DeviceFingerprint.create(IPHONE, "203.0.113.7"))
        await uow.user_devices.save(dispositivo)
    await uow.refresh_tokens.save(
        RefreshToken.create(
            user_id=usuario.id,
            token=JWT,
            device_id=dispositivo.id if dispositivo else None,
            expires_in_days=7,
        )
    )
    tokens = Mock()
    tokens.verify_refresh_token.return_value = {"sub": str(usuario.id.value), "type": "refresh"}
    tokens.refresh_token_expired.return_value = False
    tokens.create_access_token.return_value = "acceso"
    return uow, usuario, dispositivo, RefreshAccessTokenUseCase(uow, tokens)


async def test_t3_un_token_con_su_dispositivo_se_queda_en_el():
    """
    Given: Un refresh token atado a su iPhone
    When: Refresca desde otro navegador, sin cookie
    Then: Sigue atado a su iPhone
    """
    uow, _, dispositivo, refresco = await _escena()

    respuesta = await refresco.execute(RefreshAccessTokenRequestDTO(user_agent=MAC), JWT)

    assert respuesta.device_id == str(dispositivo.id.value)
    assert (await uow.refresh_tokens.find_by_token_hash(JWT)).device_id == dispositivo.id


async def test_t5_sin_cookie_y_desde_otra_red_es_el_mismo_dispositivo():
    """
    Given: Un refresh token de su iPhone, sin la cookie del dispositivo y desde otra red
    When: Refresca
    Then: No se crea otro dispositivo: sigue siendo su iPhone
    """
    uow, usuario, dispositivo, refresco = await _escena()

    respuesta = await refresco.execute(
        RefreshAccessTokenRequestDTO(user_agent=IPHONE, ip_address="198.51.100.77"), JWT
    )

    assert respuesta.device_id == str(dispositivo.id.value)
    assert len(await uow.user_devices.find_active_by_user(usuario.id)) == 1


async def test_t7_un_token_sin_dispositivo_se_rechaza():
    """
    Given: Un refresh token sin dispositivo (de antes de BE #737: ya no queda ninguno)
    When: Refresca
    Then: Rechazado como inválido: no se ata a ningún dispositivo
    """
    _, _usuario, _, refresco = await _escena(con_dispositivo=False)

    with pytest.raises(RefreshRejectedError) as rechazo:
        await refresco.execute(RefreshAccessTokenRequestDTO(user_agent=IPHONE), JWT)
    assert rechazo.value.motivo is RefreshRejection.REFRESH_TOKEN_INVALID
