"""
Desde qué barras juega cada uno (#251, PR 4): la Ryder y las partidas, igual.

Sacado de `MatchPlayersBuilder.resolve_player_data` para que las partidas de
stroke play elijan las barras con la misma regla (RyderCupAM#165): primero
(color, género) y si no, (color, sin género). Nunca la del otro género.

| Barras de la inscripción | Jugador | Valoradas en el campo        | Resultado               |
|--------------------------|---------|------------------------------|-------------------------|
| Ninguna                  | Hombre  | (Amarillas, hombre)          | Amarillas, hombre       |
| Ninguna                  | Mujer   | (Rojas, mujer)               | Rojas, mujer (BE #912)  |
| Rojas                    | Mujer   | (Rojas, mujer), (Rojas, —)   | Rojas, mujer            |
| Rojas                    | Mujer   | (Rojas, —)                   | Rojas, sin género       |
| Rojas                    | Mujer   | (Rojas, hombre)              | Rojas, sin valoración   |
| Rojas                    | Sin     | (Rojas, —)                   | Rojas, sin género       |
| Rojas                    | Sin     | (Rojas, hombre)              | Rojas, sin valoración   |
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.barra_del_jugador import (
    barra_del_jugador,
    barra_sin_golpes,
    lo_que_le_falta,
)
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_GENDER,
    MISSING_TEE_COLOR,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.value_objects.gender import Gender

AMARILLAS_H = TeeRating(course_rating=Decimal("71.2"), slope_rating=130, par=72)
ROJAS_M = TeeRating(course_rating=Decimal("73.0"), slope_rating=128, par=72)
ROJAS = TeeRating(course_rating=Decimal("70.0"), slope_rating=120, par=72)
ROJAS_H = TeeRating(course_rating=Decimal("68.0"), slope_rating=118, par=72)


@pytest.mark.parametrize(
    ("de_la_inscripcion", "genero", "valoradas", "esperado"),
    [
        pytest.param(
            None,
            Gender.MALE,
            {("YELLOW", "MALE"): AMARILLAS_H},
            (TeeColor.YELLOW, Gender.MALE, AMARILLAS_H),
            id="sin barras elegidas, amarillas",
        ),
        pytest.param(
            TeeColor.RED,
            Gender.FEMALE,
            {("RED", "FEMALE"): ROJAS_M, ("RED", None): ROJAS},
            (TeeColor.RED, Gender.FEMALE, ROJAS_M),
            id="la de su género",
        ),
        pytest.param(
            TeeColor.RED,
            Gender.FEMALE,
            {("RED", None): ROJAS},
            (TeeColor.RED, None, ROJAS),
            id="la sin género de reserva",
        ),
        pytest.param(
            TeeColor.RED,
            Gender.FEMALE,
            {("RED", "MALE"): ROJAS_H},
            (TeeColor.RED, None, None),
            id="nunca la del otro género",
        ),
        pytest.param(
            TeeColor.RED,
            None,
            {("RED", None): ROJAS},
            (TeeColor.RED, None, ROJAS),
            id="jugador sin género, la sin género",
        ),
        pytest.param(
            TeeColor.RED,
            None,
            {("RED", "MALE"): ROJAS_H},
            (TeeColor.RED, None, None),
            id="jugador sin género, ninguna",
        ),
    ],
)
def test_barra_del_jugador(de_la_inscripcion, genero, valoradas, esperado):
    barra = barra_del_jugador(de_la_inscripcion, genero, valoradas)

    assert (barra.tee_color, barra.tee_gender, barra.tee_rating) == esperado


class TestLoQueLeFalta:
    """Qué le falta a quien no tiene barras: su género, o su color (BE #360, #361)."""

    @pytest.mark.parametrize(
        ("genero", "valoradas", "esperado"),
        [
            pytest.param(Gender.FEMALE, {("RED", "FEMALE"): ROJAS_M}, None, id="con barras, nada"),
            pytest.param(None, {("RED", "MALE"): ROJAS_H}, (MISSING_GENDER, None), id="sin género"),
            pytest.param(
                Gender.FEMALE,
                {("RED", "MALE"): ROJAS_H},
                (MISSING_TEE_COLOR, "RED"),
                id="el color, no para su género",
            ),
            pytest.param(
                None,
                {("YELLOW", "MALE"): AMARILLAS_H},
                (MISSING_TEE_COLOR, "RED"),
                id="sin género y el color no existe",
            ),
        ],
    )
    def test_lo_que_le_falta(self, genero, valoradas, esperado):
        barra = barra_del_jugador(TeeColor.RED, genero, valoradas)

        assert lo_que_le_falta(barra, genero, valoradas) == esperado


# SCRATCH (P12 de stroke play, y la Ryder desde RyderCupWeb #880): sin golpes las
# barras no hace falta que estén valoradas, pero su género sí se guarda si tienen
# tarjeta; con él, el mapa del hoyo sabe de qué barra es cada muestra
@pytest.mark.parametrize(
    ("genero", "valoradas", "con_tarjeta", "esperado"),
    [
        pytest.param(
            Gender.MALE,
            {("YELLOW", "MALE"): AMARILLAS_H},
            {},
            (TeeColor.YELLOW, Gender.MALE),
            id="valorada para su género",
        ),
        pytest.param(
            Gender.MALE,
            {},
            {("YELLOW", "MALE"): object()},
            (TeeColor.YELLOW, Gender.MALE),
            id="sin valorar, con tarjeta de su género",
        ),
        pytest.param(
            Gender.MALE,
            {},
            {("YELLOW", None): object()},
            (TeeColor.YELLOW, None),
            id="con tarjeta sin género",
        ),
        pytest.param(Gender.MALE, {}, {}, (TeeColor.YELLOW, None), id="ni valorada ni con tarjeta"),
        pytest.param(
            Gender.FEMALE,
            {},
            {("RED", "MALE"): object()},
            (TeeColor.RED, None),
            id="la tarjeta es del otro género",
        ),
        pytest.param(
            None,
            {},
            {("YELLOW", "MALE"): object()},
            (TeeColor.YELLOW, None),
            id="sin género del jugador",
        ),
    ],
)
def test_barra_sin_golpes(genero, valoradas, con_tarjeta, esperado):
    barra = barra_sin_golpes(None, genero, valoradas, con_tarjeta)

    assert (barra.tee_color, barra.tee_gender) == esperado


AMARILLAS_M = TeeRating(course_rating=Decimal("74.5"), slope_rating=133, par=72)
AMARILLAS = TeeRating(course_rating=Decimal("71.0"), slope_rating=125, par=72)


class TestBarraPorDefecto:
    """
    Quien no eligió barras juega desde la habitual de su género, la misma que
    la partida rápida (BE #912, decidido el 20 nov 2026): amarillas los
    hombres y rojas las mujeres, de su género o mixtas. Si el campo no las
    tiene valoradas se quedan sin valorar, y el organizador ve el aviso.

    | #  | Jugador | Valoradas en el campo        | Resultado               |
    |----|---------|------------------------------|-------------------------|
    | D1 | Hombre  | (Amarillas, hombre)          | Amarillas, hombre       |
    | D1 | Hombre  | (Amarillas, —)               | Amarillas, sin género   |
    | D2 | Mujer   | (Rojas, mujer), (Amarillas, mujer) | Rojas, mujer      |
    | D2 | Mujer   | (Rojas, —)                   | Rojas, sin género       |
    | D3 | Mujer   | (Amarillas, mujer)           | Rojas, sin valoración   |
    | D4 | Hombre  | (Rojas, hombre)              | Amarillas, sin valoración |
    | D5 | Mujer que eligió azules | (Rojas, mujer) | Azules, sin valoración (las suyas) |
    | D6 | Sin     | (Amarillas, —)               | Amarillas, sin género   |
    | D7 | Mujer en scratch | (Rojas, mujer), con tarjeta | Rojas, mujer       |
    """

    @pytest.mark.parametrize(
        ("genero", "valoradas", "esperado"),
        [
            pytest.param(
                Gender.MALE,
                {("YELLOW", "MALE"): AMARILLAS_H},
                (TeeColor.YELLOW, Gender.MALE, AMARILLAS_H),
                id="D1 hombre, amarillas de hombre",
            ),
            pytest.param(
                Gender.MALE,
                {("YELLOW", None): AMARILLAS},
                (TeeColor.YELLOW, None, AMARILLAS),
                id="D1 hombre, amarillas mixtas",
            ),
            pytest.param(
                Gender.FEMALE,
                {("RED", "FEMALE"): ROJAS_M, ("YELLOW", "FEMALE"): AMARILLAS_M},
                (TeeColor.RED, Gender.FEMALE, ROJAS_M),
                id="D2 mujer, rojas de mujer aunque haya amarillas de mujer",
            ),
            pytest.param(
                Gender.FEMALE,
                {("RED", None): ROJAS},
                (TeeColor.RED, None, ROJAS),
                id="D2 mujer, rojas mixtas",
            ),
            pytest.param(
                Gender.FEMALE,
                {("YELLOW", "FEMALE"): AMARILLAS_M},
                (TeeColor.RED, None, None),
                id="D3 mujer sin rojas valoradas, rojas sin valorar",
            ),
            pytest.param(
                Gender.MALE,
                {("RED", "MALE"): ROJAS_H},
                (TeeColor.YELLOW, None, None),
                id="D4 hombre sin amarillas valoradas, amarillas sin valorar",
            ),
            pytest.param(
                None,
                {("YELLOW", None): AMARILLAS},
                (TeeColor.YELLOW, None, AMARILLAS),
                id="D6 sin género, amarillas como siempre",
            ),
        ],
    )
    def test_barra_del_jugador_sin_elegir_da_la_habitual_de_su_genero(
        self, genero, valoradas, esperado
    ):
        """
        Given un jugador que no eligió barras en su inscripción
        When se busca desde qué barras juega
        Then son las habituales de su género, valoradas o no
        """
        barra = barra_del_jugador(None, genero, valoradas)

        assert (barra.tee_color, barra.tee_gender, barra.tee_rating) == esperado

    def test_barra_del_jugador_que_eligio_da_la_suya_aunque_no_este_valorada(self):
        """
        Given una mujer que eligió azules en un campo con solo rojas de mujer
        When se busca desde qué barras juega
        Then son las suyas, sin valorar: la regla por defecto no pisa lo elegido (D5)
        """
        barra = barra_del_jugador(TeeColor.BLUE, Gender.FEMALE, {("RED", "FEMALE"): ROJAS_M})

        assert (barra.tee_color, barra.tee_gender, barra.tee_rating) == (TeeColor.BLUE, None, None)

    def test_lo_que_le_falta_mujer_sin_rojas_valoradas_es_su_color(self):
        """
        Given una mujer sin barras elegidas en un campo sin rojas valoradas
        When se mira qué le falta para generar el partido
        Then es el color rojo (el aviso que ve el organizador)
        """
        valoradas = {("YELLOW", "FEMALE"): AMARILLAS_M}
        barra = barra_del_jugador(None, Gender.FEMALE, valoradas)

        assert lo_que_le_falta(barra, Gender.FEMALE, valoradas) == (MISSING_TEE_COLOR, "RED")

    def test_barra_sin_golpes_sin_elegir_mujer_da_rojas(self):
        """
        Given una mujer que juega scratch sin barras elegidas
        When se buscan sus barras sin golpes
        Then son las rojas de su género, como con golpes (D7)
        """
        valoradas = {("RED", "FEMALE"): ROJAS_M, ("YELLOW", "FEMALE"): AMARILLAS_M}

        barra = barra_sin_golpes(None, Gender.FEMALE, valoradas, valoradas)

        assert (barra.tee_color, barra.tee_gender) == (TeeColor.RED, Gender.FEMALE)


class TestBarraEnElCampo:
    """
    Qué barra juega un jugador en un campo (barras por campo, 20 nov 2026). Gana la
    primera que se cumpla:

    | #  | Regla                                                         |
    |----|---------------------------------------------------------------|
    | R1 | su cambio propio para ese campo                               |
    | R2 | la del campo para todos los de su género (no pisa R1)         |
    | R3 | su barra general (o la habitual de su género), si el campo la |
    |    | tiene para su género o mixta                                  |
    | R4 | si no: sin barra válida en ese campo (el aviso de generar)    |
    """

    def _campo(self, propias=None, por_genero=None):
        from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo

        return BarrasDelCampo(propias=propias or {}, por_genero=por_genero or {})

    def test_barra_en_el_campo_su_cambio_propio_gana(self):
        """
        Given una mujer con cambio propio a azules y el campo con rojas para mujeres
        When se busca su barra en ese campo
        Then azules (R1)
        """
        from src.modules.competition.domain.services.barra_del_jugador import barra_en_el_campo

        ana = UserId.generate()
        cambios = self._campo({ana: TeeColor.BLUE}, {Gender.FEMALE: TeeColor.RED})
        valoradas = {("BLUE", "FEMALE"): ROJAS_M, ("RED", "FEMALE"): ROJAS_M}

        barra = barra_en_el_campo(ana, None, Gender.FEMALE, cambios, valoradas)

        assert (barra.tee_color, barra.tee_gender) == (TeeColor.BLUE, Gender.FEMALE)

    def test_barra_en_el_campo_la_del_campo_para_su_genero(self):
        """
        Given una mujer sin cambio propio, con barra general amarilla, y el campo con
            rojas para mujeres
        When se busca su barra en ese campo
        Then rojas (R2), aunque su general sea otra
        """
        from src.modules.competition.domain.services.barra_del_jugador import barra_en_el_campo

        cambios = self._campo(por_genero={Gender.FEMALE: TeeColor.RED})
        valoradas = {("RED", "FEMALE"): ROJAS_M, ("YELLOW", "FEMALE"): AMARILLAS_M}

        barra = barra_en_el_campo(
            UserId.generate(), TeeColor.YELLOW, Gender.FEMALE, cambios, valoradas
        )

        assert barra.tee_color == TeeColor.RED

    def test_barra_en_el_campo_la_del_campo_no_es_para_el_otro_genero(self):
        """
        Given un hombre y el campo con rojas fijadas para mujeres
        When se busca su barra
        Then la suya general (R3), no la de ellas
        """
        from src.modules.competition.domain.services.barra_del_jugador import barra_en_el_campo

        cambios = self._campo(por_genero={Gender.FEMALE: TeeColor.RED})
        valoradas = {("YELLOW", "MALE"): AMARILLAS_H, ("RED", "FEMALE"): ROJAS_M}

        barra = barra_en_el_campo(UserId.generate(), None, Gender.MALE, cambios, valoradas)

        assert (barra.tee_color, barra.tee_gender) == (TeeColor.YELLOW, Gender.MALE)

    def test_barra_en_el_campo_sin_cambios_su_general(self):
        """
        Given una mujer con barra general azul y sin cambios en el campo
        When se busca su barra
        Then azules (R3)
        """
        from src.modules.competition.domain.services.barra_del_jugador import barra_en_el_campo

        barra = barra_en_el_campo(
            UserId.generate(),
            TeeColor.BLUE,
            Gender.FEMALE,
            self._campo(),
            {("BLUE", "FEMALE"): ROJAS_M},
        )

        assert barra.tee_color == TeeColor.BLUE and barra.tee_rating is ROJAS_M

    def test_barra_en_el_campo_sin_la_suya_no_hay_otra_automatica(self):
        """
        Given una mujer con general azul en un campo sin azules para ella
        When se busca su barra
        Then sin valorar (R4): no se elige otra sola; el aviso dirá azules
        """
        from src.modules.competition.domain.services.barra_del_jugador import barra_en_el_campo

        valoradas = {("RED", "FEMALE"): ROJAS_M}
        barra = barra_en_el_campo(
            UserId.generate(), TeeColor.BLUE, Gender.FEMALE, self._campo(), valoradas
        )

        assert (barra.tee_color, barra.tee_rating) == (TeeColor.BLUE, None)
        assert lo_que_le_falta(barra, Gender.FEMALE, valoradas) == (MISSING_TEE_COLOR, "BLUE")

    def test_barra_en_el_campo_en_scratch_con_tarjeta(self):
        """
        Given SCRATCH y el campo con blancas de mujer solo con tarjeta, fijadas para ellas
        When se busca su barra con las de tarjeta
        Then blancas de mujer
        """
        from src.modules.competition.domain.services.barra_del_jugador import barra_en_el_campo

        cambios = self._campo(por_genero={Gender.FEMALE: TeeColor.WHITE})

        barra = barra_en_el_campo(
            UserId.generate(),
            None,
            Gender.FEMALE,
            cambios,
            {},
            con_tarjeta={("WHITE", "FEMALE"): object()},
        )

        assert (barra.tee_color, barra.tee_gender) == (TeeColor.WHITE, Gender.FEMALE)


class TestLoQueLeFaltaEnScratch:
    """
    En SCRATCH le vale también una barra con tarjeta (la de su género o mixta):
    el mismo criterio que el selector y que `GET /enrollments/{id}/tees`. Sin ella
    hay que elegirla y la generación se bloquea con el aviso de siempre (R4).
    """

    TARJETA = object()

    @pytest.mark.parametrize(
        ("color", "genero", "valoradas", "con_tarjeta", "esperado"),
        [
            pytest.param(
                TeeColor.RED,
                Gender.FEMALE,
                {("RED", "FEMALE"): ROJAS_M},
                {("RED", "FEMALE"): TARJETA},
                None,
                id="D1 valorada de su género",
            ),
            pytest.param(
                TeeColor.RED,
                Gender.FEMALE,
                {},
                {("RED", "FEMALE"): TARJETA},
                None,
                id="D2 sin valorar con tarjeta de su género",
            ),
            pytest.param(
                TeeColor.RED,
                Gender.FEMALE,
                {},
                {("RED", None): TARJETA},
                None,
                id="D3 con tarjeta mixta",
            ),
            pytest.param(
                TeeColor.YELLOW,
                Gender.FEMALE,
                {("YELLOW", "MALE"): AMARILLAS_H},
                {("YELLOW", "MALE"): TARJETA},
                (MISSING_TEE_COLOR, "YELLOW"),
                id="D4 solo la del otro género",
            ),
            pytest.param(
                TeeColor.GREEN,
                Gender.FEMALE,
                {("YELLOW", "MALE"): AMARILLAS_H},
                {("YELLOW", "MALE"): TARJETA},
                (MISSING_TEE_COLOR, "GREEN"),
                id="D5 el color no existe",
            ),
            pytest.param(
                TeeColor.RED,
                None,
                {},
                {("RED", "MALE"): TARJETA},
                (MISSING_GENDER, None),
                id="D6 sin género y el color solo con género",
            ),
        ],
    )
    def test_lo_que_le_falta_en_scratch(self, color, genero, valoradas, con_tarjeta, esperado):
        barra = barra_sin_golpes(color, genero, valoradas, con_tarjeta)

        assert lo_que_le_falta(barra, genero, valoradas, con_tarjeta) == esperado

    def test_d7_con_golpes_la_tarjeta_no_basta(self):
        """
        Given HANDICAP y unas rojas de mujer con tarjeta pero sin valorar
        When se mira qué le falta sin `con_tarjeta`
        Then su color, como hasta ahora
        """
        barra = barra_del_jugador(TeeColor.RED, Gender.FEMALE, {})

        assert lo_que_le_falta(barra, Gender.FEMALE, {}) == (MISSING_TEE_COLOR, "RED")

    @pytest.mark.parametrize(
        ("color", "genero", "valoradas", "con_tarjeta", "vale"),
        [
            pytest.param(TeeColor.RED, Gender.FEMALE, {("RED", "FEMALE"): ROJAS_M}, None, True),
            pytest.param(TeeColor.RED, Gender.FEMALE, {("RED", None): ROJAS}, None, True),
            pytest.param(TeeColor.RED, Gender.FEMALE, {("RED", "MALE"): ROJAS_H}, None, False),
            pytest.param(TeeColor.RED, Gender.FEMALE, {}, {("RED", "FEMALE"): TARJETA}, True),
            pytest.param(TeeColor.RED, Gender.FEMALE, {}, {("RED", None): TARJETA}, True),
            pytest.param(TeeColor.RED, Gender.FEMALE, {}, {("RED", "MALE"): TARJETA}, False),
            pytest.param(TeeColor.RED, None, {}, {("RED", "FEMALE"): TARJETA}, False),
            pytest.param(TeeColor.RED, None, {}, {("RED", None): TARJETA}, True),
            pytest.param(TeeColor.RED, Gender.FEMALE, {}, None, False),
        ],
    )
    def test_d8_la_barra_vale(self, color, genero, valoradas, con_tarjeta, vale):
        from src.modules.competition.domain.services.barra_del_jugador import la_barra_vale

        assert la_barra_vale(color, genero, valoradas, con_tarjeta) is vale
