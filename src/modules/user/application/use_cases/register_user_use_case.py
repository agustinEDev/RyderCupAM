import logging

import requests

from src.modules.user.application.dto.user_dto import (
    RegisterUserRequestDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.handicap_errors import HandicapServiceError
from src.modules.user.domain.errors.user_errors import (
    TermsAcceptanceRequiredError,
    UserAlreadyExistsError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.services.terms_of_service import current_terms_version
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.infrastructure.security.bcrypt_executor import run_bcrypt

logger = logging.getLogger(__name__)


class RegisterUserUseCase:
    """
    Caso de uso para registrar un nuevo usuario en el sistema.
    Orquesta la creación, validación y persistencia de un usuario.

    Opcionalmente, puede buscar el hándicap inicial del usuario
    si se proporciona un HandicapService.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        country_repository: CountryRepositoryInterface,
        handicap_service: HandicapService | None = None,
        email_service: IEmailService | None = None,
        *,
        security_audit: ISecurityAuditLogger,
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._country_repository = country_repository
        self._handicap_service = handicap_service
        self._email_service = email_service
        self._security_audit = security_audit

    async def execute(self, request: RegisterUserRequestDTO) -> UserResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: DTO con la información para el registro.

        Returns:
            DTO con la información del usuario recién creado.

        Raises:
            UserAlreadyExistsError: Si el correo electrónico ya está en uso.
            TermsAcceptanceRequiredError: Si no trae accept_terms exactamente True.
        """
        # Sin consentimiento explícito no hay alta. La API ya da 422, pero el
        # caso de uso no se fía de que el request llegue validado (p. ej. uno
        # construido con model_construct): solo vale el booleano True
        if getattr(request, "accept_terms", None) is not True:
            raise TermsAcceptanceRequiredError(
                "Para registrarse hay que aceptar los Términos de uso vigentes."
            )

        async with self._uow:
            # 1. Validar que el email no existe
            email_vo = Email(request.email)
            if await self._user_finder.by_email(email_vo):
                raise UserAlreadyExistsError(f"El email '{request.email}' ya está registrado.")

            # 1.5 Validar que el country_code existe (si se proporcionó)
            if request.country_code:
                country_code_vo = CountryCode(request.country_code)
                country_exists = await self._country_repository.exists(country_code_vo)
                if not country_exists:
                    raise ValueError(f"El código de país '{request.country_code}' no es válido.")

            # 2. Crear la entidad de dominio User
            gender = Gender(request.gender) if request.gender else None
            new_user = await run_bcrypt(
                User.create,
                email_str=request.email,
                plain_password=request.password,
                first_name=request.first_name,
                last_name=request.last_name,
                country_code_str=request.country_code,
                gender=gender,
            )

            # 2.1 Los Términos: se guarda la versión vigente con la fecha de
            # ahora, y la aceptación va al historial con la IP y el navegador
            terms_version = current_terms_version()
            new_user.accept_terms(terms_version)
            accepted_at = new_user.terms_accepted_at
            if accepted_at is None:  # accept_terms acaba de ponerla
                raise RuntimeError("accept_terms no dejó fecha de aceptación")
            terms_acceptance = TermsAcceptance.record(
                user_id=new_user.id,
                user_email=new_user.email.value,
                terms_version=terms_version,
                accepted_at=accepted_at,
                ip_address=request.ip_address,
                user_agent=request.user_agent,
            )

            # 2.5 Intentar buscar hándicap inicial (solo para usuarios españoles)
            handicap_value = None
            if (
                self._handicap_service
                and new_user.country_code
                and new_user.country_code.value == "ES"
            ):
                try:
                    handicap_value = await self._handicap_service.search_handicap(
                        new_user.get_full_name()
                    )
                except HandicapServiceError as e:
                    # No falla el registro si no se encuentra el hándicap
                    logger.warning(
                        "No se pudo obtener hándicap inicial para %s: %s",
                        new_user.get_full_name(),
                        e,
                    )

            # 2.6 Si no se encontró en RFEG, usar hándicap manual si fue proporcionado
            if handicap_value is None and request.manual_handicap is not None:
                handicap_value = request.manual_handicap

            # 2.7 Actualizar hándicap si se obtuvo uno (de RFEG o manual)
            if handicap_value is not None:
                new_user.update_handicap(handicap_value)

            # 2.8 Generar token de verificación de email
            verification_token = new_user.generate_verification_token()

            # 3. Guardar el usuario en el repositorio, y después su aceptación
            # (la fila apunta al usuario: tiene que existir antes)
            await self._uow.users.save(new_user)
            await self._uow.flush()
            await self._uow.terms_acceptances.save(terms_acceptance)

            # El context manager (__aexit__) hace commit automático y publica eventos

        # 3.5 Auditoría de seguridad: la aceptación de los Términos
        self._security_audit.log_terms_accepted(
            user_id=str(new_user.id.value),
            ip_address=request.ip_address or "unknown",
            user_agent=request.user_agent or "unknown",
            terms_version=terms_acceptance.terms_version,
        )

        # 4. Enviar email de verificación
        if self._email_service:
            try:
                email_sent = self._email_service.send_verification_email(
                    to_email=request.email,
                    user_name=new_user.first_name,
                    verification_token=verification_token,
                )
                if not email_sent:
                    logger.warning(
                        "No se pudo enviar el email de verificación para el usuario %s",
                        new_user.id.value,
                    )
            except (requests.RequestException, ValueError, ConnectionError):
                # Capturar excepciones específicas de red y validación
                logger.exception(
                    "Error al enviar email de verificación para el usuario %s",
                    new_user.id.value,
                )
                # No fallar el registro si el email no se pudo enviar

        # 5. Devolver la respuesta como DTO
        return UserResponseDTO.model_validate(new_user)
