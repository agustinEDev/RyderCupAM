"""
Resultado de un jugador en un hoyo, ya reducido a lo que las estadísticas
necesitan.

Existe para que el desglose de golpes (BE #168) no tenga que repetir las reglas
delicadas que ya resuelve `GetPlayerStatsUseCase._scorecard_to_par`: el tope de
doble bogey neto, el hoyo recogido que cuenta como jugado y la tarjeta de la
barra concreta que juega cada uno. Quien construye estos objetos aplica esas
reglas una sola vez; quien los agrega solo suma.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HoleOutcome:
    """
    Un hoyo jugado, con los golpes ya topados en el doble bogey neto.

    `adjusted_gross` NO son los golpes que el jugador escribió: son los que el
    WHS deja computar (Regla 3.1). Un desastre puntual queda topado, que es
    justo lo que evita que un hoyo mueva la media de una temporada.

    Attributes:
        number: Número del hoyo (1-18), que es lo que separa la ida de la vuelta
        par: Par del hoyo EN LA BARRA que juega este jugador, no el de referencia
        adjusted_gross: Golpes computables, ya topados
        strokes_received: Golpes que recibe en este hoyo por su hándicap
    """

    number: int
    par: int
    adjusted_gross: int
    strokes_received: int

    @property
    def net(self) -> int:
        """Golpes netos: los computables menos los que recibe."""
        return self.adjusted_gross - self.strokes_received

    @property
    def gross_to_par(self) -> int:
        """Respecto al par, en bruto. Un birdie es -1 lo juegue quien lo juegue."""
        return self.adjusted_gross - self.par

    @property
    def net_to_par(self) -> int:
        """Respecto al par, en neto: contra el par que le toca a este jugador."""
        return self.net - self.par
