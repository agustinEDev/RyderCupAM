"""
Accept Terms Use Case - Application Layer

El usuario autenticado acepta la versión vigente de los Términos de uso.
"""

from src.modules.user.application.dto.user_dto import AcceptTermsRequestDTO, UserResponseDTO
from src.modules.user.application.services.current_user_response import (
    build_current_user_response,
)
from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.terms_of_service import current_terms_version
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.logging.security_logger import get_security_logger


class AcceptTermsUseCase:
    """
    Caso de uso: aceptar la versión vigente de los Términos.

    - Si ya la tiene aceptada, devuelve sin bloquear ni escribir nada
      (idempotente: la fecha sigue siendo la de la primera aceptación).
    - Si no, relee al usuario con SELECT ... FOR UPDATE, guarda la versión y
      la fecha, añade una fila al historial (con IP y navegador) y deja la
      aceptación en el log de auditoría de seguridad.

    La respuesta es la de current-user (`build_current_user_response`).
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, request: AcceptTermsRequestDTO) -> UserResponseDTO:
        """
        Acepta los Términos vigentes en nombre de ese usuario.

        Args:
            request: El usuario autenticado y la IP y el navegador de la petición

        Returns:
            El usuario, ya con los Términos aceptados

        Raises:
            UserNotFoundError: Si no existe
        """
        user_id = UserId(request.user_id)
        user = await self._uow.users.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {request.user_id} not found")

        if user.terms_accepted:
            return await build_current_user_response(self._uow, user)

        user, recorded = await self._accept(user_id, request)

        if recorded is not None:
            get_security_logger().log_terms_accepted(
                user_id=request.user_id,
                ip_address=request.ip_address or "unknown",
                user_agent=request.user_agent or "unknown",
                terms_version=recorded.terms_version,
            )

        return await build_current_user_response(self._uow, user)

    async def _accept(
        self, user_id: UserId, request: AcceptTermsRequestDTO
    ) -> tuple[User, TermsAcceptance | None]:
        """Con bloqueo: dos aceptaciones a la vez no se pisan la fecha ni duplican la fila."""
        async with self._uow:
            user = await self._uow.users.find_by_id_for_update(user_id)
            if not user:
                raise UserNotFoundError(f"User with id {request.user_id} not found")

            if not user.accept_terms(current_terms_version()):
                # Otra petición la aceptó mientras esperábamos el bloqueo
                return user, None

            accepted_at = user.terms_accepted_at
            if accepted_at is None:  # accept_terms acaba de ponerla
                raise RuntimeError("accept_terms no dejó fecha de aceptación")
            recorded = TermsAcceptance.record(
                user_id=user_id,
                terms_version=current_terms_version(),
                accepted_at=accepted_at,
                ip_address=request.ip_address,
                user_agent=request.user_agent,
            )
            await self._uow.users.save(user)
            await self._uow.terms_acceptances.save(recorded)

        return user, recorded
