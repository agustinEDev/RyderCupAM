"""
Support Routes - Infrastructure Layer (API v1)

Endpoints para el módulo de soporte/contacto.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.config.dependencies import get_submit_contact_use_case
from src.config.rate_limit import (
    CONTACT_LIMIT,
    get_client_identifier,
    limiter,
)
from src.config.settings import settings
from src.modules.support.application.dto.contact_dto import (
    ContactRequestDTO,
    ContactResponseDTO,
)
from src.modules.support.application.use_cases.submit_contact_use_case import (
    ContactDeliveryError,
    ContactQuotaExceededError,
    SubmitContactUseCase,
)
from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo

logger = logging.getLogger(__name__)

CONTACT_QUOTA_EXCEEDED = "CONTACT_QUOTA_EXCEEDED"


def _textos_del_contacto() -> dict[str, str]:
    """El texto del 429, con el buzón configurado: el mismo al que llega el formulario."""
    return {
        CONTACT_QUOTA_EXCEEDED: (
            f"We cannot receive more messages right now. Please write to {settings.CONTACT_EMAIL}."
        )
    }


router = APIRouter()


@router.post(
    "/contact",
    response_model=ContactResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Submit contact form",
    description=(
        "Emails a contact form message to the app's mailbox. Rate limited to 10 per day "
        "per network (a failed send counts too) and 20 per day app-wide "
        "(429 CONTACT_QUOTA_EXCEEDED)."
    ),
)
@limiter.limit(CONTACT_LIMIT, key_func=get_client_identifier)
async def submit_contact_form(
    request: Request,  # noqa: ARG001 - Required by SlowAPI for rate limiting
    contact_request: ContactRequestDTO,
    use_case: SubmitContactUseCase = Depends(get_submit_contact_use_case),
):
    """
    Endpoint público para enviar formulario de contacto.

    No requiere autenticación. Rate limited a 10 al día por red (un envío fallido también cuenta).
    """
    try:
        return await use_case.execute(contact_request)

    except ContactQuotaExceededError:
        # El tope diario de la app: que escriban directamente
        return respuesta_con_codigo(
            status.HTTP_429_TOO_MANY_REQUESTS, _textos_del_contacto(), CONTACT_QUOTA_EXCEEDED
        )
    except ContactDeliveryError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Unable to process your request. Please try again later."},
        )
    except Exception:
        logger.exception("Unexpected error in contact form submission")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Unable to process your request. Please try again later."},
        )
