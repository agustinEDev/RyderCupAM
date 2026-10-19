"""
Completar el género de la barra en los partidos de Ryder SCRATCH ya generados
(RyderCupWeb #880).

Hasta RyderCupAM #579 una Ryder SCRATCH no leía ni el campo ni a los jugadores al
generar los partidos, y todos se guardaban sin el género de su barra: veían la
tarjeta de referencia en vez de la de su barra, y el mapa del hoyo no sabía de
qué barra era cada muestra. Los partidos nuevos ya salen bien; estos se
completan sin regenerarlos, porque regenerar borra y crea los partidos (ids
nuevos, sobres, walkovers) y no alcanza a las rondas ya en juego.

Con la misma regla que la generación (`barra_sin_golpes`), sobre el color que ya
tiene cada uno. Solo a quien no tiene género, y nada más cambia: repetirlo no
hace nada. Las rondas y los partidos terminados no se tocan: se jugaron con esa
tarjeta.
"""

from dataclasses import dataclass, field

from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import barra_sin_golpes
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

COMPETICIONES_POR_PAGINA = 200
# Las terminadas se jugaron con la tarjeta que tenían: no se cambia a toro pasado
SE_COMPLETAN = (RoundStatus.SCHEDULED, RoundStatus.IN_PROGRESS)


@dataclass(frozen=True)
class RondaCompletada:
    competicion: str
    round_id: str
    jugadores: int


@dataclass
class ResumenDelCompletado:
    rondas: list[RondaCompletada] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def jugadores(self) -> int:
        return sum(r.jugadores for r in self.rondas)


class CompletarGeneroDeLasBarrasUseCase:
    """Pone el género de su barra a los jugadores de Ryder SCRATCH que no lo tienen."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
    ):
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository

    async def execute(self, dry_run: bool) -> ResumenDelCompletado:
        resumen = ResumenDelCompletado()
        # Copias de lo que se lee de cada una: tras un fallo se deshace la
        # transacción, y lo cargado antes caduca (leerlo después ya no se puede)
        for competition_id, nombre in await self._competiciones_scratch():
            try:
                async with self._uow:
                    rondas = [
                        (r.id, r.golf_course_id)
                        for r in await self._uow.rounds.find_by_competition(competition_id)
                        if r.status in SE_COMPLETAN
                    ]
            except Exception as exc:  # se informa y se sigue con las demás
                resumen.errores.append(f"{nombre}: {exc}")
                continue
            for round_id, golf_course_id in rondas:
                try:
                    jugadores = await self._completar_ronda(round_id, golf_course_id, dry_run)
                except Exception as exc:  # se informa y se sigue con las demás
                    resumen.errores.append(f"{nombre} / ronda {round_id.value}: {exc}")
                    continue
                if jugadores:
                    resumen.rondas.append(RondaCompletada(nombre, str(round_id.value), jugadores))
        return resumen

    async def _competiciones_scratch(self) -> list[tuple[CompetitionId, str]]:
        competiciones: list[tuple[CompetitionId, str]] = []
        offset = 0
        while True:
            async with self._uow:
                pagina = await self._uow.competitions.find_all(
                    limit=COMPETICIONES_POR_PAGINA, offset=offset
                )
                competiciones.extend(
                    (c.id, str(c.name)) for c in pagina if c.play_mode == PlayMode.SCRATCH
                )
            if not pagina:
                return competiciones
            offset += COMPETICIONES_POR_PAGINA

    async def _completar_ronda(
        self, round_id: RoundId, golf_course_id: GolfCourseId, dry_run: bool
    ) -> int:
        # Todo dentro de la transacción: si algo falla, se deshace entera (y la
        # sesión queda lista para la ronda siguiente)
        async with self._uow:
            campo = await self._campos.find_by_id(golf_course_id)
            if campo is None:
                return 0
            contexto = course_context_for(campo)
            partidos = await self._uow.matches.find_by_round(round_id)
            ids = list(
                {p.user_id for m in partidos for p in (*m.team_a_players, *m.team_b_players)}
            )
            generos = {u.id: u.gender for u in await self._usuarios.find_by_ids(ids)}

            def genero_de(jugador: MatchPlayer) -> Gender | None:
                return barra_sin_golpes(
                    jugador.tee_color,
                    generos.get(jugador.user_id),
                    contexto.tee_ratings,
                    contexto.holes_by_tee,
                ).tee_gender

            if dry_run:
                return sum(m.jugadores_por_completar(genero_de) for m in partidos)
            total = 0
            for partido in partidos:
                cambiados = partido.completar_genero_de_las_barras(genero_de)
                total += cambiados
                if cambiados:
                    await self._uow.matches.update(partido)
        return total
