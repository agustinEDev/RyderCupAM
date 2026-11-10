"""
Un refresh token sustituido ya no es una sesión viva (F-02), en los dos repositorios.

  V1 «hay uno vivo más nuevo» (BE #734) no cuenta un sustituido
  V2 los dispositivos con sesión no cuentan uno que solo tiene sustituidos
  V3 el contador de sesiones activas no cuenta los sustituidos
  V4 con bloqueo, se lee el token por su hash y por su id (y lo que no está, None)
"""

import contextlib
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from main import app as fastapi_app
from src.config.dependencies import get_db_session
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)

pytestmark = pytest.mark.asyncio


@contextlib.asynccontextmanager
async def _uow(tipo: str):
    if tipo == "memoria":
        yield InMemoryUnitOfWork()
        return
    override = fastapi_app.dependency_overrides[get_db_session]
    async with contextlib.aclosing(override()) as sesiones:
        async for sesion in sesiones:
            yield SQLAlchemyUnitOfWork(sesion)
            return


async def _escena(uow):
    usuario = User.create(
        first_name="Ana",
        last_name="Pérez",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    dispositivo = UserDevice.create(usuario.id, DeviceFingerprint.create("Mac", "203.0.113.7"))
    async with uow:
        await uow.users.save(usuario)
        await uow.user_devices.save(dispositivo)
    viejo = RefreshToken.create(user_id=usuario.id, token="viejo", device_id=dispositivo.id)
    async with uow:
        await uow.refresh_tokens.save(viejo)
    return usuario, dispositivo, viejo


async def _solo_sustituido(uow, usuario, dispositivo):
    """Un login más nuevo, ya sustituido, cuyo sucesor se revocó: no queda nada vivo."""
    nuevo = RefreshToken.create(user_id=usuario.id, token="nuevo", device_id=dispositivo.id)
    sucesor = nuevo.sustituye("sucesor", datetime.now())
    sucesor.revoke()
    async with uow:
        await uow.refresh_tokens.save(nuevo)
        await uow.refresh_tokens.save(sucesor)
    return nuevo


@pytest.mark.parametrize("tipo", ["memoria", "postgres"])
async def test_v1_v2_v3_a_replaced_token_is_not_live(client: AsyncClient, tipo):
    """
    Given: Un dispositivo cuyos tokens están todos sustituidos o revocados
    Then: No hay uno vivo más nuevo, el dispositivo no tiene sesión y no cuenta como activa
    """
    async with _uow(tipo) as uow:
        usuario, dispositivo, viejo = await _escena(uow)
        async with uow:
            viejo.revoke()
            await uow.refresh_tokens.save(viejo)
        await _solo_sustituido(uow, usuario, dispositivo)
        ahora = datetime.now()

        async with uow:
            mas_nuevo = await uow.refresh_tokens.hay_uno_vivo_mas_nuevo(
                [dispositivo.id], ahora - timedelta(minutes=5), ahora
            )
            con_sesion = await uow.refresh_tokens.device_ids_with_live_tokens(usuario.id, ahora)
            activos = await uow.refresh_tokens.count_active_for_user(usuario.id)

    assert mas_nuevo is False
    assert con_sesion == set()
    assert activos == 0


@pytest.mark.parametrize("tipo", ["memoria", "postgres"])
async def test_v4_the_locked_reads_find_the_token(client: AsyncClient, tipo):
    """
    Given: Un token guardado
    Then: Las lecturas con bloqueo lo encuentran por su hash y por su id; lo que no
          está da None
    """
    async with _uow(tipo) as uow:
        _usuario, _dispositivo, viejo = await _escena(uow)
        async with uow:
            por_hash = await uow.refresh_tokens.find_by_token_hash_for_update("viejo")
            por_id = await uow.refresh_tokens.find_by_id_for_update(viejo.id)
            ninguno = await uow.refresh_tokens.find_by_token_hash_for_update("otro")
            ninguno_id = await uow.refresh_tokens.find_by_id_for_update(RefreshTokenId.generate())

    assert por_hash is not None and por_hash.id == viejo.id
    assert por_id is not None and por_id.id == viejo.id
    assert ninguno is None and ninguno_id is None


@pytest.mark.parametrize("por", ["hash", "id"])
async def test_v5_the_locked_read_sees_what_another_session_committed(client: AsyncClient, por):
    """
    Given: Una sesión de BD que ya tenía el token cargado, y otra petición que lo sustituye
           y confirma
    When: La primera lo vuelve a leer con bloqueo
    Then: Ve la fila nueva (sustituido), no la copia vieja de su caché: es lo que hace que
          el segundo de dos refrescos a la vez no emita otro sustituto
    """
    async with _uow("postgres") as primera, _uow("postgres") as segunda:
        _usuario, _dispositivo, viejo = await _escena(primera)
        await primera.refresh_tokens.find_by_token_hash("viejo")
        async with segunda:
            suyo = await segunda.refresh_tokens.find_by_token_hash("viejo")
            sucesor = suyo.sustituye("sucesor", datetime.now())
            await segunda.refresh_tokens.save(sucesor)
            await segunda.refresh_tokens.save(suyo)

        if por == "hash":
            releido = await primera.refresh_tokens.find_by_token_hash_for_update("viejo")
        else:
            releido = await primera.refresh_tokens.find_by_id_for_update(viejo.id)

    assert releido is not None
    assert releido.is_replaced
