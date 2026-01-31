"""
Authorization Helpers - Sistema centralizado de control de acceso (RBAC).

Este módulo provee funciones reutilizables para verificar permisos de usuarios
según el modelo de roles contextual del sistema.

RBAC Model:
- ADMIN (Global): is_admin = TRUE - Gestiona campos de golf, aprueba solicitudes, override
- CREATOR (Contextual): competition.creator_id == user.id - Gestiona SUS competiciones
- PLAYER (Contextual): enrollment.user_id == user.id AND status = APPROVED - Participa

Design Patterns:
- Guard Functions: Verifican permisos y lanzan HTTPException si falla
- Pure Functions: Funciones sin efectos secundarios (solo lectura)
- Dependency Injection: UoW se inyecta vía FastAPI Depends

Usage:
    from fastapi import Depends, HTTPException
    from src.shared.infrastructure.security.authorization import require_admin

    @router.delete("/admin/users/{user_id}")
    async def delete_user(user_id: str, current_user: User = Depends(get_current_user)):
        require_admin(current_user)  # Lanza 403 si no es admin
        # ... resto de lógica
"""

from fastapi import HTTPException, status

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

# ===========================================
# PURE AUTHORIZATION FUNCTIONS (No side effects)
# ===========================================


def is_admin(user: UserResponseDTO) -> bool:
    """
    Verifica si el usuario es administrador del sistema (rol global).

    Args:
        user: Usuario actual autenticado (DTO)

    Returns:
        bool: True si el usuario tiene is_admin = TRUE

    Example:
        >>> admin_user = UserResponseDTO(..., is_admin=True)
        >>> is_admin(admin_user)
        True
        >>> regular_user = UserResponseDTO(..., is_admin=False)
        >>> is_admin(regular_user)
        False
    """
    return user.is_admin


def is_creator_of(user: UserResponseDTO, competition: Competition) -> bool:
    """
    Verifica si el usuario es el creador de una competición (rol contextual).

    Args:
        user: Usuario actual autenticado (DTO)
        competition: Competición a verificar

    Returns:
        bool: True si competition.creator_id == user.id

    Example:
        >>> creator = UserResponseDTO(id="123...", ...)
        >>> comp = Competition(creator_id=UserId("123..."), ...)
        >>> is_creator_of(creator, comp)
        True
        >>> other_user = UserResponseDTO(id="456...", ...)
        >>> is_creator_of(other_user, comp)
        False
    """
    return competition.is_creator(UserId(str(user.id)))


async def is_player_in(user_id: UserId, competition_id: CompetitionId, uow) -> bool:
    """
    Verifica si el usuario está enrollado en una competición (rol contextual).

    Args:
        user_id: ID del usuario a verificar
        competition_id: ID de la competición
        uow: Unit of Work para acceder al repositorio de enrollments

    Returns:
        bool: True si existe enrollment con user_id y status = APPROVED

    Note:
        Esta función es async porque consulta la base de datos.

    Example:
        >>> async with uow:
        ...     is_player = await is_player_in(user_id, comp_id, uow)
        ...     if is_player:
        ...         print("User is enrolled!")
    """
    enrollment = await uow.enrollments.find_by_user_and_competition(
        user_id=user_id, competition_id=competition_id
    )

    if enrollment is None:
        return False

    return enrollment.status == EnrollmentStatus.APPROVED


def can_modify_competition(user: UserResponseDTO, competition: Competition) -> bool:
    """
    Verifica si el usuario puede modificar una competición.

    Puede modificar si:
    - Es administrador del sistema (ADMIN), o
    - Es el creador de la competición (CREATOR)

    Args:
        user: Usuario actual autenticado (DTO)
        competition: Competición a verificar

    Returns:
        bool: True si puede modificar la competición

    Example:
        >>> admin = UserResponseDTO(..., is_admin=True)
        >>> creator = UserResponseDTO(id="123...", is_admin=False)
        >>> comp = Competition(creator_id=UserId("123..."), ...)
        >>> can_modify_competition(admin, comp)  # Admin override
        True
        >>> can_modify_competition(creator, comp)  # Creator owns it
        True
        >>> other = UserResponseDTO(id="999...", is_admin=False)
        >>> can_modify_competition(other, comp)  # Not authorized
        False
    """
    return is_admin(user) or is_creator_of(user, competition)


# ===========================================
# GUARD FUNCTIONS (Raises HTTPException)
# ===========================================


def require_admin(user: UserResponseDTO) -> None:
    """
    Guard que requiere privilegios de administrador.

    Lanza HTTPException 403 si el usuario no es admin.

    Args:
        user: Usuario actual autenticado (DTO)

    Raises:
        HTTPException: 403 Forbidden si user.is_admin = False

    Example:
        >>> @router.delete("/admin/users/{user_id}")
        ... async def delete_user(current_user: UserResponseDTO = Depends(get_current_user)):
        ...     require_admin(current_user)
        ...     # ... lógica solo para admins
    """
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have administrator privileges",
        )


def require_creator_or_admin(user: UserResponseDTO, competition: Competition) -> None:
    """
    Guard que requiere ser creador de la competición o administrador.

    Lanza HTTPException 403 si el usuario no puede modificar la competición.

    Args:
        user: Usuario actual autenticado (DTO)
        competition: Competición a verificar

    Raises:
        HTTPException: 403 Forbidden si no es creator ni admin

    Example:
        >>> @router.put("/competitions/{id}")
        ... async def update_competition(
        ...     id: str,
        ...     current_user: UserResponseDTO = Depends(get_current_user),
        ...     uow = Depends(get_competition_uow)
        ... ):
        ...     async with uow:
        ...         comp = await uow.competitions.find_by_id(CompetitionId(id))
        ...         require_creator_or_admin(current_user, comp)
        ...         # ... lógica de actualización
    """
    if not can_modify_competition(user, competition):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the competition creator or an administrator can perform this action",
        )


async def require_player_in_competition(
    user: UserResponseDTO, competition_id: CompetitionId, uow
) -> None:
    """
    Guard que requiere estar enrollado en la competición.

    Lanza HTTPException 403 si el usuario no está enrollado con status APPROVED.

    Args:
        user: Usuario actual autenticado (DTO)
        competition_id: ID de la competición
        uow: Unit of Work para acceder al repositorio

    Raises:
        HTTPException: 403 Forbidden si no está enrollado

    Note:
        Esta función es async porque consulta la base de datos.

    Example:
        >>> @router.post("/matches/{match_id}/scores/holes/{hole_number}")
        ... async def submit_score(
        ...     match_id: str,
        ...     current_user: UserResponseDTO = Depends(get_current_user),
        ...     uow = Depends(get_competition_uow)
        ... ):
        ...     async with uow:
        ...         await require_player_in_competition(current_user, comp_id, uow)
        ...         # ... lógica de scoring (solo jugadores enrollados)
    """
    is_player = await is_player_in(UserId(str(user.id)), competition_id, uow)

    if not is_player:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only enrolled players in this competition can perform this action",
        )
