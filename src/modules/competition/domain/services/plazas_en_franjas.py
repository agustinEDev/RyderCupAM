"""
PlazasEnFranjas - Cuándo puede un jugador coger plaza en una franja (#251).

Decidido con Agustín el 6-8 oct 2026 (y en la #251, 20 sep):

- Plaza si queda sitio: el cupo sale de la hoja de salidas.
- **Una franja por jornada**, siempre.
- Como mucho **N jornadas** por jugador, las que fije el organizador.
- Puede **cambiarse**: coger una «en lugar de» otra suya, de golpe, sin
  quedarse sin sitio entre medias. Eso no suma jornada ni choca con la suya.

Aquí solo está la decisión; quién y cuándo, lo mira quien llama.
"""

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.round_id import RoundId


class PlazaNoPosibleError(ValueError):
    """No puede coger plaza en esa franja, y el mensaje dice por qué."""


class PlazasEnFranjas:
    """Las reglas para coger plaza en una franja."""

    @staticmethod
    def comprobar(
        franja: Round,
        suyas: list[Round],
        ocupadas: int,
        max_jornadas: int,
        en_lugar_de: RoundId | None = None,
    ) -> None:
        """
        Args:
            franja: Donde quiere entrar
            suyas: Las franjas en las que ya tiene plaza
            ocupadas: Cuántas plazas de esa franja están cogidas
            max_jornadas: En cuántas jornadas puede jugar como mucho
            en_lugar_de: La suya que deja a cambio, si se cambia

        Raises:
            PlazaNoPosibleError: Si no puede, con el motivo
        """
        hoja = franja.hoja_de_salidas
        if hoja is None:
            raise PlazaNoPosibleError("Solo se coge plaza en una franja de stroke play.")
        if en_lugar_de is not None and en_lugar_de not in {s.id for s in suyas}:
            raise PlazaNoPosibleError("El jugador no tiene plaza en la franja que deja.")
        if franja.id in {s.id for s in suyas}:
            raise PlazaNoPosibleError("Ya tiene plaza en esa franja.")
        if ocupadas >= hoja.cupo:
            raise PlazaNoPosibleError("La franja está llena.")
        sigue_en = [s for s in suyas if s.id != en_lugar_de]
        if any(s.round_date == franja.round_date for s in sigue_en):
            raise PlazaNoPosibleError("Como mucho una franja por jornada: ya juega ese día.")
        jornadas = {s.round_date for s in sigue_en} | {franja.round_date}
        if len(jornadas) > max_jornadas:
            raise PlazaNoPosibleError(
                f"Como mucho {max_jornadas} jornadas por jugador en esta competición."
            )
