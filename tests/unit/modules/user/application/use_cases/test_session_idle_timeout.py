"""24 h sin usar la app invalidan la sesión de ESE dispositivo (BE #376).

OWASP A07 pide invalidar las sesiones tras un periodo de inactividad. Hasta el
24 sep lo hacía un temporizador de 30 min en el navegador: con la pestaña
cerrada no invalidaba nada, y cuando saltaba, el logout echaba de todos los
dispositivos. Ahora lo decide el servidor, por dispositivo, al refrescar.

    #   caso                                             | qué pasa
    ----|------------------------------------------------|------------------------------
    D1  usado hace 23 h 59 min                           | no está inactivo
    D2  usado hace 24 h 1 min                            | inactivo
    R1  refrescar, usado hace 1 h                        | se refresca
    R2  refrescar, 25 h sin usar                         | None (401) y su token revocado
    R3  token sin dispositivo (anterior a los dispositivos) | se refresca: lo acotan los 7 días
    R4  refrescar cuenta como uso del dispositivo del TOKEN  | aunque la huella reconozca otro
    R5  caducar por inactividad                          | queda en el registro de seguridad
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.user_dto import RefreshAccessTokenRequestDTO
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import SESSION_IDLE_TIMEOUT, UserDevice
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.movil"


def _dispositivo(user: User, usado_hace: timedelta) -> UserDevice:
    ahora = datetime.now()
    return UserDevice(
        id=UserDeviceId.generate(),
        user_id=user.id,
        device_name="iPhone",
        user_agent="Mozilla/5.0 (iPhone)",
        ip_address="10.0.0.1",
        fingerprint_hash=uuid4().hex * 2,
        is_active=True,
        last_used_at=ahora - usado_hace,
        created_at=ahora - timedelta(days=3),
    )


def test_la_politica_es_de_24_horas():
    assert timedelta(hours=24) == SESSION_IDLE_TIMEOUT


@pytest.mark.parametrize(
    ("usado_hace", "inactivo"),
    [
        pytest.param(timedelta(hours=23, minutes=59), False, id="D1"),
        pytest.param(timedelta(hours=24, minutes=1), True, id="D2"),
    ],
)
def test_el_dispositivo_sabe_si_esta_inactivo(usado_hace, inactivo):
    user = User.create(
        first_name="Ana",
        last_name="Golf",
        email_str="ana@example.com",
        plain_password="V@l1dP@ss123!",
    )
    assert _dispositivo(user, usado_hace).is_idle() is inactivo


@pytest.mark.asyncio
class TestRefrescarSegunElUso:
    @pytest.fixture
    def user(self) -> User:
        return User.create(
            first_name="Ana",
            last_name="Golf",
            email_str="ana@example.com",
            plain_password="V@l1dP@ss123!",
        )

    @pytest.fixture
    def token_service(self, user):
        service = Mock()
        service.verify_refresh_token.return_value = {"sub": str(user.id.value), "type": "refresh"}
        service.create_access_token.return_value = "nuevo_access_token"
        return service

    async def _refresca(self, uow, token_service, user, dispositivo: UserDevice | None):
        await uow.users.save(user)
        if dispositivo:
            await uow.user_devices.save(dispositivo)
        await uow.refresh_tokens.save(
            RefreshToken.create(user.id, JWT, device_id=dispositivo.id if dispositivo else None)
        )
        caso = RefreshAccessTokenUseCase(uow, token_service, AsyncMock())
        return await caso.execute(RefreshAccessTokenRequestDTO(), JWT)

    async def test_r1_usado_hace_una_hora_se_refresca(self, user, token_service):
        uow = InMemoryUnitOfWork()

        respuesta = await self._refresca(
            uow, token_service, user, _dispositivo(user, timedelta(hours=1))
        )

        assert respuesta is not None

    async def test_r2_veinticinco_horas_sin_usar_no_y_queda_revocado(self, user, token_service):
        uow = InMemoryUnitOfWork()

        respuesta = await self._refresca(
            uow, token_service, user, _dispositivo(user, timedelta(hours=25))
        )

        assert respuesta is None
        assert (await uow.refresh_tokens.find_by_token_hash(JWT)).revoked is True

    async def test_r3_un_token_sin_dispositivo_se_refresca(self, user, token_service):
        uow = InMemoryUnitOfWork()

        respuesta = await self._refresca(uow, token_service, user, None)

        assert respuesta is not None

    async def test_r4_refrescar_cuenta_como_uso_del_dispositivo_del_token(
        self, user, token_service
    ):
        """El registro de dispositivos puede apuntar a otro (sin cookie, IP nueva):
        si el uso solo se apuntase allí, el del token caducaría estando en uso."""
        uow = InMemoryUnitOfWork()
        dispositivo = _dispositivo(user, timedelta(hours=23))

        await self._refresca(uow, token_service, user, dispositivo)

        guardado = await uow.user_devices.find_by_id(dispositivo.id)
        assert guardado.is_idle(now=datetime.now() + timedelta(hours=2)) is False

    async def test_r5_caducar_por_inactividad_queda_registrado(
        self, user, token_service, monkeypatch
    ):
        registro = Mock()
        monkeypatch.setattr(
            "src.modules.user.application.use_cases.refresh_access_token_use_case."
            "get_security_logger",
            lambda: registro,
        )
        uow = InMemoryUnitOfWork()

        await self._refresca(uow, token_service, user, _dispositivo(user, timedelta(hours=25)))

        registro.log_refresh_token_revoked.assert_called_once()
        assert registro.log_refresh_token_revoked.call_args.kwargs["reason"] == "idle"
