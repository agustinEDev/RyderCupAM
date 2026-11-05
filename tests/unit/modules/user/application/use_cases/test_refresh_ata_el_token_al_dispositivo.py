"""
Un refresh token sin dispositivo se ata al que se reconoce al refrescar (BE #737).

Sin esto, revocar ese dispositivo no cerraba la sesión: el access token caía por su
`did`, pero el refresh token, que no era de ningún dispositivo, seguía dando tokens
nuevos durante 7 días.

  #   caso                                              | esperado
  ----|------------------------------------------------|----------------------------------
  T1  refresca un token sin dispositivo                  | queda atado al reconocido
  T2  luego se revoca ese dispositivo                    | el siguiente refresco se rechaza
  T3  refresca un token que ya tiene dispositivo         | no se cambia de dispositivo
"""

from unittest.mock import Mock

import pytest

from src.modules.user.application.dto.device_dto import RevokeDeviceRequestDTO
from src.modules.user.application.dto.user_dto import RefreshAccessTokenRequestDTO
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
    RefreshRejectedError,
)
from src.modules.user.application.use_cases.register_device_use_case import RegisterDeviceUseCase
from src.modules.user.application.use_cases.revoke_device_use_case import RevokeDeviceUseCase
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from tests.unit.modules.user.application.use_cases._sesion_al_registrar import (
    uow_con_sesion_al_registrar,
)

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"
JWT = "refresco-antiguo-sin-dispositivo"


async def _escena(con_dispositivo=False):
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
    token = RefreshToken.create(
        user_id=usuario.id,
        token=JWT,
        device_id=dispositivo.id if dispositivo else None,
        expires_in_days=7,
    )
    await uow.refresh_tokens.save(token)
    tokens = Mock()
    tokens.verify_refresh_token.return_value = {"sub": str(usuario.id.value), "type": "refresh"}
    tokens.refresh_token_expired.return_value = False
    tokens.create_access_token.return_value = "acceso"
    refresco = RefreshAccessTokenUseCase(uow, tokens, RegisterDeviceUseCase(uow))
    return uow, usuario, dispositivo, refresco


MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.1 Safari/605.1.15"


def _peticion(ua=IPHONE):
    return RefreshAccessTokenRequestDTO(user_agent=ua, ip_address="203.0.113.7")


@pytest.mark.asyncio
async def test_t1_t2_a_token_without_device_is_bound_and_revoking_closes_it():
    """
    Given: Un refresh token de antes, sin dispositivo
    When: Refresca desde un iPhone y luego se revoca ese iPhone
    Then: El token queda atado al iPhone, y el siguiente refresco se rechaza
    """
    uow, usuario, _, refresco = await _escena()

    respuesta = await refresco.execute(_peticion(), JWT)

    guardado = await uow.refresh_tokens.find_by_token_hash(JWT)
    assert guardado.device_id is not None
    assert str(guardado.device_id.value) == respuesta.device_id

    await RevokeDeviceUseCase(uow).execute(
        RevokeDeviceRequestDTO(user_id=str(usuario.id.value), device_id=respuesta.device_id)
    )
    with pytest.raises(RefreshRejectedError):
        await refresco.execute(_peticion(), JWT)


@pytest.mark.asyncio
async def test_t3_a_token_with_its_device_keeps_it():
    """
    Given: Un refresh token atado a su iPhone
    When: Refresca y el registro reconoce otro dispositivo (sin cookie, otro navegador)
    Then: Sigue atado a su iPhone
    """
    uow, _, dispositivo, refresco = await _escena(con_dispositivo=True)

    await refresco.execute(_peticion(MAC), JWT)

    guardado = await uow.refresh_tokens.find_by_token_hash(JWT)
    assert guardado.device_id == dispositivo.id


def test_t4_binding_never_moves_a_token_to_another_device():
    """
    Given: Un token ya atado a un dispositivo
    When: Se intenta atar a otro
    Then: Sigue en el suyo; uno sin dispositivo sí se ata
    """
    from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
    from src.modules.user.domain.value_objects.user_id import UserId

    suyo, otro = UserDeviceId.generate(), UserDeviceId.generate()
    atado = RefreshToken.create(user_id=UserId.generate(), token="a", device_id=suyo)
    suelto = RefreshToken.create(user_id=UserId.generate(), token="b")

    atado.ata_al_dispositivo(otro)
    suelto.ata_al_dispositivo(otro)

    assert atado.device_id == suyo
    assert suelto.device_id == otro


@pytest.mark.asyncio
async def test_t5_the_token_device_is_reused_and_put_back_in_the_cookie():
    """
    Given: Un refresh token de su iPhone, sin la cookie del dispositivo y desde otra red
    When: Refresca
    Then: No se crea otro dispositivo: sigue siendo su iPhone, y se le vuelve a poner la cookie
    """
    uow, usuario, dispositivo, refresco = await _escena(con_dispositivo=True)

    respuesta = await refresco.execute(
        RefreshAccessTokenRequestDTO(user_agent=IPHONE, ip_address="198.51.100.77"), JWT
    )

    assert respuesta.device_id == str(dispositivo.id.value)
    assert respuesta.should_set_device_cookie is True
    assert len(await uow.user_devices.find_all_by_user(usuario.id)) == 1


@pytest.mark.asyncio
async def test_t6_with_its_device_in_the_cookie_the_cookie_is_left_alone():
    """
    Given: Un refresh token de su iPhone, con el iPhone en la cookie (junto a otra cuenta)
    When: Refresca
    Then: Es su iPhone y la cookie no se toca
    """
    _, _, dispositivo, refresco = await _escena(con_dispositivo=True)
    otra_cuenta = "11111111-1111-4111-8111-111111111111"

    respuesta = await refresco.execute(
        RefreshAccessTokenRequestDTO(
            user_agent=IPHONE,
            ip_address="203.0.113.7",
            device_id_from_cookie=f"{otra_cuenta}.{dispositivo.id.value}",
        ),
        JWT,
    )

    assert respuesta.device_id == str(dispositivo.id.value)
    assert respuesta.should_set_device_cookie is False
