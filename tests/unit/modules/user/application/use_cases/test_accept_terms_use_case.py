"""
Aceptación de los Términos en la capa de aplicación.

B1: el registro por formulario exige `accept_terms: true` y guarda la versión
vigente con la fecha. B3: el alta con Google no acepta nada. B4: el DTO del
usuario dice si tiene aceptada la vigente y cuál es. B5: aceptar es idempotente.
B7: al cambiar la vigente, hay que volver a aceptar.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.modules.user.application.dto.device_dto import RegisterDeviceResponseDTO
from src.modules.user.application.dto.oauth_dto import GoogleLoginRequestDTO
from src.modules.user.application.dto.user_dto import (
    RegisterUserRequestDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.modules.user.application.use_cases.accept_terms_use_case import AcceptTermsUseCase
from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.application.use_cases.google_login_use_case import GoogleLoginUseCase
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.services import terms_of_service
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

_REGISTRO = {
    "email": "ana@example.com",
    "password": "V@l1dP@ss123!",
    "first_name": "Ana",
    "last_name": "Lopez",
}


async def _guardado(uow: InMemoryUnitOfWork, user: User) -> User:
    async with uow:
        await uow.users.save(user)
    return user


def _usuario() -> User:
    return User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str="ana@example.com",
        plain_password="V@l1dP@ss123!",
    )


class TestRegistroDTO:
    def test_register_dto_with_accept_terms_true_is_valid(self):
        """
        Given: Los datos del registro con accept_terms true
        When: Se valida el DTO
        Then: Es válido
        """
        dto = RegisterUserRequestDTO(**_REGISTRO, accept_terms=True)

        assert dto.accept_terms is True

    def test_register_dto_without_accept_terms_is_rejected(self):
        """
        Given: Los datos del registro sin accept_terms (B2)
        When: Se valida el DTO
        Then: ValidationError: el campo es obligatorio
        """
        with pytest.raises(ValidationError) as error:
            RegisterUserRequestDTO(**_REGISTRO)

        assert any(e["loc"] == ("accept_terms",) for e in error.value.errors())

    @pytest.mark.parametrize("valor", [False, "false", 0, "yes", None])
    def test_register_dto_with_accept_terms_not_true_is_rejected(self, valor):
        """
        Given: accept_terms con algo que no es true (B2)
        When: Se valida el DTO
        Then: ValidationError
        """
        with pytest.raises(ValidationError):
            RegisterUserRequestDTO(**_REGISTRO, accept_terms=valor)


@pytest.mark.asyncio
class TestRegistro:
    async def test_register_stores_current_version_and_utc_date(self):
        """
        Given: Un registro por formulario con accept_terms true (B1)
        When: Se ejecuta el caso de uso
        Then: El usuario guardado tiene la versión vigente y la fecha de ahora (UTC)
        """
        uow = InMemoryUnitOfWork()
        countries = AsyncMock()
        countries.exists.return_value = True
        antes = datetime.now(UTC)

        respuesta = await RegisterUserUseCase(uow, countries).execute(
            RegisterUserRequestDTO(**_REGISTRO, accept_terms=True)
        )

        guardado = await uow.users.find_by_id(UserId(respuesta.id))
        assert guardado is not None
        assert guardado.terms_version == terms_of_service.current_terms_version()
        assert guardado.terms_accepted_at is not None
        assert guardado.terms_accepted_at >= antes
        assert respuesta.terms_accepted is True


@pytest.mark.asyncio
class TestAltaConGoogle:
    async def test_google_new_user_is_created_without_acceptance(self):
        """
        Given: Alguien que entra por primera vez con Google (B3)
        When: Se le da de alta
        Then: Sin fecha ni versión, y la respuesta dice que no ha aceptado
        """
        uow = InMemoryUnitOfWork()
        google = AsyncMock()
        google.exchange_code_for_user_info.return_value = GoogleUserInfo(
            google_user_id="google-id-1",
            email="nuevo@gmail.com",
            first_name="Nuevo",
            last_name="Usuario",
            email_verified=True,
            picture_url=None,
        )
        dispositivos = AsyncMock()
        dispositivos.execute.return_value = RegisterDeviceResponseDTO(
            device_id="550e8400-e29b-41d4-a716-446655440099",
            is_new_device=True,
            message="New device registered",
            set_device_cookie=True,
        )
        use_case = GoogleLoginUseCase(
            uow=uow,
            token_service=JWTTokenService(),
            google_oauth_service=google,
            register_device_use_case=dispositivos,
        )

        respuesta = await use_case.execute(
            GoogleLoginRequestDTO(
                authorization_code="code",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0 Test",
                device_id_from_cookie=None,
            )
        )

        creado = await uow.users.find_by_email(Email("nuevo@gmail.com"))
        assert creado is not None
        assert creado.terms_accepted_at is None
        assert creado.terms_version is None
        assert respuesta.user.terms_accepted is False


class TestUsuarioDTO:
    def test_user_dto_reports_acceptance_of_current_version(self):
        """
        Given: Un usuario que aceptó la versión vigente (B4)
        When: Se convierte en DTO
        Then: terms_accepted true y terms_version_required la vigente
        """
        user = _usuario()
        user.accept_terms(terms_of_service.current_terms_version())

        dto = UserResponseDTO.model_validate(user)

        assert dto.terms_accepted is True
        assert dto.terms_version_required == terms_of_service.current_terms_version()

    def test_user_dto_reports_no_acceptance(self):
        """
        Given: Un usuario sin aceptación (B4)
        When: Se convierte en DTO
        Then: terms_accepted false
        """
        dto = UserResponseDTO.model_validate(_usuario())

        assert dto.terms_accepted is False
        assert dto.terms_version_required == terms_of_service.current_terms_version()

    def test_user_dto_reports_old_version_as_not_accepted(self, monkeypatch):
        """
        Given: Un usuario que aceptó la versión anterior (B7)
        When: Cambia la vigente y se convierte en DTO
        Then: terms_accepted false y se le exige la nueva
        """
        user = _usuario()
        user.accept_terms(terms_of_service.current_terms_version())
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        dto = UserResponseDTO.model_validate(user)

        assert dto.terms_accepted is False
        assert dto.terms_version_required == "2099-01-01"

    def test_user_dto_built_by_hand_defaults_to_not_accepted(self):
        """
        Given: Un DTO construido a mano, sin los campos nuevos
        When: Se mira
        Then: Por defecto no consta como aceptado y exige la vigente
        """
        dto = UserResponseDTO(
            id="550e8400-e29b-41d4-a716-446655440000",
            email="ana@example.com",
            first_name="Ana",
            last_name="Lopez",
            display_name="Ana Lopez",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert dto.terms_accepted is False
        assert dto.terms_version_required == terms_of_service.current_terms_version()


@pytest.mark.asyncio
class TestAceptarTerminos:
    async def test_accept_terms_stores_current_version(self):
        """
        Given: Un usuario sin aceptación (B5)
        When: Acepta
        Then: Queda guardada la versión vigente con la fecha, y la respuesta lo dice
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())

        respuesta = await AcceptTermsUseCase(uow).execute(str(user.id.value))

        guardado = await uow.users.find_by_id(user.id)
        assert guardado is not None
        assert guardado.terms_version == terms_of_service.current_terms_version()
        assert guardado.terms_accepted_at is not None
        assert respuesta.terms_accepted is True
        assert respuesta.email == "ana@example.com"

    async def test_accept_terms_twice_keeps_the_first_date(self):
        """
        Given: Un usuario que ya aceptó la vigente (B5)
        When: Acepta otra vez
        Then: No falla y la fecha sigue siendo la primera
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        use_case = AcceptTermsUseCase(uow)
        await use_case.execute(str(user.id.value))
        primera = (await uow.users.find_by_id(user.id)).terms_accepted_at

        respuesta = await use_case.execute(str(user.id.value))

        assert (await uow.users.find_by_id(user.id)).terms_accepted_at == primera
        assert respuesta.terms_accepted is True

    async def test_accept_terms_after_version_change_stores_the_new_one(self, monkeypatch):
        """
        Given: Un usuario que aceptó la versión anterior (B7)
        When: Cambia la vigente y vuelve a aceptar
        Then: Queda guardada la nueva
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        await AcceptTermsUseCase(uow).execute(str(user.id.value))
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        respuesta = await AcceptTermsUseCase(uow).execute(str(user.id.value))

        assert (await uow.users.find_by_id(user.id)).terms_version == "2099-01-01"
        assert respuesta.terms_accepted is True

    async def test_accept_terms_unknown_user_raises(self):
        """
        Given: Un id que no es de nadie
        When: Se intenta aceptar
        Then: UserNotFoundError
        """
        with pytest.raises(UserNotFoundError):
            await AcceptTermsUseCase(InMemoryUnitOfWork()).execute(
                "550e8400-e29b-41d4-a716-446655440000"
            )

    async def test_accept_terms_response_matches_current_user(self):
        """
        Given: Un usuario
        When: Acepta
        Then: La respuesta es la misma que la de current-user (con sus proveedores)
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        respuesta = await AcceptTermsUseCase(uow).execute(str(user.id.value))

        actual = await GetCurrentUserUseCase(uow).execute(str(user.id.value))

        assert actual is not None
        assert respuesta.model_dump() == actual.model_dump()
