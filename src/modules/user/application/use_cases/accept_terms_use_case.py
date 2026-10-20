"""
Accept Terms Use Case - Application Layer

El usuario autenticado acepta la versión vigente de los Términos de uso.
"""

from src.modules.user.application.dto.user_dto import AcceptTermsRequestDTO, UserResponseDTO
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
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


class AcceptTermsUseCase:
    """
    Caso de uso: aceptar la versión vigente de los Términos.

    - Si el usuario de la sesión ya la tiene aceptada, se responde con él: ni
      lecturas, ni bloqueo, ni escritura (idempotente: la fecha sigue siendo
      la de la primera aceptación).
    - Si no, se lee una sola vez y con SELECT ... FOR UPDATE, se guarda la
      versión y la fecha, se añade la fila al historial si no la tenía (una por
      versión) y, tras confirmar, la aceptación va al log de auditoría.

    La respuesta es la de current-user (`build_current_user_response`).
    """

    def __init__(self, uow: UserUnitOfWorkInterface, security_audit: ISecurityAuditLogger):
        self._uow = uow
        self._security_audit = security_audit

    async def execute(self, request: AcceptTermsRequestDTO) -> UserResponseDTO:
        """
        Acepta los Términos vigentes en nombre de ese usuario.

        Args:
            request: El usuario autenticado (y el de la sesión, si se tiene) y
                la IP y el navegador de la petición

        Returns:
            El usuario, ya con los Términos aceptados

        Raises:
            UserNotFoundError: Si no existe
        """
        session_user = request.current_user
        if session_user is not None and session_user.terms_accepted:
            return session_user

        user, recorded = await self._accept(UserId(request.user_id), request)

        if recorded is not None:
            self._security_audit.log_terms_accepted(
                user_id=request.user_id,
                ip_address=request.ip_address or "unknown",
                user_agent=request.user_agent or "unknown",
                terms_version=recorded.terms_version,
            )

        known_providers = session_user.auth_providers if session_user is not None else None
        return await build_current_user_response(self._uow, user, known_providers)

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
            if accepted_at is None or user.email is None:  # solo para el tipo
                raise RuntimeError("usuario sin fecha de aceptación o sin email")
            recorded = TermsAcceptance.record(
                user_id=user_id,
                user_email=user.email.value,
                terms_version=current_terms_version(),
                accepted_at=accepted_at,
                ip_address=request.ip_address,
                user_agent=request.user_agent,
            )
            await self._uow.users.save(user)
            # Una fila por versión (UNIQUE en la BD): si ya aceptó esta versión
            # antes (la constante volvió atrás), la prueba ya está en el historial
            if not await self._uow.terms_acceptances.has_accepted(user_id, recorded.terms_version):
                await self._uow.terms_acceptances.save(recorded)

        return user, recorded
