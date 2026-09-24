"""
CompetitionStatus Value Object - Estado del ciclo de vida de una competición.

Define los estados posibles de una competición desde su creación hasta su finalización.
"""

from enum import StrEnum


class CompetitionStatus(StrEnum):
    """
    Enum para los estados del ciclo de vida de una competición.

    Estados:
    - DRAFT: Borrador, en configuración inicial
    - ACTIVE: Activa, inscripciones abiertas
    - CLOSED: Cerrada, inscripciones cerradas pero no empezó
    - IN_PROGRESS: En curso, el torneo está en desarrollo
    - COMPLETED: Finalizada
    - CANCELLED: Cancelada

    Transiciones válidas:
    DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED
               ↓    ↑    ↓    ↑       ↓
           CANCELLED  ACTIVE CANCELLED  CLOSED CANCELLED

    Backward transitions:
    - IN_PROGRESS → CLOSED: Revert to fix schedule issues
    - CLOSED → ACTIVE: Reopen enrollments to add/remove players
    """

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    def can_transition_to(self, new_status: "CompetitionStatus") -> bool:
        """
        Verifica si es válida la transición al nuevo estado.

        Args:
            new_status: Estado destino

        Returns:
            bool: True si la transición es válida, False en caso contrario

        Ejemplos:
            >>> CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.ACTIVE)
            True
            >>> CompetitionStatus.COMPLETED.can_transition_to(CompetitionStatus.DRAFT)
            False
        """
        valid_transitions = {
            CompetitionStatus.DRAFT: {
                CompetitionStatus.ACTIVE,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.ACTIVE: {
                CompetitionStatus.CLOSED,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.CLOSED: {
                CompetitionStatus.IN_PROGRESS,
                CompetitionStatus.ACTIVE,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.IN_PROGRESS: {
                CompetitionStatus.COMPLETED,
                CompetitionStatus.CLOSED,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.COMPLETED: set(),  # Estado final
            CompetitionStatus.CANCELLED: set(),  # Estado final
        }

        return new_status in valid_transitions.get(self, set())

    def is_active(self) -> bool:
        """Verifica si el estado permite inscripciones."""
        return self == CompetitionStatus.ACTIVE

    def is_final(self) -> bool:
        """Verifica si es un estado final (no permite más transiciones)."""
        return self in {CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED}

    def allows_agenda_edits(self) -> bool:
        """Verifica si se pueden crear, cambiar o borrar sesiones (BE #365).

        Desde que la competición existe hasta que termina o se cancela: la
        agenda se propone al crearla. Lo que se protege es tocar una sesión ya
        jugada, y eso lo decide cada sesión, no el estado de la competición
        (diseño del 20 sep).
        """
        return not self.is_final()

    def allows_modifications(self) -> bool:
        """Verifica si el estado permite modificar la configuración.

        Mientras las inscripciones están abiertas todavía se puede corregir el
        montaje: era solo DRAFT, y con la invitación abriendo el torneo
        (BE #319) eso convertía invitar en una puerta de un solo sentido, sin
        poder añadir siquiera el campo de golf que falta (BE #323). De CLOSED
        en adelante ya se sortean equipos y se generan partidos.
        """
        return self in {CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE}

    def allows_deletion(self) -> bool:
        """Verifica si el estado permite borrar la competicion del todo.

        Mientras no se esta jugando, equivocarse al crearla se deshace. Era solo
        DRAFT, y con las competiciones naciendo abiertas (BE #332) eso dejaba
        cancelar como unica salida, con la cancelada quedandose en la lista para
        siempre. CANCELLED entra por lo mismo: cancelar era la salida de un
        error, no su destino.

        CLOSED tambien (BE #347, 22 sep): ahi se sortean equipos y se monta el
        calendario, pero todo eso se rehace. Lo irrecuperable son los golpes, y
        se protege lo jugado, no lo montado.

        IN_PROGRESS y COMPLETED, nunca: ahi el torneo ES lo jugado.

        OJO: el estado por si solo no basta, y por eso esto es la MITAD de la
        regla. Se puede andar hacia atras —`revert-status` devuelve un torneo en
        juego a CLOSED y `reopen-enrollments` lo devuelve a ACTIVE—, y ninguna de
        las dos borra partidos ni golpes. Un torneo ya jugado puede estar en
        ACTIVE con sus tarjetas dentro. La otra mitad la pone
        `Competition.allows_deletion`, que ademas exige que no haya nada jugado.

        Regla propia y no `allows_modifications`: corregir el montaje y
        destruirlo no son lo mismo, y compartir el metodo las haria moverse
        juntas sin que nadie lo decida.
        """
        return self in {
            CompetitionStatus.DRAFT,
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
            CompetitionStatus.CANCELLED,
        }

    def allows_handicap_edits(self) -> bool:
        """Verifica si el estado permite editar el hándicap personalizado de un jugador."""
        return self in {
            CompetitionStatus.DRAFT,
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
        }

    def __composite_values__(self):
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.value,)


# Donde hay partidos que crear: cerrada, o ya en juego para las sesiones que
# vienen (BE #361). Una sola lista para la generacion a mano, la que sale al
# abrir los sobres y el aviso del organizador: si difieren, se contradicen
SE_JUEGA = (CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS)
