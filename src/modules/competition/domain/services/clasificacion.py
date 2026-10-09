"""
Clasificacion - Las clasificaciones de un stroke play (#251, PR 5).

Decidido con Agustín (decisión 4 y 7 de la #251, y P5-P8, P13, P14 el 9 oct 2026):

- **Sin desempate automático**: los empatados comparten puesto («T3»); dentro del
  empate se pintan por hándicap (P5).
- **Stableford**: más puntos, mejor (netos; brutos en el scratch, P13). Un
  retirado cuenta con lo jugado (P6).
- **Medal**: menos golpes respecto al par de lo jugado, mejor (netos o brutos):
  así se comparan jornadas en campos de par distinto. Un retirado es NR, al final
  y sin puesto (P6); en el acumulado, un NR en cualquier jornada deja NR, y va
  delante quien juega más tarjetas (P7).
- **Regla de la general** (la elige el organizador; vale también para el
  scratch, P14): acumulado, o mejor tarjeta (la mejor entregada, o la que juega
  si ya la mejora, P8).
- Quien no ha validado ningún hoyo, o no se presentó, va al final y sin puesto.
- Filtrar por categoría es una clasificación propia: los puestos, dentro de ella.
- El scratch se enseña cortado en 25 más los empatados en el corte, con la fila
  propia debajo si queda fuera (decisión 4): `cortar`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.estado_de_tarjeta import EstadoDeTarjeta
from ..value_objects.overall_standing import OverallStanding
from ..value_objects.tournament_type import TournamentType
from .tarjeta_de_stroke_play import Tarjeta


class Escala(StrEnum):
    """Con los golpes de cada uno (neta) o sin ellos (scratch)."""

    NETA = "NETA"
    SCRATCH = "SCRATCH"


class EstadoEnClasificacion(StrEnum):
    CLASIFICADO = "CLASIFICADO"
    SIN_EMPEZAR = "SIN_EMPEZAR"
    NR = "NR"
    NP = "NP"


@dataclass(frozen=True)
class TarjetaDeJornada:
    """Una tarjeta de un jugador (una por partida que juega) y su estado."""

    tarjeta: Tarjeta
    estado: EstadoDeTarjeta


@dataclass(frozen=True)
class Participante:
    """`tarjetas`, por calendario: la última jornada, la última."""

    user_id: UserId
    handicap: Decimal
    categoria: int | None
    tarjetas: tuple[TarjetaDeJornada, ...]


@dataclass(frozen=True)
class Fila:
    user_id: UserId
    puesto: int | None
    empatado: bool
    valor: int | None
    tarjetas: int
    tras: int
    estado: EstadoEnClasificacion
    categoria: int | None
    handicap: Decimal


# Sin puesto, en este orden detrás de los clasificados
_ORDEN_SIN_PUESTO = (
    EstadoEnClasificacion.SIN_EMPEZAR,
    EstadoEnClasificacion.NR,
    EstadoEnClasificacion.NP,
)


@dataclass(frozen=True)
class _Resultado:
    estado: EstadoEnClasificacion
    valor: int | None = None
    tarjetas: int = 0


class Clasificacion:
    """Calcula y corta las clasificaciones."""

    @staticmethod
    def de(
        participantes: Sequence[Participante],
        tipo: TournamentType,
        escala: Escala,
        regla: OverallStanding,
        categoria: int | None = None,
    ) -> list[Fila]:
        """
        Args:
            tipo: STABLEFORD o MEDAL
            escala: NETA (con categorías) o SCRATCH (sin ellas)
            regla: ACCUMULATED o BEST_CARD (con una sola tarjeta, lo mismo)
            categoria: Solo esa categoría, con sus propios puestos
        """
        if categoria is not None and escala == Escala.SCRATCH:
            raise ValueError("El scratch no tiene categorías.")
        medal = tipo == TournamentType.MEDAL
        filas_sin_puesto: list[Fila] = []
        clasificados: list[tuple[tuple, Participante, _Resultado]] = []
        for participante in participantes:
            if categoria is not None and participante.categoria != categoria:
                continue
            resultado = _resultado(participante, medal, escala, regla)
            if resultado.estado != EstadoEnClasificacion.CLASIFICADO:
                filas_sin_puesto.append(_fila(participante, resultado, None, False))
                continue
            clave = _clave(resultado, medal, regla)
            clasificados.append((clave, participante, resultado))

        clasificados.sort(key=lambda c: (c[0], c[1].handicap, str(c[1].user_id)))
        repeticiones: dict[tuple, int] = {}
        for clave, _, _ in clasificados:
            repeticiones[clave] = repeticiones.get(clave, 0) + 1
        filas: list[Fila] = []
        puesto_de: dict[tuple, int] = {}
        for indice, (clave, participante, resultado) in enumerate(clasificados, start=1):
            puesto = puesto_de.setdefault(clave, indice)
            filas.append(_fila(participante, resultado, puesto, repeticiones[clave] > 1))

        filas_sin_puesto.sort(
            key=lambda f: (_ORDEN_SIN_PUESTO.index(f.estado), f.handicap, str(f.user_id))
        )
        return filas + filas_sin_puesto

    @staticmethod
    def cortar(
        filas: Sequence[Fila], tamano: int, user_id: UserId | None
    ) -> tuple[list[Fila], Fila | None]:
        """
        Las que se ven (hasta el puesto `tamano`, con todos los empatados en él) y,
        si quien mira queda fuera, su propia fila para pintarla debajo.
        """
        visibles = [f for f in filas if f.puesto is not None and f.puesto <= tamano]
        dentro = {f.user_id for f in visibles}
        propia = next((f for f in filas if f.user_id == user_id and f.user_id not in dentro), None)
        return visibles, propia


def _valor(tarjeta: Tarjeta, medal: bool, escala: Escala) -> int:
    if medal:
        return tarjeta.al_par_neto if escala == Escala.NETA else tarjeta.al_par_bruto
    return tarjeta.puntos if escala == Escala.NETA else tarjeta.puntos_brutos


def _resultado(
    participante: Participante, medal: bool, escala: Escala, regla: OverallStanding
) -> _Resultado:
    jugadas = [t for t in participante.tarjetas if t.estado != EstadoDeTarjeta.NO_PRESENTADO]
    if not jugadas:
        return _Resultado(EstadoEnClasificacion.NP)
    retirado = any(t.estado == EstadoDeTarjeta.RETIRADO for t in jugadas)
    nr = medal and retirado
    # Sin nada que contar, un retirado es NR también en Stableford: «sin
    # empezar» diría que aún va a salir
    sin_nada = _Resultado(
        EstadoEnClasificacion.NR if retirado else EstadoEnClasificacion.SIN_EMPEZAR
    )
    con_hoyos = [t for t in jugadas if t.tarjeta.tras > 0]
    if regla == OverallStanding.ACCUMULATED:
        if nr:
            return _Resultado(EstadoEnClasificacion.NR)
        if not con_hoyos:
            return sin_nada
        valor = sum(_valor(t.tarjeta, medal, escala) for t in con_hoyos)
        return _Resultado(EstadoEnClasificacion.CLASIFICADO, valor, len(con_hoyos))

    # Mejor tarjeta: la mejor entregada, o la que juega si ya la mejora (P8)
    candidatas = [t for t in con_hoyos if not (medal and t.estado == EstadoDeTarjeta.RETIRADO)]
    if not candidatas:
        return sin_nada
    valores = [_valor(t.tarjeta, medal, escala) for t in candidatas]
    mejor = min(valores) if medal else max(valores)
    return _Resultado(EstadoEnClasificacion.CLASIFICADO, mejor, len(candidatas))


def _clave(resultado: _Resultado, medal: bool, regla: OverallStanding) -> tuple:
    """Menor es mejor."""
    if resultado.valor is None:
        raise ValueError("Solo los clasificados tienen clave de orden.")
    if not medal:
        return (-resultado.valor,)
    if regla == OverallStanding.ACCUMULATED:
        # Más tarjetas delante: sumar netos premiaría a quien juega menos (P7)
        return (-resultado.tarjetas, resultado.valor)
    return (resultado.valor,)


def _fila(
    participante: Participante, resultado: _Resultado, puesto: int | None, empatado: bool
) -> Fila:
    # La última jornada en juego que ya tenga hoyos: una vieja sin cerrar o una
    # futura aún a 0 no dicen por dónde va
    viva = next(
        (
            t
            for t in reversed(participante.tarjetas)
            if t.estado == EstadoDeTarjeta.JUGANDO and t.tarjeta.tras > 0
        ),
        None,
    )
    tras = (
        viva.tarjeta.tras
        if viva
        else max((t.tarjeta.tras for t in participante.tarjetas), default=0)
    )
    return Fila(
        user_id=participante.user_id,
        puesto=puesto,
        empatado=empatado,
        valor=resultado.valor,
        tarjetas=resultado.tarjetas,
        tras=tras,
        estado=resultado.estado,
        categoria=participante.categoria,
        handicap=participante.handicap,
    )
