"""
Submit Contact Use Case - Application Layer

Caso de uso para enviar un formulario de contacto como GitHub Issue.
"""

import logging

from src.modules.support.application.dto.contact_dto import (
    ContactRequestDTO,
    ContactResponseDTO,
)
from src.modules.support.application.ports.github_issue_service import (
    IGitHubIssueService,
)
from src.shared.application.validation.sanitizers import sanitize_html

logger = logging.getLogger(__name__)


class GitHubIssueCreationError(Exception):
    """Error al crear issue en GitHub."""

    pass


class SubmitContactUseCase:
    """Caso de uso para enviar el formulario de contacto."""

    def __init__(self, github_issue_service: IGitHubIssueService):
        self._github_issue_service = github_issue_service

    async def execute(self, request: ContactRequestDTO) -> ContactResponseDTO:
        """
        Ejecuta el caso de uso de contacto.

        1. Sanitiza los inputs
        2. Construye título y cuerpo de la issue
        3. Crea la issue en GitHub

        Raises:
            GitHubIssueCreationError: Si falla la creación de la issue
        """
        name = sanitize_html(request.name) or ""
        email = str(request.email)
        subject = sanitize_html(request.subject) or ""
        message = sanitize_html(request.message) or ""
        category = request.category

        title = f"[{category.value}] {subject}"
        body = (
            f"## Contact Form Submission\n\n"
            f"**Name:** {name}\n"
            f"**Email:** {email}\n"
            f"**Category:** {category.value}\n\n"
            f"---\n\n"
            f"### Message\n\n"
            f"{message}\n"
        )
        labels = [category.to_github_label()]

        success = await self._github_issue_service.create_issue(title, body, labels)

        if not success:
            logger.error("Failed to create GitHub issue for contact form submission")
            raise GitHubIssueCreationError("Failed to create GitHub issue. Please try again later.")

        return ContactResponseDTO(
            message="Your message has been received. We will get back to you soon."
        )
