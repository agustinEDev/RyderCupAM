"""
Aceptación de los Términos en la capa de aplicación.

B1: el registro por formulario exige `accept_terms: true` y guarda la versión
vigente con la fecha. B3: el alta con Google no acepta nada. B4: el DTO del
usuario dice si tiene aceptada la vigente y cuál es. B5: aceptar es idempotente.
B7: al cambiar la vigente, hay que volver a aceptar.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.modules.user.application.dto.device_dto import RegisterDeviceResponseDTO
from src.modules.user.application.dto.oauth_dto import GoogleLoginRequestDTO
from src.modules.user.application.dto.user_dto import (
    AcceptTermsRequestDTO,
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
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.errors.user_errors import (
    TermsAcceptanceRequiredError,
    UserNotFoundError,
)
from src.modules.user.domain.services import terms_of_service
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
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


IP = "203.0.113.7"
NAVEGADOR = "Mozilla/5.0 (iPhone) Safari"


@pytest.fixture
def auditoria() -> MagicMock:
    """El puerto de auditoría de seguridad, inyectado en los dos casos de uso."""
    return MagicMock()


def _filas(uow: InMemoryUnitOfWork, user_id: UserId) -> list:
    """Las filas del historial de ese usuario, en orden de llegada."""
    return [fila for fila in uow.terms_acceptances.all_rows() if fila.user_id == user_id]


def _countries() -> AsyncMock:
    countries = AsyncMock()
    countries.exists.return_value = True
    return countries


def _aceptar(user: User, actual: UserResponseDTO | None = None) -> AcceptTermsRequestDTO:
    return AcceptTermsRequestDTO(
        user_id=str(user.id.value), ip_address=IP, user_agent=NAVEGADOR, current_user=actual
    )


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
    async def test_register_stores_current_version_and_utc_date(self, auditoria):
        """
        Given: Un registro por formulario con accept_terms true (B1)
        When: Se ejecuta el caso de uso
        Then: El usuario guardado tiene la versión vigente y la fecha de ahora (UTC)
        """
        uow = InMemoryUnitOfWork()
        antes = datetime.now(UTC)

        respuesta = await RegisterUserUseCase(uow, _countries(), security_audit=auditoria).execute(
            RegisterUserRequestDTO(**_REGISTRO, accept_terms=True)
        )

        guardado = await uow.users.find_by_id(UserId(respuesta.id))
        assert guardado is not None
        assert guardado.terms_version == terms_of_service.current_terms_version()
        assert guardado.terms_accepted_at is not None
        assert guardado.terms_accepted_at >= antes
        assert respuesta.terms_accepted is True

    async def test_register_records_one_acceptance_with_ip_and_browser(self, auditoria):
        """
        Given: Un registro con accept_terms true, desde una IP y un navegador
        When: Se ejecuta el caso de uso
        Then: Una fila en el historial con la versión, la fecha del usuario, la IP
            y el navegador, y la aceptación en el log de auditoría
        """
        uow = InMemoryUnitOfWork()

        respuesta = await RegisterUserUseCase(uow, _countries(), security_audit=auditoria).execute(
            RegisterUserRequestDTO(
                **_REGISTRO, accept_terms=True, ip_address=IP, user_agent=NAVEGADOR
            )
        )

        user_id = UserId(respuesta.id)
        guardado = await uow.users.find_by_id(user_id)
        filas = _filas(uow, user_id)
        assert len(filas) == 1
        assert filas[0].terms_version == terms_of_service.current_terms_version()
        assert filas[0].accepted_at == guardado.terms_accepted_at
        assert filas[0].ip_address == IP
        assert filas[0].user_agent == NAVEGADOR
        assert filas[0].user_email == _REGISTRO["email"]
        auditoria.log_terms_accepted.assert_called_once_with(
            user_id=str(respuesta.id),
            ip_address=IP,
            user_agent=NAVEGADOR,
            terms_version=terms_of_service.current_terms_version(),
        )

    async def test_register_records_the_normalized_email(self, auditoria):
        """
        Given: Un registro con el email en mayúsculas
        When: Se ejecuta el caso de uso
        Then: La fila guarda el email normalizado de la cuenta, no lo tecleado
        """
        uow = InMemoryUnitOfWork()

        respuesta = await RegisterUserUseCase(uow, _countries(), security_audit=auditoria).execute(
            RegisterUserRequestDTO(**{**_REGISTRO, "email": "Foo@Bar.com"}, accept_terms=True)
        )

        filas = _filas(uow, UserId(respuesta.id))
        assert [fila.user_email for fila in filas] == ["foo@bar.com"]

    @pytest.mark.parametrize("valor", [False, None, "true", 1])
    async def test_register_without_consent_is_refused_by_the_use_case(self, valor, auditoria):
        """
        Given: Un request de registro que se saltó la validación HTTP
            (construido sin validar) y no trae accept_terms true
        When: Se ejecuta el caso de uso
        Then: TermsAcceptanceRequiredError, y ni usuario, ni fila, ni auditoría
        """
        uow = InMemoryUnitOfWork()
        request = RegisterUserRequestDTO.model_construct(**_REGISTRO, accept_terms=valor)

        with pytest.raises(TermsAcceptanceRequiredError):
            await RegisterUserUseCase(uow, _countries(), security_audit=auditoria).execute(request)

        assert await uow.users.find_by_email(Email(_REGISTRO["email"])) is None
        auditoria.log_terms_accepted.assert_not_called()

    async def test_register_without_the_field_is_refused_by_the_use_case(self, auditoria):
        """
        Given: Un request construido sin el campo accept_terms
        When: Se ejecuta el caso de uso
        Then: TermsAcceptanceRequiredError y no se crea nadie
        """
        uow = InMemoryUnitOfWork()
        request = RegisterUserRequestDTO.model_construct(**_REGISTRO)

        with pytest.raises(TermsAcceptanceRequiredError):
            await RegisterUserUseCase(uow, _countries(), security_audit=auditoria).execute(request)

        assert await uow.users.find_by_email(Email(_REGISTRO["email"])) is None


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
    async def test_accept_terms_stores_current_version(self, auditoria):
        """
        Given: Un usuario sin aceptación (B5)
        When: Acepta
        Then: Queda guardada la versión vigente con la fecha, y la respuesta lo dice
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))

        guardado = await uow.users.find_by_id(user.id)
        assert guardado is not None
        assert guardado.terms_version == terms_of_service.current_terms_version()
        assert guardado.terms_accepted_at is not None
        assert respuesta.terms_accepted is True
        assert respuesta.email == "ana@example.com"

    async def test_accept_terms_records_the_acceptance_and_audits_it(self, auditoria):
        """
        Given: Un usuario sin aceptación
        When: Acepta desde una IP y un navegador
        Then: Una fila en el historial con todo, y la aceptación en el log de auditoría
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())

        await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))

        filas = _filas(uow, user.id)
        assert len(filas) == 1
        assert filas[0].terms_version == terms_of_service.current_terms_version()
        assert filas[0].accepted_at == user.terms_accepted_at
        assert (filas[0].ip_address, filas[0].user_agent) == (IP, NAVEGADOR)
        assert filas[0].user_email == "ana@example.com"
        auditoria.log_terms_accepted.assert_called_once_with(
            user_id=str(user.id.value),
            ip_address=IP,
            user_agent=NAVEGADOR,
            terms_version=terms_of_service.current_terms_version(),
        )

    async def test_accept_terms_without_ip_or_browser_audits_as_unknown(self, auditoria):
        """
        Given: Un usuario sin aceptación y una petición sin IP ni navegador válidos
        When: Acepta
        Then: La fila los guarda como None y la auditoría como "unknown", como el logout
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())

        await AcceptTermsUseCase(uow, auditoria).execute(
            AcceptTermsRequestDTO(user_id=str(user.id.value))
        )

        fila = (_filas(uow, user.id))[0]
        assert (fila.ip_address, fila.user_agent) == (None, None)
        llamada = auditoria.log_terms_accepted.call_args.kwargs
        assert (llamada["ip_address"], llamada["user_agent"]) == ("unknown", "unknown")

    async def test_accept_terms_twice_keeps_the_first_date(self, auditoria):
        """
        Given: Un usuario que ya aceptó la vigente (B5)
        When: Acepta otra vez
        Then: No falla y la fecha sigue siendo la primera
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        use_case = AcceptTermsUseCase(uow, auditoria)
        await use_case.execute(_aceptar(user))
        primera = (await uow.users.find_by_id(user.id)).terms_accepted_at

        respuesta = await use_case.execute(_aceptar(user))

        assert (await uow.users.find_by_id(user.id)).terms_accepted_at == primera
        assert respuesta.terms_accepted is True

    async def test_accepting_when_the_session_user_already_accepted_reads_nothing(self, auditoria):
        """
        Given: El usuario de la sesión (el que cargó get_current_user) ya tiene
            aceptada la versión vigente
        When: Vuelve a aceptar
        Then: Se responde con ese mismo usuario: ni lecturas, ni bloqueo, ni
            escritura, ni fila nueva, ni auditoría
        """
        uow = InMemoryUnitOfWork()
        user = _usuario()
        user.accept_terms(terms_of_service.current_terms_version())
        await _guardado(uow, user)
        actual = await GetCurrentUserUseCase(uow).execute(str(user.id.value))
        espias = {
            nombre: AsyncMock(wraps=getattr(uow.users, nombre))
            for nombre in ("find_by_id", "find_by_id_for_update", "save")
        }
        for nombre, espia in espias.items():
            setattr(uow.users, nombre, espia)
        cuentas = AsyncMock(wraps=uow.oauth_accounts.find_by_user_id)
        uow.oauth_accounts.find_by_user_id = cuentas

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user, actual))

        assert respuesta == actual
        for espia in espias.values():
            espia.assert_not_called()
        cuentas.assert_not_called()
        assert _filas(uow, user.id) == []
        auditoria.log_terms_accepted.assert_not_called()

    async def test_accepting_reads_the_user_only_with_the_lock(self, auditoria):
        """
        Given: El usuario de la sesión sin aceptación
        When: Acepta
        Then: Lo lee una sola vez, con bloqueo (sin una lectura previa sin
            bloquear), y no vuelve a pedir sus cuentas OAuth
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        actual = await GetCurrentUserUseCase(uow).execute(str(user.id.value))
        bloqueo = AsyncMock(wraps=uow.users.find_by_id_for_update)
        lectura = AsyncMock(wraps=uow.users.find_by_id)
        cuentas = AsyncMock(wraps=uow.oauth_accounts.find_by_user_id)
        uow.users.find_by_id_for_update = bloqueo
        uow.users.find_by_id = lectura
        uow.oauth_accounts.find_by_user_id = cuentas

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user, actual))

        assert respuesta.terms_accepted is True
        bloqueo.assert_awaited_once_with(user.id)
        lectura.assert_not_called()
        cuentas.assert_not_called()

    async def test_accept_terms_lost_race_records_nothing(self, auditoria):
        """
        Given: El usuario de la sesión se cargó sin aceptar, pero otra petición
            aceptó mientras esta esperaba el bloqueo
        When: La lectura con bloqueo ya lo trae aceptado
        Then: No escribe, ni añade fila, ni audita, y responde que está aceptado
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        actual = await GetCurrentUserUseCase(uow).execute(str(user.id.value))
        user.accept_terms(terms_of_service.current_terms_version())
        guardar = AsyncMock(wraps=uow.users.save)
        uow.users.save = guardar

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user, actual))

        assert respuesta.terms_accepted is True
        guardar.assert_not_called()
        assert _filas(uow, user.id) == []
        auditoria.log_terms_accepted.assert_not_called()

    async def test_accept_terms_after_version_change_records_a_new_row(
        self, monkeypatch, auditoria
    ):
        """
        Given: Un usuario que aceptó la versión anterior (B7)
        When: Cambia la vigente y vuelve a aceptar
        Then: Queda guardada la nueva, con otra fila; la de la anterior se conserva
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        anterior = terms_of_service.current_terms_version()
        await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))

        assert (await uow.users.find_by_id(user.id)).terms_version == "2099-01-01"
        assert respuesta.terms_accepted is True
        filas = _filas(uow, user.id)
        assert [fila.terms_version for fila in filas] == [anterior, "2099-01-01"]

    async def test_reaccepting_a_version_already_in_the_history_adds_no_row(
        self, monkeypatch, auditoria
    ):
        """
        Given: Un usuario que aceptó la versión A y luego la B, y el backend vuelve
            a la A (se revierte la constante)
        When: Acepta la A otra vez
        Then: Su estado vuelve a la A, pero no se añade otra fila de la A: la
            prueba ya está, y la base de datos no admite dos (UNIQUE)
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        version_a = terms_of_service.current_terms_version()
        await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")
        await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", version_a)

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))

        assert respuesta.terms_accepted is True
        assert (await uow.users.find_by_id(user.id)).terms_version == version_a
        filas = _filas(uow, user.id)
        assert [fila.terms_version for fila in filas] == [version_a, "2099-01-01"]

    async def test_accept_terms_unknown_user_raises(self, auditoria):
        """
        Given: Un id que no es de nadie
        When: Se intenta aceptar
        Then: UserNotFoundError
        """
        with pytest.raises(UserNotFoundError):
            await AcceptTermsUseCase(InMemoryUnitOfWork(), auditoria).execute(
                AcceptTermsRequestDTO(user_id="550e8400-e29b-41d4-a716-446655440000")
            )


@pytest.mark.asyncio
class TestRespuestaCompartida:
    @pytest.mark.parametrize("ya_aceptado", [False, True])
    async def test_accept_terms_response_matches_current_user(self, ya_aceptado, auditoria):
        """
        Given: Un usuario con Google vinculado, haya aceptado ya o no
        When: Acepta, y se pide current-user
        Then: Las dos respuestas son iguales, proveedores incluidos
        """
        uow = InMemoryUnitOfWork()
        user = _usuario()
        if ya_aceptado:
            user.accept_terms(terms_of_service.current_terms_version())
        await _guardado(uow, user)
        async with uow:
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=user.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="google-1",
                    provider_email="ana@example.com",
                )
            )

        sesion = await GetCurrentUserUseCase(uow).execute(str(user.id.value))

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user, sesion))
        actual = await GetCurrentUserUseCase(uow).execute(str(user.id.value))

        assert actual is not None
        assert respuesta.auth_providers == ["google"]
        assert respuesta.model_dump() == actual.model_dump()

    async def test_without_the_session_user_the_response_still_matches(self, auditoria):
        """
        Given: Un usuario con Google vinculado y una petición sin el usuario de la sesión
        When: Acepta
        Then: La respuesta lee sus cuentas OAuth y coincide con current-user
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        async with uow:
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=user.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="google-2",
                    provider_email="ana@example.com",
                )
            )

        respuesta = await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))
        actual = await GetCurrentUserUseCase(uow).execute(str(user.id.value))

        assert respuesta.auth_providers == ["google"]
        assert respuesta.model_dump() == actual.model_dump()


@pytest.mark.asyncio
class TestAuditoriaSoloTrasConfirmar:
    async def test_register_does_not_audit_when_the_commit_fails(self, auditoria):
        """
        Given: Un registro válido cuya transacción falla al confirmar
        When: Se ejecuta el caso de uso
        Then: Sale el error y no queda ninguna aceptación en el log de auditoría
        """
        uow = InMemoryUnitOfWork()
        uow.commit = AsyncMock(side_effect=RuntimeError("commit roto"))

        with pytest.raises(RuntimeError):
            await RegisterUserUseCase(uow, _countries(), security_audit=auditoria).execute(
                RegisterUserRequestDTO(**_REGISTRO, accept_terms=True)
            )

        auditoria.log_terms_accepted.assert_not_called()

    async def test_accept_terms_does_not_audit_when_the_commit_fails(self, auditoria):
        """
        Given: Un usuario sin aceptación y una transacción que falla al confirmar
        When: Acepta
        Then: Sale el error y no queda ninguna aceptación en el log de auditoría
        """
        uow = InMemoryUnitOfWork()
        user = await _guardado(uow, _usuario())
        uow.commit = AsyncMock(side_effect=RuntimeError("commit roto"))

        with pytest.raises(RuntimeError):
            await AcceptTermsUseCase(uow, auditoria).execute(_aceptar(user))

        auditoria.log_terms_accepted.assert_not_called()
