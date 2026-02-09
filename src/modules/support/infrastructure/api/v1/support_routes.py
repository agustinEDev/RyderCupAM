"""
Support Routes - Infrastructure Layer (API v1)

Endpoints para el módulo de soporte/contacto.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.config.dependencies import get_submit_contact_use_case
from src.config.rate_limit import limiter
from src.modules.support.application.dto.contact_dto import (
    ContactRequestDTO,
    ContactResponseDTO,
)
from src.modules.support.application.use_cases.submit_contact_use_case import (
    GitHubIssueCreationError,
    SubmitContactUseCase,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/contact",
    response_model=ContactResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Submit contact form",
    description="Sends a contact form submission as a GitHub Issue. Rate limited to 3 per hour.",
)
@limiter.limit("3/hour")
async def submit_contact_form(
    request: Request,  # noqa: ARG001 - Required by SlowAPI for rate limiting
    contact_request: ContactRequestDTO,
    use_case: SubmitContactUseCase = Depends(get_submit_contact_use_case),
):
    """
    Endpoint público para enviar formulario de contacto.

    No requiere autenticación. Rate limited a 3 por hora por IP.
    """
    try:
        return await use_case.execute(contact_request)

    except GitHubIssueCreationError:
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
