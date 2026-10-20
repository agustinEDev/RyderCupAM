"""
ListasDeEspera - Quién puede esperar en una franja y a quién le toca la plaza (#251).

Decidido con Agustín (#251, 20 sep; y 8 oct 2026):

- Se espera en una franja **llena**, por orden de llegada, en un día en que no
  se juega y con jornadas libres en el cupo. Se puede esperar en varias.
- La plaza que se libera se **asigna** al primero de la lista que pueda cogerla:
  se salta a quien ya juega ese día o ya llenó su cupo de jornadas.

Aquí solo está la decisión; cuándo se rellena, lo mira quien llama.
"""

from src.modules.competition.domain.entities.round import Round


class EsperaNoPosibleError(ValueError):
    """No puede apuntarse a la lista de espera de esa franja, y el mensaje dice por qué."""


class ListasDeEspera:
    """Las reglas de las listas de espera."""

    @staticmethod
    def comprobar_espera(
        franja: Round,
        suyas: list[Round],
        ocupadas: int,
        max_jornadas: int,
        ya_espera: bool,
    ) -> None:
        """
        Args:
            franja: Donde quiere esperar
            suyas: Las franjas en las que ya tiene plaza
            ocupadas: Cuántas plazas de esa franja están cogidas
            max_jornadas: En cuántas jornadas puede jugar como mucho
            ya_espera: Si ya está en esa lista

        Raises:
            EsperaNoPosibleError: Si no puede, con el motivo
        """
        hoja = franja.hoja_de_salidas
        if hoja is None:
            raise EsperaNoPosibleError("Solo hay lista de espera en una franja de stroke play.")
        if franja.id in {s.id for s in suyas}:
            raise EsperaNoPosibleError("Ya tiene plaza en esa franja.")
        if ya_espera:
            raise EsperaNoPosibleError("Ya espera en esa franja.")
        if ocupadas < hoja.cupo:
            raise EsperaNoPosibleError("Queda sitio en la franja: coge plaza directamente.")
        if any(s.round_date == franja.round_date for s in suyas):
            raise EsperaNoPosibleError("Ya juega ese día: la espera es para conseguir jornada.")
        if len({s.round_date for s in suyas}) >= max_jornadas:
            raise EsperaNoPosibleError(
                f"Ya tiene sus {max_jornadas} jornadas: no puede esperar en más."
            )

    @staticmethod
    def le_toca(franja: Round, suyas: list[Round], max_jornadas: int) -> bool:
        """Si el de la lista puede coger la plaza que se ha liberado ahora mismo."""
        if any(s.round_date == franja.round_date for s in suyas):
            return False
        return len({s.round_date for s in suyas}) < max_jornadas
