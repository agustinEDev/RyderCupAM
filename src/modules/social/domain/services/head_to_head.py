"""
Domain Service: el cara a cara entre dos jugadores (BE-3, 22 oct 2026).

Decidido con Agustín (22 oct, 00:45), sustituye a «Clasificación / En bruto»:

- **Dos apartados**, cada uno con ganadas, empatadas y perdidas desde quien
  mira: **«Contra él»** (bandos contrarios en un match play, o rivales en la
  misma partida o grupo de stroke play) y **«Con él»** (compañeros en el MISMO
  partido de fourball o foursomes: cuenta el resultado del equipo). Ser del
  mismo equipo Ryder en partidos distintos no es jugar con él.
- **Rivales en stroke play = el MISMO grupo** (la misma partida rapida, o el
  mismo grupo de salida de un torneo). Jugar la misma ronda de un torneo en
  grupos distintos no cuenta: es lo que respondió Agustín, y lo conservador.
- **Quién gana, según la modalidad, nunca en bruto**: Stableford, más puntos;
  match play, quien ganó el partido; Medal, menos golpes netos. A igual valor,
  el de menos índice (tabla H; sin hándicap cuenta 0); solo con el mismo, empate.
- **Sin nada que contar, no hay cara a cara**: el apartado llega vacío (None) y
  el cliente lo oculta; un 0-0-0 se leería como «nunca os ganáis».

Puro, sin IO: el resultado de cada partida llega ya resuelto con las cuentas
oficiales de cada módulo.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from src.shared.domain.services.handicap_tiebreak import handicap_tiebreak_key
from src.shared.domain.value_objects.scoring_format import ScoringFormat

# Como guardan los partidos el ganador: un bando o el empate
TEAM_A = "A"
TEAM_B = "B"
HALVED_WINNER = "HALVED"


class Relation(StrEnum):
    """Contra él (bandos contrarios o rivales) o con él (mismo bando del mismo partido)."""

    AGAINST = "AGAINST"
    WITH = "WITH"


class Outcome(StrEnum):
    """Como acabó para quien mira."""

    WON = "WON"
    HALVED = "HALVED"
    LOST = "LOST"


@dataclass(frozen=True)
class CardResult:
    """Lo que cuenta de la tarjeta de uno en stroke play."""

    complete: bool
    points: int
    net_to_par: int
    # El índice con el que jugó: desempata a igual valor (H). None cuenta como 0
    handicap: Decimal | float | None = None


@dataclass(frozen=True)
class Record:
    """Ganadas, empatadas y perdidas de un apartado."""

    won: int = 0
    halved: int = 0
    lost: int = 0


@dataclass(frozen=True)
class HeadToHead:
    """Los dos apartados; None el que no tiene ninguna partida que contar."""

    against: Record | None
    alongside: Record | None


def stroke_play_outcome(
    mine: CardResult | None, theirs: CardResult | None, scoring: ScoringFormat | None
) -> Outcome | None:
    """
    Quién ganó entre dos rivales de una misma partida de stroke play.

    None si falta una tarjeta o alguna está a medias: no se juzga lo que no se
    jugó entero (caso 10, la opción conservadora).
    """
    if mine is None or theirs is None or not (mine.complete and theirs.complete):
        return None
    if scoring == ScoringFormat.STABLEFORD:
        # Mas puntos, mejor
        diferencia = mine.points - theirs.points
    elif scoring == ScoringFormat.MEDAL:
        # Menos golpes netos respecto al par, mejor; asi se ordena la
        # clasificacion oficial y no cambia nada si los dos juegan el mismo par
        diferencia = theirs.net_to_par - mine.net_to_par
    else:
        # Una modalidad que no sea ninguna de las dos no se adivina: no cuenta
        return None
    if diferencia == 0:
        # Empate a valor: gana el de menos índice, como en el aviso y en la
        # clasificación (tabla del 22 oct 2026, H). Solo con el mismo, empate
        return _por_handicap(mine.handicap, theirs.handicap)
    return _por_diferencia(diferencia)


def _por_handicap(mine: Decimal | float | None, theirs: Decimal | float | None) -> Outcome:
    mia, suya = handicap_tiebreak_key(mine), handicap_tiebreak_key(theirs)
    if mia == suya:
        return Outcome.HALVED
    return Outcome.WON if mia < suya else Outcome.LOST


def team_outcome(winner: str | None, my_team: str) -> Outcome | None:
    """El resultado oficial de un match play («A», «B», «HALVED») visto desde un bando."""
    if winner == HALVED_WINNER:
        return Outcome.HALVED
    if winner not in (TEAM_A, TEAM_B):
        return None
    return Outcome.WON if winner == my_team else Outcome.LOST


def relation_between(my_team: str, their_team: str) -> Relation:
    """Del mismo bando, con él; de bandos distintos, contra él."""
    return Relation.WITH if my_team == their_team else Relation.AGAINST


def tally(results: Iterable[tuple[Relation, Outcome | None]]) -> HeadToHead | None:
    """
    Suma las partidas por apartado.

    Las que no tienen resultado (None) no cuentan. Un apartado sin ninguna llega
    en None, y si no hay ninguno, el cara a cara entero es None.
    """
    cuentas: dict[Relation, dict[Outcome, int]] = {}
    for relation, outcome in results:
        if outcome is None:
            continue
        apartado = cuentas.setdefault(relation, dict.fromkeys(Outcome, 0))
        apartado[outcome] += 1

    if not cuentas:
        return None
    return HeadToHead(
        against=_record(cuentas.get(Relation.AGAINST)),
        alongside=_record(cuentas.get(Relation.WITH)),
    )


def _record(cuenta: dict[Outcome, int] | None) -> Record | None:
    if cuenta is None:
        return None
    return Record(won=cuenta[Outcome.WON], halved=cuenta[Outcome.HALVED], lost=cuenta[Outcome.LOST])


def _por_diferencia(diferencia: int) -> Outcome:
    """Positiva, gana quien mira; negativa, pierde; cero, empate."""
    if diferencia > 0:
        return Outcome.WON
    if diferencia < 0:
        return Outcome.LOST
    return Outcome.HALVED
