# -*- coding: utf-8 -*-
"""
Competition Repository - SQLAlchemy Implementation.

Implementación concreta del repositorio de competiciones usando SQLAlchemy async.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyCompetitionRepository(CompetitionRepositoryInterface):
    """
    Implementación asíncrona del repositorio de competiciones con SQLAlchemy.

    Sigue el patrón Repository establecido en el módulo User.
    Maneja la persistencia de la entidad Competition usando async/await.
    """

    def __init__(self, session: AsyncSession):
        """
        Constructor del repositorio.

        Args:
            session: Sesión asíncrona de SQLAlchemy
        """
        self._session = session

    async def add(self, competition: Competition) -> None:
        """
        Agrega una nueva competición al repositorio.

        SQLAlchemy marcará el objeto para INSERT en el próximo flush/commit.

        Args:
            competition: Entidad Competition a guardar

        Note:
            El commit se maneja en el Unit of Work, no aquí.
        """
        self._session.add(competition)

    async def update(self, competition: Competition) -> None:
        """
        Actualiza una competición existente.

        SQLAlchemy detecta automáticamente los cambios en objetos trackeados.
        Si el objeto no está en la sesión, lo mergeamos.

        Args:
            competition: Entidad Competition con datos actualizados
        """
        self._session.add(competition)

    async def delete(self, competition_id: CompetitionId) -> bool:
        """
        Elimina una competición físicamente del repositorio.

        Args:
            competition_id: ID de la competición a eliminar

        Returns:
            bool: True si se eliminó, False si no existía
        """
        competition = await self.find_by_id(competition_id)
        if competition:
            await self._session.delete(competition)
            return True
        return False

    async def find_by_id(self, competition_id: CompetitionId) -> Optional[Competition]:
        """
        Busca una competición por su ID único.

        Args:
            competition_id: ID de la competición

        Returns:
            Optional[Competition]: La competición encontrada o None
        """
        return await self._session.get(Competition, competition_id)

    async def find_by_creator(
        self,
        creator_id: UserId,
        limit: int = 100,
        offset: int = 0
    ) -> List[Competition]:
        """
        Busca todas las competiciones creadas por un usuario.

        Args:
            creator_id: ID del usuario creador
            limit: Número máximo de resultados (paginación)
            offset: Número de resultados a saltar (paginación)

        Returns:
            List[Competition]: Lista de competiciones del creador
        """
        statement = (
            select(Competition)
            .where(Competition.creator_id == creator_id)
            .order_by(Competition.created_at.desc())  # Más recientes primero
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_status(
        self,
        status: CompetitionStatus,
        limit: int = 100,
        offset: int = 0
    ) -> List[Competition]:
        """
        Busca todas las competiciones con un estado específico.

        Args:
            status: Estado de la competición (enum)
            limit: Número máximo de resultados
            offset: Número de resultados a saltar

        Returns:
            List[Competition]: Lista de competiciones con el estado especificado

        Note:
            Usamos el atributo privado _status_value porque status es un composite.
        """
        statement = (
            select(Competition)
            .where(Competition._status_value == status.value)
            .order_by(Competition.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_active_in_date_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[Competition]:
        """
        Busca competiciones activas que se superpongan con un rango de fechas.

        La query busca competiciones donde:
        - Status sea ACTIVE, CLOSED, IN_PROGRESS (estados "activos")
        - Las fechas se superpongan con el rango dado

        Solapamiento de rangos:
        - comp.start_date <= end_date AND comp.end_date >= start_date

        Args:
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango

        Returns:
            List[Competition]: Competiciones activas en el rango
        """
        # Estados considerados "activos" (no DRAFT, CANCELLED, COMPLETED)
        active_statuses = [
            CompetitionStatus.ACTIVE.value,
            CompetitionStatus.CLOSED.value,
            CompetitionStatus.IN_PROGRESS.value,
        ]

        statement = (
            select(Competition)
            .where(
                and_(
                    Competition._status_value.in_(active_statuses),
                    Competition._start_date <= end_date,
                    Competition._end_date >= start_date
                )
            )
            .order_by(Competition._start_date.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def exists_with_name(
        self,
        name: CompetitionName,
        creator_id: UserId
    ) -> bool:
        """
        Verifica si existe una competición con el nombre especificado para un creador.

        Previene duplicados del mismo creador con el mismo nombre.

        Args:
            name: Nombre de la competición (Value Object)
            creator_id: ID del usuario creador

        Returns:
            bool: True si existe, False si no existe

        Note:
            Usamos _name_value (atributo privado) porque name es un composite.
        """
        statement = (
            select(func.count())
            .select_from(Competition)
            .where(
                and_(
                    Competition._name_value == str(name),
                    Competition.creator_id == creator_id
                )
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Competition]:
        """
        Obtiene todas las competiciones con paginación.

        Args:
            limit: Número máximo de resultados (paginación)
            offset: Número de resultados a saltar (paginación)

        Returns:
            List[Competition]: Lista de todas las competiciones
        """
        statement = (
            select(Competition)
            .order_by(Competition.created_at.desc())  # Más recientes primero
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_by_creator(self, creator_id: UserId) -> int:
        """
        Cuenta el total de competiciones creadas por un usuario.

        Args:
            creator_id: ID del usuario creador

        Returns:
            int: Número total de competiciones
        """
        statement = (
            select(func.count())
            .select_from(Competition)
            .where(Competition.creator_id == creator_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one()
