"""
Resultado de un jugador en un hoyo, ya reducido a lo que las estadísticas
necesitan.

Existe para que el desglose de golpes (BE #168) no tenga que repetir las reglas
delicadas que ya resuelve `GetPlayerStatsUseCase`: el tope de doble bogey neto,
el hoyo recogido que cuenta como jugado y la tarjeta de la barra concreta que
juega cada uno. Quien construye estos objetos aplica esas reglas una sola vez;
quien los agrega solo suma.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HoleOutcome:
    """
    Un hoyo jugado, con los golpes que se dieron y los que el WHS deja computar.

    Son DOS números y no uno, por la misma razón por la que el calculador de
    partida rápida los lleva separados:

    - `gross` son los golpes de la tarjeta. Un birdie es un birdie, y ese dato
      no puede depender del reparto de golpes.
    - `adjusted_gross` es lo computable, topado en el doble bogey neto (Regla
      WHS 3.1), que es lo que impide que un hoyo desastroso mueva la media de
      una temporada.

    Derivar el bruto del topado parecía inofensivo y no lo es: para un jugador
    **plus** los golpes recibidos son negativos, así que el tope cae POR DEBAJO
    de `par + 2` y un doble bogey de verdad se contaría como bogey.

    Attributes:
        number: Número del hoyo (1-18), que es lo que separa la ida de la vuelta
        par: Par del hoyo EN LA BARRA que juega este jugador, no el de referencia
        gross: Golpes dados. En un hoyo recogido, el `par + 2` que se anota
        adjusted_gross: Golpes computables, topados en el doble bogey neto
        strokes_received: Golpes que recibe en este hoyo por su hándicap
    """

    number: int
    par: int
    gross: int
    adjusted_gross: int
    strokes_received: int

    @property
    def net(self) -> int:
        """Golpes netos: los computables menos los que recibe."""
        return self.adjusted_gross - self.strokes_received

    @property
    def gross_to_par(self) -> int:
        """Respecto al par, en bruto. Un birdie es -1 lo juegue quien lo juegue."""
        return self.gross - self.par

    @property
    def net_to_par(self) -> int:
        """Respecto al par, en neto: contra el par que le toca a este jugador."""
        return self.net - self.par
