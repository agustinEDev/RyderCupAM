"""
User Domain Repositories - Interfaces de persistencia

Exporta las interfaces de repositorio definidas en la capa de dominio.
Estas interfaces serán implementadas en la capa de infraestructura.
"""

from .user_repository_interface import UserRepositoryInterface
from .user_unit_of_work_interface import UserUnitOfWorkInterface

__all__ = [
    "UserRepositoryInterface",
    "UserUnitOfWorkInterface",
]
