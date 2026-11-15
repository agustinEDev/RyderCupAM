"""
Cuando la RFEG encuentra el hándicap desde el perfil, se avisa (D1 y D4, 16 nov 2026).

Las competiciones cerradas donde juega lo apuntan como actualizado con la RFEG
(deja de salir como no encontrado) y, en un stroke play sin empezar, corrigen su
hándicap fijado. Eso lo hace quien escucha; aquí, que se le avise y cuándo.

| Caso | Camino                                        | ¿Se avisa?                     |
|------|-----------------------------------------------|--------------------------------|
| D4   | Perfil (/handicaps/update), la RFEG lo da     | Sí, con el valor de la RFEG    |
| D1   | Perfil, la RFEG no lo da y va el manual       | No: a mano no cuenta           |
| —    | Perfil, la RFEG no lo da y no hay manual      | No (el error de siempre)       |
| D4   | Al entrar (/refresh-mine), la RFEG lo da      | Sí                             |
| —    | Al entrar, la RFEG no lo da                   | No                             |
| —    | Al entrar, ya actualizado hoy                 | No (no se pregunta)            |
| —    | Quien escucha falla                           | El hándicap queda igual        |
| R7   | Varios a la vez: a los que la RFEG da         | Sí, a cada uno, tras guardar   |
| R7   | Varios: al que no da o falla                  | No                             |
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import RefreshOwnHandicapRequestDTO
from src.modules.user.application.use_cases.refresh_own_handicap_use_case import (
    RefreshOwnHandicapUseCase,
)
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import (
    UpdateMultipleHandicapsUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_use_case import (
    UpdateUserHandicapUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.handicap_errors import (
    HandicapNotFoundError,
    HandicapServiceUnavailableError,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from tests.fakes.mock_handicap_service import MockHandicapService

pytestmark = pytest.mark.asyncio


async def _usuario(uow) -> User:
    user = User.create("Luis", "Pérez", "luis@test.com", "P@ssw0rd123!", country_code_str="ES")
    await uow.users.save(user)
    await uow.commit()
    return user


def _escucha(falla: bool = False) -> AsyncMock:
    escucha = AsyncMock()
    if falla:
        escucha.encontrado.side_effect = RuntimeError("competiciones caidas")
    return escucha


class TestDesdeElPerfil:
    async def test_si_la_rfeg_lo_da_se_avisa(self):
        """Given la RFEG lo encuentra When lo pide desde su perfil Then se avisa con su valor (D4)."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)
        escucha = _escucha()

        await UpdateUserHandicapUseCase(
            uow, MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None), escucha
        ).execute(user.id)

        escucha.encontrado.assert_awaited_once_with(user.id, 13.0)

    async def test_con_el_manual_no_se_avisa(self):
        """Given la RFEG no lo da When va el manual Then no se avisa: a mano no cuenta (D1)."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)
        escucha = _escucha()

        await UpdateUserHandicapUseCase(uow, MockHandicapService(default=None), escucha).execute(
            user.id, manual_handicap=15.0
        )

        escucha.encontrado.assert_not_awaited()

    async def test_sin_nada_no_se_avisa(self):
        """Given la RFEG no lo da y no hay manual When lo pide Then el error de siempre, sin aviso."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)
        escucha = _escucha()

        with pytest.raises(HandicapNotFoundError):
            await UpdateUserHandicapUseCase(
                uow, MockHandicapService(default=None), escucha
            ).execute(user.id)

        escucha.encontrado.assert_not_awaited()

    async def test_si_quien_escucha_falla_el_handicap_queda(self):
        """Given quien escucha falla When la RFEG lo da Then su hándicap queda guardado igual."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)

        resultado = await UpdateUserHandicapUseCase(
            uow,
            MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None),
            _escucha(falla=True),
        ).execute(user.id)

        assert resultado.handicap == pytest.approx(13.0)


class TestAlEntrar:
    async def test_si_la_rfeg_lo_da_se_avisa(self):
        """Given la RFEG lo encuentra When se refresca al entrar Then se avisa (D4)."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)
        escucha = _escucha()

        await RefreshOwnHandicapUseCase(
            uow, MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None), escucha
        ).execute(RefreshOwnHandicapRequestDTO(user_id=user.id.value))

        escucha.encontrado.assert_awaited_once_with(user.id, 13.0)

    async def test_si_no_lo_da_no_se_avisa(self):
        """Given la RFEG no lo da When se refresca Then no se avisa."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)
        escucha = _escucha()

        await RefreshOwnHandicapUseCase(uow, MockHandicapService(default=None), escucha).execute(
            RefreshOwnHandicapRequestDTO(user_id=user.id.value)
        )

        escucha.encontrado.assert_not_awaited()

    async def test_ya_actualizado_hoy_no_se_avisa(self):
        """Given ya actualizado hoy When se refresca Then no se pregunta ni se avisa."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)
        user.update_handicap(10.0)
        await uow.users.save(user)
        escucha = _escucha()

        await RefreshOwnHandicapUseCase(
            uow, MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None), escucha
        ).execute(RefreshOwnHandicapRequestDTO(user_id=user.id.value))

        escucha.encontrado.assert_not_awaited()

    async def test_si_quien_escucha_falla_contesta_igual(self):
        """Given quien escucha falla When la RFEG lo da Then contesta con su hándicap."""
        uow = InMemoryUnitOfWork()
        user = await _usuario(uow)

        resultado = await RefreshOwnHandicapUseCase(
            uow,
            MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None),
            _escucha(falla=True),
        ).execute(RefreshOwnHandicapRequestDTO(user_id=user.id.value))

        assert resultado.handicap == pytest.approx(13.0)
        assert resultado.needs_handicap is False


class TestVariosALaVez:
    async def test_se_avisa_a_cada_uno_que_la_rfeg_da(self):
        """
        Given tres jugadores: uno que la RFEG da, uno que no, y uno con la RFEG caída
        When se actualizan a la vez
        Then se avisa solo del primero, con su valor, y con todo ya guardado (R7)
        """
        uow = InMemoryUnitOfWork()
        luis = await _usuario(uow)
        ana = User.create("Ana", "Gil", "ana@test.com", "P@ssw0rd123!", country_code_str="ES")
        eva = User.create("Eva", "Sanz", "eva@test.com", "P@ssw0rd123!", country_code_str="ES")
        for u in (ana, eva):
            await uow.users.save(u)
        await uow.commit()
        rfeg = MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None)
        original = rfeg.search_handicap

        async def buscar(nombre):
            if nombre == "Eva Sanz":
                raise HandicapServiceUnavailableError("caida")
            return await original(nombre)

        rfeg.search_handicap = buscar
        escucha = _escucha()

        await UpdateMultipleHandicapsUseCase(uow, rfeg, escucha).execute([luis.id, ana.id, eva.id])

        escucha.encontrado.assert_awaited_once_with(luis.id, 13.0)

    async def test_si_quien_escucha_falla_quedan_guardados(self):
        """Given quien escucha falla When se actualizan Then los hándicaps quedan guardados."""
        uow = InMemoryUnitOfWork()
        luis = await _usuario(uow)

        stats = await UpdateMultipleHandicapsUseCase(
            uow, MockHandicapService(handicaps={"Luis Pérez": 13.0}, default=None), _escucha(True)
        ).execute([luis.id])

        assert stats["updated"] == 1
        assert (await uow.users.find_by_id(luis.id)).handicap.value == pytest.approx(13.0)
