"""
LoPendiente - Rehacer lo que le queda por jugar a quien cambia de barras (BE #912).

Decidido con Agustín: no se cambia lo ya jugado, pero sí lo que queda por jugar.
En los partidos de Ryder sin empezar y las partidas de stroke play que aún no
salieron («tienen golpes o les llegó su hora», #544) cambia la barra del jugador
y lo que depende de ella; los demás se quedan como se generaron.

Lo usan los tres cambios de barras: la general de una inscripción, la propia de
una inscripción en un campo (R1) y la del campo para todos los de un género (R2).
Por eso trabaja sobre un espacio de trabajo: cada partido o partida se bloquea
una sola vez y se rehace sobre una copia, de modo que si un mismo partido cambia
para dos jugadores (un fourball con las dos de un género), el segundo parte de
lo que dejó el primero. Nada se escribe hasta `guardar`: si algo falla antes, no
se ha tocado nada.
"""

import copy
from collections.abc import Callable, Mapping
from datetime import datetime

from src.modules.competition.application.exceptions import PendingGameNotRecalculableError
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.jugadores_del_partido import (
    JugadoresDelPartido,
)
from src.modules.competition.application.services.salidas_de_la_franja import las_que_salieron
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContext
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class LoPendiente:
    """El espacio de trabajo de un cambio de barras: lo que se rehace, y guardarlo."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        zonas: ICompetitionTimezone | None,
        reloj: Callable[[], datetime],
    ):
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        # El mismo cálculo que al generar y al reasignar: sin reglas propias
        self._del_partido = JugadoresDelPartido(golf_course_repository, user_repository)
        self._de_la_partida = JugadoresDeLaPartida(golf_course_repository, user_repository)
        # Cada campo y sus cambios, leídos una vez en toda la ejecución
        self.contextos: dict[GolfCourseId, StrokeContext] = {}
        self._cambios: dict[GolfCourseId, BarrasDelCampo] = {}
        self._rondas: dict[RoundId, Round] | None = None
        # Lo bloqueado, con su copia de trabajo, y lo que de verdad cambió
        self._partidos: dict[MatchId, tuple[Match, Match]] = {}
        self._partidas: dict[PartidaId, tuple[Partida, Partida]] = {}
        self._partidos_cambiados: set[MatchId] = set()
        self._partidas_cambiadas: set[PartidaId] = set()

    async def cambios_del_campo(
        self, competition: Competition, golf_course_id: GolfCourseId
    ) -> BarrasDelCampo:
        """Los cambios de barras de un campo, leídos una vez."""
        if golf_course_id not in self._cambios:
            self._cambios[golf_course_id] = await self._uow.barras_por_campo.del_campo(
                competition.id, golf_course_id
            )
        return self._cambios[golf_course_id]

    async def rehacer(
        self,
        competition: Competition,
        user_id: UserId,
        genero: Gender | None,
        general: TeeColor | None,
        cambios: Mapping[GolfCourseId, BarrasDelCampo] | None = None,
        solo_en: GolfCourseId | None = None,
    ) -> None:
        """
        Rehace en el espacio de trabajo lo que le queda por jugar a un jugador.

        En cada campo juega su barra efectiva (`BarrasDelCampo.color_de`: su cambio
        propio, la del campo para su género o su general), con los cambios de ese
        campo leídos o los de `cambios` si se pasan (los nuevos de quien cambia).

        Args:
            general: Su barra general (la nueva, si es lo que cambia)
            cambios: Los cambios nuevos de algún campo, en vez de los guardados
            solo_en: Solo lo de ese campo

        Raises:
            TeeNotRatedForPlayerError: Si su barra no está valorada en el campo de
                algo pendiente
            PendingGameNotRecalculableError: Si algo pendiente no se puede rehacer
                por otra cosa que su barra
        """
        rondas = await self._rondas_de(competition)
        await self._rehacer_partidos(
            competition, rondas, user_id, genero, general, cambios, solo_en
        )
        await self._rehacer_partidas(
            competition, rondas, user_id, genero, general, cambios, solo_en
        )

    async def _color_en(
        self,
        competition: Competition,
        golf_course_id: GolfCourseId,
        user_id: UserId,
        genero: Gender | None,
        general: TeeColor | None,
        cambios: Mapping[GolfCourseId, BarrasDelCampo] | None,
    ) -> TeeColor | None:
        del_campo = (cambios or {}).get(golf_course_id) or await self.cambios_del_campo(
            competition, golf_course_id
        )
        return del_campo.color_de(user_id, general, genero)

    async def _rondas_de(self, competition: Competition) -> dict[RoundId, Round]:
        if self._rondas is None:
            self._rondas = {
                r.id: r for r in await self._uow.rounds.find_by_competition(competition.id)
            }
        return self._rondas

    async def _rehacer_partidos(
        self,
        competition: Competition,
        rondas: dict[RoundId, Round],
        user_id: UserId,
        genero: Gender | None,
        general: TeeColor | None,
        cambios: Mapping[GolfCourseId, BarrasDelCampo] | None,
        solo_en: GolfCourseId | None,
    ) -> None:
        """
        Sus partidos de Ryder sin empezar. Se filtran con la lectura sin bloqueo, se
        bloquean solo esos (una vez) y se vuelve a mirar con el bloqueo: lo que esté
        en juego ni se bloquea.
        """
        if not rondas:
            return
        for leido in await self._uow.matches.find_by_rounds_for_player(list(rondas), user_id):
            ronda = rondas[leido.round_id]
            if solo_en is not None and ronda.golf_course_id != solo_en:
                continue
            if leido.status != MatchStatus.SCHEDULED:
                continue
            copia = await self._partido_de_trabajo(leido.id)
            if copia is None or copia.status != MatchStatus.SCHEDULED:
                continue
            color = await self._color_en(
                competition, ronda.golf_course_id, user_id, genero, general, cambios
            )
            bandos = await self._del_partido.con_otra_barra(
                ronda, competition, copia, user_id, color, genero, self.contextos
            )
            if bandos is not None:
                copia.recalcular_jugadores(*bandos)
                self._partidos_cambiados.add(copia.id)

    async def _partido_de_trabajo(self, match_id: MatchId) -> Match | None:
        if match_id not in self._partidos:
            partido = await self._uow.matches.find_by_id_for_update(match_id)
            if partido is None:
                return None
            self._partidos[match_id] = (partido, copy.deepcopy(partido))
        return self._partidos[match_id][1]

    async def _rehacer_partidas(
        self,
        competition: Competition,
        rondas: dict[RoundId, Round],
        user_id: UserId,
        genero: Gender | None,
        general: TeeColor | None,
        cambios: Mapping[GolfCourseId, BarrasDelCampo] | None,
        solo_en: GolfCourseId | None,
    ) -> None:
        """
        Sus partidas de stroke play que aún no salieron. Una lectura de franja y de
        zona por franja; se bloquean solo las que quedan y se vuelve a mirar con el
        bloqueo y una hora nueva: si ya salió o él ya no está, se salta.
        """
        ahora = self._reloj()
        por_franja: dict[RoundId, list[Partida]] = {}
        for leida in await self._uow.partidas.del_jugador(competition.id, user_id):
            por_franja.setdefault(leida.round_id, []).append(leida)

        for round_id, leidas in por_franja.items():
            franja = rondas.get(round_id) or await self._uow.rounds.find_by_id(round_id)
            if franja is None:
                # Una partida sin su franja no se puede ni fechar: mejor decirlo que
                # dejarla con las barras viejas sin que nadie lo sepa
                raise PendingGameNotRecalculableError("La franja de una partida ya no existe")
            if solo_en is not None and franja.golf_course_id != solo_en:
                continue
            salieron = await las_que_salieron(franja, leidas, self._zonas, ahora)
            for leida in leidas:
                if leida.id in salieron:
                    continue
                copia = await self._partida_de_trabajo(leida.id)
                # Con el bloqueo, y con la hora de ahora: pudo llegarle mientras
                if copia is None or copia.id in await las_que_salieron(
                    franja, [copia], self._zonas, self._reloj()
                ):
                    continue
                foto = next((j for j in copia.jugadores if j.user_id == user_id), None)
                if foto is None:
                    # Lo movieron o lo quitaron mientras tanto: esta ya no es suya
                    continue
                color = await self._color_en(
                    competition, franja.golf_course_id, user_id, genero, general, cambios
                )
                nueva = await self._de_la_partida.con_otra_barra(
                    competition, franja, foto, color, genero, self.contextos
                )
                if nueva is not None:
                    copia.recalcular(
                        [nueva if j.user_id == user_id else j for j in copia.jugadores]
                    )
                    self._partidas_cambiadas.add(copia.id)

    async def _partida_de_trabajo(self, partida_id: PartidaId) -> Partida | None:
        if partida_id not in self._partidas:
            partida = await self._uow.partidas.find_by_id_for_update(partida_id)
            if partida is None:
                return None
            self._partidas[partida_id] = (partida, copy.deepcopy(partida))
        return self._partidas[partida_id][1]

    @property
    def cuantos(self) -> tuple[int, int]:
        """Cuántos partidos y partidas cambian."""
        return len(self._partidos_cambiados), len(self._partidas_cambiadas)

    async def guardar(self) -> None:
        """Escribe lo que cambió: sus fotos nuevas, sobre lo bloqueado."""
        for match_id in self._partidos_cambiados:
            partido, copia = self._partidos[match_id]
            partido.recalcular_jugadores(copia.team_a_players, copia.team_b_players)
            await self._uow.matches.update(partido)
        partidas = []
        for partida_id in self._partidas_cambiadas:
            partida, copia_de_la_partida = self._partidas[partida_id]
            partida.recalcular(copia_de_la_partida.jugadores)
            partidas.append(partida)
        if partidas:
            await self._uow.partidas.guardar(partidas)
