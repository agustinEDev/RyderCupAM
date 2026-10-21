"""
Cuándo se pueden actualizar los hándicaps a mano (#251, decidido el 7 oct 2026).

Desde que se cierran las inscripciones hasta 10 s por jugador antes de la
siguiente salida, nunca con una jornada en marcha (de su primera salida a
medianoche, hora del campo). En una Ryder, del cierre a iniciar.

| Caso                                                | Ventana                                 |
|-----------------------------------------------------|-----------------------------------------|
| Inscripciones abiertas                              | Cerrada                                 |
| Terminada o cancelada                               | Cerrada                                 |
| Ryder cerrada                                       | Abierta, sin hora de cierre             |
| Ryder en juego                                      | Cerrada                                 |
| Stroke play sin franjas, cerrada                    | Abierta, sin hora de cierre             |
| Stroke play cerrada, antes de la primera salida     | Abierta hasta salida - 10 s x jugadores |
| Justo en el límite                                  | Cerrada                                 |
| Con una jornada en marcha                           | Cerrada                                 |
| Entre jornadas (pasada la medianoche)               | Abierta hasta la siguiente              |
| Tras la última jornada                              | Cerrada                                 |
| Cada motivo                                         | Con su código, para traducirlo (#541)   |
"""

from datetime import UTC, datetime, timedelta

from src.modules.competition.domain.services.ventana_de_actualizacion import (
    Jornada,
    VentanaDeActualizacion,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus

VIERNES = Jornada(
    primera_salida=datetime(2030, 10, 11, 7, 0, tzinfo=UTC),
    fin=datetime(2030, 10, 11, 22, 0, tzinfo=UTC),
)
SABADO = Jornada(
    primera_salida=datetime(2030, 10, 12, 7, 0, tzinfo=UTC),
    fin=datetime(2030, 10, 12, 22, 0, tzinfo=UTC),
)


def _ventana(
    ahora,
    status=CompetitionStatus.CLOSED,
    stroke_play=True,
    jornadas=(VIERNES, SABADO),
    jugadores=30,
):
    return VentanaDeActualizacion.calcular(
        stroke_play=stroke_play,
        status=status,
        jornadas=list(jornadas),
        jugadores=jugadores,
        ahora=ahora,
    )


class TestPorEstado:
    def test_con_las_inscripciones_abiertas_no(self):
        ventana = _ventana(datetime(2030, 10, 1, tzinfo=UTC), status=CompetitionStatus.ACTIVE)

        assert not ventana.abierta
        assert "se cierran las inscripciones" in ventana.motivo

    def test_terminada_o_cancelada_no(self):
        for status in (CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED):
            assert not _ventana(datetime(2030, 10, 1, tzinfo=UTC), status=status).abierta

    def test_ryder_cerrada_si_y_sin_hora_de_cierre(self):
        ventana = _ventana(datetime(2030, 10, 1, tzinfo=UTC), stroke_play=False, jornadas=())

        assert ventana.abierta
        assert ventana.cierra is None

    def test_ryder_en_juego_no(self):
        ventana = _ventana(
            datetime(2030, 10, 1, tzinfo=UTC),
            status=CompetitionStatus.IN_PROGRESS,
            stroke_play=False,
            jornadas=(),
        )

        assert not ventana.abierta
        assert "iniciar" in ventana.motivo

    def test_stroke_play_sin_franjas_como_la_ryder(self):
        ventana = _ventana(datetime(2030, 10, 1, tzinfo=UTC), jornadas=())

        assert ventana.abierta
        assert ventana.cierra is None

    def test_stroke_play_en_juego_sin_franjas_no_habla_de_la_ryder(self):
        ventana = _ventana(
            datetime(2030, 10, 1, tzinfo=UTC), status=CompetitionStatus.IN_PROGRESS, jornadas=()
        )

        assert not ventana.abierta
        assert "Ryder" not in ventana.motivo
        assert "franjas" in ventana.motivo


class TestAntesDeCadaJornada:
    def test_abierta_hasta_diez_segundos_por_jugador_antes_de_la_salida(self):
        ventana = _ventana(datetime(2030, 10, 10, 12, 0, tzinfo=UTC))

        assert ventana.abierta
        assert ventana.cierra == VIERNES.primera_salida - timedelta(seconds=300)

    def test_justo_en_el_limite_cerrada(self):
        limite = VIERNES.primera_salida - timedelta(seconds=300)

        ventana = _ventana(limite)

        assert not ventana.abierta
        assert "salida" in ventana.motivo
        assert _ventana(limite - timedelta(seconds=1)).abierta

    def test_con_una_jornada_en_marcha_cerrada(self):
        for ahora in (VIERNES.primera_salida, VIERNES.fin - timedelta(seconds=1)):
            ventana = _ventana(ahora, status=CompetitionStatus.IN_PROGRESS)

            assert not ventana.abierta
            assert "en marcha" in ventana.motivo

    def test_entre_jornadas_abierta_hasta_la_siguiente(self):
        ventana = _ventana(VIERNES.fin, status=CompetitionStatus.IN_PROGRESS)

        assert ventana.abierta
        assert ventana.cierra == SABADO.primera_salida - timedelta(seconds=300)

    def test_tras_la_ultima_jornada_cerrada(self):
        ventana = _ventana(SABADO.fin, status=CompetitionStatus.IN_PROGRESS)

        assert not ventana.abierta
        assert "no quedan" in ventana.motivo


class TestElCodigoDeCadaMotivo:
    """El aviso llegaba en español con la app en inglés: el front traduce el código (#541)."""

    def test_cada_caso_cerrado_con_su_codigo(self):
        casos = {
            "STATUS": _ventana(datetime(2030, 10, 1, tzinfo=UTC), status=CompetitionStatus.ACTIVE),
            "RYDER": _ventana(
                datetime(2030, 10, 1, tzinfo=UTC),
                status=CompetitionStatus.IN_PROGRESS,
                stroke_play=False,
                jornadas=(),
            ),
            "NO_WINDOWS": _ventana(
                datetime(2030, 10, 1, tzinfo=UTC), status=CompetitionStatus.IN_PROGRESS, jornadas=()
            ),
            "DAY_IN_PLAY": _ventana(VIERNES.primera_salida, status=CompetitionStatus.IN_PROGRESS),
            "NO_DAYS_LEFT": _ventana(SABADO.fin, status=CompetitionStatus.IN_PROGRESS),
            "TOO_CLOSE": _ventana(VIERNES.primera_salida - timedelta(seconds=300)),
        }

        assert {codigo: v.codigo for codigo, v in casos.items()} == {c: c for c in casos}
        assert not any(v.abierta for v in casos.values())

    def test_abierta_sin_codigo(self):
        assert _ventana(datetime(2030, 10, 10, 12, 0, tzinfo=UTC)).codigo is None


class TestElMotivoEsElDelDominio:
    """El motivo de la ventana es la constante del dominio que lee la ruta (BE #562)."""

    def test_cada_motivo_es_su_constante(self):
        from src.modules.competition.domain.services.ventana_de_actualizacion import MOTIVOS

        casos = [
            _ventana(datetime(2030, 10, 1, tzinfo=UTC), status=CompetitionStatus.ACTIVE),
            _ventana(
                datetime(2030, 10, 1, tzinfo=UTC),
                status=CompetitionStatus.IN_PROGRESS,
                stroke_play=False,
                jornadas=(),
            ),
            _ventana(
                datetime(2030, 10, 1, tzinfo=UTC),
                status=CompetitionStatus.IN_PROGRESS,
                jornadas=(),
            ),
            _ventana(datetime(2030, 10, 11, 10, 0, tzinfo=UTC)),
            _ventana(datetime(2030, 10, 13, 10, 0, tzinfo=UTC)),
            _ventana(datetime(2030, 10, 11, 6, 59, 50, tzinfo=UTC)),
        ]

        assert [v.codigo for v in casos] == [
            "STATUS",
            "RYDER",
            "NO_WINDOWS",
            "DAY_IN_PLAY",
            "NO_DAYS_LEFT",
            "TOO_CLOSE",
        ]
        for ventana in casos:
            assert ventana.motivo == MOTIVOS[ventana.codigo]
