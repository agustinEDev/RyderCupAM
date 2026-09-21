"""
Tests para RefreshOwnHandicapUseCase (RyderCupAM#340).

La lógica vivía dentro del login (HM-2a) y el login esperaba a la RFEG antes de
contestar: hasta 20 s cuando la federación iba lenta. Ahora el frontend la pide
aparte, después de entrar, y el login contesta al momento. Las reglas no
cambian: una vez al día, solo España, y pedirle el hándicap al jugador cuando la
RFEG no lo da.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.user_dto import RefreshOwnHandicapRequestDTO
from src.modules.user.application.use_cases.refresh_own_handicap_use_case import (
    RefreshOwnHandicapUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.handicap_errors import HandicapServiceUnavailableError
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


def _servicio(devuelve=None, lanza=None):
    """HandicapService falso: devuelve un valor o lanza una excepción."""
    servicio = MagicMock()
    if lanza:
        servicio.search_handicap = AsyncMock(side_effect=lanza)
    else:
        servicio.search_handicap = AsyncMock(return_value=devuelve)
    return servicio


async def _guarda(uow, usuario: User) -> User:
    async with uow:
        await uow.users.save(usuario)
        await uow.commit()
    return usuario


def _usuario(pais: str | None = "ES", email: str = "juan@example.com") -> User:
    return User.create(
        first_name="Juan",
        last_name="Garcia",
        email_str=email,
        plain_password="V@l1dP@ss123!",
        country_code_str=pais,
    )


def _actualizado_hace(usuario: User, dias: int) -> User:
    """
    El mismo usuario con un hándicap puesto hace `dias` días.

    `update_handicap` siempre fecha con el instante actual y la entidad no expone
    otra forma de retrasarlo; el test del login lo hacía reconstruyendo el User
    campo a campo, y aquí basta con mover la fecha.
    """
    usuario.update_handicap(12.5)
    usuario._handicap_updated_at = datetime.now(UTC) - timedelta(days=dias)
    return usuario


async def _handicap_guardado(uow, usuario: User) -> float | None:
    async with uow:
        leido = await uow.users.find_by_id(usuario.id)
    return leido.handicap.value if leido.handicap else None


def _pide(usuario: User) -> RefreshOwnHandicapRequestDTO:
    return RefreshOwnHandicapRequestDTO(user_id=usuario.id.value)


@pytest.mark.asyncio
class TestRefreshOwnHandicapUseCase:
    async def test_u1_espanol_la_rfeg_lo_da_se_guarda_y_no_hay_que_pedirlo(self):
        """U1: ES sin hándicap + la RFEG devuelve 18.4 -> se guarda, needs_handicap=False."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _usuario())
        servicio = _servicio(devuelve=18.4)
        # El repositorio en memoria comparte el objeto: el valor nuevo se "ve"
        # aunque nadie lo guarde. El espía es lo que prueba que se guardó.
        uow.users.save = AsyncMock(wraps=uow.users.save)

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(_pide(usuario))

        assert respuesta.needs_handicap is False
        assert respuesta.handicap == 18.4
        uow.users.save.assert_awaited_once()
        assert await _handicap_guardado(uow, usuario) == 18.4

    async def test_u2_espanol_la_rfeg_no_lo_encuentra_hay_que_pedirlo(self):
        """U2: la RFEG no lo encuentra -> needs_handicap=True y no se toca nada."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _usuario())

        respuesta = await RefreshOwnHandicapUseCase(uow, _servicio(devuelve=None)).execute(
            _pide(usuario)
        )

        assert respuesta.needs_handicap is True
        assert respuesta.handicap is None
        assert await _handicap_guardado(uow, usuario) is None

    async def test_u3_espanol_la_rfeg_falla_hay_que_pedirlo_sin_romper(self):
        """U3: la RFEG no responde -> needs_handicap=True; el error no se propaga."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _usuario())
        servicio = _servicio(lanza=HandicapServiceUnavailableError("timeout"))

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(_pide(usuario))

        assert respuesta.needs_handicap is True

    async def test_u4_actualizado_hoy_no_llama_a_la_rfeg(self):
        """U4: ya se actualizó hoy -> ni una petición a la RFEG, needs_handicap=False."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _actualizado_hace(_usuario(), dias=0))
        servicio = _servicio(devuelve=15.0)

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(_pide(usuario))

        assert respuesta.needs_handicap is False
        assert respuesta.handicap == 12.5
        servicio.search_handicap.assert_not_awaited()

    async def test_u5_actualizado_ayer_vuelve_a_buscar_con_el_nombre_completo(self):
        """U5: se actualizó ayer -> busca con el nombre completo y guarda lo nuevo."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _actualizado_hace(_usuario(), dias=1))
        servicio = _servicio(devuelve=15.0)

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(_pide(usuario))

        assert respuesta.needs_handicap is False
        assert respuesta.handicap == 15.0
        servicio.search_handicap.assert_awaited_once_with("Juan Garcia")

    async def test_u6_fuera_de_espana_hay_que_pedirlo_sin_llamar_a_la_rfeg(self):
        """U6: la RFEG solo tiene federados españoles."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _usuario(pais="FR"))
        servicio = _servicio(devuelve=10.0)

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(_pide(usuario))

        assert respuesta.needs_handicap is True
        servicio.search_handicap.assert_not_awaited()

    async def test_u7_sin_pais_hay_que_pedirlo_sin_llamar_a_la_rfeg(self):
        """U7: sin país no se sabe si es federado español."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _usuario(pais=None))
        servicio = _servicio(devuelve=10.0)

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(_pide(usuario))

        assert respuesta.needs_handicap is True
        servicio.search_handicap.assert_not_awaited()

    async def test_u8_fuera_de_espana_actualizado_hoy_no_se_pide(self):
        """U8: lo puso a mano hoy -> no se le vuelve a preguntar."""
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _actualizado_hace(_usuario(pais="FR"), dias=0))

        respuesta = await RefreshOwnHandicapUseCase(uow, _servicio()).execute(_pide(usuario))

        assert respuesta.needs_handicap is False

    async def test_u9_si_falla_el_guardado_hay_que_pedirlo(self):
        """
        U9: la RFEG lo da pero no se puede guardar -> needs_handicap=True.

        Decir que no hace falta pedirlo sería afirmar algo que no quedó guardado.
        """
        uow = InMemoryUnitOfWork()
        usuario = await _guarda(uow, _usuario())
        uow.users.save = AsyncMock(side_effect=RuntimeError("disco lleno"))

        respuesta = await RefreshOwnHandicapUseCase(uow, _servicio(devuelve=18.4)).execute(
            _pide(usuario)
        )

        assert respuesta.needs_handicap is True
        assert respuesta.handicap is None

    async def test_u10_el_usuario_ya_no_existe_devuelve_none(self):
        """U10: borrado entre la autenticación y la llamada -> None (la ruta da 404)."""
        uow = InMemoryUnitOfWork()
        servicio = _servicio(devuelve=18.4)

        respuesta = await RefreshOwnHandicapUseCase(uow, servicio).execute(
            RefreshOwnHandicapRequestDTO(user_id=uuid4())
        )

        assert respuesta is None
        servicio.search_handicap.assert_not_awaited()
