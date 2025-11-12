import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO, UserResponseDTO
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.errors.handicap_errors import HandicapServiceError
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.shared.infrastructure.email.email_service import email_service


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
        handicap_service: Optional[HandicapService] = None
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._handicap_service = handicap_service

    async def execute(self, request: RegisterUserRequestDTO) -> UserResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: DTO con la información para el registro.

        Returns:
            DTO con la información del usuario recién creado.

        Raises:
            UserAlreadyExistsError: Si el correo electrónico ya está en uso.
        """
        async with self._uow:
            # 1. Validar que el email no existe
            email_vo = Email(request.email)
            if await self._user_finder.by_email(email_vo):
                raise UserAlreadyExistsError(f"El email '{request.email}' ya está registrado.")

            # 2. Crear la entidad de dominio User
            new_user = User.create(
                email_str=request.email,
                plain_password=request.password,
                first_name=request.first_name,
                last_name=request.last_name,
            )

            # 2.5 Intentar buscar hándicap inicial (no bloquea el registro)
            handicap_value = None
            if self._handicap_service:
                try:
                    handicap_value = await self._handicap_service.search_handicap(
                        new_user.get_full_name()
                    )
                except HandicapServiceError as e:
                    # No falla el registro si no se encuentra el hándicap
                    logger.warning("No se pudo obtener hándicap inicial para %s: %s", new_user.get_full_name(), e)

            # 2.6 Si no se encontró en RFEG, usar hándicap manual si fue proporcionado
            if handicap_value is None and request.manual_handicap is not None:
                handicap_value = request.manual_handicap

            # 2.7 Actualizar hándicap si se obtuvo uno (de RFEG o manual)
            if handicap_value is not None:
                new_user.update_handicap(handicap_value)

            # 2.8 Generar token de verificación de email
            verification_token = new_user.generate_verification_token()

            # 3. Guardar el usuario en el repositorio
            await self._uow.users.save(new_user)

            # El context manager (__aexit__) hace commit automático y publica eventos

        # 4. Enviar email de verificación
        try:
            email_sent = email_service.send_verification_email(
                to_email=request.email,
                user_name=new_user.first_name,
                verification_token=verification_token
            )
            if not email_sent:
                logger.warning(
                    "No se pudo enviar el email de verificación para el usuario %s",
                    new_user.id.value
                )
        except (requests.RequestException, ValueError, ConnectionError) as e:
            # Capturar excepciones específicas de red y validación
            logger.exception(
                "Error al enviar email de verificación para el usuario %s",
                new_user.id.value
            )
            # No fallar el registro si el email no se pudo enviar

        # 5. Devolver la respuesta como DTO
        return UserResponseDTO.model_validate(new_user)
