"""
Quién se quedó sin actualizar con la RFEG, y a quién se le avisa (15 nov 2026).

Al terminar una actualización de hándicaps (y en cada pasada de una incompleta)
se mira quién se quedó sin actualizar: el organizador recibe la lista y el
jugador español al que la RFEG no encontró, su propio aviso.

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
| H5   | No encontrado y actualizado después               | No               | No           |
| H5   | No encontrado y actualizado antes                 | Sí               | Sí           |
| H5   | Sin preguntar y actualizado después de crearla    | No               | No           |
| —    | El usuario ya no existe                           | No               | No           |
| —    | El orden                                          | El de las inscripciones           |
"""

from datetime import UTC, datetime, timedelta

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

CREADA = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)
CONTESTO = CREADA + timedelta(minutes=1)


def _caso(
    resultado: ResultadoRefresco | None,
    *,
    espanol: bool = True,
    en_espana: bool = False,
    personalizado: bool = False,
    existe: bool = True,
    actualizado_en: datetime | None = None,
) -> tuple[bool, bool]:
    """(¿sale en la lista del organizador?, ¿recibe su aviso?) de un solo jugador."""
    user_id = UserId.generate()
    resultados = {} if resultado is None else {user_id: Intento(resultado, 1, momento=CONTESTO)}
    hecho = sin_actualizar(
        [
            Inscrito(
                user_id=user_id,
                handicap_personalizado=personalizado,
                existe=existe,
                espanol=espanol,
                actualizado_en=actualizado_en,
            )
        ],
        resultados,
        en_espana=en_espana,
        desde=CREADA,
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


class TestActualizadoDespues:
    def test_actualizado_despues_ya_no_sale(self):
        """
        Given un no encontrado que después actualizó su hándicap (desde su perfil)
        When se mira
        Then ya no sale ni para él ni para el organizador (H5)
        """
        despues = CONTESTO + timedelta(seconds=1)
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, actualizado_en=despues) == (False, False)

    def test_actualizado_antes_sigue_saliendo(self):
        """Given uno actualizado antes de que la RFEG contestara When se mira Then sigue."""
        assert _caso(ResultadoRefresco.NO_ENCONTRADO, actualizado_en=CONTESTO) == (True, True)

    def test_sin_preguntar_cuenta_desde_que_se_creo(self):
        """
        Given uno sin preguntar que actualizó su hándicap después de crearse la actualización
        When se mira
        Then ya no sale; si fue antes, sí
        """
        assert _caso(None, actualizado_en=CREADA + timedelta(seconds=1)) == (False, False)
        assert _caso(None, actualizado_en=CREADA) == (True, False)


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
                actualizado_en=None,
            )
            for u in ids
        ],
        {u: Intento(ResultadoRefresco.NO_ENCONTRADO, 1, momento=CONTESTO) for u in ids},
        en_espana=False,
        desde=CREADA,
    )
    assert hecho == SinActualizar(para_el_organizador=ids, no_encontrados=ids)


def test_el_momento_no_cuenta_al_comparar_intentos():
    """Los resultados de siempre se siguen comparando por resultado e intentos."""
    assert Intento(ResultadoRefresco.FALLIDO, 3, momento=CONTESTO) == Intento(
        ResultadoRefresco.FALLIDO, 3
    )
