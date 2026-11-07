"""
Tests para AdminUpdateUserUseCase.

El cambio de correo del administrador también queda pendiente (BE #753, punto 4): antes
se aplicaba sin verificar, y una errata daba la cuenta a quien tuviera esa dirección.

  AD1 el admin pone otro correo: la cuenta sigue con el suyo y el nuevo, pendiente;
      enlace al nuevo y aviso al de antes; la fila, bloqueada
  AD2 el usuario confirma con el enlace (su sesión): se aplica
  AD3 el mismo correo, o editar otros campos: nada del correo
  AD4 ocupado por otra cuenta: DuplicateEmailError (también al confirmar: E4)
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.admin_dto import AdminUpdateUserRequestDTO
from src.modules.user.application.use_cases.admin_update_user_use_case import (
    AdminUpdateUserUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.errors.user_errors import DuplicateEmailError, UserNotFoundError
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


class TestAdminUpdateUserUseCase:
    @pytest.fixture
    def uow(self):
        return InMemoryUnitOfWork()

    @pytest.fixture
    async def existing_user(self, uow):
        user = User.create(
            first_name="Carlos",
            last_name="Ruiz",
            email_str="carlos@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with uow:
            await uow.users.save(user)
        return user

    async def test_updates_name_and_handicap(self, uow, existing_user):
        use_case = AdminUpdateUserUseCase(uow, email_service=AsyncMock())
        result = await use_case.execute(
            str(existing_user.id.value),
            AdminUpdateUserRequestDTO(first_name="Carlitos", handicap=12.5),
        )

        assert result.first_name == "Carlitos"
        assert result.handicap == 12.5

    async def test_promotes_user_to_admin(self, uow, existing_user):
        use_case = AdminUpdateUserUseCase(uow, email_service=AsyncMock())
        result = await use_case.execute(
            str(existing_user.id.value), AdminUpdateUserRequestDTO(is_admin=True)
        )

        assert result.is_admin is True

    async def test_ad1_a_new_email_stays_pending_with_its_link_and_notice(self, uow, existing_user):
        existing_user.confirm_email_ownership()
        async with uow:
            await uow.users.save(existing_user)
        correos = AsyncMock()
        bloqueos = []
        bloquea = uow.users.find_by_id_for_update

        async def espia(user_id):
            bloqueos.append(user_id)
            return await bloquea(user_id)

        uow.users.find_by_id_for_update = espia

        result = await AdminUpdateUserUseCase(uow, email_service=correos).execute(
            str(existing_user.id.value), AdminUpdateUserRequestDTO(email="new-email@test.com")
        )

        assert result.email == "carlos@test.com"
        assert result.pending_email == "new-email@test.com"
        assert bloqueos == [existing_user.id]
        enlace = correos.send_email_change_confirmation.await_args.kwargs
        assert enlace["to_email"] == "new-email@test.com" and enlace["token"]
        correos.send_email_change_requested_notice.assert_awaited_once_with(
            to_email="carlos@test.com", user_name="Carlos", new_email="new-email@test.com"
        )

    async def test_ad2_the_user_confirms_it_with_the_link(self, uow, existing_user):
        from src.modules.user.application.use_cases.confirm_email_change_use_case import (
            ConfirmEmailChangeUseCase,
        )
        from src.modules.user.infrastructure.security.security_audit_logger import (
            SecurityAuditLogger,
        )

        correos = AsyncMock()
        await AdminUpdateUserUseCase(uow, email_service=correos).execute(
            str(existing_user.id.value), AdminUpdateUserRequestDTO(email="new-email@test.com")
        )
        token = correos.send_email_change_confirmation.await_args.kwargs["token"]

        usuario = await ConfirmEmailChangeUseCase(
            uow, security_audit=SecurityAuditLogger(), email_service=AsyncMock()
        ).execute(str(existing_user.id.value), token)

        assert usuario.email == "new-email@test.com"

    @pytest.mark.parametrize(
        "cambio",
        [{"email": "carlos@test.com"}, {"email": "Carlos@Test.com"}, {"first_name": "Otro"}],
    )
    async def test_ad3_no_new_email_sends_nothing(self, uow, existing_user, cambio):
        correos = AsyncMock()

        result = await AdminUpdateUserUseCase(uow, email_service=correos).execute(
            str(existing_user.id.value), AdminUpdateUserRequestDTO(**cambio)
        )

        assert result.pending_email is None
        correos.send_email_change_confirmation.assert_not_awaited()

    async def test_response_preserves_last_login_at(self, uow, existing_user):
        """
        Regression test: la respuesta de PUT /admin/users/{id} usaba el mismo
        AdminUserSummaryDTO que el listado, pero olvidaba rellenar last_login_at
        (quedaba siempre None) — el frontend lo pisaba con "Nunca" tras cualquier
        edicion, aunque el usuario si tuviera una conexion registrada.
        """
        last_used_at = datetime(2026, 7, 30, 10, 0, 0)
        async with uow:
            await uow.user_devices.save(
                UserDevice.reconstitute(
                    id=UserDeviceId.generate(),
                    user_id=existing_user.id,
                    device_name="Chrome on macOS",
                    user_agent="ua-1",
                    ip_address="1.1.1.1",
                    fingerprint_hash="hash-1",
                    is_active=True,
                    last_used_at=last_used_at,
                    created_at=last_used_at,
                )
            )

        use_case = AdminUpdateUserUseCase(uow, email_service=AsyncMock())
        result = await use_case.execute(
            str(existing_user.id.value),
            AdminUpdateUserRequestDTO(first_name="Carlitos"),
        )

        assert result.last_login_at == last_used_at

    async def test_raises_when_user_not_found(self, uow):
        from uuid import uuid4

        use_case = AdminUpdateUserUseCase(uow, email_service=AsyncMock())
        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(uuid4()), AdminUpdateUserRequestDTO(first_name="X"))

    async def test_raises_on_duplicate_email(self, uow, existing_user):
        other = User.create(
            first_name="Otro",
            last_name="Usuario",
            email_str="taken@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with uow:
            await uow.users.save(other)

        use_case = AdminUpdateUserUseCase(uow, email_service=AsyncMock())
        with pytest.raises(DuplicateEmailError):
            await use_case.execute(
                str(existing_user.id.value),
                AdminUpdateUserRequestDTO(email="taken@test.com"),
            )


async def test_a_notice_that_fails_while_being_built_does_not_escape():
    """
    Un fallo al montar los avisos (no solo al mandarlos) no se escapa: el cambio ya
    está guardado (CodeRabbit en BE #760)
    """
    from unittest.mock import MagicMock, PropertyMock

    from src.modules.user.application.services.avisa_del_cambio_de_correo import (
        avisa_del_cambio_de_correo,
    )

    usuario = MagicMock()
    type(usuario).first_name = PropertyMock(side_effect=RuntimeError("roto"))

    await avisa_del_cambio_de_correo(AsyncMock(), usuario, "nuevo@test.com", "tok")
