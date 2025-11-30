"""
Shared Domain Repositories - Interfaces compartidas de repositorio

Exporta las interfaces de repositorio que pueden ser utilizadas por múltiples módulos,
especialmente el patrón Unit of Work.
"""

from .unit_of_work_interface import UnitOfWorkInterface

__all__ = [
    "UnitOfWorkInterface",
]
