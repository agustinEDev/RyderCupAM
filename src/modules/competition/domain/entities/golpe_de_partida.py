"""
GolpeDePartida - Lo que hizo un jugador en un hoyo de su partida de stroke play (#251, PR 5).

Decidido con Agustín (decisión 11 de la #251 y el 9 oct 2026):

- Lo apunta el jugador (o el organizador por él) y lo apunta su marcador;
  **vale cuando coinciden**. Mientras falte un lado, pendiente; si difieren, no
  vale hasta que se corrija (P4).
- **Medal no deja levantar bola**; Stableford sí: la raya vale 0 puntos.
- Queda **quién metió cada lado**: las correcciones del organizador se ven
  (P9), y la exportación lo pedirá.

No es el `HoleScore` de la Ryder: aquel cuelga de un partido y un equipo, no
admite golpes dados de un plus, y lo leen estadísticas y logros.
"""

from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.competition_id import CompetitionId
from ..value_objects.partida_id import PartidaId
from ..value_objects.round_id import RoundId
from ..value_objects.validation_status import ValidationStatus

PRIMER_HOYO, ULTIMO_HOYO = 1, 18
MIN_GOLPES, MAX_GOLPES = 1, 15


class RayaNoPermitidaError(ValueError):
    """En Medal no se levanta bola: hay que acabar el hoyo."""


class GolpeDePartida:
    """Un hoyo de un jugador: su lado, el de su marcador y si coinciden."""

    def __init__(
        self,
        partida_id: PartidaId,
        round_id: RoundId,
        competition_id: CompetitionId,
        user_id: UserId,
        hoyo: int,
        propio: int | None,
        propio_enviado: bool,
        propio_por: UserId | None,
        del_marcador: int | None,
        marcador_enviado: bool,
        marcador_por: UserId | None,
        creado: datetime,
        actualizado: datetime,
    ):
        if not PRIMER_HOYO <= hoyo <= ULTIMO_HOYO:
            raise ValueError(f"El hoyo va del {PRIMER_HOYO} al {ULTIMO_HOYO}, no {hoyo}.")
        self._partida_id = partida_id
        self._round_id = round_id
        self._competition_id = competition_id
        self._user_id = user_id
        self._hoyo = hoyo
        self._propio = propio
        self._propio_enviado = propio_enviado
        self._propio_por = propio_por
        self._del_marcador = del_marcador
        self._marcador_enviado = marcador_enviado
        self._marcador_por = marcador_por
        self._creado = creado
        self._actualizado = actualizado

    @classmethod
    def crear(
        cls,
        partida_id: PartidaId,
        round_id: RoundId,
        competition_id: CompetitionId,
        user_id: UserId,
        hoyo: int,
        momento: datetime,
    ) -> "GolpeDePartida":
        """Un hoyo sin nada apuntado todavía."""
        return cls(
            partida_id=partida_id,
            round_id=round_id,
            competition_id=competition_id,
            user_id=user_id,
            hoyo=hoyo,
            propio=None,
            propio_enviado=False,
            propio_por=None,
            del_marcador=None,
            marcador_enviado=False,
            marcador_por=None,
            creado=momento,
            actualizado=momento,
        )

    # ==================== Comandos ====================

    def anotar_propio(
        self, golpes: int | None, acepta_raya: bool, quien: UserId, momento: datetime
    ) -> None:
        """El lado del jugador (o del organizador por él). None es levantar bola."""
        self._comprobar(golpes, acepta_raya)
        self._propio, self._propio_enviado, self._propio_por = golpes, True, quien
        self._actualizado = momento

    def anotar_del_marcador(
        self, golpes: int | None, acepta_raya: bool, quien: UserId, momento: datetime
    ) -> None:
        """El lado del marcador (o del organizador, que hace de marcador)."""
        self._comprobar(golpes, acepta_raya)
        self._del_marcador, self._marcador_enviado, self._marcador_por = golpes, True, quien
        self._actualizado = momento

    @staticmethod
    def _comprobar(golpes: int | None, acepta_raya: bool) -> None:
        if golpes is None:
            if not acepta_raya:
                raise RayaNoPermitidaError("En Medal no se levanta bola: hay que acabar el hoyo.")
            return
        if not MIN_GOLPES <= golpes <= MAX_GOLPES:
            raise ValueError(f"Los golpes van de {MIN_GOLPES} a {MAX_GOLPES}, no {golpes}.")

    # ==================== Consultas ====================

    @property
    def estado(self) -> ValidationStatus:
        """PENDING si falta un lado; MATCH si coinciden (también dos rayas); si no, MISMATCH."""
        if not (self._propio_enviado and self._marcador_enviado):
            return ValidationStatus.PENDING
        if self._propio == self._del_marcador:
            return ValidationStatus.MATCH
        return ValidationStatus.MISMATCH

    @property
    def validado(self) -> bool:
        return self.estado == ValidationStatus.MATCH

    @property
    def golpes_validados(self) -> int | None:
        """Los golpes que cuentan, si está validado; None también es una raya validada."""
        return self._propio if self.validado else None

    @property
    def partida_id(self) -> PartidaId:
        return self._partida_id

    @property
    def round_id(self) -> RoundId:
        return self._round_id

    @property
    def competition_id(self) -> CompetitionId:
        return self._competition_id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def hoyo(self) -> int:
        return self._hoyo

    @property
    def propio(self) -> int | None:
        return self._propio

    @property
    def propio_enviado(self) -> bool:
        return self._propio_enviado

    @property
    def propio_por(self) -> UserId | None:
        return self._propio_por

    @property
    def del_marcador(self) -> int | None:
        return self._del_marcador

    @property
    def marcador_enviado(self) -> bool:
        return self._marcador_enviado

    @property
    def marcador_por(self) -> UserId | None:
        return self._marcador_por

    @property
    def creado(self) -> datetime:
        return self._creado

    @property
    def actualizado(self) -> datetime:
        return self._actualizado
