"""La respuesta con código: el `detail` es siempre el texto fijo (BE #562).

| Caso                                   | Resultado                          |
|----------------------------------------|------------------------------------|
| Campos de más                          | En la raíz, tras los fijos         |
| `error_code` entre los campos          | Sustituye al código                |
| `detail` entre los campos              | TypeError: nadie pisa el texto fijo |
"""

import json

import pytest

from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo

TEXTOS = {"X": "Texto fijo"}


def test_extra_fields_go_to_the_root():
    cuerpo = json.loads(respuesta_con_codigo(400, TEXTOS, "X", players=[]).body)

    assert cuerpo == {"detail": "Texto fijo", "error_code": "X", "players": []}


def test_error_code_in_fields_replaces_the_code():
    cuerpo = json.loads(
        respuesta_con_codigo(400, TEXTOS, "X", error_code="Y", reason_code="X").body
    )

    assert cuerpo == {"detail": "Texto fijo", "error_code": "Y", "reason_code": "X"}


def test_detail_in_fields_is_rejected():
    """
    Given: Un `detail` entre los campos de más
    When: Se construye la respuesta
    Then: TypeError: el texto es siempre el fijo del código, nunca otro
    """
    with pytest.raises(TypeError, match="detail"):
        respuesta_con_codigo(400, TEXTOS, "X", detail="texto de la excepción")
