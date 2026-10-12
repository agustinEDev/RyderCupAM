"""
Las franjas de un stroke play en el dominio (#251, decidido el 7 oct 2026).

| Caso                                              | Resultado                        |
|---------------------------------------------------|----------------------------------|
| Stroke play: agenda hasta iniciar                 | Sí en borrador/abierta/cerrada   |
| Stroke play: agenda en juego o terminada          | No                               |
| Ryder: agenda en juego                            | Sí, como siempre (hasta terminar)|
| Stroke play sin hoja de salidas                   | Error                            |
| Ryder con hoja de salidas                         | Error                            |
| Franja nueva                                      | Individual, 95 %, con su hoja    |
| Cambiar la hoja                                   | Se cambia                        |
| Cambiar la hoja de una sesión de Ryder            | Error                            |
| Franjas de la jornada que se solapan              | Error con cuál                   |
| La misma franja al editarla                       | No choca consigo misma           |
| Otra jornada, misma hora                          | No choca                         |
| Otro campo, misma hora                            | No choca (es por el tee)         |
"""

from datetime import date, time

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.franjas_de_la_jornada import (
    FranjasDeLaJornada,
    FranjasSolapadasError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

SABADO = date(2030, 10, 12)


def _competicion(tipo=TournamentType.STABLEFORD, status=CompetitionStatus.ACTIVE):
    extra = (
        {}
        if tipo is not TournamentType.RYDER_CUP
        else {
            "team_1_name": "Europa",
            "team_2_name": "América",
        }
    )
    return Competition(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Medal de octubre"),
        dates=DateRange(SABADO, SABADO),
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        tournament_type=tipo,
        status=status,
        **extra,
    )


def _hoja(primera="09:00", ultima="12:00") -> HojaDeSalidas:
    return HojaDeSalidas(time.fromisoformat(primera), time.fromisoformat(ultima), 10, 4)


CAMPO = GolfCourseId.generate()


def _franja(hoja=None, dia=SABADO, sesion=SessionType.MORNING, campo=CAMPO) -> Round:
    return Round.create_franja(
        competition_id=CompetitionId.generate(),
        golf_course_id=campo,
        round_date=dia,
        session_type=sesion,
        hoja_de_salidas=hoja or _hoja(),
    )


class TestHastaCuandoSeEditaLaAgenda:
    @pytest.mark.parametrize(
        "status", [CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED]
    )
    def test_stroke_play_hasta_iniciar(self, status):
        assert _competicion(status=status).allows_agenda_edits()

    @pytest.mark.parametrize("status", [CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED])
    def test_stroke_play_ni_en_juego_ni_terminada(self, status):
        assert not _competicion(status=status).allows_agenda_edits()

    def test_la_ryder_como_siempre_hasta_terminar(self):
        ryder = _competicion(TournamentType.RYDER_CUP, CompetitionStatus.IN_PROGRESS)

        assert ryder.allows_agenda_edits()
        assert not _competicion(
            TournamentType.RYDER_CUP, CompetitionStatus.COMPLETED
        ).allows_agenda_edits()


class TestQueSesionLleva:
    def test_un_stroke_play_necesita_la_hoja_de_salidas(self):
        with pytest.raises(ValueError, match="hoja de salidas"):
            _competicion().comprobar_hoja_de_salidas(None)

    def test_una_ryder_no_la_lleva(self):
        with pytest.raises(ValueError, match="Ryder"):
            _competicion(TournamentType.RYDER_CUP).comprobar_hoja_de_salidas(_hoja())

    def test_cada_una_con_lo_suyo_vale(self):
        _competicion().comprobar_hoja_de_salidas(_hoja())
        _competicion(TournamentType.RYDER_CUP).comprobar_hoja_de_salidas(None)


class TestLaFranja:
    def test_nace_individual_al_95_con_su_hoja(self):
        franja = _franja()

        assert franja.match_format is MatchFormat.SINGLES
        assert franja.handicap_mode is None
        assert franja.allowance_percentage == 95
        assert franja.hoja_de_salidas == _hoja()

    def test_se_le_cambia_la_hoja(self):
        franja = _franja()

        franja.cambiar_hoja_de_salidas(_hoja("15:00", "18:00"))

        assert franja.hoja_de_salidas == _hoja("15:00", "18:00")

    def test_a_una_sesion_de_ryder_no(self):
        sesion = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=SABADO,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        with pytest.raises(ValueError, match="franja"):
            sesion.cambiar_hoja_de_salidas(_hoja())


class TestSolape:
    def test_dos_de_la_misma_jornada_que_se_solapan(self):
        manana = _franja(_hoja("09:00", "12:00"))

        with pytest.raises(FranjasSolapadasError, match="MORNING"):
            FranjasDeLaJornada.comprobar(_hoja("11:00", "14:00"), SABADO, CAMPO, [manana])

    def test_al_editarla_no_choca_consigo_misma(self):
        manana = _franja(_hoja("09:00", "12:00"))

        FranjasDeLaJornada.comprobar(
            _hoja("09:30", "12:30"), SABADO, CAMPO, [manana], excepto=manana.id
        )

    def test_otra_jornada_a_la_misma_hora_no_choca(self):
        domingo = _franja(_hoja("09:00", "12:00"), dia=date(2030, 10, 13))

        FranjasDeLaJornada.comprobar(_hoja("09:00", "12:00"), SABADO, CAMPO, [domingo])

    def test_en_otro_campo_a_la_misma_hora_no_choca(self):
        """El solape es por el tee compartido: en otro campo no lo hay (7 oct 2026)."""
        en_el_otro = _franja(_hoja("09:00", "12:00"), campo=GolfCourseId.generate())

        FranjasDeLaJornada.comprobar(_hoja("09:00", "12:00"), SABADO, CAMPO, [en_el_otro])
