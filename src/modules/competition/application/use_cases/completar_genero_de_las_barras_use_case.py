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
hace nada. Las rondas terminadas no se tocan: se jugaron con esa tarjeta.
"""

from dataclasses import dataclass, field

from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import barra_sin_golpes
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
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
        for competicion in await self._competiciones_scratch():
            async with self._uow:
                rondas = await self._uow.rounds.find_by_competition(competicion.id)
            for ronda in rondas:
                if ronda.status not in SE_COMPLETAN:
                    continue
                try:
                    jugadores = await self._completar_ronda(ronda, dry_run)
                except Exception as exc:  # se informa y se sigue con las demás
                    resumen.errores.append(f"{competicion.name} / ronda {ronda.id.value}: {exc}")
                    continue
                if jugadores:
                    resumen.rondas.append(
                        RondaCompletada(str(competicion.name), str(ronda.id.value), jugadores)
                    )
        return resumen

    async def _competiciones_scratch(self):
        competiciones = []
        offset = 0
        while True:
            async with self._uow:
                pagina = await self._uow.competitions.find_all(
                    limit=COMPETICIONES_POR_PAGINA, offset=offset
                )
            if not pagina:
                return [c for c in competiciones if c.play_mode == PlayMode.SCRATCH]
            competiciones.extend(pagina)
            offset += COMPETICIONES_POR_PAGINA

    async def _completar_ronda(self, ronda, dry_run: bool) -> int:
        campo = await self._campos.find_by_id(ronda.golf_course_id)
        if campo is None:
            return 0
        contexto = course_context_for(campo)
        async with self._uow:
            partidos = await self._uow.matches.find_by_round(ronda.id)
            ids = list(
                {p.user_id for m in partidos for p in (*m.team_a_players, *m.team_b_players)}
            )
            generos = {u.id: u.gender for u in await self._usuarios.find_by_ids(ids)}

            def genero_de(jugador):
                return barra_sin_golpes(
                    jugador.tee_color,
                    generos.get(jugador.user_id),
                    contexto.tee_ratings,
                    contexto.holes_by_tee,
                ).tee_gender

            if dry_run:
                # Sin tocar los partidos: ni siquiera en memoria
                return sum(
                    1
                    for m in partidos
                    for p in (*m.team_a_players, *m.team_b_players)
                    if p.tee_gender is None and genero_de(p) is not None
                )
            total = 0
            for partido in partidos:
                cambiados = partido.completar_genero_de_las_barras(genero_de)
                total += cambiados
                if cambiados:
                    await self._uow.matches.update(partido)
        return total
