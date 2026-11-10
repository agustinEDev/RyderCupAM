"""
Al cliente solo le llegan dos códigos del refresco (BE #733).

Desde BE #731 el 401 del refresco decía el motivo exacto, y quien tuviera una cookie
de refresco robada podía saber si la cuenta se había borrado, si cambió la contraseña
o si cerró sesión. El front solo necesita separar el final normal de un rechazo; el
motivo detallado se queda en el log de seguridad.

  #   motivo interno                                  | código público
  ----|------------------------------------------------|------------------
  P1  falta el token, caducó o 24 h sin uso            | SESSION_ENDED
      o cookie sustituida hace más de 1 h sin usar su    |
      sustituto (F-02, Agustín 10 nov: sin alarma)       |
  P2  inválido, no existe, revocado, cuenta borrada o  | SESSION_REJECTED
      desactivada                                      |
  P3  cada motivo interno tiene su código público      | ninguno se queda sin
"""

import pytest

from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshRejection,
    codigo_publico,
)

FINAL_NORMAL = {
    RefreshRejection.REFRESH_TOKEN_MISSING,
    RefreshRejection.REFRESH_TOKEN_EXPIRED,
    RefreshRejection.SESSION_IDLE,
    RefreshRejection.REPLACEMENT_WINDOW_EXPIRED,
}


@pytest.mark.parametrize("motivo", sorted(FINAL_NORMAL))
def test_p1_el_final_normal_es_session_ended(motivo):
    """
    Given: Un motivo del final normal de la sesión
    When: Se traduce para el cliente
    Then: SESSION_ENDED
    """
    assert codigo_publico(motivo) == "SESSION_ENDED"


@pytest.mark.parametrize("motivo", sorted(set(RefreshRejection) - FINAL_NORMAL))
def test_p2_lo_demas_es_session_rejected_sin_decir_por_que(motivo):
    """
    Given: Un rechazo: inválido, no existe, revocado, cuenta borrada o desactivada
    When: Se traduce para el cliente
    Then: SESSION_REJECTED, igual para todos: no dice el estado de la cuenta
    """
    assert codigo_publico(motivo) == "SESSION_REJECTED"


def test_p3_ningun_motivo_se_queda_sin_codigo_publico():
    """
    Given: Todos los motivos internos
    When: Se traducen
    Then: Solo salen los dos códigos públicos
    """
    assert {codigo_publico(m) for m in RefreshRejection} == {"SESSION_ENDED", "SESSION_REJECTED"}
