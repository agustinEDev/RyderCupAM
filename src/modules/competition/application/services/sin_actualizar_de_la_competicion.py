"""
SinActualizarDeLaCompeticion - Quién se quedó sin actualizar con la RFEG en una competición.

Decidido con Agustín el 15 nov 2026 (H1-H6). La misma regla para la pasada,
que avisa al terminar, y para «Requiere tu Atención», que lo enseña mientras
siga siendo cierto. La decisión está en el dominio
(`sin_actualizar_con_la_rfeg`); aquí solo se reúne lo que necesita.
"""

from collections.abc import Iterable, Mapping

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import Intento
from src.modules.competition.domain.services.sin_actualizar_con_la_rfeg import (
    Inscrito,
    SinActualizar,
    sin_actualizar,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

ESPANA = "ES"

# Terminadas: la pasada ya dijo lo suyo (H1)
_TERMINADAS = (EstadoActualizacion.COMPLETA, EstadoActualizacion.INCOMPLETA)


def _en_espana(competicion: Competition) -> bool:
    return competicion.location.main_country.value == ESPANA


def es_espanol(usuario: User) -> bool:
    """Nacionalidad española en su perfil; sin nacionalidad, no."""
    return usuario.country_code is not None and usuario.country_code.value == ESPANA


class SinActualizarDeLaCompeticion:
    """Lee la competición, sus inscritos y lo apuntado, y decide."""

    @staticmethod
    async def de(
        uow: CompetitionUnitOfWorkInterface,
        usuarios: UserRepositoryInterface,
        competicion: Competition,
        actualizacion: ActualizacionDeHandicaps,
    ) -> SinActualizar:
        inscritos = await uow.enrollments.find_by_competition_and_status(
            competicion.id, EnrollmentStatus.APPROVED
        )
        por_id = {u.id: u for u in await usuarios.find_by_ids([i.user_id for i in inscritos])}
        resultados = await uow.handicap_updates.resultados(actualizacion.id)
        return SinActualizarDeLaCompeticion.de_lo_leido(
            competicion, actualizacion, inscritos, por_id, resultados
        )

    @staticmethod
    def de_lo_leido(
        competicion: Competition,
        actualizacion: ActualizacionDeHandicaps,
        inscritos: Iterable[Enrollment],
        por_id: Mapping[UserId, User],
        resultados: Mapping[UserId, Intento],
    ) -> SinActualizar:
        """
        Lo mismo, con lo ya leído: los inscritos aprobados, sus usuarios por id
        y lo apuntado en la actualización.
        """
        return sin_actualizar(
            [
                Inscrito(
                    user_id=i.user_id,
                    handicap_personalizado=i.has_custom_handicap(),
                    existe=i.user_id in por_id,
                    espanol=i.user_id in por_id and es_espanol(por_id[i.user_id]),
                )
                for i in inscritos
            ],
            resultados,
            en_espana=_en_espana(competicion),
            completa=actualizacion.estado is EstadoActualizacion.COMPLETA,
        )

    @staticmethod
    async def no_encontrado(
        uow: CompetitionUnitOfWorkInterface,
        jugador: User,
        inscripcion: Enrollment,
        competicion: Competition,
        actualizacion: ActualizacionDeHandicaps,
    ) -> bool:
        """
        Si a este jugador le toca el aviso de no encontrado, leyendo solo lo suyo
        (T2): el panel lo pregunta cada vez que alguien entra.
        """
        intento = await uow.handicap_updates.resultado_de(actualizacion.id, jugador.id)
        hecho = sin_actualizar(
            [
                Inscrito(
                    user_id=jugador.id,
                    handicap_personalizado=inscripcion.has_custom_handicap(),
                    existe=True,
                    espanol=es_espanol(jugador),
                )
            ],
            {} if intento is None else {jugador.id: intento},
            en_espana=_en_espana(competicion),
            completa=actualizacion.estado is EstadoActualizacion.COMPLETA,
        )
        return jugador.id in hecho.no_encontrados

    @staticmethod
    def terminada(actualizacion: ActualizacionDeHandicaps) -> bool:
        """
        Si la pasada ya dijo lo suyo (H1). Una incompleta que se vuelve a pasar
        ya terminó antes: se sigue enseñando lo de entonces mientras tanto.
        """
        if actualizacion.estado in _TERMINADAS:
            return True
        return actualizacion.estado is EstadoActualizacion.EN_CURSO and (
            actualizacion.reanudada is not None
        )
