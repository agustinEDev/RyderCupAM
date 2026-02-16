"""
ScheduleFormatService - Domain Service para la secuencia de formatos de rondas.

Encapsula la regla de negocio de cómo se distribuyen los formatos de partido
(Singles, Fourball, Foursomes) a lo largo de las sesiones de una competición.
"""

from src.modules.competition.domain.value_objects.match_format import MatchFormat


class ScheduleFormatService:
    """
    Servicio de dominio para construir secuencias de formatos de partido.

    Reglas de negocio (basadas en formato Ryder Cup):
    - 1 sesión: [Singles]
    - 2 sesiones: [Fourball, Singles]
    - 3 sesiones: [Foursomes, Fourball, Singles]
    - 4+: alterna Fourball/Foursomes, Singles siempre última
    """

    @staticmethod
    def build_format_sequence(total_sessions: int) -> list[MatchFormat]:
        """
        Construye la secuencia de formatos para N sesiones.

        Args:
            total_sessions: Número total de sesiones a generar

        Returns:
            Lista de MatchFormat en el orden de sesiones
        """
        if total_sessions <= 0:
            return []
        if total_sessions == 1:
            return [MatchFormat.SINGLES]

        # Generar las N-1 sesiones previas alternando Fourball/Foursomes
        alternation = [MatchFormat.FOURBALL, MatchFormat.FOURSOMES]
        preceding: list[MatchFormat] = []
        for i in range(total_sessions - 1):
            preceding.append(alternation[i % 2])

        # Invertir para que la secuencia final quede correcta:
        # 2 sesiones: [Fourball] + Singles
        # 3 sesiones: [Foursomes, Fourball] + Singles
        # 4 sesiones: [Fourball, Foursomes, Fourball] + Singles
        preceding.reverse()

        preceding.append(MatchFormat.SINGLES)
        return preceding
