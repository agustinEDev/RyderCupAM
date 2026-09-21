"""
EnrollmentOpener - Abrir una competicion programada, en un solo sitio.

Una competicion con apertura programada espera en DRAFT hasta que su momento
pasa, y **quien la abre es quien la mira**: no hay ningun proceso de fondo, igual
que no lo hay para la anotacion que se abre a la hora de su sesion (BE #305).

«Mirarla» son dos caminos, no uno: abrir su ficha y verla en un listado. El
segundo hacia falta porque una competicion que anuncia «abre el martes» y sigue
apareciendo cerrada el miercoles esta mintiendo, y hasta ahora solo abria la
ficha (BE #331).

Duplicar los pasos habria sido peligroso por lo de siempre: un camino que abra
sin persistir deja la competicion abierta en memoria y cerrada en la base de
datos, y el siguiente que mire la vuelve a encontrar en borrador.
"""

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)


class EnrollmentOpener:
    """Abre las inscripciones de las competiciones a las que ya les toca."""

    @staticmethod
    async def abrir_las_que_toquen(
        competitions: list[Competition],
        uow: CompetitionUnitOfWorkInterface,
        zona_del_campo: ICompetitionTimezone | None,
    ) -> None:
        """Abre las que ya pasaron su momento, y deja el resto como estaban.

        Args:
            competitions: Las competiciones que se acaban de leer.
            uow: Para persistir la apertura. Se usa dentro de la transaccion de
                quien llama, que es quien hace el commit.
            zona_del_campo: De donde sale la zona horaria del campo que se juega.
                `None` desactiva la apertura — util para construir el caso de uso
                sin ella.
        """
        if zona_del_campo is None:
            return

        for competition in competitions:
            await EnrollmentOpener._abrir_si_toca(competition, uow, zona_del_campo)

    @staticmethod
    async def _abrir_si_toca(
        competition: Competition,
        uow: CompetitionUnitOfWorkInterface,
        zona_del_campo: ICompetitionTimezone,
    ) -> None:
        """Abre una, si le toca.

        La hora es local del campo donde se juega, asi que hace falta su zona.
        Sin campo todavia —o con uno cuya zona no se conoce— el torneo espera:
        no se adivina, porque abrir a deshora anuncia una cosa y hace otra
        (decidido el 20 sep).
        """
        # Las dos preguntas baratas ANTES de resolver la zona, que baja a la
        # base de datos: en un listado de hasta 100 eso seria el N+1 que BE #330
        # ya tuvo que arreglar una vez.
        #
        # La segunda no es redundante aunque `due_to_open` tambien mire el
        # estado, porque `due_to_open` lo mira DESPUES de haber pagado la
        # consulta. Y hace falta: abrir una competicion borra sus dias, pero
        # CANCELARLA no, asi que una cancelada se queda con los dias puestos
        # para siempre y sin esto pagaria la consulta en cada listado, siempre,
        # para acabar descartandola
        if competition.enrollment_opens_days_before is None:
            return
        if not competition.allows_enrollment_opening():
            return

        zona = await zona_del_campo.for_competition(competition)
        if not competition.due_to_open(zona):
            return

        competition.activate()
        await uow.competitions.update(competition)
