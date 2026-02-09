"""
GitHub Issue Service - Infrastructure Layer

Implementación concreta del servicio de GitHub Issues usando la REST API.
"""

import asyncio
import logging
from http import HTTPStatus

import requests

from src.config.settings import settings
from src.modules.support.application.ports.github_issue_service import (
    IGitHubIssueService,
)

logger = logging.getLogger(__name__)


class GitHubIssueService(IGitHubIssueService):
    """Adaptador que crea issues en GitHub via REST API."""

    GITHUB_API_URL = "https://api.github.com"

    async def create_issue(self, title: str, body: str, labels: list[str]) -> bool:
        """
        Crea una issue en GitHub.

        Usa asyncio.to_thread() para ejecutar requests.post() sin bloquear
        el event loop de asyncio.
        """
        token = settings.GH_ISSUES_TOKEN
        repo = settings.GITHUB_ISSUES_REPO

        if not token or not repo:
            logger.error(
                "GitHub Issues configuration missing: GH_ISSUES_TOKEN or GITHUB_ISSUES_REPO"
            )
            return False

        url = f"{self.GITHUB_API_URL}/repos/{repo}/issues"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "title": title,
            "body": body,
            "labels": labels,
        }

        try:
            response = await asyncio.to_thread(
                requests.post, url, json=payload, headers=headers, timeout=10
            )

            if response.status_code == HTTPStatus.CREATED:
                issue_url = response.json().get("html_url", "unknown")
                logger.info(f"GitHub issue created successfully: {issue_url}")
                return True

            logger.error(f"GitHub API returned {response.status_code}: {response.text[:200]}")
            return False

        except requests.RequestException as e:
            logger.error(f"GitHub API request failed: {type(e).__name__}: {e}")
            return False
