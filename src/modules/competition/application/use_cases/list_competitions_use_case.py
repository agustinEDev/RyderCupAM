# -*- coding: utf-8 -*-
"""
Caso de Uso: Listar Competitions con filtros.

Permite obtener lista de competiciones con filtros opcionales.
"""

from typing import List, Optional
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus


class ListCompetitionsUseCase:
    """
    Caso de uso para listar competiciones con filtros opcionales.

    CLEAN ARCHITECTURE: Este use case retorna ENTIDADES de dominio, NO DTOs.
    La conversión a DTOs y el cálculo de campos de presentación (is_creator,
    enrolled_count, location_formatted) es responsabilidad de la capa de
    presentación (API Layer).

    Orquesta:
    1. Aplicar filtros opcionales (status, creator_id)
    2. Retornar lista de entidades Competition

    Responsabilidades:
    - Filtrado por criterios de negocio
    - Coordinar acceso a repositorios mediante UoW

    NO es responsabilidad del use case:
    - Formatear datos para presentación
    - Calcular campos derivados para UI
    - Convertir entidades a DTOs
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para acceso a repositorios
        """
        self._uow = uow

    async def execute(
        self,
        status: Optional[str] = None,
        creator_id: Optional[str] = None,
    ) -> List[Competition]:
        """
        Ejecuta el caso de uso de listado de competiciones.

        Args:
            status: Filtro opcional por estado (ej: "ACTIVE", "DRAFT")
            creator_id: Filtro opcional por creador (UUID string)

        Returns:
            Lista de entidades Competition

        Raises:
            ValueError: Si los parámetros de filtro son inválidos
        """
        async with self._uow:
            # Obtener competiciones según filtros
            competitions = await self._fetch_filtered_competitions(status, creator_id)
            return competitions

    async def _fetch_filtered_competitions(
        self,
        status: Optional[str],
        creator_id: Optional[str],
    ) -> List[Competition]:
        """
        Obtiene competiciones aplicando filtros.

        Args:
            status: Filtro por estado (opcional)
            creator_id: Filtro por creador (opcional)

        Returns:
            Lista de entidades Competition
        """
        # Si hay filtro por status
        if status:
            status_enum = CompetitionStatus(status.upper())
            competitions = await self._uow.competitions.find_by_status(status_enum)

            # Si además hay filtro por creator_id, filtrar en memoria
            if creator_id:
                creator_user_id = UserId(creator_id)
                competitions = [
                    c for c in competitions if c.creator_id == creator_user_id
                ]

            return competitions

        # Si solo hay filtro por creator_id
        if creator_id:
            creator_user_id = UserId(creator_id)
            return await self._uow.competitions.find_by_creator(creator_user_id)

        # Sin filtros: retornar todas las competiciones
        return await self._uow.competitions.find_all()
