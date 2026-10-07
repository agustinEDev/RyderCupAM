"""Las actualizaciones de hándicaps y sus resultados, en Postgres (#251)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.repositories.handicap_update_repository_interface import (
    HandicapUpdateRepositoryInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    handicap_refreshes_table,
    handicap_updates_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyHandicapUpdateRepository(HandicapUpdateRepositoryInterface):
    """Una fila por actualización, y una por actualización y jugador con sus intentos."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, actualizacion: ActualizacionDeHandicaps) -> None:
        await self._session.execute(
            handicap_updates_table.insert().values(**self._fila(actualizacion))
        )

    async def update(self, actualizacion: ActualizacionDeHandicaps) -> None:
        tabla = handicap_updates_table
        await self._session.execute(
            tabla.update()
            .where(tabla.c.id == str(actualizacion.id))
            .values(status=str(actualizacion.estado), finished_at=actualizacion.terminada)
        )

    async def find_by_id(self, update_id: uuid.UUID) -> ActualizacionDeHandicaps | None:
        tabla = handicap_updates_table
        fila = (
            await self._session.execute(select(tabla).where(tabla.c.id == str(update_id)))
        ).first()
        return None if fila is None else self._entidad(fila)

    async def ultima_de(self, competition_id: CompetitionId) -> ActualizacionDeHandicaps | None:
        tabla = handicap_updates_table
        fila = (
            await self._session.execute(
                select(tabla)
                .where(tabla.c.competition_id == competition_id)
                # Con desempate: dos creadas en el mismo instante no quedan al azar
                .order_by(tabla.c.created_at.desc(), tabla.c.id.desc())
                .limit(1)
            )
        ).first()
        return None if fila is None else self._entidad(fila)

    async def resultados(self, update_id: uuid.UUID) -> dict[UserId, Intento]:
        tabla = handicap_refreshes_table
        result = await self._session.execute(
            select(tabla.c.user_id, tabla.c.result, tabla.c.attempts).where(
                tabla.c.update_id == str(update_id)
            )
        )
        return {
            fila.user_id: Intento(ResultadoRefresco(fila.result), fila.attempts) for fila in result
        }

    async def apuntar(
        self,
        update_id: uuid.UUID,
        user_id: UserId,
        resultado: ResultadoRefresco,
        momento: datetime,
    ) -> None:
        tabla = handicap_refreshes_table
        fila = insert(tabla).values(
            update_id=str(update_id),
            user_id=user_id,
            result=str(resultado),
            attempts=1,
            refreshed_at=momento,
        )
        await self._session.execute(
            fila.on_conflict_do_update(
                index_elements=[tabla.c.update_id, tabla.c.user_id],
                set_={
                    "result": fila.excluded.result,
                    "attempts": tabla.c.attempts + 1,
                    "refreshed_at": fila.excluded.refreshed_at,
                },
            )
        )

    @staticmethod
    def _fila(actualizacion: ActualizacionDeHandicaps) -> dict:
        return {
            "id": str(actualizacion.id),
            "competition_id": actualizacion.competition_id,
            "origin": str(actualizacion.origen),
            "status": str(actualizacion.estado),
            "created_at": actualizacion.creada,
            "finished_at": actualizacion.terminada,
        }

    @staticmethod
    def _entidad(fila) -> ActualizacionDeHandicaps:
        return ActualizacionDeHandicaps(
            id=uuid.UUID(fila.id),
            competition_id=fila.competition_id,
            origen=OrigenActualizacion(fila.origin),
            estado=EstadoActualizacion(fila.status),
            creada=fila.created_at,
            terminada=fila.finished_at,
        )
