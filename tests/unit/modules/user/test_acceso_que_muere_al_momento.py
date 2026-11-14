"""
El acceso muere al cerrar sesión o cambiar la contraseña, no 15 minutos después
(auditoría de la fase 6, B-05).

Cerrar sesión y cambiar la contraseña revocaban solo los tokens de refresco: el de
acceso, si alguien lo había robado, seguía valiendo hasta caducar. Ahora el token lleva
cuándo se emitió (`iat`) y el dispositivo, cuándo se cerraron sus sesiones: cada petición
rechaza lo emitido antes. El dispositivo sigue activo, «de fiar» y en la lista.

    caso                                                  | qué pasa
    ------------------------------------------------------|----------------------------------
    el token de acceso lleva su hora                      | `iat`
    B1 cierro sesión                                      | mi acceso: 401 al momento
    B2 cierro sesión en el móvil                          | el ordenador sigue dentro
    B3 vuelvo a entrar en el mismo móvil                  | entro; sigue activo y de fiar
    B4 cambio la contraseña                               | los demás dispositivos, fuera
    B5 cambio la contraseña                               | yo sigo dentro con sesión nueva
    B6 token sin hora (de antes de desplegar)             | vale, salvo cierre posterior
    cambiar solo el correo                                | no cierra nada
"""

import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.config.dependencies.comun import get_current_user
from src.modules.user.application.dto.user_dto import (
    LogoutRequestDTO,
    UpdateSecurityRequestDTO,
)
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.use_cases.logout_user_use_case import LogoutUserUseCase
from src.modules.user.application.use_cases.update_security_use_case import (
    UpdateSecurityUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

pytestmark = pytest.mark.asyncio

CONTRASENA = "V@l1dP@ss123!"
NUEVA = "Otr4C0ntr@s3na!"
RUTA = "/api/v1/auth/current-user"


async def _persona(uow) -> User:
    user = User.create(
        first_name="Ana", last_name="Golf", email_str="ana@example.com", plain_password=CONTRASENA
    )
    async with uow:
        await uow.users.save(user)
    return user


async def _dispositivo(uow, user: User, agente: str) -> UserDevice:
    device = UserDevice.create(user.id, DeviceFingerprint.create(agente, "1.2.3.4"))
    async with uow:
        await uow.user_devices.save(device)
    return device


def _acceso(user: User, device: UserDevice) -> str:
    return JWTTokenService().create_access_token(
        data=datos_del_acceso(str(user.id.value), str(device.id.value))
    )


def _peticion(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": RUTA,
            "raw_path": RUTA.encode(),
            "query_string": b"",
            "headers": [(b"cookie", f"access_token={token}".encode())],
            "client": ("1.2.3.4", 1),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


async def _entra(uow, token: str):
    return await get_current_user(_peticion(token), None, uow)


async def _no_entra(uow, token: str) -> None:
    with pytest.raises(HTTPException) as rechazo:
        await _entra(uow, token)
    assert rechazo.value.status_code == 401


async def _sale(uow, user: User, device: UserDevice) -> None:
    await LogoutUserUseCase(uow, security_audit=SecurityAuditLogger()).execute(
        LogoutRequestDTO(device_id=str(device.id.value)), str(user.id.value)
    )


def _cambio(device: UserDevice | None, **datos) -> UpdateSecurityRequestDTO:
    return UpdateSecurityRequestDTO(
        current_password=CONTRASENA,
        dispositivo_actual=str(device.id.value) if device else None,
        **datos,
    )


def _caso_del_cambio(uow) -> UpdateSecurityUseCase:
    return UpdateSecurityUseCase(
        uow, security_audit=SecurityAuditLogger(), token_service=JWTTokenService()
    )


async def test_the_access_token_carries_when_it_was_issued():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    antes = time.time()

    payload = JWTTokenService().verify_access_token(_acceso(ana, movil))

    assert payload is not None
    assert antes - 1 <= payload["iat"] <= time.time() + 1


async def test_b1_signing_out_kills_my_access_at_once():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    token = _acceso(ana, movil)
    assert (await _entra(uow, token)).email == "ana@example.com"

    await _sale(uow, ana, movil)

    await _no_entra(uow, token)


async def test_b2_signing_out_on_the_phone_keeps_the_computer_in():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    ordenador = await _dispositivo(uow, ana, "Ordenador/1.0")
    del_ordenador = _acceso(ana, ordenador)

    await _sale(uow, ana, movil)

    assert (await _entra(uow, del_ordenador)).email == "ana@example.com"


async def test_b3_signing_in_again_on_the_same_phone_works_and_it_stays_trusted():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    await _sale(uow, ana, movil)
    time.sleep(0.01)

    nuevo = _acceso(ana, movil)

    assert (await _entra(uow, nuevo)).email == "ana@example.com"
    async with uow:
        activos = await uow.user_devices.find_active_ids_of_user([movil.id], ana.id)
    assert movil.id in activos


async def test_b4_changing_the_password_kills_the_other_devices_at_once():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    ordenador = await _dispositivo(uow, ana, "Ordenador/1.0")
    del_ordenador = _acceso(ana, ordenador)

    await _caso_del_cambio(uow).execute(
        str(ana.id.value), _cambio(movil, new_password=NUEVA, confirm_password=NUEVA)
    )

    await _no_entra(uow, del_ordenador)


async def test_b5_changing_the_password_keeps_me_in_with_a_new_session():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    viejo = _acceso(ana, movil)

    respuesta = await _caso_del_cambio(uow).execute(
        str(ana.id.value), _cambio(movil, new_password=NUEVA, confirm_password=NUEVA)
    )

    sesion = respuesta.sesion_nueva
    assert sesion is not None
    # El de antes, fuera (por si lo tenía otro); el nuevo, dentro
    await _no_entra(uow, viejo)
    assert (await _entra(uow, sesion.access_token)).email == "ana@example.com"
    # Con su refresco guardado para este dispositivo, y su CSRF
    async with uow:
        guardado = await uow.refresh_tokens.find_by_token_hash(sesion.refresh_token)
    assert guardado is not None
    assert guardado.device_id == movil.id
    assert not guardado.revoked
    assert sesion.csrf_token
    # Y nada de tokens en el cuerpo de la respuesta
    assert "sesion_nueva" not in respuesta.model_dump()


async def test_changing_only_the_email_closes_nothing():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    ordenador = await _dispositivo(uow, ana, "Ordenador/1.0")
    del_ordenador = _acceso(ana, ordenador)

    respuesta = await _caso_del_cambio(uow).execute(
        str(ana.id.value), _cambio(movil, new_email="ana.nueva@example.com")
    )

    assert respuesta.sesion_nueva is None
    assert (await _entra(uow, del_ordenador)).email == "ana@example.com"


async def test_b6_a_token_without_issue_time_is_valid_until_its_device_signs_out():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    servicio = JWTTokenService()
    # Como los de antes de desplegar: sin `iat`
    import jwt

    from src.config.settings import settings

    payload = servicio.verify_access_token(_acceso(ana, movil))
    assert payload is not None
    payload.pop("iat")
    sin_hora = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert (await _entra(uow, sin_hora)).email == "ana@example.com"

    await _sale(uow, ana, movil)

    await _no_entra(uow, sin_hora)


class TestElDispositivo:
    """La regla, en el dominio."""

    async def test_never_signed_out_admits_any_token(self):
        uow = InMemoryUnitOfWork()
        ana = await _persona(uow)
        movil = await _dispositivo(uow, ana, "Movil/1.0")

        assert movil.admite_el_acceso(None)
        assert movil.admite_el_acceso(time.time())

    async def test_after_signing_out_only_later_tokens(self):
        from datetime import UTC, datetime

        uow = InMemoryUnitOfWork()
        ana = await _persona(uow)
        movil = await _dispositivo(uow, ana, "Movil/1.0")
        ahora = datetime.now(UTC)
        movil.cierra_las_sesiones(ahora)

        assert not movil.admite_el_acceso(ahora.timestamp() - 10)
        assert not movil.admite_el_acceso(ahora.timestamp())
        assert movil.admite_el_acceso(ahora.timestamp() + 0.001)
        assert not movil.admite_el_acceso(None)


class TestLaRutaDelCambio:
    """La ruta pone el dispositivo del token y la sesión nueva en cookies."""

    async def test_b5_the_route_sets_the_new_session_cookies_and_not_in_the_body(self):
        from unittest.mock import AsyncMock

        from fastapi import Response

        from src.modules.user.application.dto.user_dto import (
            SesionNuevaDTO,
            UpdateSecurityResponseDTO,
            UserResponseDTO,
        )
        from src.modules.user.infrastructure.api.v1 import user_routes

        uow = InMemoryUnitOfWork()
        ana = await _persona(uow)
        dto = UserResponseDTO.model_validate(ana)
        caso = AsyncMock()
        caso.execute.return_value = UpdateSecurityResponseDTO(
            user=dto,
            sesion_nueva=SesionNuevaDTO(
                access_token="acceso-nuevo", refresh_token="refresco-nuevo", csrf_token="csrf"
            ),
        )
        peticion = _peticion("x")
        peticion.state.dispositivo_actual = "dispositivo-del-token"
        respuesta = Response()

        cuerpo = await user_routes.update_security(
            peticion,
            UpdateSecurityRequestDTO(
                current_password=CONTRASENA,
                new_password=NUEVA,
                confirm_password=NUEVA,
                dispositivo_actual="otro-que-manda-el-cliente",
            ),
            respuesta,
            caso,
            dto,
        )

        enviado = caso.execute.call_args.args[1]
        assert enviado.dispositivo_actual == "dispositivo-del-token"
        galletas = respuesta.headers.getlist("set-cookie")
        assert any("acceso-nuevo" in g for g in galletas)
        assert any("refresco-nuevo" in g for g in galletas)
        assert any(g.startswith("csrf_token=csrf") for g in galletas)
        assert "acceso-nuevo" not in cuerpo.model_dump_json()

    def test_the_dependency_gives_the_use_case_its_token_service(self):
        import inspect

        from fastapi.params import Depends as Dependencia

        from src.config.dependencies.usuarios import get_token_service, get_update_security_use_case

        # Inyectado como las demás factorías (/code-review): se puede sustituir en tests
        por_defecto = (
            inspect.signature(get_update_security_use_case).parameters["token_service"].default
        )
        assert isinstance(por_defecto, Dependencia)
        assert por_defecto.dependency is get_token_service
        servicio = get_token_service()
        caso = get_update_security_use_case(
            InMemoryUnitOfWork(), None, SecurityAuditLogger(), servicio
        )
        assert caso._token_service is servicio


class TestLaRutaDelCierre:
    """La ruta de salir cierra el dispositivo del token, nunca el que mande el cliente."""

    async def test_b1_the_logout_route_closes_the_token_device_not_the_clients(self):
        from unittest.mock import AsyncMock

        from fastapi import Response

        from src.modules.user.application.dto.user_dto import UserResponseDTO
        from src.modules.user.infrastructure.api.v1 import auth_routes

        uow = InMemoryUnitOfWork()
        ana = await _persona(uow)
        caso = AsyncMock()
        peticion = _peticion("x")
        peticion.state.dispositivo_actual = "dispositivo-del-token"

        await auth_routes.logout_user(
            peticion,
            LogoutRequestDTO(device_id="otro-que-manda-el-cliente"),
            Response(),
            UserResponseDTO.model_validate(ana),
            None,
            caso,
        )

        assert caso.execute.call_args.args[0].device_id == "dispositivo-del-token"


async def test_signing_out_with_someone_elses_device_closes_nothing():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    bea = User.create(
        first_name="Bea", last_name="Golf", email_str="bea@example.com", plain_password=CONTRASENA
    )
    async with uow:
        await uow.users.save(bea)
    de_bea = await _dispositivo(uow, bea, "Movil/1.0")
    token_de_bea = _acceso(bea, de_bea)

    await _sale(uow, ana, de_bea)

    assert (await _entra(uow, token_de_bea)).email == "bea@example.com"


async def test_b5_no_new_session_for_a_device_that_is_not_mine():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    bea = User.create(
        first_name="Bea", last_name="Golf", email_str="bea@example.com", plain_password=CONTRASENA
    )
    async with uow:
        await uow.users.save(bea)
    de_bea = await _dispositivo(uow, bea, "Movil/1.0")

    respuesta = await _caso_del_cambio(uow).execute(
        str(ana.id.value), _cambio(de_bea, new_password=NUEVA, confirm_password=NUEVA)
    )

    assert respuesta.sesion_nueva is None


async def test_password_change_locks_devices_before_tokens_like_sign_out():
    """
    /code-review de B-05: el mismo orden de bloqueos que el cierre de sesión y los
    refrescos (dispositivo, luego tokens), o se pueden interbloquear; y la hora del
    cierre, tras bloquear (un cierre a la vez no se pisa).
    """
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    orden: list[str] = []
    bloquea = uow.user_devices.find_active_by_user_for_update
    revoca = uow.refresh_tokens.revoke_all_for_user

    async def bloquea_y_apunta(user_id):
        orden.append("dispositivos")
        return await bloquea(user_id)

    async def revoca_y_apunta(user_id):
        orden.append("tokens")
        return await revoca(user_id)

    uow.user_devices.find_active_by_user_for_update = bloquea_y_apunta
    uow.refresh_tokens.revoke_all_for_user = revoca_y_apunta

    await _caso_del_cambio(uow).execute(
        str(ana.id.value), _cambio(movil, new_password=NUEVA, confirm_password=NUEVA)
    )

    assert orden == ["dispositivos", "tokens"]


async def test_sign_out_does_not_touch_another_devices_refresh_tokens():
    """/code-review de B-05: con la cookie de refresco de otro dispositivo, solo se cierra
    el de la petición (BE #376), y no se bloquean dos filas."""
    from src.modules.user.domain.entities.refresh_token import RefreshToken

    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    ordenador = await _dispositivo(uow, ana, "Ordenador/1.0")
    async with uow:
        await uow.refresh_tokens.save(RefreshToken.create(ana.id, "jwt-ordenador", ordenador.id))

    await LogoutUserUseCase(uow, security_audit=SecurityAuditLogger()).execute(
        LogoutRequestDTO(device_id=str(movil.id.value), refresh_token="jwt-ordenador"),
        str(ana.id.value),
    )

    async with uow:
        assert not (await uow.refresh_tokens.find_by_token_hash("jwt-ordenador")).revoked


@pytest.mark.parametrize("cookie", [None, "jwt-del-ordenador"])
async def test_sign_out_revokes_the_requests_device_refresh_tokens_without_its_cookie(cookie):
    """
    CodeRabbit en BE-1: sin la cookie de refresco (o con la de otro dispositivo), los
    tokens del dispositivo de la petición quedaban vivos; uno copiado refrescaba y volvía
    a entrar con un acceso posterior al cierre. Se revocan los suyos, nunca los del otro.
    """
    from src.modules.user.domain.entities.refresh_token import RefreshToken

    uow = InMemoryUnitOfWork()
    ana = await _persona(uow)
    movil = await _dispositivo(uow, ana, "Movil/1.0")
    ordenador = await _dispositivo(uow, ana, "Ordenador/1.0")
    async with uow:
        await uow.refresh_tokens.save(RefreshToken.create(ana.id, "jwt-del-movil", movil.id))
        await uow.refresh_tokens.save(
            RefreshToken.create(ana.id, "jwt-del-ordenador", ordenador.id)
        )

    await LogoutUserUseCase(uow, security_audit=SecurityAuditLogger()).execute(
        LogoutRequestDTO(device_id=str(movil.id.value), refresh_token=cookie),
        str(ana.id.value),
    )

    async with uow:
        assert (await uow.refresh_tokens.find_by_token_hash("jwt-del-movil")).revoked
        assert not (await uow.refresh_tokens.find_by_token_hash("jwt-del-ordenador")).revoked
