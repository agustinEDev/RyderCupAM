"""
GitHub Issue Service Interface - Application Layer Port

Define el contrato para el servicio de creación de issues en GitHub.
"""

from abc import ABC, abstractmethod


class IGitHubIssueService(ABC):
    """
    Puerto para el servicio de GitHub Issues.

    Implementaciones posibles:
    - GitHubIssueService (producción - GitHub REST API)
    - MockGitHubIssueService (testing)
    """

    @abstractmethod
    async def create_issue(self, title: str, body: str, labels: list[str]) -> bool:
        """
        Crea una issue en GitHub.

        Args:
            title: Título de la issue
            body: Cuerpo de la issue (markdown)
            labels: Lista de labels a asignar

        Returns:
            True si se creó correctamente, False en caso contrario
        """
        pass
