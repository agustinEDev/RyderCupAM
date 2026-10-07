"""
A quién se pregunta a la RFEG en una actualización de hándicaps (#251, 7 oct 2026).

Cada pasada hace hasta 3 intentos por jugador. Si una actualización quedó a
medias, la siguiente pasada termina solo lo que falta.

| Caso                                     | ¿Se pregunta? |
|------------------------------------------|---------------|
| Sin preguntar todavía                    | Sí            |
| Con hándicap personalizado               | No, nunca     |
| Actualizado, no encontrado, sin licencia | No            |
| Falló                                    | Sí            |
"""

from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Candidato,
    RefrescoDeHandicapsService,
    ResultadoRefresco,
)
from src.modules.user.domain.value_objects.user_id import UserId


def _a_quien(personalizado=False, resultado=None) -> bool:
    user_id = UserId.generate()
    resultados = {} if resultado is None else {user_id: resultado}
    return user_id in RefrescoDeHandicapsService.a_quien(
        [Candidato(user_id=user_id, handicap_personalizado=personalizado)], resultados
    )


class TestAQuien:
    def test_sin_preguntar_todavia_si(self):
        assert _a_quien()

    def test_con_personalizado_nunca(self):
        assert not _a_quien(personalizado=True)

    def test_lo_que_ya_tiene_respuesta_no_se_repite(self):
        for resultado in (
            ResultadoRefresco.ACTUALIZADO,
            ResultadoRefresco.NO_ENCONTRADO,
            ResultadoRefresco.SIN_LICENCIA_ESPANOLA,
        ):
            assert not _a_quien(resultado=resultado), resultado

    def test_lo_que_fallo_se_vuelve_a_preguntar(self):
        assert _a_quien(resultado=ResultadoRefresco.FALLIDO)

    def test_respeta_el_orden_de_los_candidatos(self):
        ids = [UserId.generate() for _ in range(4)]
        candidatos = [Candidato(user_id=u, handicap_personalizado=False) for u in ids]

        assert RefrescoDeHandicapsService.a_quien(candidatos, {}) == ids
