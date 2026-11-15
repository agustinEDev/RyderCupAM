"""
Quién se quedó sin actualizar con la RFEG, y a quién se le avisa (15 nov 2026).

Al terminar una actualización de hándicaps (y en cada pasada de una incompleta)
se mira quién se quedó sin actualizar: el organizador recibe la lista y el
jugador español al que la RFEG no encontró, su propio aviso. Solo cuenta lo que
dijo la RFEG (D1, 16 nov 2026): un hándicap puesto a mano no lo actualiza.

| Caso | Jugador                                           | ¿Al organizador? | ¿Aviso suyo? |
|------|---------------------------------------------------|------------------|--------------|
| H2   | Español, la RFEG no lo encontró                   | Sí               | Sí (H3)      |
| H4   | Español, la RFEG falló                            | Sí               | No           |
| H2   | Español, sin preguntar todavía (incompleta)       | Sí               | No           |
| H2   | Actualizado                                       | No               | No           |
| H2   | Con hándicap personalizado                        | No               | No           |
| H2   | Extranjero (sin licencia), competición en España  | Sí               | No (H6)      |
| H2   | Extranjero (sin licencia), competición fuera      | No               | No (H6)      |
| H6   | Extranjero no encontrado (raro), fuera de España  | No               | No           |
| H6   | Extranjero no encontrado (raro), en España        | Sí               | No           |
| D1   | Hándicap puesto a mano después (sin la RFEG)      | Sí               | Sí           |
| D1   | La RFEG lo encontró después (ACTUALIZADO apuntado)| No               | No           |
| T4   | Aprobado tras una actualización COMPLETA          | No               | No           |
| T4   | Aprobado tras una INCOMPLETA (sin preguntar)      | Sí               | No           |
| D3   | Quien no está en no encontrados                   | Se le retira el aviso (`sin_aviso`)  |
| —    | El usuario ya no existe                           | No               | No           |
| —    | El orden                                          | El de las inscripciones           |
"""

from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.competition.domain.services.sin_actualizar_con_la_rfeg import (
    Inscrito,
    SinActualizar,
    sin_actualizar,
)
from src.modules.user.domain.value_objects.user_id import UserId


def _caso(
    resultado: ResultadoRefresco | None,
    *,
    espanol: bool = True,
    en_espana: bool = False,
    personalizado: bool = False,
    existe: bool = True,
    completa: bool = False,
) -> tuple[bool, bool]:
    """(¿sale en la lista del organizador?, ¿recibe su aviso?) de un solo jugador."""
    user_id = UserId.generate()
    resultados = {} if resultado is None else {user_id: Intento(resultado, 1)}
    hecho = sin_actualizar(
        [
            Inscrito(
                user_id=user_id,
                handicap_personalizado=personalizado,
                existe=existe,
                espanol=espanol,
            )
        ],
        resultados,
        en_espana=en_espana,
        completa=completa,
    )
    return user_id in hecho.para_el_organizador, user_id in hecho.no_encontrados


class TestEspanoles:
    def test_no_encontrado_va_al_organizador_y_se_le_avisa(self):
        """
        Given un español al que la RFEG no encontró
        When se mira quién se quedó sin actualizar
        Then sale en la lista del organizador y recibe su aviso (H2, H3)
        """
        assert _caso(ResultadoRefresco.NO_ENCONTRADO) == (True, True)

    def test_si_la_rfeg_fallo_va_al_organizador_pero_a_el_nada(self):
        """
        Given un español con el que la RFEG falló
        When se mira
        Then sale en la lista del organizador, pero él no recibe nada (H4)
        """
        assert _caso(ResultadoRefresco.FALLIDO) == (True, False)

    def test_sin_preguntar_todavia_va_al_organizador(self):
        """
        Given un español al que no se llegó a preguntar (incompleta)
        When se mira
        Then sale en la lista del organizador, sin aviso suyo
        """
        assert _caso(None) == (True, False)

    def test_actualizado_no_sale(self):
        """Given uno actualizado When se mira Then no sale en ningún sitio."""
        assert _caso(ResultadoRefresco.ACTUALIZADO) == (False, False)

    def test_con_personalizado_no_sale(self):
        """
        Given uno con hándicap personalizado (lo puso el organizador)
        When se mira
        Then no sale aunque no se le preguntara
        """
        assert _caso(None, personalizado=True) == (False, False)
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, personalizado=True) == (False, False)

    def test_un_usuario_que_ya_no_existe_no_sale(self):
        """Given un jugador borrado When se mira Then no hay a quién nombrar ni avisar."""
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, existe=False) == (False, False)


class TestExtranjeros:
    def test_en_una_competicion_en_espana_van_al_organizador(self):
        """
        Given un extranjero (sin licencia española) en una competición en España
        When se mira
        Then sale en la lista del organizador, para que le ponga el hándicap a mano (H2)
        """
        assert _caso(ResultadoRefresco.SIN_LICENCIA_ESPANOLA, espanol=False, en_espana=True) == (
            True,
            False,
        )

    def test_en_una_competicion_fuera_no_salen(self):
        """Given un extranjero en una competición fuera de España When se mira Then no sale."""
        assert _caso(ResultadoRefresco.SIN_LICENCIA_ESPANOLA, espanol=False) == (False, False)

    def test_nunca_reciben_el_aviso_de_no_encontrado(self):
        """
        Given un extranjero apuntado como no encontrado (cambió de país después)
        When se mira
        Then no recibe aviso nunca (H6); al organizador, solo si es en España
        """
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, espanol=False) == (False, False)
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, espanol=False, en_espana=True) == (
            True,
            False,
        )


class TestSoloCuentaLaRfeg:
    def test_la_rfeg_lo_encontro_despues_ya_no_sale(self):
        """
        Given un no encontrado que después la RFEG sí encontró (desde su perfil),
              que queda apuntado como ACTUALIZADO en la actualización
        When se mira
        Then ya no sale ni para él ni para el organizador (D1, H5)
        """
        assert _caso(ResultadoRefresco.ACTUALIZADO) == (False, False)

    def test_el_handicap_del_perfil_no_cuenta(self):
        """
        Given un no encontrado
        When se mira (lo que haya puesto a mano no llega aquí)
        Then sigue saliendo: la regla no mira el hándicap del perfil (D1)
        """
        assert "actualizado_en" not in Inscrito.__dataclass_fields__
        assert _caso(ResultadoRefresco.NO_ENCONTRADO) == (True, True)


class TestAprobadoDespues:
    def test_tras_una_completa_no_sale(self):
        """
        Given un jugador aprobado después de una actualización COMPLETA (nunca preguntado)
        When se mira
        Then no sale: esa actualización no era para él (T4)
        """
        assert _caso(None, completa=True) == (False, False)

    def test_tras_una_incompleta_sale(self):
        """Given uno sin preguntar en una INCOMPLETA When se mira Then sale (el botón le pregunta)."""
        assert _caso(None, completa=False) == (True, False)

    def test_con_respuesta_en_una_completa_sigue_contando(self):
        """Given un no encontrado en una COMPLETA When se mira Then sale y se le avisa."""
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, completa=True) == (True, True)


class TestSinAviso:
    def test_a_quien_no_esta_no_encontrado_se_le_retira(self):
        """
        Given uno no encontrado, uno actualizado, uno fallido y uno con personalizado
        When se mira
        Then a todos menos al no encontrado se les retira el aviso (D3)
        """
        perdido, bien, roto, propio, borrado = (UserId.generate() for _ in range(5))
        hecho = sin_actualizar(
            [
                Inscrito(
                    user_id=u, handicap_personalizado=u == propio, existe=u != borrado, espanol=True
                )
                for u in (perdido, bien, roto, propio, borrado)
            ],
            {
                perdido: Intento(ResultadoRefresco.NO_ENCONTRADO, 1),
                bien: Intento(ResultadoRefresco.ACTUALIZADO, 1),
                roto: Intento(ResultadoRefresco.FALLIDO, 3),
            },
            en_espana=False,
            completa=False,
        )
        assert hecho.sin_aviso == [bien, roto, propio]


def test_en_el_orden_de_las_inscripciones():
    """Given varios When se mira Then salen en el orden en que llegan las inscripciones."""
    ids = [UserId.generate() for _ in range(3)]
    hecho = sin_actualizar(
        [
            Inscrito(
                user_id=u,
                handicap_personalizado=False,
                existe=True,
                espanol=True,
            )
            for u in ids
        ],
        {u: Intento(ResultadoRefresco.NO_ENCONTRADO, 1) for u in ids},
        en_espana=False,
        completa=False,
    )
    assert hecho == SinActualizar(para_el_organizador=ids, no_encontrados=ids, sin_aviso=[])
