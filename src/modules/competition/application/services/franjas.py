"""
Franjas - Lo común de crear y cambiar sesiones según el tipo de competición (#251).

Decidido con Agustín el 6-7 oct 2026:

- **Una Ryder** tiene sesiones con formato de partido, y su agenda se toca
  hasta que termina (BE #365).
- **Un Stableford o un Medal** tiene franjas: individuales al 95 %, con su hoja
  de salidas, sin solaparse en la misma jornada, y se tocan hasta iniciar.

Aquí se traduce cada regla del dominio a un error de la aplicación, con el
mismo mensaje para crear, cambiar y borrar.
"""

from collections.abc import Iterable
from datetime import date

from src.modules.competition.application.dto.round_match_dto import TeeSheetDTO
from src.modules.competition.application.exceptions import (
    AgendaNotEditableError,
    FranjaInvalidaError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.franjas_de_la_jornada import FranjasDeLaJornada
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


def comprobar_agenda(competition: Competition) -> None:
    """
    Raises:
        AgendaNotEditableError: Si ya no se pueden tocar sus sesiones
    """
    if competition.allows_agenda_edits():
        return
    if competition.stroke_play is not None:
        raise AgendaNotEditableError(
            "Las franjas de un Stableford o un Medal se cambian hasta iniciar la "
            f"competición. Estado actual: {competition.status.value}"
        )
    raise AgendaNotEditableError(
        "La agenda solo se puede cambiar hasta que la competición termina o se cancela. "
        f"Estado actual: {competition.status.value}"
    )


def hoja_de(dto: TeeSheetDTO | None) -> HojaDeSalidas | None:
    """
    La hoja de salidas que viene en la petición, si viene.

    Raises:
        FranjaInvalidaError: Si no es posible (intervalo, partida, horas)
    """
    if dto is None:
        return None
    try:
        return HojaDeSalidas(
            primera_salida=dto.first_tee_time,
            ultima_salida=dto.last_tee_time,
            intervalo_minutos=dto.interval_minutes,
            jugadores_por_partida=dto.group_size,
        )
    except ValueError as e:
        raise FranjaInvalidaError(str(e)) from e


def comprobar_tipo(
    competition: Competition,
    hoja: HojaDeSalidas | None,
    con_formato: bool,
    trae_formato: bool,
    exige_formato: bool,
) -> None:
    """
    Una franja lleva hoja y no formato; una sesión de Ryder, formato y no hoja.

    Args:
        competition: De qué tipo es
        hoja: La hoja de salidas que se pide, si se pide
        con_formato: Si se pide formato de partido, modo de hándicap o allowance
        trae_formato: Si se pide, en concreto, el formato de partido
        exige_formato: Si la sesión de Ryder tiene que traer formato (al crearla)

    Raises:
        FranjaInvalidaError: Si no le corresponde
    """
    if competition.stroke_play is not None:
        if con_formato:
            raise FranjaInvalidaError(
                "Una franja de un Stableford o un Medal no lleva formato de partido ni "
                "allowance: es individual al 95 %."
            )
        if exige_formato:
            _comprobar(competition, hoja)
        return
    if hoja is not None:
        _comprobar(competition, hoja)
    if exige_formato and not trae_formato:
        raise FranjaInvalidaError(
            "Una sesión de Ryder necesita su formato de partido (SINGLES, FOURBALL o FOURSOMES)."
        )


def comprobar_solape(
    hoja: HojaDeSalidas,
    dia: date,
    campo: GolfCourseId,
    sesiones: Iterable[Round],
    excepto: RoundId | None = None,
) -> None:
    """
    Raises:
        FranjaInvalidaError: Si choca con otra franja de esa jornada
    """
    try:
        FranjasDeLaJornada.comprobar(hoja, dia, campo, sesiones, excepto=excepto)
    except ValueError as e:
        raise FranjaInvalidaError(str(e)) from e


def _comprobar(competition: Competition, hoja: HojaDeSalidas | None) -> None:
    try:
        competition.comprobar_hoja_de_salidas(hoja)
    except ValueError as e:
        raise FranjaInvalidaError(str(e)) from e


async def comprobar_que_nadie_pierde_su_sitio(
    uow: CompetitionUnitOfWorkInterface,
    franja: Round,
    hoja_nueva: HojaDeSalidas | None,
    dia_nuevo: date | None,
) -> None:
    """
    Cambiar la forma de una franja vale en cualquier dirección mientras nadie de
    dentro pierda su sitio (decisión 5 de la #251): ni quedarse sin plaza al
    achicarla, ni acabar con dos franjas el mismo día al moverla.

    Raises:
        FranjaInvalidaError: Diciendo por qué
    """
    plazas = await uow.plazas.de_la_competicion(franja.competition_id)
    dentro = [p.user_id for p in plazas if p.round_id == franja.id]
    if not dentro:
        return
    if hoja_nueva is not None and hoja_nueva.cupo < len(dentro):
        raise FranjaInvalidaError(
            f"La franja quedaría con {hoja_nueva.cupo} plazas y tiene {len(dentro)} "
            "jugadores dentro: muévelos antes."
        )
    if dia_nuevo is not None and dia_nuevo != franja.round_date:
        sesiones = {s.id: s for s in await uow.rounds.find_by_competition(franja.competition_id)}
        chocan = {
            p.user_id
            for p in plazas
            if p.user_id in dentro
            and p.round_id != franja.id
            and sesiones[p.round_id].round_date == dia_nuevo
        }
        if chocan:
            raise FranjaInvalidaError(
                f"{len(chocan)} de sus jugadores ya juega ese día en otra franja: "
                "como mucho una por jornada."
            )


async def comprobar_que_esta_vacia(uow: CompetitionUnitOfWorkInterface, franja: Round) -> None:
    """
    Raises:
        FranjaInvalidaError: Si alguien tiene plaza en ella: borrarla le quitaría el sitio
    """
    plazas = await uow.plazas.de_la_competicion(franja.competition_id)
    dentro = sum(1 for p in plazas if p.round_id == franja.id)
    if dentro:
        raise FranjaInvalidaError(
            f"La franja tiene {dentro} jugadores con plaza: muévelos o quítalos antes de borrarla."
        )
