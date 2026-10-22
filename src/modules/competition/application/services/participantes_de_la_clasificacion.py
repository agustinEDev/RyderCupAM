"""
Los participantes de una clasificación de stroke play, a partir de lo leído.

Lo comparten las clasificaciones de la ficha (`ClasificacionGeneralUseCase` y
compañía) y las generales finales por lotes del cara a cara (J): una sola
forma de montar las tarjetas, el hándicap que desempata y el «tras», para que
las dos no puedan contar distinto.
"""

from collections.abc import Mapping, Sequence
from datetime import date, time

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.clasificacion import (
    Clasificacion,
    Escala,
    Fila,
    Participante,
    TarjetaDeJornada,
)
from src.modules.competition.domain.services.tarjeta_de_stroke_play import TarjetaDeStrokePlay
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


def participantes_de(
    partidas: Sequence[Partida],
    golpes: Sequence[GolpeDePartida],
    franjas: Mapping,
    categorias: Mapping[UserId, int | None],
) -> tuple[list[Participante], dict[UserId, str | None]]:
    """
    Los participantes con sus tarjetas, en orden de calendario, y el género de
    las barras de cada uno. `franjas` son las rondas de esas partidas, por id.
    """
    validados: dict[tuple, dict[int, int | None]] = {}
    for golpe in golpes:
        if golpe.validado:
            validados.setdefault((golpe.partida_id, golpe.user_id), {})[golpe.hoyo] = (
                golpe.golpes_validados
            )
    user_ids = list({u for p in partidas for u in p.user_ids})
    tarjetas: dict[UserId, list[TarjetaDeJornada]] = {}
    handicaps = {}
    generos: dict[UserId, str | None] = {}

    # Por calendario: el hándicap que desempata (H) es el de su última
    # jornada, y se queda el de la última partida recorrida; y las tarjetas
    # llegan en ese orden a la clasificación (el «tras»)
    def cuando(partida: Partida) -> tuple[date, time]:
        franja: Round = franjas[partida.round_id]
        hoja = franja.hoja_de_salidas
        return franja.round_date, hoja.hora_de(partida.numero) if hoja else time.min

    for partida in sorted(partidas, key=cuando):
        for foto in partida.jugadores:
            tarjeta = TarjetaDeStrokePlay.de(foto, validados.get((partida.id, foto.user_id), {}))
            estado = partida.estados_de_tarjeta[foto.user_id]
            tarjetas.setdefault(foto.user_id, []).append(TarjetaDeJornada(tarjeta, estado))
            handicaps[foto.user_id] = foto.handicap
            # El de su última partida, como el hándicap (#856); sin dato en
            # ella, el último que se supo (/code-review)
            if foto.tee_gender is not None:
                generos[foto.user_id] = foto.tee_gender.value
    participantes = [
        Participante(u, handicaps[u], categorias.get(u), tuple(tarjetas[u])) for u in user_ids
    ]
    return participantes, generos


async def generales_netas(
    uow: CompetitionUnitOfWorkInterface, competiciones: Sequence[Competition]
) -> dict[CompetitionId, list[Fila]]:
    """
    La general neta de varios stroke play, con la regla de cada uno, en un
    número fijo de lecturas: sus partidas, sus golpes y sus rondas, de una vez
    (revisión del 22 oct 2026, J). Se llama dentro de la unidad de trabajo.

    La categoría no cambia el orden de la general (solo filtra la de cada
    categoría), así que aquí no se leen las inscripciones. Tampoco los
    nombres: quien la usa solo quiere los puestos.
    """
    de_stroke_play = [c for c in competiciones if c.stroke_play is not None]
    if not de_stroke_play:
        return {}
    partidas = await uow.partidas.de_las_competiciones([c.id for c in de_stroke_play])
    golpes = (
        await uow.golpes_de_partida.de_las_partidas([p.id for p in partidas]) if partidas else []
    )
    round_ids = list({p.round_id for p in partidas})
    franjas = {f.id: f for f in await uow.rounds.find_by_ids(round_ids)} if round_ids else {}

    # Agrupadas una sola vez: recorrerlas por cada torneo crecía con el número
    # de torneos compartidos (CodeRabbit BE #641)
    partidas_de: dict[CompetitionId, list[Partida]] = {}
    for partida in partidas:
        partidas_de.setdefault(partida.competition_id, []).append(partida)
    torneo_de_partida = {p.id: p.competition_id for p in partidas}
    golpes_de: dict[CompetitionId, list[GolpeDePartida]] = {}
    for golpe in golpes:
        torneo = torneo_de_partida.get(golpe.partida_id)
        if torneo is not None:
            golpes_de.setdefault(torneo, []).append(golpe)

    generales: dict[CompetitionId, list[Fila]] = {}
    for competicion in de_stroke_play:
        ajustes = competicion.stroke_play
        if ajustes is None:
            continue
        participantes, _ = participantes_de(
            partidas_de.get(competicion.id, []), golpes_de.get(competicion.id, []), franjas, {}
        )
        generales[competicion.id] = Clasificacion.de(
            participantes, competicion.tournament_type, Escala.NETA, ajustes.overall_standing
        )
    return generales
