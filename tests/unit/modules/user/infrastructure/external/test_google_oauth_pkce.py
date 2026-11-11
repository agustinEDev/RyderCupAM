"""
PKCE en el canje del código de Google (FE-02, parte de backend; fase 3 del plan a 9).

Desde la 2.58.0 (release 3 de la fase 3) el `code_verifier` es OBLIGATORIO: el front
2.73.0 ya lo manda siempre.

  P1 sin code_verifier: el cuerpo no vale y el servicio no admite canjear sin él
  P2 con code_verifier: se le pasa a Google
  P3 verifier que no casa con el challenge: Google da 400, y es el mismo error que un código malo
  P4 verifier mal formado: el cuerpo no vale (422), sin llamar a Google
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.modules.user.application.dto.oauth_dto import (
    GoogleLoginRequestDTO,
    LinkGoogleAccountRequestDTO,
)
from src.modules.user.application.ports.google_oauth_service_interface import (
    IGoogleOAuthService,
)
from src.modules.user.infrastructure.external.google_oauth_service import (
    HTTP_OK,
    GoogleOAuthService,
)

VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CLIENTE = "src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient"


def _cliente(token_status: int = HTTP_OK) -> AsyncMock:
    """Un httpx falso: token con ese estado y userinfo bueno."""
    token = MagicMock(status_code=token_status, text="{}")
    token.json.return_value = {"access_token": "ya29.token"}
    userinfo = MagicMock(status_code=HTTP_OK)
    userinfo.json.return_value = {
        "sub": "google-1",
        "email": "ana@gmail.com",
        "email_verified": True,
        "given_name": "Ana",
        "family_name": "Lopez",
    }
    cliente = AsyncMock()
    cliente.post.return_value = token
    cliente.get.return_value = userinfo
    cliente.__aenter__ = AsyncMock(return_value=cliente)
    cliente.__aexit__ = AsyncMock(return_value=None)
    return cliente


def _lo_que_se_mando(cliente: AsyncMock) -> dict:
    """El cuerpo del POST al endpoint de tokens de Google."""
    return cliente.post.call_args.kwargs["data"]


@pytest.mark.parametrize("dto", [GoogleLoginRequestDTO, LinkGoogleAccountRequestDTO])
def test_p1_sin_verifier_el_cuerpo_no_vale(dto):
    """
    Given: Un cuerpo de login o de vincular sin code_verifier
    When: Se valida
    Then: No vale
    """
    with pytest.raises(ValidationError):
        dto(authorization_code="code")


def test_p1_el_servicio_no_canjea_sin_verifier():
    """
    Given: El servicio de Google y su puerto
    When: Se mira la firma del canje
    Then: El code_verifier no tiene valor por defecto ni admite None
    """
    for clase in (GoogleOAuthService, IGoogleOAuthService):
        parametro = inspect.signature(clase.exchange_code_for_user_info).parameters["code_verifier"]
        assert parametro.default is inspect.Parameter.empty, clase
        assert "None" not in str(parametro.annotation), clase


@pytest.mark.asyncio
async def test_p2_con_verifier_se_le_pasa_a_google():
    """
    Given: Un canje con code_verifier
    When: Se canjea el código
    Then: A Google le llega ese code_verifier
    """
    cliente = _cliente()
    with patch(CLIENTE, return_value=cliente):
        info = await GoogleOAuthService().exchange_code_for_user_info(
            "code", code_verifier=VERIFIER
        )

    assert _lo_que_se_mando(cliente)["code_verifier"] == VERIFIER
    assert info.email == "ana@gmail.com"


@pytest.mark.asyncio
async def test_p3_un_verifier_que_no_casa_es_el_error_de_un_codigo_malo():
    """
    Given: Google rechaza el canje (invalid_grant: el verifier no casa con el challenge)
    When: Se canjea el código
    Then: ValueError con el mismo texto que un código malo
    """
    cliente = _cliente(token_status=400)
    with (
        patch(CLIENTE, return_value=cliente),
        pytest.raises(ValueError, match="^Invalid or expired Google authorization code$"),
    ):
        await GoogleOAuthService().exchange_code_for_user_info("code", code_verifier=VERIFIER)


@pytest.mark.parametrize("dto", [GoogleLoginRequestDTO, LinkGoogleAccountRequestDTO])
@pytest.mark.parametrize(
    "verifier",
    ["corto", "x" * 129, VERIFIER[:-1] + "!", VERIFIER[:-1] + " "],
    ids=["menos-de-43", "mas-de-128", "caracter-no-valido", "espacio"],
)
def test_p4_un_verifier_mal_formado_no_vale(dto, verifier):
    """
    Given: Un code_verifier fuera del RFC 7636 (43-128 de [A-Za-z0-9-._~])
    When: Se valida el cuerpo
    Then: No vale
    """
    with pytest.raises(ValidationError):
        dto(authorization_code="code", code_verifier=verifier)


@pytest.mark.parametrize("dto", [GoogleLoginRequestDTO, LinkGoogleAccountRequestDTO])
def test_p4_admite_los_verifiers_validos(dto):
    """
    Given: Un code_verifier válido de 43 y otro de 128 caracteres
    When: Se validan
    Then: Valen los dos
    """
    assert dto(authorization_code="code", code_verifier=VERIFIER).code_verifier == VERIFIER
    largo = "a-._~" * 25 + "abc"
    assert dto(authorization_code="code", code_verifier=largo).code_verifier == largo
