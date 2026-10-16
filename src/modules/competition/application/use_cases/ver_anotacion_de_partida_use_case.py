"""
Caso de Uso: La partida para anotar y las tarjetas de los suyos (#251, PR 5).

Las pestañas 1 (anotar y marcar) y 3 (tarjetas de su partida) de la pantalla de
anotar. Cada jugador con sus 18 hoyos —su lado, el de su marcador y si
coinciden— y los totales de lo VALIDADO, que es lo único que cuenta.
"""

from uuid import UUID

from src.modules.competition.application.dto.partidas_dto import (
    TeeGroupHoleDTO,
    TeeGroupScoringPlayerDTO,
    TeeGroupScoringViewDTO,
    TeeGroupTotalsDTO,
)
from src.modules.competition.application.exceptions import PartidaNotFoundError
from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.jornadas_de_la_competicion import (
    ZonaDesconocidaError,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.vista_de_la_franja import (
    primera_salida_en_el_campo,
)
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.tarjeta_de_stroke_play import TarjetaDeStrokePlay
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    HOYOS,
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class VerAnotacionDePartidaUseCase:
    """La partida con los golpes de cada uno."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        user_repository: UserRepositoryInterface,
        golf_courses: IGolfCourseRepository | None = None,
    ):
        self._uow = uow
        self._zonas = zonas
        self._usuarios = user_repository
        # Para el nombre del campo bajo el título de la anotación (BE #532)
        self._campos = golf_courses

    async def execute(self, group_id: UUID, quien: UserId) -> TeeGroupScoringViewDTO:
        """
        Raises:
            PartidaNotFoundError: Si la partida o su franja no existen
        """
        async with self._uow:
            partida = await self._uow.partidas.find_by_id(PartidaId(group_id))
            franja = await self._uow.rounds.find_by_id(partida.round_id) if partida else None
            if partida is None or franja is None or franja.hoja_de_salidas is None:
                raise PartidaNotFoundError(f"No existe la partida {group_id}")
            competicion = await self._uow.competitions.find_by_id(partida.competition_id)
            if competicion is None:
                raise PartidaNotFoundError(f"No existe la partida {group_id}")
            try:
                # Con el desfase del campo, como `scoring_opens_at` de la Ryder:
                # el cliente lee la hora de la cadena, y en UTC anunciaba otra
                # (pasada del front, FE #824)
                abre = await primera_salida_en_el_campo(franja, self._zonas)
            except ZonaDesconocidaError:
                abre = None
            golpes = await self._uow.golpes_de_partida.de_la_partida(partida.id)
            # También de quien anotó y ya no está (movido, o el organizador)
            quienes = list(
                dict.fromkeys(
                    [*partida.user_ids, *(g.marcador_por for g in golpes if g.marcador_por)]
                )
            )
            nombres = await PlayerNames.de_la_competicion(
                quienes, partida.competition_id, self._usuarios, self._uow
            )
            nombres_de_campos = (
                await self._campos.find_names_by_ids([franja.golf_course_id])
                if self._campos
                else {}
            )
        de_quien = {(g.user_id, g.hoyo): g for g in golpes}
        jugaron = partida.quienes_jugaron(golpes)
        marcado_por = {marcado: marcador for marcador, marcado in partida.marcadores.items()}
        marca = partida.marcadores.get(quien)
        return TeeGroupScoringViewDTO(
            group_id=partida.id.value,
            round_id=partida.round_id.value,
            golf_course_id=franja.golf_course_id.value,
            golf_course_name=nombres_de_campos.get(str(franja.golf_course_id)),
            number=partida.numero,
            tee_time=franja.hoja_de_salidas.hora_de(partida.numero).strftime("%H:%M"),
            status=partida.estado.value,
            scoring_opens_at=abre,
            tournament_type=competicion.tournament_type.value,
            picked_up_allowed=competicion.tournament_type == TournamentType.STABLEFORD,
            i_mark_user_id=marca.value if marca else None,
            players=[
                _jugador(partida, foto, de_quien, nombres, marcado_por, jugaron)
                for foto in partida.jugadores
            ],
        )


def _jugador(
    partida: Partida,
    foto: JugadorDePartida,
    de_quien: dict[tuple[UserId, int], GolpeDePartida],
    nombres: dict[UserId, str],
    marcado_por: dict[UserId, UserId],
    jugaron: set[UserId],
) -> TeeGroupScoringPlayerDTO:
    suyos = {hoyo: de_quien.get((foto.user_id, hoyo)) for hoyo in range(1, HOYOS + 1)}
    validados = {h: g.golpes_validados for h, g in suyos.items() if g is not None and g.validado}
    tarjeta = TarjetaDeStrokePlay.de(foto, validados)
    marca = partida.marcadores.get(foto.user_id)
    le_marca = marcado_por.get(foto.user_id)
    return TeeGroupScoringPlayerDTO(
        user_id=foto.user_id.value,
        name=nombres.get(foto.user_id, ""),
        playing_handicap=foto.playing_handicap,
        tee_color=foto.tee_color.value,
        tee_gender=foto.tee_gender.value if foto.tee_gender else None,
        card_status=partida.estados_de_tarjeta[foto.user_id].value,
        marks_user_id=marca.value if marca else None,
        marked_by_user_id=le_marca.value if le_marca else None,
        brought_in=foto.user_id in partida.traidos,
        played=foto.user_id in jugaron,
        holes=[_hoyo(foto, hoyo, golpe, nombres) for hoyo, golpe in suyos.items()],
        totals=TeeGroupTotalsDTO(
            thru=tarjeta.tras,
            points=tarjeta.puntos,
            gross_points=tarjeta.puntos_brutos,
            gross=tarjeta.golpes_brutos,
            net=tarjeta.golpes_netos,
            to_par_net=tarjeta.al_par_neto,
            to_par_gross=tarjeta.al_par_bruto,
            complete=tarjeta.completa,
        ),
    )


def _hoyo(
    foto: JugadorDePartida,
    hoyo: int,
    golpe: GolpeDePartida | None,
    nombres: dict[UserId, str],
) -> TeeGroupHoleDTO:
    por = golpe.marcador_por if golpe else None
    return TeeGroupHoleDTO(
        hole=hoyo,
        par=foto.par_por_hoyo[hoyo - 1],
        strokes_received=foto.golpes_por_hoyo[hoyo - 1],
        own_score=golpe.propio if golpe else None,
        own_submitted=golpe.propio_enviado if golpe else False,
        marker_score=golpe.del_marcador if golpe else None,
        marker_submitted=golpe.marcador_enviado if golpe else False,
        marker_by=por.value if por else None,
        marker_by_name=nombres.get(por) or None if por else None,
        status=golpe.estado.value if golpe else "PENDING",
    )
