"""La apertura programada de las inscripciones (BE #319, #332).

El organizador dice CUANTOS DIAS antes abre, no una fecha. El instante se
deriva de la fecha de inicio en cada lectura, asi que mover el torneo mueve la
apertura con el.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.user.domain.value_objects.user_id import UserId

MADRID = "Europe/Madrid"


def _crear(days_before: int | None = None, start: date | None = None) -> Competition:
    """Una competición recién creada, con o sin apertura programada."""
    comienzo = start or (date.today() + timedelta(days=30))
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=UserId(uuid4()),
        name=CompetitionName("Ryder Cup 2026"),
        dates=DateRange(comienzo, comienzo + timedelta(days=2)),
        location=Location(main_country="ES"),
        team_1_name="Europa",
        team_2_name="USA",
        play_mode=PlayMode.SCRATCH,
        enrollment_opens_days_before=days_before,
    )


class TestElCampo:
    """Cuantos dias antes: 1 a 14, o nada."""

    @pytest.mark.parametrize("dias", [1, 7, 14])
    def test_acepta_de_uno_a_catorce(self, dias):
        assert _crear(dias).enrollment_opens_days_before == dias

    def test_sin_programar_es_lo_normal(self):
        """La mayoria de torneos no programan nada: nacen abiertos."""
        assert _crear().enrollment_opens_days_before is None

    @pytest.mark.parametrize("dias", [0, 15, -1, 100])
    def test_rechaza_lo_que_esta_fuera_del_rango(self, dias):
        """Dos semanas es el tope, y cero dias no es «antes» de nada."""
        with pytest.raises(ValueError, match="1 y 14"):
            _crear(dias)

    def test_se_puede_desprogramar(self):
        """`None` aqui quita la fecha, no significa «dejala como esta»."""
        competition = _crear(5)

        competition.schedule_enrollment_opening(None)

        assert competition.enrollment_opens_days_before is None


class TestCuandoLeToca:
    """`due_to_open` mira el calendario del campo, no el del servidor."""

    def test_todavia_no_le_toca(self):
        competition = _crear(5, start=date.today() + timedelta(days=30))

        assert competition.due_to_open(MADRID) is False

    def test_ya_le_toca(self):
        """El torneo empieza en tres dias y abria cinco antes: hace dos que paso."""
        competition = _crear(5, start=date.today() + timedelta(days=3))

        assert competition.due_to_open(MADRID) is True

    def test_sin_programar_nunca_le_toca(self):
        """Sin dias no hay reloj que consultar: ahi abre la invitacion.

        El factory sigue naciendo en DRAFT —quien la abre al crearla es el caso
        de uso (BE #332)—, asi que esta competicion esta en borrador y sin
        programar, que es justo el caso.
        """
        competition = _crear(start=date.today() + timedelta(days=1))

        assert competition.status == CompetitionStatus.DRAFT
        assert competition.due_to_open(MADRID) is False

    def test_sin_zona_espera_en_vez_de_adivinar(self):
        competition = _crear(5, start=date.today() + timedelta(days=3))

        assert competition.due_to_open(None) is False

    def test_solo_un_borrador_se_abre_solo(self):
        """Una cancelada no resucita porque pase su hora."""
        competition = _crear(5, start=date.today() + timedelta(days=3))
        competition.cancel()

        assert competition.due_to_open(MADRID) is False

    def test_mover_las_fechas_mueve_la_apertura(self):
        """Es la razon de derivarlo: la apertura sigue al torneo.

        Antes el instante se guardaba, asi que adelantar el torneo dejaba la
        apertura donde estaba y habia que acordarse de cambiarla.
        """
        competition = _crear(5, start=date.today() + timedelta(days=30))
        assert competition.due_to_open(MADRID) is False

        cerca = date.today() + timedelta(days=3)
        competition.update_info(dates=DateRange(cerca, cerca + timedelta(days=2)))

        assert competition.due_to_open(MADRID) is True


class TestLaCoherenciaEntreElEstadoYLaProgramacion:
    """DRAFT significa «esperando su hora»: quitarla no puede dejarla varada.

    Tres caminos rompian eso, y los tres salen de lo mismo: bajo el modelo nuevo
    (BE #332) «sin programacion» quiere decir «abierta», asi que una competicion
    no puede quedarse en DRAFT sin nada que esperar.
    """

    def test_desprogramarla_la_abre(self):
        """Quitar los dias es decir «abrela ya», no «dejala cerrada para siempre».

        Antes daba igual: una competicion sin programar estaba en DRAFT porque
        todavia no la habia abierto nadie. Ahora, sin dias, lo que corresponde
        es tenerla abierta — y sin esto se quedaba cerrada sin forma de salir
        salvo el boton que FE #640 quiere retirar.
        """
        competition = _crear(5)
        assert competition.status == CompetitionStatus.DRAFT

        competition.schedule_enrollment_opening(None)

        assert competition.status == CompetitionStatus.ACTIVE
        assert competition.enrollment_opens_days_before is None

    def test_desprogramar_una_ya_abierta_no_la_toca(self):
        """No hay nada que abrir, y volver a abrirla anunciaria algo que ya paso."""
        competition = _crear()
        competition.activate()

        competition.schedule_enrollment_opening(None)

        assert competition.status == CompetitionStatus.ACTIVE

    def test_no_se_puede_programar_lo_que_ya_esta_abierto(self):
        """Programar una apertura sobre algo abierto se aceptaba y no hacia nada.

        El organizador recibia un 200 y el campo de vuelta en cada lectura,
        mientras la gente se apuntaba: la app anunciaba una apertura futura de
        algo que llevaba dias abierto.
        """
        competition = _crear()
        competition.activate()

        with pytest.raises(ValueError, match="ya están abiertas"):
            competition.schedule_enrollment_opening(5)

    def test_abrirla_a_mano_deja_de_prometer_una_apertura(self):
        """Adelantar la apertura cumple la programacion: ya no hay nada que esperar.

        Si el dato se quedara, la ficha seguiria diciendo «abre 5 dias antes»
        cuando ya abrio, y eso es una promesa que el sistema ya no puede cumplir.
        """
        competition = _crear(5)

        competition.activate()

        assert competition.status == CompetitionStatus.ACTIVE
        assert competition.enrollment_opens_days_before is None
